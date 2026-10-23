"""#159: the video quote is priced at the tier that is actually submitted. '1K' (the image default) never maps to 4k,
no-resolution video defaults to 480p on agent and canvas paths, and a price-API failure is shown as 「估算价」/'Estimated'
for the submitted tier, never silently as the catalog price. All mocked: no key, no WaveSpeed, $0."""
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
    if not any(m["model_id"] == SEED for m in MODELS):
        monkeypatch.setattr("ComfyArt.tests.test_wavespeed.MODELS", MODELS)
        MODELS.append(_meta(SEED, {"prompt": {"type": "string"}, "image": {"type": "string"},
                                   "duration": {"type": "integer", "minimum": 4, "maximum": 15},
                                   "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1"]},
                                   "resolution": {"type": "string", "enum": ENUM}}, ("prompt", "image"), price=0.24))
        yield ws
        MODELS[:] = [m for m in MODELS if m["model_id"] != SEED]
    else:
        yield ws


def per_tier(inputs):
    if inputs.get("resolution") not in TABLE:
        raise ValueError("invalid resolution")  # mock server answers 500, like the real 400
    return round(TABLE[inputs["resolution"]] * inputs.get("duration", 5), 4)


JOB = {"feature": "image_to_video", "model": SEED, "prompt": "p", "image": "https://x/a.png", "duration": 5, "ratio": "16:9"}


@pytest.mark.parametrize("asked,tier", [("1K", "480p"), ("2K", "480p"), ("768p", "720p"), ("720p", "720p"), ("4k", "4k")])
def test_pick_never_matches_across_units(asked, tier):
    assert wavespeed._pick(ENUM, asked) == tier
    assert wavespeed._pick(ENUM, "1K") != "4k"


@pytest.mark.parametrize("res,tier", [("1K", "480p"), ("768p", "720p"), ("480p", "480p")])
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


async def test_price_api_400_is_an_estimate_for_the_submitted_tier(seed, monkeypatch):
    seed["prices"].pop(SEED, None)  # unknown to the price API -> 400
    job = {**JOB, "resolution": "1K"}
    est = await wavespeed.estimate(job)
    assert est["source"] == "estimate" and est["price"] == 0.24 and est["tier"] == "480p · 5s"
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0.0)  # 0 = always confirm, so the dialog shows
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit(job)
    assert e.value.status == 409 and e.value.estimate and e.value.tier == "480p · 5s" and not seed["submits"]
    body = json.loads(wavespeed._respond_error(e.value).body)["error"]
    assert body["estimate"] is True and body["tier"] == "480p · 5s" and body["confirm_usd"] == 0.24
    await wavespeed.submit({**job, "confirmed": True})
    assert seed["submits"][-1][1]["resolution"] == body["tier"].split(" · ")[0]  # dialog tier == submitted tier
    # the dialog text the page builds from this body (comfy.ts askCost) says 估算价 / Estimated, with the tier
    for lang, word in (("zh", "估算价"), ("en", "Estimated")):
        loc = json.loads((ROOT / f"src/locales/{lang}.json").read_text())
        text = loc["jobs.confirmEstimateTier"].replace("{0}", "0.24").replace("{1}", body["tier"])
        assert word in text and "480p · 5s" in text and "0.24" in text
        assert word in loc["wsKey.estimatedTag"]


def test_no_silent_catalog_source_anywhere():
    # the catalog fallback is labelled 'estimate' (test_wavespeed::test_estimate_falls_back_to_catalog_price_marked_as_estimate)
    assert '"catalog"' not in (ROOT / "api/wavespeed.py").read_text().split("async def quote(")[1].split("async def estimate(")[0]


async def test_agent_and_canvas_defaults_quote_and_submit_480p(seed, monkeypatch):
    # with no resolution clicked both paths send videoResolution('', ...) / the written-back chip value: 480p
    seed["prices"][SEED] = per_tier
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 100.0)
    for res in ("480p", "1K"):  # 1K = an old card that still carries the image default
        await wavespeed.submit({**JOB, "resolution": res})
        assert seed["quotes"][-1]["inputs"]["resolution"] == seed["submits"][-1][1]["resolution"] == "480p"


def test_frontend_wiring():
    gen = (ROOT / "src/generate.ts").read_text()
    assert "resolution: shape.props.resolution || '768p'" not in gen and gen.count("videoResOf(shape.props)") == 2
    assert "if (video) props = { ...props, resolution: videoResOf(" in gen  # createGenerator
    bot = (ROOT / "src/botCommands.ts").read_text()
    assert "resolution: videoResolution(" in bot  # agent generate_video
    gs = (ROOT / "src/ui/GenSettings.tsx").read_text()
    assert "update({ resolution: vres })" in gs and "value={shownVideoRes(p, caps)}" in gs and "shownVideoRes(p, caps)}" in gs
    comfy = (ROOT / "src/comfy.ts").read_text()
    assert "wsBody?.error?.estimate" in comfy and "jobs.confirmEstimateTier" in comfy
    assert "e?.source === 'estimate'" in (ROOT / "src/ui/GenPanel.tsx").read_text()


def test_frontend_video_resolution():
    if not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"):
        pytest.fail("needs node + npm install (#131)")
    out = ROOT / ".." / "vres.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "video_resolution.ts"})
    js = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    assert js["list"][0] == "480p"
    assert js["unknownModel"] == ["480p", "480p", "480p", "480p", "768p"]
    assert js["seedance"] == ["480p", "480p", "480p", "720p", "4k"]
    assert js["seedanceDefault"] == "720p" and js["badDefault"] == "480p"
