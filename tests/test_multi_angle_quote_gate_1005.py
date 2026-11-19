"""Server-side lineart quote gate and expired-ask end-turn. No network."""
from __future__ import annotations

import copy
import json

import pytest

from multi_angle_plan_fixture import HEADPHONES_PLAN
from test_multi_angle_stages_911 import confirm_quote, run, setup  # noqa: F401

from ComfyArt.api import bot_asks, bot_turns, chat_store, mcp, multi_angle as ma, paid_guard
from ComfyArt.api.mcp_tools import bot_tools, canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.api.mcp_tools.bot_tools import ASK_EXPIRED_MARK


def _body(out: dict) -> dict:
    return json.loads(next(b["text"] for b in out["content"] if b["type"] == "text"))


@pytest.mark.asyncio
async def test_direct_generate_after_card_answer_redirects_to_quote_card(run, monkeypatch):
    """(a) Setup card answered, quote not confirmed: generate_image is refused first."""
    rows, sent = run
    setup(rows, "3:4")
    before = copy.deepcopy(rows)
    catalog_calls = []

    async def catalog(*_a, **_k):
        catalog_calls.append("catalog")
        return {}

    monkeypatch.setattr("ComfyArt.api.wavespeed.catalog", catalog)
    paid_guard.begin_turn("chat-ma", text="商品详情页", provider_text="商品详情页")
    used = dict(paid_guard.TURNS["chat-ma"].used)
    try:
        out = await mcp._tools_call({"name": "generate_image", "arguments": {
            "skill": ma.SKILL, "composition_plan": HEADPHONES_PLAN,
            "multi_angle_stage": "preview", "ratio": "1:1"}})
        after = dict(paid_guard.TURNS["chat-ma"].used)
    finally:
        paid_guard.end_turn("chat-ma")
    body = _body(out)
    assert body["submitted"] is False and body["status"] == "blocked"
    assert body["next_step"] == "quote_card" and body["quote_card"] == "线稿预览"
    assert "线稿预览" in body["error"] and "报价" in body["error"]
    assert sent == [] and catalog_calls == [] and rows == before
    assert after == used


@pytest.mark.asyncio
async def test_confirmed_quote_allows_generate_through_the_guard(run):
    """(b) Quote confirmed in session state: generate_image passes the normal guard."""
    rows, sent = run
    setup(rows, "3:4")
    confirm_quote(rows)
    paid_guard.begin_turn("chat-ma", text="商品详情页", provider_text="商品详情页")
    try:
        out = await mcp._tools_call({"name": "generate_image", "arguments": {
            "skill": ma.SKILL, "composition_plan": HEADPHONES_PLAN,
            "multi_angle_stage": "preview", "ratio": "1:1"}})
        body = _body(out)
        assert body.get("submitted") is True and sent
        assert paid_guard.TURNS["chat-ma"].used.get(paid_guard.TURNS["chat-ma"].plan_item, 0) == 1
    finally:
        paid_guard.end_turn("chat-ma")


@pytest.mark.asyncio
async def test_expired_ask_ends_turn_before_generate_image(monkeypatch):
    """(c) An expired ask_user ends the turn; the scripted next generate_image never runs."""
    from ComfyArt.bot.local_llm import LocalLlmProvider
    from ComfyArt.bot.providers import TurnHandle, TurnRequest
    from ComfyArt.bot.run_budget import resolve_policy
    from test_agent_budget_391 import calls, reply

    monkeypatch.setattr(bot_asks, "ASK_TIMEOUT_S", 0)
    chat = chat_store.create_chat(user="default", project="mock-1005", provider="local-llm")
    cid = chat["id"]
    chat_store.create_message(chat_id=cid, role="user", blocks=[
        {"type": "skill", "name": ma.SKILL}, {"type": "text", "text": "商品详情页"}])
    assistant = chat_store.create_message(chat_id=cid, role="assistant", blocks=[], status="running")
    handle = TurnHandle()
    state = bot_turns._TurnState(handle, cid, assistant["id"])
    monkeypatch.setitem(bot_turns.ACTIVE_TURNS, cid, state)
    trace, sent, seen, results = [], [], [], []
    script = [
        calls(("ask_user", {"prompt": "setup"})),
        calls(("generate_image", {"skill": ma.SKILL, "prompt": "must not run",
                                  "composition_plan": HEADPHONES_PLAN})),
        reply("must not be requested"),
    ]
    provider = LocalLlmProvider(base_url=lambda: "http://mock-no-network/v1")

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if (json_body or {}).get("method") == "tools/list":
            return {"result": {"tools": [{"name": n, "inputSchema": {"type": "object", "properties": {}}}
                                          for n in ("ask_user", "generate_image")]}}
        if not url.endswith("/chat/completions"):
            return {"data": [{"id": "mock-1005", "context_length": 32000}]}
        seen.append(json_body["messages"])
        return script[len(seen) - 1]

    async def real_mcp(session, endpoint, name, arguments):
        trace.append(name)
        out = await mcp._tools_call({"name": name, "arguments": arguments})
        assert out is not None
        text = next(b["text"] for b in out["content"] if b["type"] == "text")
        results.append(text)
        return text, []

    async def page_supplier(action, args, project, timeout, chat=""):
        sent.append((action, copy.deepcopy(args)))
        return {"ids": ["holder:1"], "submitted": True}

    async def window(*_a):
        return 32000

    async def no_price(*_a, **_k):
        return None

    async def no_models(*_a):
        return []

    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", real_mcp)
    monkeypatch.setattr(provider, "_context_window", window)
    monkeypatch.setattr(provider, "_price_call", no_price)
    monkeypatch.setattr(provider, "_price_one", no_price)
    monkeypatch.setattr(provider, "_models_for", no_models)
    monkeypatch.setattr(provider, "_run_store", lambda: None)
    monkeypatch.setattr(provider, "_run_policy", lambda: resolve_policy(env={}))
    monkeypatch.setattr(bot_tools, "broadcast", lambda *_a, **_k: None)
    monkeypatch.setattr(canvas, "submit_command", page_supplier)
    paid_guard.begin_turn(cid, text="商品详情页", provider_text="商品详情页")
    used_before = dict(paid_guard.TURNS[cid].used)
    token = BOT_CHAT_ID.set(cid)
    try:
        result = await provider.send(TurnRequest(
            chat_id=cid, user_text=f"Use the ComfyArt skill '{ma.SKILL}' for this task.",
            goal_text="商品详情页", lang="zh", mcp_endpoint="http://mock-no-network/mcp",
            model="mock-1005"), _noop, handle)
        used_after = dict(paid_guard.TURNS[cid].used)
    finally:
        BOT_CHAT_ID.reset(token)
        paid_guard.end_turn(cid)
        bot_turns.ACTIVE_TURNS.pop(cid, None)
    assert trace == ["ask_user"], trace
    assert len(seen) == 1 and sent == []
    assert ASK_EXPIRED_MARK in results[0]
    assert "End the turn now" in results[0]
    assert "proceed conservatively" not in results[0]
    stored = chat_store.list_messages(cid)
    asks = [b for row in stored for b in row.get("blocks") or [] if b.get("type") == "ask"]
    assert asks and asks[-1]["status"] == "expired"
    assert result.run["stop"]["sub"] == "ask_expired"
    assert result.run["stop"]["code"] == "awaiting_confirm:ask_expired"
    assert result.error == "" and result.aborted is False
    assert "generate_image" not in trace
    assert used_after == used_before


async def _noop(_event):
    return None
