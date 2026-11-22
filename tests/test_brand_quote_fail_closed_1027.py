"""A quote or confirm that fails must not call generate_image.

Both loops run LocalLlmProvider.send. The tool counter is the mocked MCP
the provider actually invokes. Prices stay local. No WaveSpeed call.
The confirm stub is only the fixture that plays a person; production
_confirm_plan is what runs for the unattended case.
"""
from __future__ import annotations

import json

import pytest

from ComfyArt.api import brand_identity as brand
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.providers import TurnHandle
from ComfyArt.bot.run_budget import resolve_policy
from test_agent_budget_391 import Rig, calls, reply
from test_brand_wrapup_1027 import _card1, _reach_finals

SLOTS = ("spec", "cup", "bag", "storefront")


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
            return calls(("generate_image", {
                "prompt": "board", "skill": brand.SKILL, "brand_slot": "moodboard"}))
        if n == 0:
            return calls(*((
                "generate_image",
                {"prompt": slot, "skill": brand.SKILL, "brand_slot": slot},
            ) for slot in SLOTS))
        return reply("不再生成")
    return script


def _at_stage(stage):
    if stage == "first":
        brand.record_card_answer(_card1(), {
            "bi_delivery": {"selected": ["A"]}, "bi_color": {"selected": ["A"]},
            "bi_mark": {"selected": ["A"]}, "bi_source": {"selected": ["A"]}})
    else:
        _reach_finals()


def _mcp(name, args, i):
    if name == "generate_image":
        return json.dumps({"ids": [f"h-{args.get('brand_slot')}"]})
    return json.dumps({})


async def _run(monkeypatch, *, budget: bool, price: str, confirm: str, stage: str = "final"):
    brand.reset_for_tests()
    BOT_CHAT_ID.set("c")
    _at_stage(stage)
    rig = Rig(monkeypatch, _script_for(stage), mcp=_mcp)
    if not budget:
        pol = resolve_policy(env={"COMFYART_AGENT_BUDGET_LOOP": "0"})
        monkeypatch.setattr(rig.p, "_run_policy", lambda: pol)

    if price == "local":
        async def local_price(model, inputs):
            return (0.04, "estimate", "test")

        monkeypatch.setattr(rig.p, "_price_one", local_price)
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
async def test_quote_build_exception_does_not_generate(monkeypatch, budget, stage):
    async def boom(*_a, **_k):
        raise RuntimeError("quote build failed")

    monkeypatch.setattr("ComfyArt.bot.plan_quote.build_quote", boom)
    generated, events, res = await _run(
        monkeypatch, budget=budget, price="production", confirm="production", stage=stage)
    assert generated == []
    text = "\n".join(e.text for e in events if e.t == "delta" and e.text)
    assert "quote build failed" in text
    assert res.error


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_confirm_timeout_does_not_generate(monkeypatch, budget):
    generated, events, _res = await _run(monkeypatch, budget=budget, price="ask", confirm="timeout")
    assert generated == []
    text = "\n".join(e.text for e in events if e.t == "delta" and e.text)
    assert "TimeoutError" in text or "confirm timed out" in text


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
