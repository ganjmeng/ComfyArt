"""Offline wiring on current main. No listener, DNS, provider, or audit hook in this process."""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import aiohttp
import pytest

from tools.protection_v3.constants import LOGICAL_GIT, LOGICAL_SOURCE
from tools.protection_v3.declaration import AuthorizationMissing, DeclarationError
from tools.protection_v3.guard_loader import load_frozen_guard
from tools.protection_v3.launcher import decide
from tools.protection_v3.startup import (
    StartupRefused,
    connect_product,
    preflight,
    production_startup,
    synthetic_test_authorization,
)
from tools.protection_v3.wrapper import PriceRequestDenied

ROOT = Path(__file__).resolve().parent.parent
HOME = "/var/lib/comfyart-unactivated/main-72f387a8/home"
RUNTIME = "main-72f387a8-unactivated"
IPS = frozenset({"203.0.113.5"})
PRICE = "https://api.wavespeed.ai/api/v3/model/price"


def _prepared():
    return preflight(
        source_git=LOGICAL_GIT, source_sha256=LOGICAL_SOURCE, source_path=str(ROOT),
        home=HOME, port=8946, runtime_id=RUNTIME,
    )


def _deny_dns(monkeypatch):
    def _explode(*_args, **_kwargs):
        raise AssertionError("dns")

    monkeypatch.setattr(socket, "getaddrinfo", _explode)


def test_missing_authorization_does_not_enter_product():
    entered = []

    async def startup(_prepared_value, _shared):
        entered.append(True)

    async def run():
        with pytest.raises(AuthorizationMissing):
            await connect_product(_prepared(), None, startup=startup, price_ips=IPS, guard=load_frozen_guard())

    asyncio.run(run())
    assert entered == []
    assert not Path(HOME).exists()


def test_cli_stops_before_product_entry_and_rejects_recovery_tree():
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    base = [sys.executable, "-m", "tools.protection_v3.launcher",
            "--source-git", LOGICAL_GIT, "--source-sha256", LOGICAL_SOURCE,
            "--source-path", str(ROOT), "--home", HOME, "--port", "8946", "--runtime-id", RUNTIME]
    refused = subprocess.run(base, cwd=ROOT, env=env, capture_output=True, text=True)
    assert refused.returncode == 3 and refused.stderr.strip() == "authorization_missing; not started"
    with pytest.raises(DeclarationError) as old:
        preflight(source_git="738ddbf19c71890ca1820f26e4a7e8852685ebd7", source_sha256=LOGICAL_SOURCE,
                  source_path=str(ROOT), home=HOME, port=8946, runtime_id=RUNTIME)
    assert old.value.code == "recovery_tree_is_not_main_product"
    assert decide(["--port", "8932"], env) == 2


def test_production_runner_is_refused_and_quote_detail_reaches_the_shared_guard(monkeypatch):
    _deny_dns(monkeypatch)
    entered = []

    async def startup(_prepared_value, shared):
        entered.append(shared.guard)
        import ComfyArt.api.wavespeed as wavespeed
        wavespeed._quotes.clear()
        wavespeed._catalog.update(models={}, at=0.0)
        os.environ["WAVESPEED_API_KEY"] = "synthetic-offline-not-a-credential"
        try:
            with pytest.raises(PriceRequestDenied) as denied:
                await wavespeed.quote_detail("acme/offline-price", {"prompt": "cup"})
            assert denied.value.reason == "inputs_plural_not_official"
            posts = [item for item in shared.attempts if item[0] == "POST"]
            assert posts and sorted(posts[-1][2]) == ["inputs", "model_id"]
            assert shared.http_guard_ids and set(shared.http_guard_ids) == {id(shared.guard)}
            assert shared.connector_guard_ids and set(shared.connector_guard_ids) == {id(shared.guard)}
            for sock in shared.sockets:
                assert shared.guard.price_socket_allowed(sock, ("203.0.113.5", 443)) is False
                sock.close()
        finally:
            os.environ.pop("WAVESPEED_API_KEY", None)
        return "entered"

    async def run():
        prepared = _prepared()
        with pytest.raises(StartupRefused) as refused:
            await connect_product(
                prepared, synthetic_test_authorization(prepared),
                startup=production_startup, price_ips=IPS, guard=load_frozen_guard(),
            )
        assert refused.value.code == "tech_pm_approval_required"
        result, shared = await connect_product(
            prepared, synthetic_test_authorization(prepared),
            startup=startup, price_ips=IPS, guard=load_frozen_guard(),
        )
        assert result == "entered"
        assert entered[0] is shared.guard

    asyncio.run(run())
    assert not Path(HOME).exists()


def test_singular_aiohttp_request_revokes_on_success_error_and_cancel(monkeypatch):
    _deny_dns(monkeypatch)

    async def run():
        guard = load_frozen_guard()
        state = {"mode": "ok"}

        async def startup(_prepared_value, shared):
            async def observe(method, url, _kwargs, bound, sock):
                if not str(url).endswith("/model/price"):
                    return
                if state["mode"] == "error":
                    raise aiohttp.ClientError("offline transport")
                if state["mode"] == "cancel":
                    raise asyncio.CancelledError()
                assert bound.price_socket_allowed(sock, ("203.0.113.5", 443)) is True

            shared.observe = observe

            async def once():
                async with aiohttp.ClientSession() as session:
                    async with session.post(PRICE, json={"model_id": "acme/offline-price", "input": {}}) as res:
                        body = await res.json()
                        return res.status, body["data"]["discounted_price"]

            state["mode"] = "ok"
            assert await once() == (200, 0.1)
            ok_sock = shared.sockets[-1]
            assert guard.price_socket_allowed(ok_sock, ("203.0.113.5", 443)) is False
            state["mode"] = "error"
            with pytest.raises(aiohttp.ClientError):
                await once()
            assert guard.price_socket_allowed(shared.sockets[-1], ("203.0.113.5", 443)) is False
            state["mode"] = "cancel"
            with pytest.raises(asyncio.CancelledError):
                await once()
            assert guard.price_socket_allowed(shared.sockets[-1], ("203.0.113.5", 443)) is False
            for sock in shared.sockets:
                sock.close()
            return "done"

        result, shared = await connect_product(
            _prepared(), synthetic_test_authorization(_prepared()),
            startup=startup, price_ips=IPS, guard=guard,
        )
        assert result == "done"
        assert set(shared.http_guard_ids) == {id(guard)}

    asyncio.run(run())


def test_child_and_peer_requests_stay_isolated(monkeypatch):
    _deny_dns(monkeypatch)

    async def run():
        guard = load_frozen_guard()
        release = asyncio.Event()
        seen = {}

        async def startup(_prepared_value, shared):
            async def observe(method, url, _kwargs, bound, sock):
                if not str(url).endswith("/model/price"):
                    return
                seen.setdefault("socks", []).append(sock)
                if "child" in seen:
                    seen["peer"] = bound.price_socket_allowed(seen["socks"][0], ("203.0.113.5", 443))
                    return

                async def child():
                    seen["during"] = bound.price_socket_allowed(sock, ("203.0.113.5", 443))
                    await release.wait()
                    seen["after"] = bound.price_socket_allowed(sock, ("203.0.113.5", 443))
                    seen["same"] = bound._PRICE_SCOPE.get() is seen["scope"]

                seen["scope"] = bound._PRICE_SCOPE.get()
                seen["child"] = asyncio.create_task(child())
                await asyncio.sleep(0)

            shared.observe = observe

            async def post(label):
                async with aiohttp.ClientSession() as session:
                    async with session.post(PRICE, json={"model_id": label, "input": {}}) as res:
                        return res.status

            first = asyncio.create_task(post("a"))
            second = asyncio.create_task(post("b"))
            assert await first == 200 and await second == 200
            release.set()
            await seen["child"]
            assert seen["during"] is True and seen["after"] is False and seen["same"] is True
            assert seen["peer"] is False
            assert len(shared.sockets) == 2
            for sock in shared.sockets:
                assert guard.price_socket_allowed(sock, ("203.0.113.5", 443)) is False
                sock.close()
            return "isolated"

        result, _shared = await connect_product(
            _prepared(), synthetic_test_authorization(_prepared()),
            startup=startup, price_ips=IPS, guard=guard,
        )
        assert result == "isolated"

    asyncio.run(run())


def test_audit_hook_runs_in_a_subprocess_with_the_same_guard():
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, "-m", "tools.protection_v3.offline_entry"],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["unscoped"] == "denied"
    assert report["quote_detail"] == "inputs_plural_not_official"
    assert report["post_body_keys"] == ["inputs", "model_id"]
    assert report["shared"] is True
    assert report["sockets_revoked"] is True
    assert report["audit_guard"]
    assert report["connector_guard"]
