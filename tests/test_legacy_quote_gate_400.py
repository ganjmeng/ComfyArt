"""#400: legacy (non-agent-loop) path must hit the same paid quote gate as agent-loop.

Entries that still reach the legacy path (user-triggerable):
  - settings `agent-budget-loop: false` (AgentLlmProvider user_policy_layer; no dedicated UI toggle,
    but the settings API / settings.json honor it)
  - env `COMFYART_AGENT_BUDGET_LOOP=0` (dev / ops / tests)

Approach: keep the fixed-step loop when the flag is off, but attach a RunContext (store=None)
so `_emit_mcp` / paid fallbacks call `agent_loop.paid_gate`. Decline / unattended skip => 0 paid
MCP calls and 0 charge. Removing the `loop["run"] = run_ctx` wiring (or the paid_gate block in
`_emit_mcp`) makes these tests red.
"""
from __future__ import annotations

import json

import pytest

from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import BotEvent, TurnHandle, TurnRequest
from ComfyArt.bot.run_budget import resolve_policy


def _tc(i, name, args):
    return {"id": f"t{i}", "function": {"name": name, "arguments": json.dumps(args)}}


def calls(*items):
    return {"choices": [{"message": {"content": "", "tool_calls": [
        _tc(i, n, a) for i, (n, a) in enumerate(items)]}}]}


def reply(text):
    return {"choices": [{"message": {"content": text, "tool_calls": []}}]}


GEN = ("generate_image", {"prompt": "cat", "model": "m"})


class LegacyRig:
    """LocalLlmProvider with budget_loop forced off (the #400 legacy path)."""

    def __init__(self, monkeypatch, script, *, credits=1.0, prices=None, confirm=False, mode="interactive"):
        self.p = LocalLlmProvider(base_url=lambda: "http://x/v1")
        self.script = script
        self.n = 0
        self.mcp: list = []
        self.confirms: list = []
        self.mode = mode
        pol = resolve_policy(user={"credits_usd": credits, "agent.budget_loop": False}, env={})
        assert not pol.enabled
        monkeypatch.setattr(self.p, "_run_policy", lambda: pol)
        monkeypatch.setattr(self.p, "_run_store", lambda: None)

        async def ctx_window(session, model):
            return 32_000
        monkeypatch.setattr(self.p, "_context_window", ctx_window)

        async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
            if url.endswith("/chat/completions"):
                r = self.script[self.n]
                self.n += 1
                return r
            return {"result": {"tools": [{"name": "generate_image"}, {"name": "get_canvas"}]}}
        monkeypatch.setattr(self.p, "_request_json", fake_request)

        async def fake_call(session, endpoint, name, arguments):
            self.mcp.append((name, dict(arguments)))
            return json.dumps({"id": f"shape:{len(self.mcp)}"}), []
        monkeypatch.setattr(self.p, "_mcp_call_tool", fake_call)

        async def price(name, args):
            return (prices or {}).get(name, 1.5)
        monkeypatch.setattr(self.p, "_price_call", price)

        async def ask(turn, handle, lang, name, p, left):
            self.confirms.append((name, p, left))
            return confirm
        monkeypatch.setattr(self.p, "_confirm_over_quote", ask)

    async def send(self, text="画一张猫"):
        events: list[BotEvent] = []

        async def emit(ev):
            events.append(ev)

        res = await self.p.send(
            TurnRequest(chat_id="c", user_text=text, lang="zh", mcp_endpoint="http://x/mcp",
                        model="m", run_mode=self.mode),
            emit, TurnHandle())
        return res, events

    def paid_mcp(self):
        return [c for c in self.mcp if c[0] == "generate_image"]


@pytest.mark.asyncio
async def test_legacy_paid_over_quote_decline_zero_calls_zero_charge(monkeypatch):
    """Legacy path: paid tool over remaining credits must quote first; decline = 0 MCP, 0 charge.
    Mutation: drop `loop["run"] = run_ctx` (or the paid_gate block in `_emit_mcp`) → this goes red."""
    r = LegacyRig(monkeypatch, [calls(GEN), reply("done")], credits=1.0,
                  prices={"generate_image": 1.5}, confirm=False)
    res, _ = await r.send()
    assert len(r.confirms) == 1, "must ask the over-quote card before any paid call"
    assert r.paid_mcp() == [], r.mcp
    assert res.aborted is True
    # in-memory budget on the legacy RunContext: nothing charged
    # (res.run is None on legacy — no store — so assert via confirms + zero MCP)


@pytest.mark.asyncio
async def test_legacy_paid_over_quote_confirm_runs_once(monkeypatch):
    r = LegacyRig(monkeypatch, [calls(GEN), reply("done")], credits=1.0,
                  prices={"generate_image": 1.5}, confirm=True)
    res, _ = await r.send()
    assert len(r.confirms) == 1
    assert len(r.paid_mcp()) == 1
    assert not res.aborted and not res.error


@pytest.mark.asyncio
async def test_legacy_unattended_over_quote_skips_no_charge(monkeypatch):
    """Unattended legacy: would-ask quote is skipped; 0 paid calls, 0 charge (same as agent-loop)."""
    r = LegacyRig(monkeypatch, [calls(GEN), reply("done")], credits=1.0,
                  prices={"generate_image": 1.5}, confirm=True, mode="unattended")
    res, _ = await r.send()
    assert r.confirms == [], "unattended must not wait on a confirm card"
    assert r.paid_mcp() == []
    assert res.error  # budget:unattended_skipped stop text


@pytest.mark.asyncio
async def test_legacy_under_budget_still_gates_then_calls(monkeypatch):
    """Under the run credit ceiling paid_gate allows the call (same as agent-loop); it still went
    through the gate (pending marker) — a missing run context would also call, so we only assert
    the call happens and no confirm was shown."""
    r = LegacyRig(monkeypatch, [calls(GEN), reply("done")], credits=5.0,
                  prices={"generate_image": 0.4}, confirm=False)
    res, _ = await r.send()
    assert r.confirms == []
    assert len(r.paid_mcp()) == 1
    assert not res.aborted


@pytest.mark.asyncio
async def test_flag_off_still_creates_run_context_for_gate(monkeypatch):
    """Sanity: with budget_loop off, send still builds a RunContext used as loop['run']."""
    seen = {}

    real = LocalLlmProvider._paid_run_context

    def wrap(self, turn, *, window, lang, policy):
        ctx = real(self, turn, window=window, lang=lang, policy=policy)
        seen["ctx"] = ctx
        return ctx

    monkeypatch.setattr(LocalLlmProvider, "_paid_run_context", wrap)
    r = LegacyRig(monkeypatch, [reply("hi")], credits=1.0)
    await r.send("你好")
    assert "ctx" in seen and seen["ctx"].store is None
    assert seen["ctx"].mode == "interactive"
