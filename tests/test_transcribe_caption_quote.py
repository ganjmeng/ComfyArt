"""QA (mock only): /transcribe and /caption request shape + quote; whisper quote vs per-second charge (#123/#31)."""
from __future__ import annotations

import pytest

from ComfyArt.api import wavespeed
from tests.test_wavespeed import ws  # noqa: F401

WHISPER = "wavespeed-ai/openai-whisper-turbo"
CAPTION = "wavespeed-ai/image-captioner"
AUDIO = "/api/view?filename=voice.webm&subfolder=&type=input"
PIC = "/api/view?filename=pic.png&subfolder=&type=input"
RATE = 0.0007  # $/s: WaveSpeed bills whisper per second (M32: 4.752 s clip charged $0.0035 = 5 s x $0.0007)
BASE = 0.0007


@pytest.fixture
def media(fresh_user_dir):
    d = fresh_user_dir / "input"
    d.mkdir(parents=True, exist_ok=True)
    (d / "voice.webm").write_bytes(b"audio")
    (d / "pic.png").write_bytes(b"png")


def _per_second(inputs):
    return round(RATE * inputs["duration"], 6) if inputs.get("duration") else BASE


async def test_transcribe_route_request_shape_and_quote(ws, bot_client, media):
    ws["outputs"] = ["hi"]
    ws["prices"][WHISPER] = BASE
    res = await bot_client.post("/comfyart/wavespeed/transcribe", json={"src": AUDIO})
    assert res.status == 200 and (await res.json())["text"] == "hi"
    model, payload = ws["submits"][0]
    assert model == WHISPER and payload["audio"].startswith("https://cdn.test/")
    assert "duration" not in payload  # #185: the length prices the job only, never submitted (schema has none)
    assert ws["quotes"] == [{"model_id": WHISPER, "inputs": {"duration": 60}}]  # #185: unknown length -> 60 s fallback


async def test_caption_route_request_shape_and_quote(ws, bot_client, media):
    ws["outputs"] = ["a cat"]
    ws["prices"][CAPTION] = 0.001
    res = await bot_client.post("/comfyart/wavespeed/caption", json={"src": PIC})
    assert res.status == 200 and (await res.json())["text"] == "a cat"
    model, payload = ws["submits"][0]
    assert model == CAPTION and payload["image"].startswith("https://cdn.test/")
    assert ws["quotes"] == [{"model_id": CAPTION, "inputs": {}}]
    assert (await wavespeed.estimate({"feature": "caption", "image": PIC}))  # estimate path works


@pytest.mark.parametrize("route,src", [("transcribe", ""), ("caption", None)])
async def test_routes_reject_missing_src(ws, bot_client, route, src):
    res = await bot_client.post(f"/comfyart/wavespeed/{route}", json={"src": src})
    assert res.status == 400 and not ws["submits"]


@pytest.mark.parametrize("seconds", [10, 60, 300])
async def test_whisper_quote_equals_charge(ws, seconds):
    """Quote with the duration the caller would pass vs the per-second charge for that audio."""
    ws["prices"][WHISPER] = _per_second
    quoted, _ = await wavespeed.quote(WHISPER, {"feature": "transcribe", "audio": AUDIO, "duration": seconds})
    charged = round(RATE * seconds, 6)
    print(f"QA {seconds}s quoted={quoted} charged={charged}")
    assert quoted == pytest.approx(charged, rel=0.2)  # #31 acceptance: within 20%


# --- #185: quote == charge for per-second whisper, 60 s fallback labelled as an estimate ---------------------------

@pytest.mark.parametrize("seconds", [10, 60, 300])
async def test_whisper_estimate_equals_charge_exactly(ws, seconds):
    ws["prices"][WHISPER] = _per_second
    est = await wavespeed.estimate({"feature": "transcribe", "audio": AUDIO, "duration": seconds})
    print(f"#185 {seconds}s quoted={est['price']} charged={round(RATE * seconds, 6)} source={est['source']}")
    assert est["price"] == round(RATE * seconds, 6) and est["source"] == "quote" and "duration_estimated" not in est


async def test_whisper_fractional_length_rounds_up(ws):
    ws["prices"][WHISPER] = _per_second
    assert (await wavespeed.quote(WHISPER, {"feature": "transcribe", "duration": 9.2}))[0] == round(RATE * 10, 6)


@pytest.mark.parametrize("dur", [None, 0, -3, float("inf"), "x", True])
async def test_whisper_unknown_length_estimated_at_60s(ws, dur):
    ws["prices"][WHISPER] = _per_second
    inputs = {"feature": "transcribe", "audio": AUDIO, **({} if dur is None else {"duration": dur})}
    est = await wavespeed.estimate(inputs)
    print(f"#185 fallback dur={dur!r} quoted={est['price']} source={est['source']}")
    assert est["price"] == round(RATE * 60, 6) and est["source"] == "estimate" and est["duration_estimated"] is True


@pytest.mark.parametrize("seconds", [10, 60, 300])
async def test_transcribe_route_prices_with_page_duration(ws, bot_client, media, seconds):
    ws["outputs"] = ["hi"]
    ws["prices"][WHISPER] = _per_second
    res = await bot_client.post("/comfyart/wavespeed/transcribe", json={"src": AUDIO, "duration": seconds})
    assert res.status == 200
    _, payload = ws["submits"][0]
    assert "duration" not in payload
    assert ws["quotes"] == [{"model_id": WHISPER, "inputs": {"duration": seconds}}]


@pytest.mark.parametrize("seconds", [10, 60, 300])
async def test_whisper_price_api_down_local_estimate_equals_charge(ws, seconds):
    ws["prices"].pop(WHISPER, None)  # price API 400: local estimate = catalog $/s x rounded-up seconds
    est = await wavespeed.estimate({"feature": "transcribe", "audio": AUDIO, "duration": seconds})
    print(f"#185 price-API down {seconds}s quoted={est['price']} charged={round(RATE * seconds, 6)} source={est['source']}")
    assert est["price"] == round(RATE * seconds, 6) and est["source"] == "estimate" and not est.get("unpriced")


async def test_whisper_price_api_down_unknown_length_60s(ws):
    ws["prices"].pop(WHISPER, None)
    est = await wavespeed.estimate({"feature": "transcribe", "audio": AUDIO})
    print(f"#185 price-API down unknown length quoted={est['price']} source={est['source']}")
    assert est["price"] == round(RATE * 60, 6) and est["source"] == "estimate" and est["duration_estimated"] is True


async def test_m32_real_clip_rounds_up_to_charge(ws):
    ws["prices"].pop(WHISPER, None)  # the real M32 run: 4.752 s clip, charged $0.0035
    assert (await wavespeed.quote(WHISPER, {"feature": "transcribe", "duration": 4.752}))[0] == 0.0035


async def test_whisper_price_api_down_route_never_409(ws, bot_client, media):
    ws["prices"].pop(WHISPER, None)
    ws["outputs"] = ["hi"]
    for body in ({"src": AUDIO}, {"src": AUDIO, "duration": 10}):
        ws["submits"].clear()
        res = await bot_client.post("/comfyart/wavespeed/transcribe", json=body)
        assert res.status == 200 and ws["submits"]
