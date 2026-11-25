"""P1: an estimate under the default confirm line still shows a card, and confirmed=True cannot submit it.

The default line is 50 credits ($0.50). These tests do not set the threshold to 0.
A purely official quote under that line still has no card. Anything else with a billable
unit asks, and the only buttons are 重新取价 and 取消. wavespeed.submit returns 409 and
posts nothing, including when the client sends confirmed=True.

Mocks only. No live price fetch, no paid call.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from ComfyArt.api import wavespeed
from ComfyArt.bot.plan_quote import REPRICE_LABEL, SOURCE_ESTIMATE, SOURCE_QUOTE, build_quote
from ComfyArt.tests.test_plan_quote_235 import _run, _step, _tc

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
CATALOG = json.loads((FIX / "wavespeed_catalog_subset.json").read_text())
FLARE = "openai/gpt-image-2.6-flare/text-to-image"

# Product default: DEFAULT_CONFIRM_CREDITS / 100. Not 0 (0 means always confirm).
THRESHOLD = wavespeed.DEFAULT_CONFIRM_CREDITS / 100


def _buttons(card, lang="zh"):
    opts = card.ask_spec()["options"]
    assert [o["id"] for o in opts] == ["reprice", "cancel"]
    assert [o["label"] for o in opts] == [REPRICE_LABEL[lang], "取消" if lang == "zh" else "Cancel"]
    assert "start" not in {o["id"] for o in opts}


async def _no_models(_feature):
    return []


async def _quote(steps, pricer):
    return await build_quote(steps, "zh", threshold=THRESHOLD, pricer=pricer, models_for=_no_models)


async def test_single_estimate_under_the_default_line_asks_and_does_not_submit(monkeypatch):
    """One step, list-price estimate $0.05. The card exists. The agent does not run it."""
    async def pricer(_model, _inputs):
        return 0.05, "estimate", "list_price"

    step = _step("棚拍", "generate_image", "acme/flare", prompt="p")
    card = await _quote([step], pricer)
    assert card is not None and card.ask is True
    assert card.lines[0].source == SOURCE_ESTIMATE
    assert card.total == pytest.approx(0.05)
    _buttons(card)
    assert "可以重新取价，或取消" in card.prompt
    assert "达到了你设置的" not in card.prompt and "确定开始" not in card.prompt

    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [
            _tc(1, "generate_image", {"prompt": "p", "model": "acme/flare"}),
        ]}}]},
        {"choices": [{"message": {"content": "should not run", "tool_calls": []}}]},
    ]
    _result, _events, mcp, _quoted, confirms = await _run(monkeypatch, responses, quote=card, confirm="cancel")
    assert mcp == []
    assert confirms and [o["id"] for o in confirms[0]["options"]] == ["reprice", "cancel"]


async def test_under_line_list_price_prompt_is_verbatim_and_over_line_still_names_the_line():
    """Product sentence for one list-price estimate under the default $0.50 line, zh and en.

    $0.05 is 5 credits. The over-line card ($0.85, 85 credits) still names the confirm line.
    """
    async def under(_model, _inputs):
        return 0.05, "estimate", "list_price"

    step = _step("棚拍", "generate_image", "acme/flare", prompt="p")
    zh = await _quote([step], under)
    assert zh is not None and zh.ask is True and zh.lines[0].reason == "list_price"
    assert zh.prompt == (
        "这次生成预计约 5 积分。实时价格暂不可用，按未打折标价估算，实际扣费可能更低。可以重新取价，或取消。"
    )
    assert "确认线" not in zh.prompt and "达到了" not in zh.prompt
    en = await build_quote([step], "en", threshold=THRESHOLD, pricer=under, models_for=_no_models)
    assert en is not None
    assert en.prompt == (
        "This generation is estimated at about 5 credits. The live price is unavailable; "
        "this is an undiscounted list-price estimate and the actual charge may be lower. Re-price, or cancel."
    )
    assert "confirm limit" not in en.prompt

    async def over(_model, _inputs):
        return 0.85, "estimate", "list_price"

    zh_over = await _quote([step], over)
    assert zh_over is not None and "确认线" in zh_over.prompt and "达到了" in zh_over.prompt
    en_over = await build_quote([step], "en", threshold=THRESHOLD, pricer=over, models_for=_no_models)
    assert en_over is not None and "confirm limit" in en_over.prompt


async def test_two_step_estimate_batch_under_the_default_line_does_not_submit(monkeypatch):
    """Two estimates, $0.04 + $0.04. ask stays true, so the batch does not start."""
    async def pricer(_model, _inputs):
        return 0.04, "estimate", "list_price"

    steps = [
        _step("甲", "generate_image", "acme/a", prompt="a"),
        _step("乙", "generate_image", "acme/b", prompt="b"),
    ]
    card = await _quote(steps, pricer)
    assert card is not None and card.ask is True and card.total == pytest.approx(0.08)
    _buttons(card)
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [
            _tc(1, "generate_image", {"prompt": "a", "model": "acme/a"}),
            _tc(2, "generate_image", {"prompt": "b", "model": "acme/b"}),
        ]}}]},
        {"choices": [{"message": {"content": "should not run", "tool_calls": []}}]},
    ]
    _result, _events, mcp, _quoted, confirms = await _run(monkeypatch, responses, quote=card, confirm="cancel")
    assert mcp == []
    assert len(confirms) == 1


async def test_mixed_exact_and_estimate_under_the_default_line_does_not_submit(monkeypatch):
    """$0.05 exact + $0.045 estimate = $0.095. One non-quote line blocks the batch."""
    async def pricer(model, _inputs):
        if model == "acme/exact":
            return 0.05
        return 0.045, "estimate", "list_price"

    steps = [
        _step("精确", "generate_image", "acme/exact", prompt="a"),
        _step("估算", "generate_image", "acme/est", prompt="b"),
    ]
    card = await _quote(steps, pricer)
    assert card is not None and card.ask is True
    assert card.total == pytest.approx(0.095)
    assert [ln.source for ln in card.lines] == [SOURCE_QUOTE, SOURCE_ESTIMATE]
    _buttons(card)
    responses = [
        {"choices": [{"message": {"content": "", "tool_calls": [
            _tc(1, "generate_image", {"prompt": "a", "model": "acme/exact"}),
            _tc(2, "generate_image", {"prompt": "b", "model": "acme/est"}),
        ]}}]},
        {"choices": [{"message": {"content": "should not run", "tool_calls": []}}]},
    ]
    _result, _events, mcp, _quoted, confirms = await _run(monkeypatch, responses, quote=card, confirm="cancel")
    assert mcp == []
    assert confirms and "start" not in {o["id"] for o in confirms[0]["options"]}


async def test_exact_quote_under_the_default_line_still_skips_the_card():
    async def pricer(_model, _inputs):
        return 0.04

    card = await _quote([_step("便宜", "generate_image", "acme/cheap", prompt="p")], pricer)
    assert card is None


@pytest.fixture
async def price_api(monkeypatch):
    """Local price API. mode is 'hang' (timeout), '503', or '4005'. No network."""
    state = {"mode": "503", "posts": 0, "submits": []}
    wavespeed._quotes.clear()
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    wavespeed._jobs.clear()
    wavespeed._submits.clear()
    app = web.Application()

    async def models(_request):
        return web.json_response({"code": 200, "data": list(CATALOG.values())})

    async def price(request):
        state["posts"] += 1
        if state["mode"] == "hang":
            await asyncio.sleep(0.2)
        if state["mode"] == "4005":
            return web.json_response({"code": 4005, "message": "model not found"}, status=400)
        return web.json_response({"code": 500, "message": "unavailable"}, status=503)

    async def submit(request):
        state["submits"].append(await request.json())
        return web.json_response({"code": 200, "data": {"id": "task-should-not-exist", "status": "created"}})

    async def balance(_request):
        return web.json_response({"code": 200, "data": {"balance": 10}})

    app.router.add_get("/api/v3/models", models)
    app.router.add_get("/api/v3/balance", balance)
    app.router.add_post("/api/v3/model/price", price)
    app.router.add_post("/api/v3/{model:.+}", submit)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-not-a-real-key")
    monkeypatch.setattr(wavespeed, "QUOTE_TIMEOUT_S", 0.05)
    monkeypatch.setattr(wavespeed, "QUOTE_RETRY_BACKOFF_S", 0.0)
    # Leave confirm_usd on the product default. Do not set it to 0.
    assert wavespeed.confirm_usd() == pytest.approx(THRESHOLD)
    yield state
    await server.close()


def _flare_step():
    return _step("棚拍", "generate_image", FLARE, prompt="p")


async def _provider_price(model, inputs):
    from ComfyArt.bot.local_llm import LocalLlmProvider
    provider = LocalLlmProvider.__new__(LocalLlmProvider)
    return await provider._price_one(model, inputs)


async def test_single_503_under_the_default_line_shows_a_card_and_submits_nothing(price_api):
    price_api["mode"] = "503"
    price, source, reason = await _provider_price(FLARE, {})
    assert (price, source, reason) == (0.05, SOURCE_ESTIMATE, "list_price")
    card = await _quote([_flare_step()], _provider_price)
    assert card is not None and card.ask is True and card.total == pytest.approx(0.05)
    _buttons(card)
    job = {"feature": "text_to_image", "model": FLARE, "prompt": "p"}
    with pytest.raises(wavespeed.WaveSpeedError) as err:
        await wavespeed.submit(job)
    assert err.value.status == 409 and err.value.estimate and not price_api["submits"]
    with pytest.raises(wavespeed.WaveSpeedError) as again:
        await wavespeed.submit({**job, "confirmed": True})
    assert again.value.status == 409 and again.value.estimate and price_api["submits"] == []


async def test_single_timeout_under_the_default_line_shows_a_card_and_submits_nothing(price_api):
    price_api["mode"] = "hang"
    price, source, reason = await _provider_price(FLARE, {})
    assert (price, source, reason) == (0.05, SOURCE_ESTIMATE, "list_price")
    card = await _quote([_flare_step()], _provider_price)
    assert card is not None and card.ask is True
    _buttons(card)
    job = {"feature": "text_to_image", "model": FLARE, "prompt": "p"}
    with pytest.raises(wavespeed.WaveSpeedError) as err:
        await wavespeed.submit(job)
    assert err.value.status == 409 and err.value.estimate and price_api["submits"] == []
    with pytest.raises(wavespeed.WaveSpeedError) as again:
        await wavespeed.submit({**job, "confirmed": True})
    assert again.value.status == 409 and price_api["submits"] == []


async def test_confirmed_4005_is_409_and_submits_nothing(price_api):
    price_api["mode"] = "4005"
    job = {"feature": "text_to_image", "model": FLARE, "prompt": "p", "confirmed": True}
    with pytest.raises(wavespeed.WaveSpeedError) as err:
        await wavespeed.submit(job)
    assert err.value.status == 409 and err.value.unpriced and not err.value.estimate
    assert price_api["submits"] == []
    card = await _quote([_flare_step()], _provider_price)
    assert card is not None and card.ask is True
    _buttons(card)
    assert card.lines[0].price == "未定价"


def test_canvas_confirm_copy_matches_the_agent_card_and_has_no_continue():
    """The canvas <Confirm/> strings are the agent sentences, and the button is 重新取价."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    zh = json.loads((root / "src/locales/zh.json").read_text())
    en = json.loads((root / "src/locales/en.json").read_text())
    assert zh["jobs.confirmUnpriced"] == zh["quote.unpricedPrompt"]
    assert en["jobs.confirmUnpriced"] == en["quote.unpricedPrompt"]
    assert zh["quote.unpricedTitle"] == "暂未定价" and zh["quote.estimateTitle"] == "价格暂不可用"
    for key in ("jobs.confirmUnpriced", "jobs.confirmUnpricedGif", "jobs.confirmEstimate",
                "jobs.confirmEstimateTier", "jobs.confirmEstimateGif"):
        assert "确定继续" not in zh[key] and "继续会" not in zh[key]
        assert "Continue?" not in en[key]
    comfy = (root / "src/comfy.ts").read_text()
    ask = comfy[comfy.index("export function askCost"):comfy.index("export async function queuePrompt")]
    assert "quote.unpricedTitle" in ask and "quote.estimateTitle" in ask and "quote.reprice" in ask
    gate = (root / "src/ui/confirmationSubmission.ts").read_text()
    assert "if (unpriced || estimate) return false" in gate
