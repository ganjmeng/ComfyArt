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

from tools.protection_v3.constants import LOGICAL_GIT, LOGICAL_SOURCE, STALE_MAIN_GIT, STALE_MAIN_SOURCE
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
    with pytest.raises(DeclarationError) as stale:
        preflight(source_git=STALE_MAIN_GIT, source_sha256=STALE_MAIN_SOURCE,
                  source_path=str(ROOT), home=HOME, port=8946, runtime_id=RUNTIME)
    assert stale.value.code == "stale_main_source"
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
            price, source, reason = await wavespeed.quote_detail("acme/offline-price", {"prompt": "cup"})
            assert (price, source, reason) == (0.1, "quote", "live")
            posts = [item for item in shared.attempts if item[0] == "POST"]
            body = posts[-1][2]
            assert set(body) == {"model_id", "input"} and isinstance(body["input"], dict)
            assert "inputs" not in body
            assert all(item[1].endswith("/api/v3/models") or item[1].endswith("/api/v3/model/price") for item in shared.attempts)
            assert shared.transport_calls == 2 and len(shared.sockets) == 2
            assert shared.submissions == 0
            assert shared.http_guard_ids and set(shared.http_guard_ids) == {id(shared.guard)}
            assert shared.connector_guard_ids and set(shared.connector_guard_ids) == {id(shared.guard)}
            revoked = []
            for sock in shared.sockets:
                allowed = shared.guard.price_socket_allowed(sock, ("203.0.113.5", 443))
                revoked.append({"id": id(sock), "fd": sock.fileno(), "allowed": allowed})
                assert allowed is False
                sock.close()
            assert len(revoked) == 2
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


def test_quote_detail_caches_only_finite_nonnegative_amounts(monkeypatch):
    _deny_dns(monkeypatch)

    async def run():
        guard = load_frozen_guard()

        async def startup(_prepared_value, shared):
            import ComfyArt.api.wavespeed as wavespeed
            wavespeed._quotes.clear()
            wavespeed._catalog.update(models={}, at=0.0)
            os.environ["WAVESPEED_API_KEY"] = "synthetic-offline-not-a-credential"
            state = {"raise": None}

            async def observe(method, url, _kwargs, bound, sock):
                if not str(url).endswith("/model/price"):
                    return
                assert bound is guard and bound.price_socket_allowed(sock, ("203.0.113.5", 443)) is True
                if state["raise"] is not None:
                    raise state["raise"]

            shared.observe = observe
            try:
                async def one(prompt, reply):
                    wavespeed._quotes.clear()
                    before = len(wavespeed._quotes)
                    shared.price_reply = reply
                    result = await wavespeed.quote_detail("acme/offline-price", {"prompt": prompt})
                    return result, len(wavespeed._quotes) > before

                good, cached = await one("plus", {"code": 200, "data": {"discounted_price": 0.25}})
                assert good == (0.25, "quote", "live") and cached
                again = await wavespeed.quote_detail("acme/offline-price", {"prompt": "plus"})
                assert again[2] == "cache"
                zero, zero_cached = await one("zero", {"code": 200, "data": {"discounted_price": 0}})
                assert zero == (0.0, "quote", "live") and zero_cached
                for prompt, reply in (
                    ("err", {"code": 4005, "message": "model not found", "data": {"discounted_price": 0}}),
                    ("neg", {"code": 200, "data": {"discounted_price": -1}}),
                    ("nan", {"code": 200, "data": {"discounted_price": float("nan")}}),
                    ("inf", {"code": 200, "data": {"discounted_price": float("inf")}}),
                    ("miss", {"code": 200}),
                ):
                    result, stored = await one(prompt, reply)
                    assert result[1] != "quote" and stored is False
                    assert not (result[1] == "quote" and result[0] == 0)
                before_calls, before_socks = shared.transport_calls, len(shared.sockets)
                state["raise"] = aiohttp.ClientError("offline transport")
                failed, stored = await one("down", {"code": 200, "data": {"discounted_price": 0}})
                error_batch = shared.sockets[before_socks:]
                assert failed[1] != "quote" and stored is False
                assert shared.transport_calls - before_calls == 2 and len(error_batch) == 2
                assert all(guard.price_socket_allowed(sock, ("203.0.113.5", 443)) is False for sock in error_batch)
                before_calls, before_socks = shared.transport_calls, len(shared.sockets)
                state["raise"] = asyncio.CancelledError()
                with pytest.raises(asyncio.CancelledError):
                    await one("stop", {"code": 200, "data": {"discounted_price": 0.1}})
                cancel_batch = shared.sockets[before_socks:]
                assert shared.transport_calls - before_calls == 1 and len(cancel_batch) == 1
                assert guard.price_socket_allowed(cancel_batch[0], ("203.0.113.5", 443)) is False
                async with aiohttp.ClientSession() as session:
                    with pytest.raises(PriceRequestDenied):
                        async with session.post("https://api.wavespeed.ai/api/v3/balance", json={"model_id": "m", "inputs": {}}):
                            pass
                assert all("predictions" not in item[1] and "/turbo" not in item[1] for item in shared.attempts)
            finally:
                os.environ.pop("WAVESPEED_API_KEY", None)
                for sock in shared.sockets:
                    sock.close()
            return "checked"

        result, shared = await connect_product(
            _prepared(), synthetic_test_authorization(_prepared()),
            startup=startup, price_ips=IPS, guard=guard,
        )
        assert result == "checked" and set(shared.http_guard_ids) == {id(guard)}

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

            import ComfyArt.api.wavespeed as wavespeed
            wavespeed._quotes.clear()
            wavespeed._catalog.update(models={}, at=0.0)
            os.environ["WAVESPEED_API_KEY"] = "synthetic-offline-not-a-credential"

            async def post(prompt):
                price, source, _reason = await wavespeed.quote_detail("acme/offline-price", {"prompt": prompt})
                return price, source

            first = asyncio.create_task(post("left"))
            second = asyncio.create_task(post("right"))
            assert await first == (0.1, "quote") and await second == (0.1, "quote")
            release.set()
            await seen["child"]
            assert seen["during"] is True and seen["after"] is False and seen["same"] is True
            assert seen["peer"] is False
            posts = [item for item in shared.attempts if str(item[1]).endswith("/model/price")]
            assert len(posts) == 2
            assert shared.transport_calls == len(shared.sockets) >= 2
            assert shared.submissions == 0
            assert all(set(item[2]) == {"model_id", "input"} for item in posts)
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
    assert report["quote_detail"] == [0.1, "quote", "live"]
    assert report["post_body_keys"] == ["input", "model_id"]
    assert report["transport_result"][1] != "quote"
    assert report["cancel"] == "cancelled"
    assert report["shared"] is True
    assert report["audit_guard"] and report["connector_guard"]
    for name, transports in (("success", 2), ("transport_error", 2), ("cancel", 1)):
        row = report["scenarios"][name]
        assert row["transport_calls"] == transports
        assert row["sockets_registered"] == transports
        assert row["submissions"] == 0
        assert len(row["sockets"]) == transports
        assert all(item["allowed"] is False for item in row["sockets"])
    assert report["scenarios"]["pre_reject"] == {
        "transport_calls": 0, "sockets_registered": 0, "submissions": 0,
    }
