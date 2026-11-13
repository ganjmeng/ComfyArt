from __future__ import annotations

import asyncio

from aiohttp import web
from conftest import SENT, wait_bot_done, write_settings

from ComfyArt.api import bot_asks, chat_store
from ComfyArt.api.bot import reap_stale_messages
from ComfyArt.api.bot_turns import ACTIVE_TURNS
from ComfyArt.bot.providers import BotEvent


async def _chat(client, provider="fake-test", headers=None):
    resp = await client.post("/comfyart/bot/chats", json={"project": "p", "provider": provider}, headers=headers)
    assert resp.status == 200
    return (await resp.json())["chat"]


async def test_everything_is_off_by_default(bot_client):
    write_settings(**{"enable-mcp": False, "enable-bot": False})
    assert (await (await bot_client.get("/comfyart/bot/status")).json()) == {"enabled": False, "user": "default", "providers": []}
    resp = await bot_client.post("/comfyart/bot/chats", json={"project": "p", "provider": "codex"})
    assert resp.status == 403
    assert (await bot_client.post("/comfyart/bot/complete", json={"text": "hi"})).status == 403


async def test_bot_works_without_mcp_but_external_send_needs_it(bot_client, fake_provider):
    # #219: the Agent no longer needs the MCP switch; only external tools sending a turn do
    write_settings(**{"enable-mcp": False, "enable-bot": True})
    assert (await bot_client.get("/comfyart/bot/chats?project=p")).status == 200
    chat = (await (await bot_client.post("/comfyart/bot/chats", json={"project": "p", "provider": "fake-test"})).json())["chat"]
    assert (await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send", json={"text": "hi"})).status == 403


async def test_create_requires_project_and_known_provider(bot_client, fake_provider):
    assert (await bot_client.post("/comfyart/bot/chats", json={"provider": "fake-test"})).status == 400
    assert (await bot_client.post("/comfyart/bot/chats", json={"project": "p", "provider": "nope"})).status == 400


async def test_other_users_cannot_see_or_touch_a_chat(bot_client, fake_provider):
    chat = await _chat(bot_client)
    alice = {"comfy-user": "alice"}
    assert (await bot_client.get(f"/comfyart/bot/chats/{chat['id']}", headers=alice)).status == 404
    assert (await bot_client.delete(f"/comfyart/bot/chats/{chat['id']}", headers=alice)).status == 404
    listed = await (await bot_client.get("/comfyart/bot/chats?project=p", headers=alice)).json()
    assert listed["chats"] == []
    assert (await bot_client.get("/comfyart/bot/chats?project=p", headers={"comfy-user": "mallory"})).status == 403


async def test_send_streams_blocks_and_titles_the_chat(bot_client, fake_provider):
    # "make a poster" parses as an image goal (#383). This turn only calls get_canvas, so
    # self-check fails and appends a warn notice — product-correct, not a regression (#416).
    fake_provider.script = [BotEvent(t="thinking", text="Plan "), BotEvent(t="thinking", text="first"),
                            BotEvent(t="delta", text="Hello "), BotEvent(t="delta", text="there"),
                            BotEvent(t="tool_use", name="get_canvas", input={}, id="t1"),
                            BotEvent(t="tool_result", name="get_canvas", text="{}", id="t1")]
    chat = await _chat(bot_client)
    resp = await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send", json={"text": "make a poster", "memory": "MEM", "context": "[CTX]"})
    assert resp.status == 200
    data = await wait_bot_done(bot_client, chat["id"])
    assistant = data["messages"][-1]
    assert [b["type"] for b in assistant["blocks"]] == ["thinking", "text", "tool_use", "tool_result", "notice"]
    assert assistant["blocks"][0]["text"] == "Plan first"
    assert assistant["blocks"][1]["text"] == "Hello there"
    assert assistant["blocks"][3]["duration_ms"] >= 0
    notice = assistant["blocks"][4]
    assert notice["level"] == "warn" and notice.get("self_check", {}).get("self_check") == "fail"
    assert data["chat"]["title"] == "make a poster"
    assert data["chat"]["resume_token"] == "tok-1"
    # bot_send prefixes [Review: ON|OFF] (#364) before memory + user text + context
    ut = fake_provider.last_turn.user_text
    assert ut.startswith("[Review: ON]")
    assert "MEM\n\nmake a poster" in ut
    assert ut.endswith("[CTX]")
    assert [b["text"] for b in data["messages"][0]["blocks"] if b["type"] == "text"] == ["make a poster"]
    assert fake_provider.last_turn.mcp_endpoint.endswith(f"/comfyart/mcp?bot_chat={chat['id']}")
    assert any(event == "comfyart-bot" and data["event"] == "turn_done" for event, data in SENT)


async def test_messages_queue_while_busy_and_stop_aborts(bot_client, fake_provider):
    fake_provider.gate = asyncio.Event()
    chat = await _chat(bot_client)
    await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send", json={"text": "one"})
    second = await (await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send", json={"text": "two"})).json()
    assert second["queued"] is True
    await asyncio.sleep(0.15)
    assert (await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/stop")).status == 200
    fake_provider.gate = None
    data = await wait_bot_done(bot_client, chat["id"])
    statuses = [m["status"] for m in data["messages"] if m["role"] == "assistant"]
    assert statuses == ["aborted", "done"]


async def test_ask_answer_round_trip(bot_client, fake_provider):
    chat = await _chat(bot_client)
    ask = bot_asks.create_ask(chat["id"], "m", bot_asks.validate_spec(
        {"prompt": "color?", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]}))
    bad = await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/asks/{ask.id}/answer", json={"selected": ["z"]})
    assert bad.status == 422
    ok = await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/asks/{ask.id}/answer", json={"selected": ["b"]})
    assert ok.status == 202
    assert (await ask.future)["selected"] == ["b"]


async def test_log_and_patch_message(bot_client, fake_provider):
    chat = await _chat(bot_client)
    logged = await (await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/log", json={
        "text": "a cat", "blocks": [{"type": "task", "holder": "shape:x"}]})).json()
    reply = logged["messages"][1]
    patched = await bot_client.patch(f"/comfyart/bot/chats/{chat['id']}/messages/{reply['id']}",
                                     json={"blocks": [{"type": "task", "holder": "shape:x", "srcs": ["/v"]}]})
    assert patched.status == 200
    assert chat_store.list_messages(chat["id"])[1]["blocks"][0]["srcs"] == ["/v"]
    assert chat_store.get_chat(chat["id"])["title"] == "a cat"


async def test_patch_refuses_the_streaming_message(bot_client, fake_provider):
    fake_provider.gate = asyncio.Event()
    chat = await _chat(bot_client)
    started = await (await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send", json={"text": "x"})).json()
    resp = await bot_client.patch(f"/comfyart/bot/chats/{chat['id']}/messages/{started['assistant_message']['id']}",
                                  json={"blocks": []})
    assert resp.status == 409
    fake_provider.gate.set()
    await wait_bot_done(bot_client, chat["id"])


async def test_refs_need_an_attachment_capable_provider(bot_client, fake_provider, monkeypatch):
    from ComfyArt.bot.providers import ProviderCaps
    monkeypatch.setattr(type(fake_provider), "capabilities", lambda self: ProviderCaps(attachments=False))
    chat = await _chat(bot_client)
    resp = await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send",
                                 json={"text": "x", "refs": [{"id": "shape:a", "src": "/api/view?filename=a.png"}]})
    assert resp.status == 400
    assert "cannot take images" in (await resp.json())["error"]


async def test_settings_validate_keys_and_types(bot_client):
    assert (await bot_client.put("/comfyart/settings", json={"nope": 1})).status == 400
    assert (await bot_client.put("/comfyart/settings", json={"enable-bot": "yes"})).status == 400
    saved = await (await bot_client.put("/comfyart/settings", json={"bot-local-llm-url": "http://h/v1"})).json()
    assert saved["bot-local-llm-url"] == "http://h/v1"
    assert saved["ocr-engine"] == "local"
    assert (await bot_client.put("/comfyart/settings", json={"ocr-engine": "cloud"})).status == 400
    saved = await (await bot_client.put("/comfyart/settings", json={"ocr-engine": "agent"})).json()
    assert saved["ocr-engine"] == "agent"


_LOCAL_ONLY_PATCHES = ({"enable-mcp": True}, {"enable-bot": True}, {"bot-enable-comfy-mcp": True},
                       {"bot-comfy-mcp-command": "calc"}, {"bot-hermes-ssh-host": "evil"})


async def test_lan_clients_cannot_change_what_the_agent_runs(bot_client, monkeypatch):
    # #937: port of upstream 54b6a377
    write_settings(**{"enable-mcp": False, "enable-bot": False})
    monkeypatch.setattr(web.BaseRequest, "remote", "192.168.0.50")
    for patch in _LOCAL_ONLY_PATCHES:
        resp = await bot_client.put("/comfyart/settings", json=patch)
        assert resp.status == 403 and next(iter(patch)) in (await resp.json())["error"]
    # echoing an unchanged value is fine, and every other setting still saves from the LAN
    saved = await (await bot_client.put("/comfyart/settings", json={"enable-bot": False, "ocr-engine": "agent"})).json()
    assert saved["ocr-engine"] == "agent" and saved["enable-bot"] is False
    from ComfyArt.api.settings import all_settings
    stored = all_settings()
    assert stored["enable-mcp"] is False and stored["enable-bot"] is False
    assert stored["bot-comfy-mcp-command"] == "" and stored["bot-hermes-ssh-host"] == ""


async def test_forwarded_headers_do_not_make_a_lan_client_local(bot_client, monkeypatch):
    # #937: local detection uses the TCP peer only; a spoofed X-Forwarded-For / X-Real-IP is ignored
    write_settings(**{"enable-mcp": False})
    monkeypatch.setattr(web.BaseRequest, "remote", "10.0.0.7")
    resp = await bot_client.put("/comfyart/settings", json={"enable-mcp": True},
                                headers={"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1",
                                         "Forwarded": "for=127.0.0.1"})
    assert resp.status == 403


async def test_localhost_can_change_what_the_agent_runs(bot_client, monkeypatch):
    # #937: the machine running ComfyUI (IPv4, IPv6 and IPv4-mapped loopback) still changes them
    for peer in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
        write_settings(**{"enable-mcp": False, "enable-bot": False, "bot-enable-comfy-mcp": False,
                          "bot-comfy-mcp-command": "", "bot-hermes-ssh-host": ""})
        monkeypatch.setattr(web.BaseRequest, "remote", peer)
        for patch in _LOCAL_ONLY_PATCHES:
            resp = await bot_client.put("/comfyart/settings", json=patch)
            assert resp.status == 200, (peer, patch)
            key, value = next(iter(patch.items()))
            assert (await resp.json())[key] == value


async def test_unknown_peer_is_not_treated_as_local(bot_client, monkeypatch):
    # #937: no peer address (e.g. a unix socket) is refused instead of crashing
    write_settings(**{"enable-mcp": False})
    monkeypatch.setattr(web.BaseRequest, "remote", None)
    assert (await bot_client.put("/comfyart/settings", json={"enable-mcp": True})).status == 403


async def test_float_settings_accept_int_and_reject_bool(bot_client):
    """Browser JSON has no 5.0 vs 5; a float setting must accept either and still reject bool."""
    from ComfyArt.api import settings
    float_keys = [k for k, v in settings.SETTINGS_SPEC.items() if type(v) is float]
    assert "agent-credits-usd" in float_keys
    for key in float_keys:
        for raw in (5, 5.0):
            resp = await bot_client.put("/comfyart/settings", json={key: raw})
            assert resp.status == 200, await resp.text()
            saved = await resp.json()
            assert saved[key] == 5.0
            assert type(saved[key]) is float
            stored = settings.read_json(settings.app_path("settings.json"), {})
            assert type(stored[key]) is float and stored[key] == 5.0
        for bad in (True, False):
            resp = await bot_client.put("/comfyart/settings", json={key: bad})
            assert resp.status == 400
            body = await resp.json()
            assert "must be a float" in body["error"]
        stored = settings.read_json(settings.app_path("settings.json"), {})
        assert stored[key] == 5.0 and type(stored[key]) is float
        resp = await bot_client.put("/comfyart/settings", json={key: "5"})
        assert resp.status == 400
        assert "must be a float" in (await resp.json())["error"]


async def test_status_survives_a_failing_probe(bot_client, fake_provider, monkeypatch):
    async def boom(self):
        raise OSError(448, "untrusted mount point")
    monkeypatch.setattr(type(fake_provider), "probe", boom)
    resp = await bot_client.get("/comfyart/bot/status")
    assert resp.status == 200
    entry = next(p for p in (await resp.json())["providers"] if p["id"] == "fake-test")
    assert entry["available"] is False and "untrusted mount point" in entry["detail"]


async def test_status_refresh_clears_probe_cache(bot_client, fake_provider, monkeypatch):
    from ComfyArt.bot import providers as providers_mod
    cleared: list[str] = []
    orig = providers_mod.AgentProvider.clear_probe_cache

    def tracking(self):
        cleared.append(self.id)
        return orig(self)

    monkeypatch.setattr(providers_mod.AgentProvider, "clear_probe_cache", tracking)
    cold = await bot_client.get("/comfyart/bot/status")
    assert cold.status == 200 and cleared == []
    warm = await bot_client.get("/comfyart/bot/status?refresh=1")
    assert warm.status == 200
    assert "fake-test" in cleared


def test_reap_marks_unfinished_messages_aborted():
    chat = chat_store.create_chat(user="default", project="p", provider="codex")
    msg = chat_store.create_message(chat_id=chat["id"], role="assistant", blocks=[], status="streaming")
    ACTIVE_TURNS.clear()
    reap_stale_messages()
    assert chat_store.list_messages(chat["id"])[0]["status"] == "aborted"
    assert msg["status"] == "streaming"
