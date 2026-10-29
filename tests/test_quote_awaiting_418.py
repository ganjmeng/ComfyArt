"""#418 ruling: a pending quote card is 'awaiting confirm', never user_stop; only the user's Cancel is a stop.

Interactive: the card waits indefinitely (no timeout) and the run is checkpointed awaiting_confirm.
Unattended / no live client: not approved -> zero paid calls, turn ends normally as
awaiting_confirm:not_approved, never hangs. Mocks only, $0.
"""
from __future__ import annotations

import asyncio

from ComfyArt.api import bot_turns
from ComfyArt.api.mcp_tools import bot_tools
from ComfyArt.bot.providers import BotEvent, TurnHandle, TurnRequest
from ComfyArt.tests.test_plan_quote_235 import _provider, _tc
from ComfyArt.tests.test_single_gen_confirm_418 import _one


def _resp():
    return [
        {"choices": [{"message": {"content": "", "tool_calls": [_tc(1, "generate_image", {"prompt": "a"})]}}]},
        {"choices": [{"message": {"content": "done", "tool_calls": []}}]},
    ]


async def _go(monkeypatch, *, run_mode=None, chat_id="c418"):
    provider = _provider()
    mcp, events, checkpoints = [], [], []
    responses = _resp()

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if url.endswith("/chat/completions"):
            return responses.pop(0)
        return {"result": {"tools": [{"name": "generate_image"}, {"name": "update_plan"}]}}

    async def fake_call(session, endpoint, name, arguments):
        mcp.append(name)
        return f"ok {name}", []

    async def fake_quote(steps, lang_):
        return _one()

    from ComfyArt.bot import agent_loop
    orig_cp = agent_loop.RunContext.checkpoint

    def spy_cp(self, messages=None, *, status="running", detail="", **kw):
        checkpoints.append(status)
        return orig_cp(self, messages, status=status, detail=detail, **kw)

    monkeypatch.setattr(agent_loop.RunContext, "checkpoint", spy_cp)
    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
    monkeypatch.setattr(provider, "_quote_steps", fake_quote)

    async def emit(ev: BotEvent):
        events.append(ev)

    kw = {"run_mode": run_mode} if run_mode else {}
    result = await asyncio.wait_for(provider.send(
        TurnRequest(chat_id=chat_id, user_text="做一张", lang="zh", mcp_endpoint="http://x/mcp", model="m", **kw),
        emit, TurnHandle()), timeout=20)
    return result, events, mcp, checkpoints


def _stop(result):
    return ((result.run or {}).get("stop") or {})


async def test_no_client_is_not_approved_not_user_stop(monkeypatch):
    result, events, mcp, _ = await _go(monkeypatch)  # no ACTIVE_TURNS entry = nobody to ask
    assert mcp == []
    assert not result.aborted and result.error == ""
    stop = _stop(result)
    assert stop.get("reason") == "awaiting_confirm" and stop.get("sub") == "not_approved"
    assert any("没有人确认" in (e.text or "") for e in events if e.t == "delta")


async def test_unattended_mode_never_waits(monkeypatch):
    called = []

    async def never(*a, **k):
        called.append(1)
        await asyncio.sleep(3600)

    monkeypatch.setattr(bot_tools, "_await_ask", never)
    st = bot_turns._TurnState(TurnHandle(), "c418u", "m1")
    monkeypatch.setitem(bot_turns.ACTIVE_TURNS, "c418u", st)
    result, _e, mcp, _ = await _go(monkeypatch, run_mode="unattended", chat_id="c418u")
    assert called == [] and mcp == [] and not result.aborted
    assert _stop(result).get("reason") == "awaiting_confirm"


async def _interactive(monkeypatch, answer):
    seen = {}

    async def fake_ask(chat_id, state, spec, **kw):
        seen.update(kw, awaiting=state.awaiting)
        return answer

    monkeypatch.setattr(bot_tools, "_await_ask", fake_ask)
    st = bot_turns._TurnState(TurnHandle(), "c418i", "m1")
    monkeypatch.setitem(bot_turns.ACTIVE_TURNS, "c418i", st)
    out = await _go(monkeypatch, chat_id="c418i")
    return out, seen, st


async def test_interactive_waits_forever_and_checkpoints_awaiting(monkeypatch):
    (result, _e, mcp, cps), seen, st = await _interactive(
        monkeypatch, {"status": "answered", "selected": ["start"]})
    assert seen.get("wait_forever") is True and seen.get("timeout") is None
    assert seen["awaiting"] == "confirm" and st.awaiting == ""
    assert "awaiting_confirm" in cps
    assert mcp == ["generate_image"] and result.error == ""


async def test_only_user_cancel_is_user_stop(monkeypatch):
    (result, _e, mcp, _), _s, _st = await _interactive(
        monkeypatch, {"status": "answered", "selected": ["cancel"]})
    assert mcp == []
    stop = _stop(result)
    assert stop.get("reason") == "user_stop" and stop.get("sub") == "quote_declined"


def test_await_ask_wait_forever_has_no_timeout():
    import inspect
    src = inspect.getsource(bot_tools._await_ask)
    assert "wait_forever" in src
