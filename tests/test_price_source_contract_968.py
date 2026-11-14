"""#968: the three-state price contract survives a fallback on a **slow** price API.

Paid acceptance (#959, sha 65b5299c) saw the first `POST /api/v3/model/price` take 10.61 s against the
old 10 s timeout. `_quote` fell back to the undiscounted published table ($0.115), but
`LocalLlmProvider._price_one` returned only the amount, so `build_quote` rendered it as an exact price:
card $0.466 / 47 credits vs charge $0.4545 / 46 credits.

These tests mock a price API that hangs (a real timeout, not a 4xx), then assert:
1. the card says 「约」 and 「标价上限估算」, and the source reaches the ask card;
2. the free quote retries once (15 s / 1 retry) and never submits during the quote;
3. the submitted job is still quoted/charged at the API's discounted price;
4. per-line and total credits agree;
5. token-billed providers (Replicate `quote: "unknown"`, DeepSeek) never become an exact price.

Mocks only: local WaveSpeed stand-in, no key, no network, $0.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from ComfyArt.api import wavespeed
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.plan_quote import (
    SOURCE_ESTIMATE, SOURCE_QUOTE, SOURCE_UNPRICED, build_quote,
)
from ComfyArt.bot.run_budget import ui_credits

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
CATALOG = json.loads((FIX / "wavespeed_catalog_subset.json").read_text())

FLARE_T2I = "openai/gpt-image-2.6-flare/text-to-image"
LIST_USD = 0.05       # published medium/1k cell (undiscounted) — the fallback number
DISCOUNT_USD = 0.045  # priced once the price API answers: the amount actually charged


async def _no_models(feature):
    return []


def _provider() -> LocalLlmProvider:
    return LocalLlmProvider.__new__(LocalLlmProvider)


def _step(model: str = FLARE_T2I, text: str = "棚拍", prompt: str = "p") -> dict:
    return {"text": text, "tool": "generate_image", "model": model, "arguments": {"prompt": prompt}}


@pytest.fixture
async def slow_price(monkeypatch, fresh_user_dir):
    """Local WaveSpeed: the price API hangs until `state["hang"]` is cleared, then answers a discount."""
    state = {"hang": True, "hang_s": 0.3, "price_posts": 0, "submits": [], "status": 200}
    wavespeed._quotes.clear()
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    wavespeed._jobs.clear()
    wavespeed._submits.clear()
    app = web.Application()

    async def models(_request):
        return web.json_response({"code": 200, "data": list(CATALOG.values())})

    async def price(request):
        state["price_posts"] += 1
        body = await request.json()
        if state["hang"]:
            await asyncio.sleep(state["hang_s"])  # slow cold start: the client times out
        if state["status"] >= 400:
            return web.json_response({"code": 4005, "message": "model not found"}, status=state["status"])
        return web.json_response({"code": 200, "data": {
            "model_id": body.get("model_id"), "unit_price": LIST_USD, "price": LIST_USD,
            "discounted_price": DISCOUNT_USD, "discount_rate": 0.9, "currency": "USD"}})

    async def submit(request):
        state["submits"].append((request.match_info["model"], await request.json()))
        return web.json_response({"code": 200, "data": {"id": f"task{len(state['submits'])}", "status": "created"}})

    async def result(request):
        return web.json_response({"code": 200, "data": {
            "id": request.match_info["id"], "status": "completed", "outputs": [], "error": ""}})

    async def balance(_request):
        return web.json_response({"code": 200, "data": {"balance": 10}})

    app.router.add_get("/api/v3/models", models)
    app.router.add_get("/api/v3/balance", balance)
    app.router.add_post("/api/v3/model/price", price)
    app.router.add_get("/api/v3/predictions/{id}/result", result)
    app.router.add_post("/api/v3/{model:.+}", submit)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-not-a-real-key")
    monkeypatch.setattr(wavespeed, "QUOTE_TIMEOUT_S", 0.05)
    monkeypatch.setattr(wavespeed, "QUOTE_RETRY_BACKOFF_S", 0.0)
    monkeypatch.setattr(wavespeed, "POLL_MIN", 0.0)
    yield state
    await server.close()


async def _quote_card(pricer) -> object:
    return await build_quote([_step()], "zh", threshold=0.0, pricer=pricer, models_for=_no_models)


# ---- the bug: a slow price API must never render as an exact price ----

async def test_price_timeout_card_is_estimate_labelled_list_price_and_retries_once(slow_price):
    provider = _provider()
    price, source, reason = await provider._price_one(FLARE_T2I, {})
    # The paid fallback row: the undiscounted published table, explicitly an estimate.
    assert (price, source, reason) == (LIST_USD, SOURCE_ESTIMATE, "list_price")
    # The free quote timed out once and was retried exactly once; nothing was submitted.
    assert slow_price["price_posts"] == 2
    assert slow_price["submits"] == []

    card = await _quote_card(provider._price_one)
    assert card is not None and card.ask
    line = card.lines[0]
    # 1/2. source survives _price_one -> build_quote; the amount carries 「约」 and names the list price.
    assert line.source == SOURCE_ESTIMATE
    assert line.reason == "list_price" and line.approx and not line.unpriced
    assert line.price == "约 5 积分"
    assert "标价上限估算" in line.text
    assert card.total_text == "约 5 积分"
    spec_line = card.ask_spec()["lines"][0]
    assert spec_line["source"] == "estimate" and spec_line["price"] == "约 5 积分"

    # 3. once the price API is warm the same quote is the discounted price, and submitting the
    # confirmed job does not repeat the free-quote retries or the submit (one task, one charge).
    slow_price["hang"] = False
    assert await wavespeed.quote(FLARE_T2I, {}) == (DISCOUNT_USD, SOURCE_QUOTE)
    task = await wavespeed.submit({"feature": "text_to_image", "model": FLARE_T2I, "prompt": "p", "confirmed": True})
    assert len(slow_price["submits"]) == 1
    # _quoted() records the submit-time price: the discounted amount, not the list-price estimate.
    assert wavespeed._jobs[task]["quoted"] == DISCOUNT_USD
    assert wavespeed._jobs[task]["quoted"] < LIST_USD


async def test_a_healthy_price_api_stays_an_exact_quote(slow_price):
    slow_price["hang"] = False
    card = await _quote_card(_provider()._price_one)
    assert card is not None
    line = card.lines[0]
    assert line.source == SOURCE_QUOTE and not line.approx and not line.unpriced
    assert line.price == "5 积分"  # ceil(0.045 x 100) = 5
    assert "标价上限" not in line.text and "约" not in card.total_text


async def test_a_4xx_price_error_is_not_retried_and_the_fallback_is_still_an_estimate(slow_price):
    slow_price["hang"] = False
    slow_price["status"] = 400
    price, source, reason = await _provider()._price_one(FLARE_T2I, {})
    assert (price, source, reason) == (LIST_USD, SOURCE_ESTIMATE, "list_price")
    assert slow_price["price_posts"] == 1  # a 4xx will fail the same way: no retry


async def test_no_table_and_no_live_price_is_unpriced_never_a_number(slow_price):
    slow_price["hang"] = False
    slow_price["status"] = 400
    price, source, reason = await _provider()._price_one("acme/not-in-any-table", {})
    assert (price, source) == (None, SOURCE_UNPRICED) and reason == ""
    card = await build_quote([_step("acme/not-in-any-table")], "zh", threshold=100.0,
                             pricer=_provider()._price_one, models_for=_no_models)
    assert card is not None and card.ask  # unknown price always asks, even under the line
    assert card.lines[0].unpriced and card.lines[0].source == SOURCE_UNPRICED
    assert card.lines[0].price == "约" and "0" not in card.lines[0].price


# ---- rounding: the rows and the total must agree ----

async def test_per_line_and_total_credits_share_one_rounding():
    """4 x $0.115: each row ceilings to 12 credits, so the total is 48 — not ceil(0.46) = 46."""
    async def pricer(_model, _inputs):
        return 0.115

    steps = [_step("acme/poster", f"图 {i}", f"p{i}") for i in range(4)]
    card = await build_quote(steps, "zh", threshold=0.0, pricer=pricer, models_for=_no_models)
    assert card is not None
    assert [ln.price for ln in card.lines] == ["12 积分"] * 4
    assert [ln.credits for ln in card.lines] == [12, 12, 12, 12]
    assert card.total == pytest.approx(0.46)
    assert card.total_credits == sum(ln.credits for ln in card.lines) == 48
    assert card.total_text == "48 积分"
    assert "预计约 48 积分" in card.prompt
    # the old rendering rounded the USD sum instead: 46. The card may not show both numbers.
    assert ui_credits(card.total) == 46 != card.total_credits

    en = await build_quote(steps, "en", threshold=0.0, pricer=pricer, models_for=_no_models)
    assert en is not None and en.total_text == "48 credits"
    assert [ln.price for ln in en.lines] == ["12 credits"] * 4


async def test_a_mixed_estimate_and_exact_card_sums_the_rounded_rows():
    async def pricer(model, _inputs):
        return 0.115 if model == "acme/a" else (0.115, "estimate", "base_price")

    steps = [_step("acme/a", "A"), _step("acme/b", "B")]
    card = await build_quote(steps, "zh", threshold=0.0, pricer=pricer, models_for=_no_models)
    assert card is not None
    assert [ln.price for ln in card.lines] == ["12 积分", "约 12 积分"]
    assert card.total_credits == 24 and card.total_text == "约 24 积分"
    assert [ln.source for ln in card.lines] == [SOURCE_QUOTE, SOURCE_ESTIMATE]


# ---- token-billed providers never get an invented exact per-run price ----

async def test_an_unknown_source_is_never_exact():
    """Replicate's routing answer is `quote: "unknown"` and DeepSeek is billed in tokens, not USD.
    Anything outside quote/estimate/unpriced is downgraded: a number becomes 约, no number is unpriced."""
    async def unknown_with_number(_model, _inputs):
        return 0.02, "unknown"

    async def unknown_without_number(_model, _inputs):
        return None, "unknown"

    card = await build_quote([_step("acme/token")], "zh", threshold=0.0,
                             pricer=unknown_with_number, models_for=_no_models)
    assert card is not None
    assert card.lines[0].source == SOURCE_ESTIMATE and card.lines[0].approx
    assert card.lines[0].price == "约 2 积分"

    card = await build_quote([_step("acme/token")], "zh", threshold=100.0,
                             pricer=unknown_without_number, models_for=_no_models)
    assert card is not None and card.ask
    assert card.lines[0].unpriced and card.lines[0].source == SOURCE_UNPRICED
    assert card.lines[0].amount == 0.0 and card.lines[0].price == "约"


# ---- the mutation guard: `_price_one` must carry the source, not just the amount ----

async def test_mutation_dropped_source_goes_red(slow_price):
    """Roll `_price_one` back to `price, _source = await quote(...); return price` and this test
    fails at the tuple unpack (TypeError) plus the card's estimate assertions below."""
    result = await _provider()._price_one(FLARE_T2I, {})
    assert isinstance(result, tuple) and len(result) == 3, result
    price, source, reason = result
    assert (price, source, reason) == (LIST_USD, SOURCE_ESTIMATE, "list_price")
    card = await _quote_card(_provider()._price_one)
    assert card is not None and card.lines[0].source == SOURCE_ESTIMATE
    assert card.lines[0].price.startswith("约 ") and "标价上限" in card.lines[0].text
