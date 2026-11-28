"""#1022: one-shot completions use the USD gate, and failed holds settle or stay.

Offline only. No model endpoint is contacted. A connector error is raised in
process, which is the same class aiohttp raises before ClientRequest.send.
"""
from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import aiohttp
import pytest
from aiohttp.client_reqrep import ConnectionKey
from PIL import Image

from ComfyArt.api import bot_complete
from ComfyArt.bot.llm_usd_gate import (
    TWO_DOLLAR_CEILING_NANO,
    ledger_state,
    open_authorized_scope,
    user_notice,
)
from ComfyArt.bot.local_llm import LlmHttpError
from test_llm_usd_gate import URL, _route, _text, _usage, _zero_bound

ROOT = Path(__file__).resolve().parents[1]
NOTICES = {
    "image_too_large": "llm.imageTooLarge",
    "unbounded_multimodal": "llm.imageUnreadable",
    "over_budget": "llm.overBudget",
    "unbounded_billed_input": "llm.messageBlocked",
    "project_unverified": "llm.messageBlocked",
}


def _png(tmp_path: Path, name: str = "ref.png") -> str:
    folder = tmp_path / "input"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / name
    Image.new("RGB", (32, 16), (12, 80, 40)).save(dest, format="PNG")
    return f"/api/view?filename={name}&type=input"


def _open(project_id: str, *, user: str = "default") -> None:
    from server import PromptServer
    from ComfyArt.api import project_store
    from ComfyArt.api.mcp_commands import _pages

    project_store.save_project(user, project_id, "{}", project_id, [])
    client = f"tab-{project_id}"
    PromptServer.instance.sockets[client] = object()
    _pages[client] = project_id


def _close_tabs() -> None:
    from server import PromptServer
    from ComfyArt.api.mcp_commands import _pages

    _pages.clear()
    PromptServer.instance.sockets.clear()


@pytest.fixture(autouse=True)
def _opt_in_llm_usd_gate(monkeypatch):
    monkeypatch.setenv("COMFYART_LLM_USD_GATE", "1")


@pytest.fixture(autouse=True)
def _tabs():
    _close_tabs()
    yield
    _close_tabs()


class _Response:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self._payload = payload

    async def text(self) -> str:
        return json.dumps(self._payload)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


class _Session:
    posts: list[dict] = []
    status = 200
    payload: dict = {"choices": [{"message": {"content": "kept"}}]}
    boom: BaseException | None = None

    def __init__(self, *args, **kwargs):
        self.headers = kwargs.get("headers") or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def request(self, method, url, **kwargs):
        _Session.posts.append({
            "method": method, "url": url, "json": kwargs.get("json"), "headers": kwargs.get("headers"),
        })
        if _Session.boom is not None:
            raise _Session.boom
        return _Response(_Session.status, _Session.payload)

    def get(self, url, **kwargs):
        raise AssertionError("passthrough model list is not part of this test")


@pytest.fixture
def fake_llm(monkeypatch):
    _Session.posts = []
    _Session.status = 200
    _Session.payload = {"choices": [{"message": {"content": "kept"}}]}
    _Session.boom = None
    monkeypatch.setattr(aiohttp, "ClientSession", _Session)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-a-live-secret")
    return _Session


def _connector_error() -> aiohttp.ClientConnectorError:
    key = ConnectionKey("api.deepseek.com", 443, True, True, None, None, None)
    return aiohttp.ClientConnectorError(key, ConnectionRefusedError(111, "Connection refused"))


def _notice(lang: str, code: str) -> str:
    return user_notice(code, lang)


async def _post(bot_client, **body):
    return await bot_client.post("/comfyart/llm/complete", json=body)


def test_ask_sends_the_open_project_and_keeps_approved_notices():
    source = (ROOT / "src/llm.ts").read_text(encoding="utf-8")
    assert "currentProject()" in source
    assert "approvedLlmNotice" in source
    for key in NOTICES.values():
        assert key in source
    assert "llm_complete" not in (ROOT / "bot/local_llm.py").read_text(encoding="utf-8")
    assert "llm_complete" not in (ROOT / "bot/agent_loop.py").read_text(encoding="utf-8")
    locales_zh = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
    locales_en = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))
    for code, key in NOTICES.items():
        assert user_notice(code, "zh") == locales_zh[key]
        assert user_notice(code, "en") == locales_en[key]
        assert "HTTP" not in locales_zh[key] and "token" not in locales_en[key].lower()


async def test_allowed_image_call_keeps_the_completion_text(bot_client, fake_llm, tmp_path):
    _open("projalpha")
    src = _png(tmp_path)
    brand = '{"name":"North","colors":["#112233"]}'
    fake_llm.payload = {"choices": [{"message": {"content": brand}}], **_usage(0, 1)}
    res = await _post(bot_client, text="extract the brand", system="You are a brand reader.", images=[src], project="projalpha", lang="zh")
    assert res.status == 200, await res.text()
    body = await res.json()
    assert body == {"text": brand, "model": "deepseek-flash"}
    assert len(fake_llm.posts) == 1
    posted = fake_llm.posts[0]
    assert posted["method"] == "POST"
    assert posted["url"] == "https://api.deepseek.com/chat/completions"
    assert posted["json"]["stream"] is False
    assert posted["json"]["thinking"] == {"type": "disabled"}
    part = posted["json"]["messages"][-1]["content"]
    url = part[-1]["image_url"]["url"]
    raw = __import__("base64").b64decode(url.split(",", 1)[1])
    with Image.open(io.BytesIO(raw)) as im:
        assert im.format == "JPEG"
        assert max(im.size) <= 1568
    from ComfyArt.bot.llm_usd_gate import default_ledger_path
    state = ledger_state(default_ledger_path())
    row = next(iter(state["reservations"].values()))
    assert row["status"] == "reconciled"
    raw_ledger = json.loads(Path(default_ledger_path()).read_text(encoding="utf-8"))
    saved = next(iter(raw_ledger["reservations"].values()))
    assert saved["project_id"] == "projalpha"
    assert saved["input_evidence"]["image_tokens"] == 1024
    assert state["accounted_nano"] == 1200


async def test_text_only_official_call_fail_closes_with_no_post(bot_client, fake_llm, caplog):
    _open("projalpha")
    res = await _post(bot_client, text="plan a storyboard", system="Reply JSON.", images=[], project="projalpha", lang="en")
    assert res.status == 400
    assert (await res.json())["error"] == _notice("en", "unbounded_billed_input")
    assert fake_llm.posts == []
    assert "unbounded_billed_input" in caplog.text
    from ComfyArt.bot.llm_usd_gate import default_ledger_path
    assert not Path(default_ledger_path()).exists()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_blocks_use_only_the_approved_notice(bot_client, fake_llm, tmp_path, lang):
    _open("projalpha")
    src = _png(tmp_path)
    # The per-call $0.50 block needs more body than aiohttp's 1MB test default.
    bot_client.server.app._client_max_size = 4 * 1024 * 1024
    huge = await _post(
        bot_client, text="look", system="x" * 1_700_000, images=[src], project="projalpha", lang=lang,
    )
    assert huge.status == 400, await huge.text()
    assert (await huge.json())["error"] == _notice(lang, "image_too_large")
    folder = tmp_path / "input"
    folder.mkdir(parents=True, exist_ok=True)
    from test_llm_usd_gate import _png_ihdr
    (folder / "bomb.png").write_bytes(_png_ihdr(20000, 15000))
    declared = await _post(
        bot_client, text="look", system="brief", images=["/api/view?filename=bomb.png&type=input"],
        project="projalpha", lang=lang,
    )
    assert declared.status == 400
    assert (await declared.json())["error"] == _notice(lang, "image_too_large")
    unread = await _post(
        bot_client, text="look", system="be brief", images=["https://example.test/a.png"], project="projalpha", lang=lang,
    )
    assert unread.status == 400
    assert (await unread.json())["error"] == _notice(lang, "unbounded_multimodal")
    assert fake_llm.posts == []


async def test_cumulative_stop_is_per_saved_project_and_a_new_project_starts_at_zero(bot_client, fake_llm, tmp_path):
    src = _png(tmp_path)
    _open("alpha01")
    _open("beta02")
    medium = {"text": "look", "system": "y" * 800_000, "images": [src], "lang": "zh"}
    first = await _post(bot_client, **medium, project="alpha01")
    assert first.status == 200, await first.text()
    assert len(fake_llm.posts) == 1
    blocked = await _post(bot_client, **medium, project="alpha01")
    assert blocked.status == 400
    assert (await blocked.json())["error"] == _notice("zh", "over_budget")
    assert len(fake_llm.posts) == 1
    other = await _post(bot_client, **medium, project="beta02")
    assert other.status == 200, await other.text()
    assert len(fake_llm.posts) == 2
    _close_tabs()
    _open("gamma03")
    fresh = await _post(bot_client, **medium, project="gamma03")
    assert fresh.status == 200, await fresh.text()
    from ComfyArt.bot.llm_usd_gate import default_ledger_path
    rows = json.loads(Path(default_ledger_path()).read_text(encoding="utf-8"))["reservations"].values()
    by_project: dict[str, int] = {}
    for row in rows:
        by_project[row["project_id"]] = by_project.get(row["project_id"], 0) + 1
    assert by_project["alpha01"] == 1
    assert by_project["beta02"] == 1
    assert by_project["gamma03"] == 1
    assert "local" not in by_project and "" not in by_project


async def test_spoofed_or_ambiguous_project_does_not_open_a_bucket(bot_client, fake_llm, tmp_path):
    src = _png(tmp_path)
    _open("alpha01")
    _open("beta02")
    body = {"text": "look", "system": "brief", "images": [src], "lang": "en"}
    spoof = await _post(bot_client, **body, project="not-saved")
    assert spoof.status == 400
    assert (await spoof.json())["error"] == _notice("en", "project_unverified")
    missing = await _post(bot_client, **body)
    assert missing.status == 400
    assert (await missing.json())["error"] == _notice("en", "project_unverified")
    assert fake_llm.posts == []
    from ComfyArt.bot.llm_usd_gate import default_ledger_path
    assert not Path(default_ledger_path()).exists()
    _close_tabs()
    _open("alpha01")
    attributed = await _post(bot_client, **body)
    assert attributed.status == 200, await attributed.text()
    saved = next(iter(json.loads(Path(default_ledger_path()).read_text(encoding="utf-8"))["reservations"].values()))
    assert saved["project_id"] == "alpha01"


async def test_home_calls_do_not_share_the_local_bucket(bot_client, fake_llm, tmp_path):
    src = _png(tmp_path)
    res = await _post(bot_client, text="read this memory", system="extract", images=[src], lang="zh")
    assert res.status == 200, await res.text()
    from ComfyArt.bot.llm_usd_gate import default_ledger_path
    saved = next(iter(json.loads(Path(default_ledger_path()).read_text(encoding="utf-8"))["reservations"].values()))
    assert saved["project_id"] == bot_complete.outside_project_id("default")
    assert saved["project_id"] not in ("", "local")
    _open("alpha01")
    other = await _post(bot_client, text="look", system="brief", images=[src], project="alpha01", lang="zh")
    assert other.status == 200, await other.text()
    ids = {row["project_id"] for row in json.loads(Path(default_ledger_path()).read_text(encoding="utf-8"))["reservations"].values()}
    assert ids == {bot_complete.outside_project_id("default"), "alpha01"}


async def test_bare_connector_exception_is_not_a_refund(bot_client, fake_llm, tmp_path):
    """A raised ClientConnectorError has no trace, so the hold stays."""
    _open("alpha01")
    src = _png(tmp_path)
    fake_llm.boom = _connector_error()
    res = await _post(bot_client, text="look", system="brief", images=[src], project="alpha01", lang="zh")
    assert res.status == 502
    from ComfyArt.bot.llm_usd_gate import default_ledger_path
    state = ledger_state(default_ledger_path())
    row = next(iter(state["reservations"].values()))
    assert row["status"] == "retained"
    assert row["retain_reason"] == "transport:ClientConnectorError"
    assert state["accounted_nano"] == row["reserved_nano"] > 0
    fake_llm.boom = None
    fake_llm.payload = {"choices": [{"message": {"content": "ok"}}], **_usage(0, 1)}
    again = await _post(bot_client, text="look", system="brief", images=[src], project="alpha01", lang="zh")
    assert again.status == 200, await again.text()
    assert ledger_state(default_ledger_path())["accounted_nano"] == row["reserved_nano"] + 1200


async def test_official_bot_complete_refuses_a_shared_local_bucket(bot_client, monkeypatch):
    from ComfyArt.bot.providers import TurnResult, get_provider, register_provider
    from conftest import FakeProvider, write_settings

    previous = get_provider("local-llm")

    class _Local(FakeProvider):
        id = "local-llm"
        label = "Local LLM"

        sent = 0

        async def send(self, turn, emit, handle):
            self.last_turn = turn
            self.sent += 1
            return TurnResult()

    local = _Local()
    register_provider(local)
    write_settings(**{"bot-provider": "local-llm"})
    try:
        _open("alpha01")
        ok = await bot_client.post("/comfyart/bot/complete", json={"text": "hi", "project": "alpha01", "lang": "en"})
        assert ok.status == 200, await ok.text()
        assert local.last_turn.project_id == "alpha01"
        refused = await bot_client.post("/comfyart/bot/complete", json={"text": "hi", "project": "made-up", "lang": "zh"})
        assert refused.status == 400
        assert (await refused.json())["error"] == _notice("zh", "project_unverified")
        assert local.sent == 1
    finally:
        if previous is not None:
            register_provider(previous)


def _run(coro):
    return asyncio.run(coro)


def test_unproven_failures_stay_and_verified_usage_settles_once(tmp_path):
    from ComfyArt.bot.llm_usd_gate import dispatch

    path = tmp_path / "fail.json"
    # Amount-only $2 scope, not the controlled profile. Several full holds
    # would pass the default $0.05 ceiling and stop the later cases early.
    open_authorized_scope(str(path), TWO_DOLLAR_CEILING_NANO)
    hold = 24_000_000

    async def connector():
        raise _connector_error()

    with pytest.raises(aiohttp.ClientConnectorError):
        _run(dispatch(_text(max_tokens=20000), route=_route(), url=URL, send=connector, ledger_path=str(path), bound_fn=_zero_bound))
    state = ledger_state(str(path))
    row = next(iter(state["reservations"].values()))
    assert row["status"] == "retained" and row["retain_reason"] == "transport:ClientConnectorError"
    assert state["accounted_nano"] == hold

    async def connect_timeout():
        raise aiohttp.ConnectionTimeoutError("connect")

    with pytest.raises(aiohttp.ConnectionTimeoutError):
        _run(dispatch(_text(max_tokens=20000), route=_route(), url=URL, send=connect_timeout, ledger_path=str(path), bound_fn=_zero_bound))
    assert ledger_state(str(path))["accounted_nano"] == hold * 2

    async def timeout():
        raise asyncio.TimeoutError()

    with pytest.raises(asyncio.TimeoutError):
        _run(dispatch(_text(max_tokens=20000), route=_route(), url=URL, send=timeout, ledger_path=str(path), bound_fn=_zero_bound))
    state = ledger_state(str(path))
    assert any(row["retain_reason"] == "transport:TimeoutError" for row in state["reservations"].values())
    assert state["accounted_nano"] == hold * 3

    async def disconnected():
        raise aiohttp.ServerDisconnectedError("closed")

    with pytest.raises(aiohttp.ServerDisconnectedError):
        _run(dispatch(_text(max_tokens=20000), route=_route(), url=URL, send=disconnected, ledger_path=str(path), bound_fn=_zero_bound))
    state = ledger_state(str(path))
    assert any(row["retain_reason"] == "transport:ServerDisconnectedError" for row in state["reservations"].values())
    assert state["accounted_nano"] == hold * 4

    async def http_usage():
        raise LlmHttpError(500, json.dumps({"error": {"message": "busy"}, **_usage(0, 2)}))

    with pytest.raises(LlmHttpError):
        _run(dispatch(_text(max_tokens=20000), route=_route(), url=URL, send=http_usage, ledger_path=str(path), bound_fn=_zero_bound))
    state = ledger_state(str(path))
    reconciled = [row for row in state["reservations"].values() if row["status"] == "reconciled"]
    assert len(reconciled) == 1 and reconciled[0]["actual_nano"] == 2400
    assert state["accounted_nano"] == hold * 4 + 2400
    from ComfyArt.bot.llm_usd_gate import settle
    settled_id = next(key for key, row in state["reservations"].items() if row["status"] == "reconciled")
    again = settle(str(path), settled_id, _usage(0, 2)["usage"])
    assert again["code"] == "missing_reservation"
    assert ledger_state(str(path))["accounted_nano"] == hold * 4 + 2400

    async def http_unknown():
        raise LlmHttpError(400, json.dumps({"error": {"message": "bad request"}}))

    with pytest.raises(LlmHttpError):
        _run(dispatch(_text(max_tokens=20000), route=_route(), url=URL, send=http_unknown, ledger_path=str(path), bound_fn=_zero_bound))
    state = ledger_state(str(path))
    assert any(row["retain_reason"] == "transport:LlmHttpError" for row in state["reservations"].values())
    assert state["accounted_nano"] == hold * 5 + 2400

    async def http_malformed():
        raise LlmHttpError(200, json.dumps({"usage": {"prompt_tokens": 1}}))

    with pytest.raises(LlmHttpError):
        _run(dispatch(_text(max_tokens=20000), route=_route(), url=URL, send=http_malformed, ledger_path=str(path), bound_fn=_zero_bound))
    state = ledger_state(str(path))
    assert any(row["retain_reason"] == "missing_or_malformed_usage" for row in state["reservations"].values())
    assert state["accounted_nano"] == hold * 6 + 2400

    # A restarted reader sees the same totals. Nothing is inferred back to zero.
    again = ledger_state(str(path))
    assert again["accounted_nano"] == state["accounted_nano"]
    assert {row["status"] for row in again["reservations"].values()} == {
        row["status"] for row in state["reservations"].values()
    }


def test_controlled_scope_still_keeps_a_connector_failure(tmp_path):
    from ComfyArt.bot.llm_usd_gate import LlmScopeStopped, dispatch

    path = tmp_path / "controlled.json"
    open_authorized_scope(str(path), TWO_DOLLAR_CEILING_NANO, max_posts=2)

    async def connector():
        raise _connector_error()

    with pytest.raises(LlmScopeStopped):
        _run(dispatch(_text(max_tokens=20000), route=_route(), url=URL, send=connector, ledger_path=str(path), bound_fn=_zero_bound))
    state = ledger_state(str(path))
    row = next(iter(state["reservations"].values()))
    assert row["status"] == "retained"
    assert row["retain_reason"] == "transport:ClientConnectorError"
    assert state["accounted_nano"] == 24_000_000
    assert state["control_state"]["circuit_open"] is True


def test_concurrent_unproven_connector_errors_keep_each_hold(tmp_path):
    import threading
    from ComfyArt.bot.llm_usd_gate import dispatch

    path = tmp_path / "concurrent.json"
    barrier = threading.Barrier(8)
    errors: list[BaseException] = []

    def once():
        async def connector():
            raise _connector_error()

        barrier.wait()
        try:
            asyncio.run(dispatch(
                _text(max_tokens=1000), route=_route(), url=URL, send=connector,
                ledger_path=str(path), bound_fn=_zero_bound,
            ))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=once) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(errors) == 8
    assert all(isinstance(exc, aiohttp.ClientConnectorError) for exc in errors)
    state = ledger_state(str(path))
    assert len(state["reservations"]) == 8
    assert {row["status"] for row in state["reservations"].values()} == {"retained"}
    assert state["accounted_nano"] == 8 * 1_200_000


def _closed_port() -> int:
    import socket
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _local_route(base: str) -> dict:
    return {
        "provider": "deepseek", "model": "deepseek-flash", "catalog_model": "deepseek-flash",
        "base_url": base.rstrip("/"), "secret_env": "DEEPSEEK_API_KEY",
        "adapter": "deepseek_official", "passthrough": False, "quote": "unknown",
    }


async def _redirect_to_closed():
    from aiohttp import web
    closed = _closed_port()
    received: list[bytes] = []
    app = web.Application()

    async def handler(request):
        received.append(await request.read())
        raise web.HTTPTemporaryRedirect(location=f"http://127.0.0.1:{closed}/chat/completions")

    app.router.add_post("/chat/completions", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    return runner, f"http://127.0.0.1:{port}", received


async def test_redirect_then_connector_error_keeps_the_dispatch_hold(tmp_path):
    """First local server gets the POST. The 307 target refuses. The hold stays."""
    from ComfyArt.bot.llm_usd_gate import dispatch, exchange_with_send_proof

    runner, base, received = await _redirect_to_closed()
    path = tmp_path / "redirect.json"
    url = base + "/chat/completions"
    body = _text(max_tokens=20000)
    try:
        async def send():
            await exchange_with_send_proof(
                "POST", url, headers={"Content-Type": "application/json"}, timeout=5, json_body=body,
            )

        before = 0
        with pytest.raises(aiohttp.ClientConnectorError):
            await dispatch(body, route=_local_route(base), url=url, send=send, ledger_path=str(path), bound_fn=_zero_bound)
    finally:
        await runner.cleanup()
    assert received and len(received[0]) > 0
    state = ledger_state(str(path))
    row = next(iter(state["reservations"].values()))
    assert row["status"] == "retained"
    assert row["retain_reason"] == "transport:ClientConnectorError"
    assert state["accounted_nano"] == row["reserved_nano"] == 24_000_000
    assert state["accounted_nano"] > before


async def test_initial_connection_refusal_releases_only_with_an_empty_trace(tmp_path):
    from ComfyArt.bot.llm_usd_gate import RequestNotWritten, dispatch, exchange_with_send_proof

    port = _closed_port()
    base = f"http://127.0.0.1:{port}"
    path = tmp_path / "refused.json"
    url = base + "/chat/completions"
    body = _text(max_tokens=20000)

    async def send():
        await exchange_with_send_proof(
            "POST", url, headers={"Content-Type": "application/json"}, timeout=5, json_body=body,
        )

    with pytest.raises(RequestNotWritten) as refused:
        await dispatch(body, route=_local_route(base), url=url, send=send, ledger_path=str(path), bound_fn=_zero_bound)
    assert isinstance(refused.value.cause, aiohttp.ClientConnectorError)
    state = ledger_state(str(path))
    row = next(iter(state["reservations"].values()))
    assert row["status"] == "released" and row["actual_nano"] == 0
    assert row["retain_reason"] == "no_network:RequestNotWritten:ClientConnectorError"
    assert state["accounted_nano"] == 0


async def test_llm_complete_redirect_keeps_the_hold_and_a_refused_connect_releases(bot_client, monkeypatch, tmp_path):
    from ComfyArt.api import provider_admin
    from ComfyArt.bot.llm_usd_gate import default_ledger_path

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-a-live-secret")
    _open("alpha01")
    src = _png(tmp_path)
    runner, base, received = await _redirect_to_closed()
    monkeypatch.setattr(provider_admin, "llm_route", lambda active=None: _local_route(base))
    try:
        redirected = await _post(
            bot_client, text="look", system="brief", images=[src], project="alpha01", lang="en",
        )
    finally:
        await runner.cleanup()
    assert redirected.status == 502, await redirected.text()
    assert received and len(received[0]) > 0
    state = ledger_state(default_ledger_path())
    row = next(iter(state["reservations"].values()))
    assert row["status"] == "retained"
    assert row["retain_reason"] == "transport:ClientConnectorError"
    held = state["accounted_nano"]
    assert held == row["reserved_nano"] > 0

    closed = _closed_port()
    monkeypatch.setattr(provider_admin, "llm_route", lambda active=None: _local_route(f"http://127.0.0.1:{closed}"))
    refused = await _post(
        bot_client, text="look", system="brief", images=[src], project="alpha01", lang="en",
    )
    assert refused.status == 502
    state = ledger_state(default_ledger_path())
    released = [item for item in state["reservations"].values() if item["status"] == "released"]
    assert len(released) == 1
    assert released[0]["actual_nano"] == 0
    assert released[0]["retain_reason"] == "no_network:RequestNotWritten:ClientConnectorError"
    assert state["accounted_nano"] == held
