"""Offline lifecycle of one price request. No DNS, no remote socket, no server."""
from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from tools.protection_v3.constants import (
    FROZEN_BOOTSTRAP_SHA256,
    FROZEN_GUARD_SHA256,
    FROZEN_LAUNCHER_SHA256,
    LOGICAL_GIT,
    LOGICAL_SOURCE,
)
from tools.protection_v3.declaration import (
    AuthorizationMissing,
    DeclarationError,
    declare,
    reject_probe_and_credentials,
    require_authorization,
)
from tools.protection_v3.launcher import decide
from tools.protection_v3.wrapper import (
    controlled_price_request,
    network_audit,
    open_controlled_socket,
)
from tools.protection_v3.guard_loader import load_frozen_guard

ROOT = Path(__file__).resolve().parent.parent
PRICE = "https://api.wavespeed.ai/api/v3/model/price"
ADDRESS = ("203.0.113.5", 443)
ADDR = (socket.AF_INET, socket.SOCK_STREAM, 0, "", ADDRESS)
IPS = frozenset({"203.0.113.5"})
HOME = "/var/lib/comfyart-unactivated/logical-d4a09666/home"
RUNTIME = "logical-d4a09666-unactivated"


class _Session:
    trust_env = False
    _default_params = None
    _default_headers = None
    _default_proxy = None
    _default_proxy_auth = None
    _connector = None


def _pair(_addr_info):
    left, right = socket.socketpair()
    right.close()
    return left


def _body():
    return {"json": {"model_id": "openai/gpt-image-2.6-flare/edit", "input": {"width": 1152, "height": 2048}}}


def _deny_dns(monkeypatch):
    def _explode(*_args, **_kwargs):
        raise AssertionError("dns")

    monkeypatch.setattr(socket, "getaddrinfo", _explode)


def _close(sock):
    try:
        sock.close()
    except OSError:
        pass


def test_frozen_originals_keep_their_hashes():
    frozen = ROOT / "docs/integrate/protection-v3/frozen"
    import hashlib
    found = {
        "wavespeed_price_guard.py": FROZEN_GUARD_SHA256,
        "bootstrap_quote_only_strict.py": FROZEN_BOOTSTRAP_SHA256,
        "start_quote_only_strict.py": FROZEN_LAUNCHER_SHA256,
    }
    for name, expect in found.items():
        assert hashlib.sha256((frozen / name).read_bytes()).hexdigest() == expect


def test_declaration_accepts_only_the_logical_source_and_does_not_authorize(tmp_path):
    declared = declare(
        source_git=LOGICAL_GIT, source_sha256=LOGICAL_SOURCE,
        home=HOME, port=8946, runtime_id=RUNTIME,
    )
    assert declared.activated is False
    assert declared.fingerprint == "ca76d4c48564cf632ac9fee804b16663df415aae7c2c67fcd8b3b9208600bcab"
    assert not Path(HOME).exists()
    with pytest.raises(DeclarationError) as delivery:
        declare(source_git="1cc1a279a0d1d2cd3ec907bf818f5c5451249acb", source_sha256=LOGICAL_SOURCE,
                home=HOME, port=8946, runtime_id=RUNTIME)
    assert delivery.value.code == "delivery_commit_is_not_logical_source"
    with pytest.raises(DeclarationError) as retired:
        declare(source_git=LOGICAL_GIT, source_sha256=LOGICAL_SOURCE, home=HOME, port=8932, runtime_id=RUNTIME)
    assert retired.value.code == "retired_port"
    with pytest.raises(DeclarationError) as old_home:
        declare(source_git=LOGICAL_GIT, source_sha256=LOGICAL_SOURCE,
                home="/workspace/comfyart-authority-1004", port=8946, runtime_id=RUNTIME)
    assert old_home.value.code == "old_home"
    with pytest.raises(AuthorizationMissing):
        require_authorization(None)
    with pytest.raises(DeclarationError) as recorded:
        require_authorization("not-a-record")
    assert recorded.value.code == "authorization_not_recorded"
    with pytest.raises(DeclarationError):
        reject_probe_and_credentials({"COMFYART_QUOTE_PROBE_EXECUTE": "1"})
    with pytest.raises(DeclarationError):
        reject_probe_and_credentials({"WAVESPEED_API_KEY": "secret-value"})
    assert not (tmp_path / "created").exists()


def test_launcher_exits_without_starting(tmp_path):
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    base = [sys.executable, "-m", "tools.protection_v3.launcher",
            "--source-git", LOGICAL_GIT, "--source-sha256", LOGICAL_SOURCE,
            "--home", HOME, "--port", "8946", "--runtime-id", RUNTIME]
    missing = subprocess.run([sys.executable, "-m", "tools.protection_v3.launcher"], cwd=ROOT, env=env,
                             capture_output=True, text=True)
    assert missing.returncode == 2 and "not started" in missing.stderr
    refused = subprocess.run(base, cwd=ROOT, env=env, capture_output=True, text=True)
    assert refused.returncode == 3 and refused.stderr.strip() == "authorization_missing; not started"
    probed = subprocess.run(base, cwd=ROOT, env={**env, "COMFYART_QUOTE_PROBE_EXECUTE": "1"},
                            capture_output=True, text=True)
    assert probed.returncode == 2 and "probe_disabled" in probed.stderr
    keyed = subprocess.run(base, cwd=ROOT, env={**env, "WAVESPEED_API_KEY": "secret-value"},
                           capture_output=True, text=True)
    assert keyed.returncode == 2 and "secret-value" not in keyed.stderr and "secret-value" not in keyed.stdout
    assert decide(["--port", "8932"], env) == 2
    assert not Path(HOME).exists()
    assert not list(tmp_path.iterdir())


def test_wrapper_revokes_registered_socket_on_success_and_transport_error(monkeypatch):
    asyncio.run(_success_and_error(monkeypatch))


async def _success_and_error(monkeypatch):
    _deny_dns(monkeypatch)
    guard = load_frozen_guard()

    async def ok_transport(_session, _method, _url, _kwargs, bound):
        sock = open_controlled_socket(bound, ADDR, _pair)
        network_audit(bound, "socket.connect", (sock, ADDRESS))
        assert bound.price_socket_allowed(sock, ADDRESS) is True
        return sock

    sock = await controlled_price_request(_Session(), "POST", PRICE, _body(), guard=guard, transport=ok_transport, price_ips=IPS)
    assert guard._PRICE_SOCKETS.get(sock) is None
    assert guard.price_socket_allowed(sock, ADDRESS) is False
    with pytest.raises(PermissionError):
        network_audit(guard, "socket.connect", (sock, ADDRESS))
    _close(sock)

    async def bad_transport(_session, _method, _url, _kwargs, bound):
        sock_error = open_controlled_socket(bound, ADDR, _pair)
        holder.append(sock_error)
        raise ConnectionError("offline transport")

    holder = []
    with pytest.raises(ConnectionError, match="offline transport"):
        await controlled_price_request(_Session(), "POST", PRICE, _body(), guard=guard, transport=bad_transport, price_ips=IPS)
    assert guard._PRICE_SOCKETS.get(holder[0]) is None
    assert guard.price_socket_allowed(holder[0], ADDRESS) is False
    _close(holder[0])


def test_cancellation_revokes_only_that_request_and_child_cannot_reuse_scope(monkeypatch):
    asyncio.run(_cancellation(monkeypatch))


async def _cancellation(monkeypatch):
    _deny_dns(monkeypatch)
    guard = load_frozen_guard()
    entered_a = asyncio.Event()
    entered_b = asyncio.Event()
    both_open_checked = asyncio.Event()
    release_b = asyncio.Event()
    child_after = asyncio.Event()
    seen = {}

    async def transport_a(_session, _method, _url, _kwargs, bound):
        sock = open_controlled_socket(bound, ADDR, _pair)
        seen["a_sock"] = sock
        seen["a_scope"] = bound._PRICE_SCOPE.get()

        async def child():
            seen["child_during"] = bound.price_socket_allowed(sock, ADDRESS)
            seen["child_scope"] = bound._PRICE_SCOPE.get()
            await child_after.wait()
            seen["child_after"] = bound.price_socket_allowed(sock, ADDRESS)
            seen["child_registered"] = bound._PRICE_SOCKETS.get(sock)
            try:
                open_controlled_socket(bound, ADDR, _pair)
                seen["child_factory"] = "allowed"
            except PermissionError:
                seen["child_factory"] = "denied"
            try:
                network_audit(bound, "socket.connect", (sock, ADDRESS))
                seen["child_audit"] = "allowed"
            except PermissionError:
                seen["child_audit"] = "denied"

        seen["child"] = asyncio.create_task(child())
        await asyncio.sleep(0)
        entered_a.set()
        await asyncio.sleep(3600)

    async def transport_b(_session, _method, _url, _kwargs, bound):
        sock = open_controlled_socket(bound, ADDR, _pair)
        seen["b_sock"] = sock
        seen["b_scope"] = bound._PRICE_SCOPE.get()
        entered_b.set()
        await entered_a.wait()
        seen["b_sees_a_while_both_open"] = bound.price_socket_allowed(seen["a_sock"], ADDRESS)
        both_open_checked.set()
        await release_b.wait()
        seen["b_own_while_open"] = bound.price_socket_allowed(sock, ADDRESS)
        seen["b_sees_a_after_cancel"] = bound.price_socket_allowed(seen["a_sock"], ADDRESS)
        return "b"

    task_a = asyncio.create_task(controlled_price_request(
        _Session(), "POST", PRICE, _body(), guard=guard, transport=transport_a, price_ips=IPS))
    task_b = asyncio.create_task(controlled_price_request(
        _Session(), "POST", PRICE, _body(), guard=guard, transport=transport_b, price_ips=IPS))
    await both_open_checked.wait()
    assert seen["child_during"] is True
    assert seen["b_sees_a_while_both_open"] is False
    task_a.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task_a
    assert seen["a_scope"].active is False
    assert guard._PRICE_SOCKETS.get(seen["a_sock"]) is None
    assert guard.price_socket_allowed(seen["a_sock"], ADDRESS) is False
    child_after.set()
    await seen["child"]
    assert seen["child_scope"] is seen["a_scope"]
    assert seen["child_after"] is False
    assert seen["child_registered"] is None
    assert seen["child_factory"] == "denied"
    assert seen["child_audit"] == "denied"
    release_b.set()
    assert await task_b == "b"
    assert seen["b_own_while_open"] is True
    assert seen["b_sees_a_after_cancel"] is False
    assert seen["b_scope"].active is False
    assert guard.price_socket_allowed(seen["b_sock"], ADDRESS) is False
    _close(seen["a_sock"])
    _close(seen["b_sock"])


def test_stale_child_context_cannot_use_a_later_request(monkeypatch):
    asyncio.run(_stale(monkeypatch))


async def _stale(monkeypatch):
    _deny_dns(monkeypatch)
    guard = load_frozen_guard()
    first_done = asyncio.Event()
    second_open = asyncio.Event()
    release_second = asyncio.Event()
    seen = {}

    async def first_transport(_session, _method, _url, _kwargs, bound):
        sock = open_controlled_socket(bound, ADDR, _pair)
        seen["old"] = sock

        async def child():
            await first_done.wait()
            await second_open.wait()
            seen["stale_on_new"] = bound.price_socket_allowed(seen["new"], ADDRESS)
            seen["stale_on_old"] = bound.price_socket_allowed(sock, ADDRESS)
            scope, token = bound.begin_price_request(set(IPS))
            try:
                seen["begun_on_new"] = bound.price_socket_allowed(seen["new"], ADDRESS)
                seen["begun_scope_is_new"] = bound._PRICE_SCOPE.get() is seen["new_scope"]
            finally:
                bound.end_price_request(scope, token)

        seen["child"] = asyncio.create_task(child())
        await asyncio.sleep(0)
        return "first"

    async def second_transport(_session, _method, _url, _kwargs, bound):
        sock = open_controlled_socket(bound, ADDR, _pair)
        seen["new"] = sock
        seen["new_scope"] = bound._PRICE_SCOPE.get()
        second_open.set()
        await release_second.wait()
        return "second"

    assert await controlled_price_request(
        _Session(), "POST", PRICE, _body(), guard=guard, transport=first_transport, price_ips=IPS) == "first"
    first_done.set()
    second = asyncio.create_task(controlled_price_request(
        _Session(), "POST", PRICE, _body(), guard=guard, transport=second_transport, price_ips=IPS))
    await second_open.wait()
    await seen["child"]
    assert seen["stale_on_new"] is False
    assert seen["stale_on_old"] is False
    assert seen["begun_on_new"] is False
    assert seen["begun_scope_is_new"] is False
    release_second.set()
    assert await second == "second"
    assert guard.price_socket_allowed(seen["new"], ADDRESS) is False
    _close(seen["old"])
    _close(seen["new"])
