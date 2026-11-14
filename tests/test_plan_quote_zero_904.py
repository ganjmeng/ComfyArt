"""#904: the plan-quote confirm decision.

A **known 0-credit** plan must not raise a confirm card: the agent continues.
An **unknown price** is not 0 credits and still asks (source=unpriced). A mixed
plan judges only its priced part, and a blocked/refused step makes no paid call,
so it never forces a card either.

Mocks only, $0: every price is injected; no WaveSpeed or LLM request.
"""
from __future__ import annotations

from ComfyArt.bot.plan_quote import build_quote
from ComfyArt.tests.test_plan_quote_235 import POSTER, _run, _step, _tc

FREE = "acme/free"          # a model the price table prices at exactly $0.00
MYSTERY = "acme/mystery"    # no price anywhere: source=unpriced

# #956: an SVG edit is refused before pricing; the quote line names the reason and
# authorizes no run (units 0). It must not become a 0-credit confirm card.
SVG_EDIT = {"tool": "generate_image", "text": "矢量标志",
            "arguments": {"prompt": "svg", "refs": ["shape:1"], "output_format": "svg"}}


async def _quote(steps, *, threshold=0.5, prices=None, models=None, lang="zh", router=None):
    prices = prices or {}

    async def pricer(model, inputs):
        return prices.get(model)

    async def models_for(feature):
        return list((models or {}).get(feature, []))

    return await build_quote(steps, lang, threshold=threshold, pricer=pricer,
                             models_for=models_for, router=router)


# --- a known 0-credit plan continues without a card --------------------------

async def test_priced_zero_plan_has_no_card():
    quote = await _quote([_step("a", "generate_image", FREE, prompt="a"),
                          _step("b", "generate_image", FREE, prompt="b")],
                         prices={FREE: 0.0})
    assert quote is not None and quote.total == 0.0 and quote.ask is False
    assert all(ln.amount == 0.0 and not ln.unpriced for ln in quote.lines)


async def test_priced_zero_single_call_is_not_a_plan_quote():
    quote = await _quote([_step("a", "generate_image", FREE, prompt="a")], prices={FREE: 0.0})
    assert quote is None  # no card, the call runs as before


async def test_priced_zero_plan_skips_even_at_a_zero_confirm_line():
    """threshold 0 = "always confirm a real spend"; a 0 spend has nothing to confirm."""
    quote = await _quote([_step("a", "generate_image", FREE, prompt="a"),
                          _step("b", "generate_image", FREE, prompt="b")],
                         threshold=0, prices={FREE: 0.0})
    assert quote is not None and quote.total == 0.0 and quote.ask is False


# --- a real spend keeps the confirm line exactly as before -------------------

async def test_priced_plan_still_asks_at_the_confirm_line():
    steps = [_step("a", "generate_image", POSTER, prompt="a"),
             _step("b", "generate_image", POSTER, prompt="b")]
    at = await _quote(steps, prices={POSTER: 0.25})       # exactly 50 credits
    under = await _quote(steps, prices={POSTER: 0.24})    # 48 credits
    over = await _quote(steps, prices={POSTER: 0.30})     # 60 credits
    assert at is not None and at.total == 0.50 and at.ask is True
    assert under is not None and under.total == 0.48 and under.ask is False
    assert over is not None and over.total == 0.60 and over.ask is True


async def test_a_zero_confirm_line_still_asks_for_a_real_spend():
    quote = await _quote([_step("a", "generate_image", POSTER, prompt="a")],
                         threshold=0, prices={POSTER: 0.04})
    assert quote is not None and quote.ask is True


# --- an unknown price is not 0 credits: it always asks -----------------------

async def test_unpriced_paid_step_asks_even_when_the_total_is_zero():
    quote = await _quote([_step("unknown", "generate_image", MYSTERY, prompt="a"),
                          _step("free", "generate_image", FREE, prompt="b")],
                         prices={FREE: 0.0})
    assert quote is not None and quote.total == 0.0
    assert quote.lines[0].unpriced and quote.lines[0].units == 1
    assert quote.ask is True  # 0 credits != "we could not tell the price"


async def test_single_unpriced_call_keeps_its_one_step_card():
    quote = await _quote([_step("unknown", "generate_image", MYSTERY, prompt="a")])
    assert quote is not None and quote.ask is True
    assert "这次生成" in quote.prompt  # the #904 card shape: one generation, still asking


# --- mixed plans judge only the priced part ---------------------------------

async def test_mixed_plan_judges_only_the_priced_part():
    free = _step("free", "generate_image", FREE, prompt="z")
    paid = _step("paid", "generate_image", POSTER, prompt="p")
    under = await _quote([free, paid], prices={FREE: 0.0, POSTER: 0.40})
    at = await _quote([free, paid], prices={FREE: 0.0, POSTER: 0.50})
    assert under is not None and under.total == 0.40 and under.ask is False
    assert at is not None and at.total == 0.50 and at.ask is True


async def test_mixed_plan_with_an_unknown_step_still_asks():
    quote = await _quote([_step("unknown", "generate_image", MYSTERY, prompt="a"),
                          _step("paid", "generate_image", POSTER, prompt="b")],
                         prices={POSTER: 0.40})
    assert quote is not None and quote.total == 0.40 and quote.ask is True


# --- a step that makes no paid call never forces a card ----------------------

async def test_blocked_steps_make_no_paid_call_and_do_not_force_a_card():
    quote = await _quote([SVG_EDIT, {**SVG_EDIT, "text": "矢量标志 2"}])
    assert quote is not None and quote.total == 0.0 and quote.ask is False
    assert all(ln.units == 0 and ln.unpriced for ln in quote.lines)


async def test_blocked_step_does_not_force_a_card_next_to_a_cheap_paid_step():
    quote = await _quote([SVG_EDIT, _step("paid", "generate_image", POSTER, prompt="p")],
                         prices={POSTER: 0.40})
    assert quote is not None and quote.total == 0.40 and quote.ask is False
    assert [ln.units for ln in quote.lines] == [0, 1]


async def test_single_blocked_step_keeps_its_line_but_never_asks():
    """#956 keeps the refusal line; #904 makes sure it raises no 0-credit card."""
    quote = await _quote([SVG_EDIT])
    assert quote is not None and len(quote.lines) == 1
    assert quote.lines[0].unpriced and quote.lines[0].units == 0
    assert quote.ask is False


# --- the agent actually continues; an unknown price never does --------------

async def test_zero_credit_plan_runs_without_a_confirm_card(monkeypatch):
    quote = await _quote([_step("a", "generate_image", FREE, prompt="a"),
                          _step("b", "generate_image", FREE, prompt="b")],
                         prices={FREE: 0.0})
    assert quote is not None and quote.ask is False
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [
            _tc(1, "generate_image", {"prompt": "a", "model": FREE}),
            _tc(2, "generate_image", {"prompt": "b", "model": FREE}),
        ]}}]},
        {"choices": [{"message": {"content": "done", "tool_calls": []}}]},
    ]
    result, events, mcp, _quoted, confirms = await _run(monkeypatch, responses, quote=quote)
    assert confirms == []
    assert [n for n, _ in mcp] == ["generate_image", "generate_image"]
    assert result.error == "" and events[-1].text == "done"


async def test_unpriced_plan_never_auto_continues(monkeypatch):
    quote = await _quote([_step("unknown", "generate_image", MYSTERY, prompt="a")])
    assert quote is not None and quote.ask is True
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [
            _tc(1, "generate_image", {"prompt": "a", "model": MYSTERY}),
        ]}}]},
        {"choices": [{"message": {"content": "should not run", "tool_calls": []}}]},
    ]
    result, events, mcp, _quoted, confirms = await _run(monkeypatch, responses, quote=quote, confirm="cancel")
    assert len(confirms) == 1 and confirms[0]["kind"] == "plan_quote"
    assert mcp == [] and result.error == ""
    assert any("已取消" in (e.text or "") for e in events)
