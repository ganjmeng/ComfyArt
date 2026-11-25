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
    # Unknown length is priced at 60s and labelled estimate, so the route does not submit.
    # A known duration still submits; that payload shape is test_transcribe_route_prices_with_page_duration.
    body = await res.json()
    assert res.status == 409 and body["error"]["estimate"] is True and ws["submits"] == []
    assert ws["quotes"] == [{"model_id": WHISPER, "input": {"duration": 60}}]


async def test_caption_route_request_shape_and_quote(ws, bot_client, media):
    ws["outputs"] = ["a cat"]
    ws["prices"][CAPTION] = 0.001
    res = await bot_client.post("/comfyart/wavespeed/caption", json={"src": PIC})
    assert res.status == 200 and (await res.json())["text"] == "a cat"
    model, payload = ws["submits"][0]
    assert model == CAPTION and payload["image"].startswith("https://cdn.test/")
    assert ws["quotes"] == [{"model_id": CAPTION, "input": {}}]
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
    assert ws["quotes"] == [{"model_id": WHISPER, "input": {"duration": seconds}}]


@pytest.mark.parametrize("seconds", [10, 60, 300])
async def test_whisper_price_reject_4005_is_unpriced_not_a_per_second_estimate(ws, seconds):
    """A 4005 is not a timeout. The per-second table must not stand in for it."""
    ws["prices"][WHISPER] = None
    est = await wavespeed.estimate({"feature": "transcribe", "audio": AUDIO, "duration": seconds})
    assert est["price"] is None and est["source"] == "unpriced"
    assert est["price"] != round(RATE * seconds, 6)


async def test_whisper_price_reject_4005_unknown_length_is_unpriced(ws):
    ws["prices"][WHISPER] = None
    est = await wavespeed.estimate({"feature": "transcribe", "audio": AUDIO})
    assert est["price"] is None and est["source"] == "unpriced"
    assert est["price"] != round(RATE * 60, 6)


async def test_m32_clip_is_unpriced_when_the_price_api_rejects(ws):
    """4005 does not invent the old $0.0035 local estimate for a 4.752 s clip."""
    ws["prices"][WHISPER] = None
    price, source = await wavespeed.quote(WHISPER, {"feature": "transcribe", "duration": 4.752})
    assert (price, source) == (None, "unpriced")


async def test_whisper_price_reject_does_not_submit(ws, bot_client, media):
    ws["prices"][WHISPER] = None
    ws["outputs"] = ["hi"]
    for body in ({"src": AUDIO}, {"src": AUDIO, "duration": 10}):
        ws["submits"].clear()
        res = await bot_client.post("/comfyart/wavespeed/transcribe", json=body)
        payload = await res.json()
        err = payload.get("error") if isinstance(payload.get("error"), dict) else payload
        assert res.status == 409 and err.get("unpriced") is True
        assert ws["submits"] == []
