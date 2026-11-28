"""A quote or confirm that fails must not call generate_image.

Both loops run LocalLlmProvider.send. The tool counter is the mocked MCP
the provider actually invokes. Prices stay local. No WaveSpeed call.
The confirm stub is only the fixture that plays a person; production
_confirm_plan is what runs for the unattended case.
"""
from __future__ import annotations

import json

import pytest

from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle
from ComfyArt.bot.run_budget import resolve_policy
from test_agent_budget_391 import Rig, calls, reply

SKILL = "brand-identity-director"
# Any ratios from the skill row's table; the plan is the agent's, not a fixed slot list.
FINAL_RATIOS = ("3:4", "3:4", "1:1", "16:9")


class _Asking:
    ask = True
    total = 0.16
    units = 4
    cancel_text = "已取消"

    def ask_spec(self):
        return {"questions": [{"id": "confirm", "options": [{"id": "start", "label": "开始"}]}]}


def _script_for(stage):
    def script(messages, n):
        if n == 0 and stage == "first":
            return calls(("generate_image", {"prompt": "board", "skill": SKILL, "ratio": "16:9"}))
        if n == 0:
            return calls(*((
                "generate_image",
                {"prompt": f"piece {i}", "skill": SKILL, "ratio": ratio},
            ) for i, ratio in enumerate(FINAL_RATIOS)))
        return reply("不再生成")
    return script


def _mcp(name, args, i):
    if name == "generate_image":
        return json.dumps({"ids": [f"h-{i}"]})
    return json.dumps({})


async def _run(monkeypatch, *, budget: bool, price: str, confirm: str, stage: str = "final"):
    BOT_CHAT_ID.set("c")
    rig = Rig(monkeypatch, _script_for(stage), mcp=_mcp)
    if not budget:
        pol = resolve_policy(env={"COMFYART_AGENT_BUDGET_LOOP": "0"})
        monkeypatch.setattr(rig.p, "_run_policy", lambda: pol)

    if price == "local":
        async def local_price(model, inputs):
            return (0.04, "estimate", "test")

        monkeypatch.setattr(rig.p, "_price_one", local_price)
    elif price == "production":
        # Rig pins an offline plan price so ordinary tests never call WaveSpeed.
        # These cases put the production pricer back. With no key it does not
        # call the price API: a published estimate or an unpriced result, which
        # still has to be confirmed before a submit.
        monkeypatch.setattr(rig.p, "_price_one", LocalLlmProvider._price_one.__get__(rig.p, LocalLlmProvider))
    elif price == "ask":
        async def asking(steps, lang):
            return _Asking()

        monkeypatch.setattr(rig.p, "_quote_steps", asking)

    if confirm == "start":
        async def yes(spec, turn, handle, **_kw):
            return "start"

        monkeypatch.setattr(rig.p, "_confirm_plan", yes)
    elif confirm == "decline":
        async def no(spec, turn, handle, **_kw):
            return "cancel"

        monkeypatch.setattr(rig.p, "_confirm_plan", no)
    elif confirm == "timeout":
        async def timed_out(spec, turn, handle, **_kw):
            raise TimeoutError("confirm timed out")

        monkeypatch.setattr(rig.p, "_confirm_plan", timed_out)
    # confirm == "production" leaves LocalLlmProvider._confirm_plan in place.

    res, events = await rig.send("做品牌", goal="", handle=TurnHandle())
    generated = [name for name, _args in rig.mcp if name == "generate_image"]
    return generated, events, res


@pytest.mark.parametrize("stage", ["first", "final"])
@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_missing_key_still_asks_and_does_not_generate(monkeypatch, budget, stage):
    """No WaveSpeed key. Quote construction must not raise and must not submit."""
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    monkeypatch.setattr("ComfyArt.api.wavespeed._saved_key", lambda: "")
    from ComfyArt.api import wavespeed
    wavespeed._quotes.clear()
    generated, events, _res = await _run(
        monkeypatch, budget=budget, price="production", confirm="production", stage=stage)
    assert generated == []
    text = "\n".join(e.text for e in events if e.t == "delta" and e.text)
    assert "WaveSpeed needs an API key" not in text
    assert "没有人确认" in text or "未开始" in text


@pytest.mark.parametrize("stage", ["first", "final"])
@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_quote_build_exception_does_not_generate(monkeypatch, budget, stage):
    async def boom(*_a, **_k):
        raise RuntimeError("quote build failed")

    monkeypatch.setattr("ComfyArt.bot.plan_quote.build_quote", boom)
    generated, events, res = await _run(
        monkeypatch, budget=budget, price="production", confirm="production", stage=stage)
    assert generated == []
    # The chat shows the product sentence. The exception stays on the turn error.
    text = "\n".join(e.text for e in events if e.t == "delta" and e.text)
    assert "没有开始" in text or "Nothing started" in text
    assert "quote build failed" in (res.error or "")
    assert res.error


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_confirm_timeout_does_not_generate(monkeypatch, budget):
    generated, events, res = await _run(monkeypatch, budget=budget, price="ask", confirm="timeout")
    assert generated == []
    text = "\n".join(e.text for e in events if e.t == "delta" and e.text)
    assert "没有开始" in text or "Nothing started" in text
    assert "TimeoutError" in (res.error or "") or "confirm timed out" in (res.error or "")


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_confirm_decline_does_not_generate(monkeypatch, budget):
    generated, _events, res = await _run(monkeypatch, budget=budget, price="ask", confirm="decline")
    assert generated == []
    assert res.aborted or (res.run and res.run.get("stop", {}).get("reason") == "user_stop") or not generated


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_unattended_production_confirm_does_not_generate(monkeypatch, budget):
    generated, events, _res = await _run(monkeypatch, budget=budget, price="ask", confirm="production")
    assert generated == []
    text = "\n".join(e.text for e in events if e.t == "delta" and e.text)
    assert "没有人确认" in text or "未开始" in text


@pytest.mark.parametrize("stage,count", [("first", 1), ("final", 4)])
@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_confirmed_start_still_calls_generate(monkeypatch, budget, stage, count):
    generated, _events, _res = await _run(
        monkeypatch, budget=budget, price="local", confirm="start", stage=stage)
    assert generated == ["generate_image"] * count
