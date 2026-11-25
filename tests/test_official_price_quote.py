"""Offline product checks for the official price body and quote cache.

The price POST uses singular ``input``. Error codes, negatives, and non-finite
amounts stay out of the quote cache. Zero from a real price response stays a
quote. A missing or failed response is not rewritten to a cached zero, and
start does not run on that failure.

Local aiohttp only. No provider host, no image generation, no process server.
"""
from __future__ import annotations

import socket

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from ComfyArt.api import gif_image, wavespeed
from ComfyArt.bot.plan_quote import SOURCE_QUOTE, build_quote

QWEN = "alibaba/qwen-image-3.0/text-to-image"
FLARE = gif_image.FLARE_T2I


def _closed_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
async def price_api(monkeypatch):
    state = {
        "bodies": [],
        "submits": [],
        "reply": {"code": 200, "data": {"discounted_price": 0.25}},
    }
    wavespeed._quotes.clear()
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    wavespeed._jobs.clear()
    wavespeed._submits.clear()
    app = web.Application()

    async def models(_request):
        return web.json_response({"code": 200, "data": [{
            "model_id": QWEN,
            "api_schema": {"api_schemas": [{"request_schema": {
                "type": "object",
                "properties": {"prompt": {"type": "string"}},
                "required": ["prompt"],
            }}]},
        }]})

    async def price(request):
        body = await request.json()
        state["bodies"].append(body)
        return web.json_response(state["reply"])

    async def submit(request):
        state["submits"].append((request.match_info["model"], await request.json()))
        return web.json_response({"code": 200, "data": {"id": "should-not-run", "status": "created"}})

    app.router.add_get("/api/v3/models", models)
    app.router.add_post("/api/v3/model/price", price)
    app.router.add_post("/api/v3/{model:.+}", submit)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-not-a-real-key")
    monkeypatch.setattr(wavespeed, "QUOTE_RETRY_BACKOFF_S", 0.0)
    monkeypatch.setattr(wavespeed, "QUOTE_TIMEOUT_S", 1.0)
    yield state
    await server.close()
    wavespeed._quotes.clear()


async def _no_models(_feature):
    return []


def _step(model: str, prompt: str) -> dict:
    return {"text": prompt, "tool": "generate_image", "model": model, "arguments": {"prompt": prompt}}


async def test_price_body_is_singular_input_and_a_real_amount_is_cached(price_api):
    price, source, reason = await wavespeed.quote_detail(QWEN, {"prompt": "plus"})
    assert (price, source, reason) == (0.25, "quote", "live")
    body = price_api["bodies"][-1]
    assert set(body) == {"model_id", "input"}
    assert isinstance(body["input"], dict) and "inputs" not in body
    assert body["model_id"] == QWEN
    before = len(price_api["bodies"])
    again = await wavespeed.quote_detail(QWEN, {"prompt": "plus"})
    assert again[2] == "cache" and again[0] == pytest.approx(0.25)
    assert len(price_api["bodies"]) == before
    assert len(wavespeed._quotes) == 1


async def test_legitimate_zero_is_a_quote_and_is_cached(price_api):
    price_api["reply"] = {"code": 200, "data": {"discounted_price": 0}}
    price, source, reason = await wavespeed.quote_detail(QWEN, {"prompt": "zero"})
    assert (price, source, reason) == (0.0, "quote", "live")
    assert wavespeed._quotes
    cached = await wavespeed.quote_detail(QWEN, {"prompt": "zero"})
    assert cached[0] == 0.0 and cached[1] == "quote" and cached[2] == "cache"


@pytest.mark.parametrize("prompt,reply", [
    ("err", {"code": 4005, "message": "model not found", "data": {"discounted_price": 0}}),
    ("neg", {"code": 200, "data": {"discounted_price": -1}}),
    ("nan", {"code": 200, "data": {"discounted_price": float("nan")}}),
    ("inf", {"code": 200, "data": {"discounted_price": float("inf")}}),
    ("miss", {"code": 200}),
    ("bool", {"code": 200, "data": {"discounted_price": True}}),
    ("text", {"code": 200, "data": {"price": "0"}}),
])
async def test_bad_price_responses_are_not_cached_and_are_not_a_fake_zero(price_api, prompt, reply):
    price_api["reply"] = reply
    wavespeed._quotes.clear()
    before = len(wavespeed._quotes)
    result = await wavespeed.quote_detail(QWEN, {"prompt": prompt})
    assert result[1] != "quote"
    assert len(wavespeed._quotes) == before
    assert not (result[1] == "quote" and result[0] == 0)
    assert result != (0.0, "quote", "live")


async def test_error_amount_is_not_an_exact_quote_when_a_list_price_exists(price_api):
    """Code 4005 is unpriced even when a list price and a disguised amount are both available."""
    price_api["reply"] = {
        "code": 4005, "message": "model not found", "data": {"discounted_price": 999},
    }
    wavespeed._quotes.clear()
    price, source, reason = await wavespeed.quote_detail(FLARE, {"prompt": "disguised"})
    listed = gif_image.documented_usd(FLARE)
    assert listed is not None
    assert (price, source, reason) == (None, "unpriced", "price_error_4005")
    assert price != listed and price != 999
    assert wavespeed._quotes == {}


async def test_missing_key_does_not_call_the_price_api(price_api, monkeypatch):
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    monkeypatch.setattr(wavespeed, "_saved_key", lambda: "")
    before = len(price_api["bodies"])
    price, source, reason = await wavespeed.quote_detail(QWEN, {"prompt": "nokey"})
    assert (price, source) == (None, "unpriced") and reason == ""
    assert len(price_api["bodies"]) == before
    assert wavespeed._quotes == {}


async def test_transport_failure_is_not_cached_as_zero(price_api, monkeypatch):
    monkeypatch.setenv("WAVESPEED_BASE_URL", f"http://127.0.0.1:{_closed_port()}")
    wavespeed._quotes.clear()
    with pytest.raises(wavespeed.WaveSpeedError):
        await wavespeed.quote_detail(QWEN, {"prompt": "down"})
    assert wavespeed._quotes == {}


async def test_failed_quote_does_not_start(price_api, monkeypatch):
    """A business error that carries discounted_price 0 must not start a run.

    The confirm line is far above zero, so a cached zero quote would skip the
    ask and post the job. This failure stays unpriced and posts nothing.
    """
    price_api["reply"] = {
        "code": 4005, "message": "model not found", "data": {"discounted_price": 0},
    }
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 100.0)
    wavespeed._quotes.clear()
    card = await build_quote([_step(QWEN, "cup")], "en", threshold=100.0,
                             pricer=wavespeed.quote_detail, models_for=_no_models)
    assert card is not None and card.ask
    assert card.lines[0].source != SOURCE_QUOTE
    assert card.lines[0].unpriced
    with pytest.raises(wavespeed.WaveSpeedError) as err:
        await wavespeed.submit({"feature": "text_to_image", "model": QWEN, "prompt": "cup"})
    assert err.value.unpriced is True
    assert price_api["submits"] == []
    assert wavespeed._quotes == {}


async def test_a_nan_price_is_unpriced_not_a_list_price_estimate(price_api, monkeypatch):
    """A non-finite amount is not a timeout or a 5xx, so it is not an estimate."""
    price_api["reply"] = {
        "code": 200, "data": {"discounted_price": float("nan")},
    }
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0.0)
    wavespeed._quotes.clear()
    price, source, reason = await wavespeed.quote_detail(FLARE, {"prompt": "board"})
    assert (price, source, reason) == (None, "unpriced", "price_unavailable")
    card = await build_quote([_step(FLARE, "board")], "en", threshold=0.0,
                             pricer=wavespeed.quote_detail, models_for=_no_models)
    assert card is not None and card.ask
    assert card.lines[0].source == "unpriced"
    assert card.lines[0].price == "Unpriced"
    assert [o["id"] for o in card.ask_spec()["options"]] == ["reprice", "cancel"]
    assert wavespeed._quotes == {}


@pytest.mark.parametrize("code", [4005, 4006, 4007])
async def test_rejecting_price_codes_are_unpriced_not_an_estimate(price_api, code):
    price_api["reply"] = {"code": code, "message": "price failed"}
    wavespeed._quotes.clear()
    price, source, reason = await wavespeed.quote_detail(FLARE, {"prompt": f"reject {code}"})
    assert gif_image.documented_usd(FLARE) is not None
    assert (price, source, reason) == (None, "unpriced", f"price_error_{code}")
    assert len(price_api["bodies"]) == 1
    assert wavespeed._quotes == {}


async def test_price_input_carries_the_billed_edit_fields(price_api, monkeypatch):
    priced = {"prompt": "edit", "images": ["https://x/a.png", "https://x/b.png"],
              "mask_image": "https://x/m.png", "resolution": "2k", "quality": "high"}

    async def same(_model, inputs):
        return dict(inputs)

    monkeypatch.setattr(wavespeed, "priced_inputs", same)
    await wavespeed.quote_detail(gif_image.FLARE_EDIT, priced)
    sent = price_api["bodies"][-1]["input"]
    for key in ("images", "mask_image", "resolution", "quality"):
        assert sent[key] == priced[key]
