"""WaveSpeed price API contract: singular `input`, and only a real amount is a quote.

Mocked local HTTP only. No provider submit and no live price call.
A discounted price of 0 is a quote. An error or a missing amount is not turned into 0.
"""
from __future__ import annotations

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from ComfyArt.api import wavespeed

MODEL = "acme/price-contract"
_PROPS = {
    "prompt": {"type": "string"},
    "resolution": {"type": "string", "enum": ["1k", "2k"], "default": "1k"},
    "quality": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
    "images": {"type": "array", "maxItems": 4},
}


def _meta():
    return {
        "model_id": MODEL,
        "base_price": 0.2,
        "api_schema": {"api_schemas": [{"request_schema": {"properties": _PROPS}}]},
    }


def _ok(amount):
    return 200, {"code": 200, "message": "success", "data": {
        "model_id": MODEL, "price": 0.45, "discounted_price": amount, "currency": "USD"}}


@pytest.fixture
async def price_api(monkeypatch):
    wavespeed._quotes.clear()
    state = {"posts": [], "reply": _ok(0.1)}
    app = web.Application()

    async def price(request):
        body = await request.json()
        state["posts"].append(body)
        reply = state["reply"](body) if callable(state["reply"]) else state["reply"]
        status, payload = reply
        return web.json_response(payload, status=status)

    app.router.add_post("/api/v3/model/price", price)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-not-a-real-key")

    async def catalog(refresh=False):
        return {MODEL: _meta()}

    monkeypatch.setattr(wavespeed, "catalog", catalog)
    yield state
    wavespeed._quotes.clear()
    await server.close()


def _job(**extra):
    job = {"prompt": "cup", "resolution": "2k", "quality": "high", "images": ["a", "b"]}
    job.update(extra)
    return job


async def test_request_uses_singular_input_with_billable_fields(price_api):
    price, source, reason = await wavespeed.quote_detail(MODEL, _job())
    assert (price, source) == (0.1, "quote")
    assert reason == "live"
    body = price_api["posts"][0]
    assert set(body) == {"model_id", "input"}
    assert "inputs" not in body
    assert body["input"]["resolution"] == "2k"
    assert body["input"]["quality"] == "high"
    assert body["input"]["images"] == ["ref-1", "ref-2"]


async def test_cache_does_not_reuse_another_parameter_set(price_api):
    def reply(body):
        amount = 0.0 if body["input"]["resolution"] == "1k" else 0.2
        return _ok(amount)

    price_api["reply"] = reply
    first, src1, _ = await wavespeed.quote_detail(MODEL, _job(resolution="1k"))
    second, src2, _ = await wavespeed.quote_detail(MODEL, _job(resolution="2k"))
    again, src3, why = await wavespeed.quote_detail(MODEL, _job(resolution="1k"))
    assert (first, src1) == (0.0, "quote")
    assert (second, src2) == (0.2, "quote")
    assert (again, src3, why) == (0.0, "quote", "cache")
    assert len(price_api["posts"]) == 2
    assert price_api["posts"][0]["input"]["resolution"] == "1k"
    assert price_api["posts"][1]["input"]["resolution"] == "2k"


async def test_genuine_discounted_zero_is_a_quote(price_api):
    price_api["reply"] = _ok(0)
    price, source, reason = await wavespeed.quote_detail(MODEL, _job())
    assert price == 0.0 and source == "quote" and reason == "live"
    cached, src2, why = await wavespeed.quote_detail(MODEL, _job())
    assert cached == 0.0 and src2 == "quote" and why == "cache"
    assert len(price_api["posts"]) == 1


@pytest.mark.parametrize("reply", [
    (200, {"code": 4005, "message": "Failed to retrieve model pricing.",
           "data": {"discounted_price": 0, "price": 0}}),
    (200, {"message": "success", "data": {"discounted_price": 0, "price": 0}}),
    (200, {"code": 200, "data": {"discounted_price": True, "price": 0}}),
    (200, {"code": 200, "data": {"discounted_price": "0", "price": 0}}),
    (200, {"code": 200, "data": {"discounted_price": float("nan"), "price": 0}}),
    (200, {"code": 200, "data": {"discounted_price": float("inf"), "price": 0}}),
    (200, {"code": 200, "data": {"discounted_price": -0.01, "price": 0}}),
    (200, {"code": 200, "data": {}}),
    (400, {"code": 4005, "message": "Failed to retrieve model pricing.",
           "data": {"discounted_price": 0}}),
])
async def test_missing_or_error_zero_is_not_a_quote(price_api, reply):
    price_api["reply"] = reply
    price, source, reason = await wavespeed.quote_detail(MODEL, _job())
    assert source != "quote"
    assert price is None
    assert source == "unpriced"
    assert reason != "list_price"
    # the rejected body must not be cached as a zero quote
    price_api["reply"] = _ok(0.3)
    nxt, src2, _ = await wavespeed.quote_detail(MODEL, _job())
    assert (nxt, src2) == (0.3, "quote")
    assert len(price_api["posts"]) == 2


def test_amount_parser_accepts_zero_and_rejects_non_amounts():
    assert wavespeed._quote_amount({"code": 200, "data": {"discounted_price": 0, "price": 0.45}}) == 0.0
    assert wavespeed._quote_amount({"code": 200, "data": {"price": 0}}) == 0.0
    for bad in (True, False, "0", None, float("nan"), float("inf"), -1, -0.0 if False else -0.01):
        assert wavespeed._quote_amount({"code": 200, "data": {"discounted_price": bad}}) is None
    assert wavespeed._quote_amount({"code": 4005, "data": {"discounted_price": 0}}) is None
    assert wavespeed._quote_amount({"data": {"discounted_price": 0}}) is None
    assert wavespeed._quote_amount({"code": 200, "data": {}}) is None
