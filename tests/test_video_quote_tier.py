"""#159: the video quote is priced at the tier that is actually submitted. '1K' (the image default) never maps to 4k;
an unset or unknown video resolution is the model's schema default (seedance: 720p; no default: the first tier) on the
agent and canvas paths. On a price-API failure the catalog base_price is only used when it is the price of the submitted
tier (the schema default tier), labelled 「估算价」/'Estimated'; any other tier shows no amount and always asks before
it is submitted. Never another tier's catalog price. All mocked: no key, no WaveSpeed, $0."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ComfyArt.api import wavespeed
from ComfyArt.tests.test_wavespeed import MODELS, _meta, ws  # noqa: F401  (ws fixture)

ROOT = Path(__file__).resolve().parent.parent
SEED = "bytedance/seedance-2.0/image-to-video"
ENUM = ["480p", "720p", "1080p", "4k"]
TABLE = {"480p": 0.108, "720p": 0.216, "1080p": 0.486, "4k": 1.9}


@pytest.fixture
def seed(ws, monkeypatch):
    # like the live seedance-2.0 schema: resolution default 720p, duration default 5
    MODELS.append(_meta(SEED, {"prompt": {"type": "string"}, "image": {"type": "string"},
                               "duration": {"type": "integer", "enum": [5, 10, 15], "default": 5},
                               "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1"]},
                               "resolution": {"type": "string", "enum": ENUM, "default": "720p"}}, ("prompt", "image"), price=0.24))
    yield ws
    MODELS[:] = [m for m in MODELS if m["model_id"] != SEED]


def per_tier(inputs):
    if inputs.get("resolution") not in TABLE:
        raise ValueError("invalid resolution")  # mock server answers 500, like the real 400
    return round(TABLE[inputs["resolution"]] * inputs.get("duration", 5), 4)


JOB = {"feature": "image_to_video", "model": SEED, "prompt": "p", "image": "https://x/a.png", "duration": 5, "ratio": "16:9"}


@pytest.mark.parametrize("asked,tier,with_default", [("1K", "480p", "480p"), ("1K", "720p", "720p"), ("2K", "720p", "720p"),
                                                     ("custom", "720p", "720p"), ("768p", "720p", "720p"), ("4k", "4k", "720p"), ("1080p", "1080p", "720p")])
def test_pick_never_matches_across_units(asked, tier, with_default):
    assert wavespeed._pick(ENUM, asked, None if with_default == "480p" else with_default) == tier
    assert wavespeed._pick(ENUM, "1K") != "4k" and wavespeed._pick(ENUM, "1K", "720p") != "4k"


@pytest.mark.parametrize("res,tier", [("1K", "720p"), ("768p", "720p"), ("480p", "480p"), ("1080p", "1080p")])
async def test_quote_tier_equals_submitted_tier(seed, monkeypatch, res, tier):
    seed["prices"][SEED] = per_tier
    job = {**JOB, "resolution": res}
    price, src = await wavespeed.quote(SEED, job)
    assert src == "quote" and seed["quotes"][-1]["inputs"]["resolution"] == tier
    assert price == pytest.approx(TABLE[tier] * 5)
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 100.0)
    await wavespeed.submit(job)
    sent = seed["submits"][-1][1]
    assert sent["resolution"] == tier  # quote params == submit params
    for k in ("resolution", "duration", "aspect_ratio"):
        if k in seed["quotes"][-1]["inputs"]:
            assert seed["quotes"][-1]["inputs"][k] == sent.get(k)


def _loc(lang):
    return json.loads((ROOT / f"src/locales/{lang}.json").read_text())


async def test_price_api_400_default_tier_is_an_estimate(seed, monkeypatch):
    # branch 1: base_price is the price of the schema default tier (720p · 5s) and that is the submitted tier
    seed["prices"].pop(SEED, None)  # unknown to the price API -> 400
    job = {**JOB, "resolution": "1K"}  # old card value -> schema default 720p
    est = await wavespeed.estimate(job)
    assert est["source"] == "estimate" and est["price"] == 0.24 and est["tier"] == "720p · 5s"
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0.0)  # 0 = always confirm, so the dialog shows
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit(job)
    assert e.value.status == 409 and e.value.estimate and e.value.tier == "720p · 5s" and not seed["submits"]
    body = json.loads(wavespeed._respond_error(e.value).body)["error"]
    assert body["estimate"] is True and body["tier"] == "720p · 5s" and body["confirm_usd"] == 0.24
    await wavespeed.submit({**job, "confirmed": True})
    assert seed["submits"][-1][1]["resolution"] == body["tier"].split(" · ")[0]  # dialog tier == submitted tier
    for lang, word in (("zh", "估算价"), ("en", "Estimated")):
        text = _loc(lang)["jobs.confirmEstimateTier"].replace("{0}", "0.24").replace("{1}", body["tier"])
        assert word in text and "720p · 5s" in text and "0.24" in text
        assert word in _loc(lang)["wsKey.estimatedTag"]


@pytest.mark.parametrize("res,dur,tier", [("1080p", 5, "1080p · 5s"), ("4k", 5, "4k · 5s"), ("720p", 10, "720p · 10s")])
async def test_price_api_400_other_tier_shows_no_amount_and_always_asks(seed, monkeypatch, res, dur, tier):
    # branch 2: no price for the submitted tier: no amount, never the catalog price of the default tier, always confirm
    seed["prices"].pop(SEED, None)
    job = {**JOB, "resolution": res, "duration": dur}
    est = await wavespeed.estimate(job)
    assert est["source"] == "unpriced" and est["price"] is None and est["confirm"] is True and est["tier"] == tier
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 100.0)  # even far below the threshold it asks
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit(job)
    assert e.value.status == 409 and not seed["submits"]
    body = json.loads(wavespeed._respond_error(e.value).body)["error"]
    assert body["unpriced"] is True and body["confirm_usd"] is None and body["tier"] == tier and "estimate" not in body
    await wavespeed.submit({**job, "confirmed": True})
    sent = seed["submits"][-1][1]
    assert f"{sent['resolution']} · {sent['duration']}s" == tier  # dialog tier == submitted tier
    for lang, text in (("zh", "暂时查不到准确价格，继续会按 {0} 实际扣费"), ("en", "Couldn't get the exact price; continuing will be charged at the actual rate for {0}")):
        loc = _loc(lang)
        assert loc["jobs.confirmUnpriced"] == text and "$" not in text and "$" not in loc["wsKey.unpricedTag"]


async def test_storyboard_with_an_unpriced_scene_asks_without_a_total(seed, monkeypatch):
    seed["prices"].pop(SEED, None)
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 100.0)
    sb = {**JOB, "resolution": "1080p", "scenes": [{"prompt": "a"}, {"prompt": "b"}]}
    est = await wavespeed.estimate(sb)
    assert est["source"] == "unpriced" and est["price"] is None and est["confirm"] is True


def test_no_silent_catalog_source_anywhere():
    src = (ROOT / "api/wavespeed.py").read_text().split("async def quote(")[1].split("async def estimate(")[0]
    assert '"catalog"' not in src and "_is_default_tier(" in src


async def test_agent_and_canvas_defaults_quote_and_submit_the_model_default(seed, monkeypatch):
    # no resolution clicked: agent sends videoResolution('', resolutions, defaults.resolution), the canvas the written-back
    # chip value (same function), and a job without one is priced at what WaveSpeed runs: the schema default, 720p
    seed["prices"][SEED] = per_tier
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 100.0)
    for res in ("720p", "1K", None):
        job = {**JOB, **({"resolution": res} if res else {})}
        await wavespeed.submit(job)
        assert seed["quotes"][-1]["inputs"]["resolution"] == "720p"
        assert seed["submits"][-1][1].get("resolution", "720p") == "720p"
    # the catalog the UI reads (#95 caps) carries that default, so the chip shows 720p too
    meta = next(m for m in MODELS if m["model_id"] == SEED)
    assert wavespeed._caps(wavespeed._schema({**meta, "api_schema": meta["api_schema"]}))["defaults"]["resolution"] == "720p"


def test_frontend_wiring():
    gen = (ROOT / "src/generate.ts").read_text()
    assert "resolution: shape.props.resolution || '768p'" not in gen and gen.count("videoResOf(shape.props)") == 2
    assert "if (video) props = { ...props, resolution: videoResOf(" in gen  # createGenerator
    bot = (ROOT / "src/botCommands.ts").read_text()
    assert "resolution: videoResolution(" in bot and "model.defaults?.resolution" in bot  # agent generate_video
    gs = (ROOT / "src/ui/GenSettings.tsx").read_text()
    assert "update({ resolution: vres })" in gs and "value={shownVideoRes(p, caps)}" in gs and "caps?.defaults?.resolution" in gs
    comfy = (ROOT / "src/comfy.ts").read_text()
    assert "wsBody?.error?.estimate" in comfy and "jobs.confirmEstimateTier" in comfy
    assert "wsBody?.error?.unpriced" in comfy and "jobs.confirmUnpriced" in comfy
    panel = (ROOT / "src/ui/GenPanel.tsx").read_text()
    assert "e?.source === 'estimate'" in panel and "e?.source === 'unpriced'" in panel and "wsKey.unpricedTag" in panel


def test_frontend_video_resolution():
    if not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"):
        pytest.fail("needs node + npm install (#131)")
    out = ROOT / ".." / "vres.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "video_resolution.ts"})
    js = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    assert js["list"][0] == "480p"  # no model data at all: the first tier
    assert js["unknownModel"] == ["480p", "480p", "480p", "480p", "768p"]
    assert js["seedance"] == ["480p", "480p", "480p", "720p", "4k"]  # schema enum without a default: the first tier
    assert js["seedanceDefault"] == "720p" and js["badDefault"] == "480p"
    assert js["seedanceDefaultUnset"] == ["720p", "720p", "720p", "720p", "4k"]  # schema default 720p: unset/unknown -> 720p
