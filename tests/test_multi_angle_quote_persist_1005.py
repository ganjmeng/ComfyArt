"""Lineart content wording and the forced quote card. No network and no spend.

The panel note "inner faces" is a surface, not a direction. A priced preview under
the confirm line must still persist a plan_quote card and wait; start=true is only
an answered card. PRECHECK_ONLY never submits.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from multi_angle_plan_fixture import HEADPHONES_PLAN
from test_agent_budget_391 import calls, reply
from test_multi_angle_stages_911 import DESC, REF

from ComfyArt.api import bot_asks, bot_turns, chat_store, mcp, multi_angle as ma, paid_guard
from ComfyArt.api.mcp_tools import bot_tools, canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.local_llm import LocalLlmProvider, explain_unsubmitted
from ComfyArt.bot.plan_quote import build_quote
from ComfyArt.bot.providers import TurnHandle, TurnRequest


SURFACE = "earcup inner faces, cushion padding, headband inner lining"
FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "quote_0f4039e8"


def _plan():
    plan = copy.deepcopy(HEADPHONES_PLAN)
    plan["panels"][3]["content"] = SURFACE
    return plan


def _load(name):
    return json.loads((FIXTURE / name).read_text())


def test_quote_route_without_the_turn_chat_param_blocks_the_exact_plan():
    """The agent prices a quote before MCP sets BOT_CHAT_ID. That block is 0 units."""
    from ComfyArt.api.mcp_tools.canvas import quote_route
    gen2 = _load("gen2.json")["input"]
    token = BOT_CHAT_ID.set("")
    try:
        routed = quote_route("generate_image", dict(gen2))
    finally:
        BOT_CHAT_ID.reset(token)
    assert routed is not None and routed[0] == ""
    blocked = routed[1]["param_blocked"]
    assert "ask_user" in blocked["error"]
    assert blocked.get("submitted") is False


def test_inner_faces_is_a_surface_and_directions_still_fail():
    ma.validate_content(SURFACE)
    raw = _plan()
    plan = ma.validate_plan(raw)
    panel = next(p for p in plan["panels"] if p["id"] == "4")
    assert panel["content"] == SURFACE
    # geometry and description are not content. Camera wording there stays.
    assert plan["panels"][0]["geometry"] == raw["panels"][0]["geometry"]
    assert "three-quarter" in plan["panels"][1]["description"]
    assert "90-degree" in plan["panels"][2]["description"]
    assert "top-down" in plan["panels"][6]["description"]
    for bad in ("left earcup", "facing the camera", "camera above the headband"):
        with pytest.raises(ValueError, match="direction"):
            ma.validate_content(bad)


def test_redirect_is_not_rewritten_into_the_generic_unsubmitted_error():
    raw = json.dumps({
        "submitted": False, "status": "blocked", "next_step": "quote_card",
        "redirect": "quote_card", "quote_card": "线稿预览",
        "error": "先出示「线稿预览」报价卡",
    }, ensure_ascii=False)
    assert explain_unsubmitted("generate_image", raw, "zh") is None


@pytest.mark.asyncio
async def test_forced_quote_asks_when_pricing_marks_zero_units():
    async def pricer(_name, _args):
        return 0.01

    async def models_for(_feature):
        return [("mock/edit", 0.01)]

    def router(_tool, _args, position=0):
        return "", {"param_blocked": {"error": "blocked", "submitted": False}}

    steps = [{"text": "preview", "tool": "generate_image", "model": "mock/edit",
              "arguments": {"skill": ma.SKILL, "multi_angle_stage": "preview", "prompt": "lineart", "count": 1}}]
    quote = await build_quote(steps, "zh", threshold=1.0, pricer=pricer, models_for=models_for, router=router)
    assert quote is not None and quote.ask is True
    spec = quote.ask_spec()
    assert spec["kind"] == "plan_quote"
    assert {o["id"] for o in spec["options"]} == {"start", "cancel"}


async def _turn(monkeypatch, script, *, answer, precheck=False, bind_chat=True):
    chat = chat_store.create_chat(user="default", project="mock-quote", provider="local-llm")
    cid = chat["id"]
    chat_store.create_message(chat_id=cid, role="user", blocks=[
        {"type": "skill", "name": ma.SKILL}, {"type": "text", "text": DESC},
        {"type": "image", "url": REF}])
    token = BOT_CHAT_ID.set(cid)
    spec = bot_asks.validate_spec({"prompt": "setup"})
    BOT_CHAT_ID.reset(token)
    block = {"type": "ask", "ask_id": "setup", "status": "answered", **spec, "answers": {
        ma.SOURCE: {"selected": ["single_front"]}, ma.ASPECT: {"selected": ["1:1"]}}}
    chat_store.create_message(chat_id=cid, role="assistant", blocks=[block])
    assistant = chat_store.create_message(chat_id=cid, role="assistant", blocks=[], status="running")
    handle = TurnHandle()
    state = bot_turns._TurnState(handle, cid, assistant["id"])
    monkeypatch.setitem(bot_turns.ACTIVE_TURNS, cid, state)
    sent = []

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if (json_body or {}).get("method") == "tools/list":
            return {"result": {"tools": [{"name": n, "inputSchema": {"type": "object"}}
                                          for n in ("generate_image", "quote_plan")]}}
        if not str(url).endswith("/chat/completions"):
            return {"data": [{"id": "mock", "context_length": 32000}]}
        return script.pop(0)

    async def real_mcp(session, endpoint, name, arguments):
        # The live tool call is an HTTP request that sets the chat for that
        # request only. The quote is built earlier, in the agent task.
        tool_token = BOT_CHAT_ID.set(cid)
        try:
            out = await mcp._tools_call({"name": name, "arguments": arguments})
        finally:
            BOT_CHAT_ID.reset(tool_token)
        return next(b["text"] for b in out["content"] if b["type"] == "text"), []

    async def page_supplier(action, args, project, timeout, chat=""):
        sent.append((action, copy.deepcopy(args)))
        raise AssertionError("no image submit")

    def answer_broadcast(event, payload):
        if event != "turn_ask" or payload.get("kind") != "plan_quote":
            return
        if answer == "expired":
            bot_asks.resolve_ask(payload["ask_id"], "expired")
            return
        selected = ["start"] if answer == "start" else ["cancel"]
        bot_asks.resolve_ask(payload["ask_id"], "answered", selected=selected)

    async def price(*_a, **_k):
        return 0.01

    async def models(_feature):
        return [("mock/edit", 0.01)]

    provider = LocalLlmProvider(base_url=lambda: "http://mock-no-network/v1")
    async def window(*_a):
        return 32000

    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", real_mcp)
    monkeypatch.setattr(provider, "_context_window", window)
    monkeypatch.setattr(provider, "_price_one", price)
    monkeypatch.setattr(provider, "_price_call", price)
    monkeypatch.setattr(provider, "_models_for", models)
    monkeypatch.setattr(provider, "_run_store", lambda: None)
    monkeypatch.setattr(bot_tools, "broadcast", answer_broadcast)
    monkeypatch.setattr(canvas, "submit_command", page_supplier)
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: None)
    monkeypatch.setattr(canvas, "unregistered_model", lambda *a, **k: None)
    monkeypatch.setattr(canvas, "load_config", lambda: {"features": {}})
    if precheck:
        monkeypatch.setenv("COMFYART_CONTROLLED_PRECHECK_ONLY", "1")
    else:
        monkeypatch.delenv("COMFYART_CONTROLLED_PRECHECK_ONLY", raising=False)
    paid_guard.begin_turn(cid, text=DESC, provider_text=DESC)
    token = BOT_CHAT_ID.set(cid) if bind_chat else None
    events = []

    async def collect(event):
        events.append(event)

    try:
        result = await provider.send(TurnRequest(
            chat_id=cid, user_text=f"Use the ComfyArt skill '{ma.SKILL}'. {DESC}",
            goal_text=DESC, lang="zh", mcp_endpoint="http://mock-no-network/mcp", model="mock"),
            collect, handle)
    finally:
        if token is not None:
            BOT_CHAT_ID.reset(token)
        paid_guard.end_turn(cid)
        bot_turns.ACTIVE_TURNS.pop(cid, None)
        os.environ.pop("COMFYART_CONTROLLED_PRECHECK_ONLY", None)
    stored = chat_store.list_messages(cid)
    quotes = [b for row in stored for b in row.get("blocks") or [] if b.get("kind") == "plan_quote"]
    return result, events, sent, quotes


def _preview_args():
    return {
        "skill": ma.SKILL, "composition_plan": _plan(), "refs": [REF],
        "multi_angle_stage": "preview", "width": 1152, "height": 2048, "ratio": "9:16", "count": 1,
    }


def _assert_lineart_card(quotes):
    assert quotes and quotes[0]["kind"] == "plan_quote"
    assert any("线稿预览" in (ln.get("text") or "") for ln in quotes[0].get("lines") or [])
    assert {o["id"] for o in quotes[0]["options"]} == {"start", "cancel"}


@pytest.mark.asyncio
@pytest.mark.parametrize("which", ["quote_plan", "gen1", "gen2", "gen3"])
async def test_exact_persisted_call_waits_on_a_lineart_card_without_a_preset_chat(monkeypatch, which):
    """Live quote_plan/generate ran with BOT_CHAT_ID still empty and returned start=true."""
    if which == "quote_plan":
        args = _load("quote_plan.json")["input"]
        script = [calls(("quote_plan", args)), reply("done")]
    else:
        args = _load(f"{which}.json")["input"]
        script = [calls(("generate_image", args)), reply("done")]
    _result, events, sent, quotes = await _turn(
        monkeypatch, script, answer="cancel", bind_chat=False)
    _assert_lineart_card(quotes)
    assert quotes[0]["status"] == "answered"
    assert sent == []
    if which == "quote_plan":
        row = next(e for e in events if e.t == "tool_result" and e.name == "quote_plan")
        assert '"start": true' not in row.text and '"start":true' not in row.text.replace(" ", "")


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["cancel", "expired"])
async def test_unconfirmed_quote_never_starts_or_submits(monkeypatch, answer):
    steps = {"steps": [{"text": "线稿", "tool": "generate_image", "model": "mock/edit",
                        "arguments": _preview_args()}]}
    result, events, sent, quotes = await _turn(
        monkeypatch, [calls(("quote_plan", steps)), reply("done")], answer=answer)
    assert quotes and quotes[0]["kind"] == "plan_quote"
    assert any("线稿预览" in (ln.get("text") or "") for ln in quotes[0].get("lines") or [])
    assert {o["id"] for o in quotes[0]["options"]} == {"start", "cancel"}
    assert quotes[0]["status"] == ("expired" if answer == "expired" else "answered")
    row = next(e for e in events if e.t == "tool_result" and e.name == "quote_plan")
    assert '"start": true' not in row.text and '"start":true' not in row.text.replace(" ", "")
    assert sent == []


@pytest.mark.asyncio
async def test_missing_turn_does_not_auto_start(monkeypatch):
    steps = {"steps": [{"text": "线稿", "tool": "generate_image", "model": "mock/edit",
                        "arguments": _preview_args()}]}
    chat = chat_store.create_chat(user="default", project="mock-quote", provider="local-llm")
    cid = chat["id"]
    provider = LocalLlmProvider(base_url=lambda: "http://mock-no-network/v1")
    script = [calls(("quote_plan", steps)), reply("done")]

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if not str(url).endswith("/chat/completions"):
            return {"result": {"tools": [{"name": "quote_plan"}]}} if (json_body or {}).get("method") == "tools/list" else {"data": [{"id": "m", "context_length": 8000}]}
        return script.pop(0)

    async def price(*_a, **_k):
        return 0.01

    async def window(*_a):
        return 8000

    async def no_mcp(*_a, **_k):
        return "should-not-run", []

    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", no_mcp)
    monkeypatch.setattr(provider, "_context_window", window)
    monkeypatch.setattr(provider, "_price_one", price)
    monkeypatch.setattr(provider, "_models_for", lambda *_a: [("mock/edit", 0.01)])
    monkeypatch.setattr(provider, "_run_store", lambda: None)
    events = []

    async def collect(event):
        events.append(event)

    result = await provider.send(TurnRequest(
        chat_id=cid, user_text="preview", lang="zh", mcp_endpoint="http://mock/mcp", model="m"),
        collect, TurnHandle())
    row = next(e for e in events if e.t == "tool_result" and e.name == "quote_plan")
    assert '"start": true' not in row.text
    assert result.aborted is False


@pytest.mark.asyncio
async def test_confirmed_preview_stays_precheck_and_does_not_submit(monkeypatch):
    args = _load("gen2.json")["input"]
    _result, events, sent, quotes = await _turn(
        monkeypatch, [calls(("generate_image", args)), reply("done")],
        answer="start", precheck=True, bind_chat=False)
    _assert_lineart_card(quotes)
    assert quotes[0]["status"] == "answered" and quotes[0]["selected"] == ["start"]
    assert sent == []
    texts = " ".join(e.text or "" for e in events if e.t == "tool_result")
    assert "controlled_precheck_only" in texts
