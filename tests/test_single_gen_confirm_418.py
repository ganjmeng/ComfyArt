"""#418: one generation at/over confirm_usd shows the #397 quote card and waits, whatever the step count.

Mocks only, $0: prices injected, LLM + MCP faked.
"""
from __future__ import annotations

import pytest

from ComfyArt.bot.plan_quote import CANCEL_TEXT, Line, Quote, build_quote, canon_key
from ComfyArt.tests.test_plan_quote_235 import POSTER, _quote, _run, _step, _tc


def _one(price=0.60, lang="zh"):
    line = Line("生成图像 · poster-xl", "60 积分", price, False, False,
                canon_key("generate_image", {"prompt": "a"}, POSTER))
    return Quote(lines=[line], total=price, n=1, ask=True, lang=lang, prompt="p",
                 total_label="总价", total_text="60 积分", keys=[line.key], cancel_text=CANCEL_TEXT[lang])


async def test_single_step_over_line_is_quoted_and_asks():
    q, _ = await _quote([_step("海报", "generate_image", POSTER, prompt="p")], prices={POSTER: 0.60})
    assert q is not None and q.n == 1 and q.ask is True
    assert "这次生成" in q.prompt and "步" not in q.prompt


async def test_single_step_exactly_at_line_asks():
    q, _ = await _quote([_step("海报", "generate_image", POSTER, prompt="p")], prices={POSTER: 0.50},
                        threshold=0.5)
    assert q is not None and q.ask is True


async def test_single_step_under_line_has_no_card():
    q, _ = await _quote([_step("海报", "generate_image", POSTER, prompt="p")], prices={POSTER: 0.04})
    assert q is None


async def test_single_step_en_prompt():
    q, _ = await _quote([_step("Poster", "generate_image", POSTER, prompt="p")], prices={POSTER: 0.60}, lang="en")
    assert q.prompt.startswith("This generation will cost about") and "steps" not in q.prompt


def _resp():
    return [
        {"choices": [{"message": {"content": "", "tool_calls": [_tc(1, "generate_image", {"prompt": "a"})]}}]},
        {"choices": [{"message": {"content": "done", "tool_calls": []}}]},
    ]


async def test_expensive_single_call_waits_for_ok_then_runs(monkeypatch):
    result, _e, mcp, quoted, confirms = await _run(monkeypatch, _resp(), quote=_one(), confirm="start")
    assert len(quoted) == 1 and len(quoted[0]) == 1
    assert len(confirms) == 1 and confirms[0]["kind"] == "plan_quote"
    assert mcp == [("generate_image", {"prompt": "a"})] and result.error == ""


async def test_expensive_single_call_cancel_charges_nothing(monkeypatch):
    _r, events, mcp, _q, confirms = await _run(monkeypatch, _resp(), quote=_one(), confirm="cancel")
    assert len(confirms) == 1 and mcp == []
    assert any(CANCEL_TEXT["zh"] in (e.text or "") for e in events)


async def test_single_ok_does_not_arm_plan_gate(monkeypatch):
    resp = [
        {"choices": [{"message": {"content": "", "tool_calls": [_tc(1, "generate_image", {"prompt": "a"})]}}]},
        {"choices": [{"message": {"content": "", "tool_calls": [_tc(2, "generate_image", {"prompt": "b"})]}}]},
        {"choices": [{"message": {"content": "done", "tool_calls": []}}]},
    ]
    _r, _e, mcp, quoted, confirms = await _run(monkeypatch, resp, quote=_one(), confirm="start")
    assert [a["prompt"] for _, a in mcp] == ["a", "b"] and len(confirms) == 2  # each pricey call asks once
