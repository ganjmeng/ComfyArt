"""#203: 报价 = 扣费 for the remaining paid features (seedance video is covered by test_video_quote_tier.py, #159).

For every model of: image upscale, background removal (image + video), erase, expand, multiple angles, split layers,
OCR, mockup, text edit, music, sound effect, TTS, image-to-3D, and every non-seedance video model (text / image /
reference to video, motion control, lip sync, extend, video upscale), the job is quoted and then submitted to the
local mock WaveSpeed. The mock price API prices whatever price-relevant fields it is asked about; the charge is the
same function applied to the payload that was actually submitted. Quote must equal charge, and every field the quote
priced must be the value that was sent. Schemas are the recorded catalog subset (tests/fixtures). Mock only: no key,
no network, $0."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from test_wavespeed import uncurated, wavespeed, ws  # noqa: F401  (fixtures)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())
CONFIG = json.loads((Path(__file__).resolve().parent.parent / "api" / "wavespeed_models.json").read_text())
PRICED = ("duration", "resolution", "aspect_ratio", "size", "num_images", "quality")

# tool (what the agent / canvas sends as `feature`) -> catalog feature whose models it runs
TOOLS = {
    "upscale_image": "upscale_image",
    "remove_background": "remove_background",
    "erase_region": "erase_region",
    "expand_image": "expand_image",
    "change_angle": "change_angle",
    "split_layers": "split_layers",
    "ocr": "ocr",
    "create_mockup": "image_edit",
    "replace_text": "image_edit",
    "generate_music": "music",
    "generate_sound_effect": "sound_effect",
    "text_to_speech": "text_to_speech",
    "image_to_3d": "image_to_3d",
    "text_to_video": "text_to_video",
    "image_to_video": "image_to_video",
    "reference_to_video": "reference_to_video",
    "motion_control": "motion_control",
    "lip_sync": "lip_sync",
    "extend_video": "extend_video",
    "upscale_video": "upscale_video",
    "remove_video_background": "remove_video_background",
}
VIDEO_TOOLS = {"text_to_video", "image_to_video", "reference_to_video", "extend_video"}
DURATION_TOOLS = ("text_to_video", "image_to_video", "reference_to_video", "extend_video", "generate_music", "generate_sound_effect")
EXECUTED: set[tuple[str, str]] = set()  # (tool, model) cases that really ran past the schema gate


def cases():
    out = []
    for tool, feature in TOOLS.items():
        for m in CONFIG["features"].get(feature, {}).get("models", []):
            mid = m["id"]
            if "seedance" in mid:
                continue  # #159 covers seedance
            if feature == "image_edit" and mid != CONFIG["features"]["image_edit"].get("default"):
                continue  # mockup / text edit run the default edit model; the other edit models are covered by #192
            out.append(pytest.param(tool, mid, id=f"{tool}:{mid}", marks=() if mid in FIXTURE else pytest.mark.skip(reason="no recorded schema")))
    return out


def price_of(inputs: dict) -> float:
    """Mock price API: a different number for every combination of priced fields (and reference image count)."""
    p = 0.01
    for k in PRICED:
        if k in inputs:
            # order-sensitive digest: an ord() sum collides on anagrams such as 16:9 / 9:16
            p += (int(hashlib.sha256(f"{k}={inputs[k]}".encode()).hexdigest(), 16) % 997) / 10000
    n = len(inputs.get("images") or [])
    return round(p + 0.015 * max(n - 1, 0), 6)


def charged(payload: dict) -> float:
    """What WaveSpeed bills for the run: the same price function over the fields that were actually submitted."""
    sent = {k: payload[k] for k in PRICED if k in payload and isinstance(payload[k], (int, float, str))}
    if isinstance(payload.get("images"), list):
        sent["images"] = payload["images"]
    return price_of(sent)


URL = {"image": "https://cdn.test/a.png", "video": "https://cdn.test/a.mp4", "audio": "https://cdn.test/a.mp3"}


def _url_for(name: str) -> str:
    n = name.lower()
    if "video" in n:
        return URL["video"]
    if "audio" in n or "voice" in n or "speech" in n:
        return URL["audio"]
    return URL["image"]


def job_for(tool: str, model: str) -> dict:
    """A job like the canvas / agent sends, with every required schema field filled."""
    job = {"feature": tool, "model": model, "prompt": "a red chair", "text": "你好，欢迎使用。", "image": URL["image"],
           "confirmed": False}
    if tool in VIDEO_TOOLS:
        job.update({"duration": 5, "resolution": "720p", "ratio": "16:9"})
    if tool in ("motion_control", "lip_sync", "extend_video", "upscale_video", "remove_video_background"):
        job["video"] = URL["video"]
    if tool == "lip_sync":
        job["audio"] = URL["audio"]
    if tool == "reference_to_video":
        job["images"] = [URL["image"], "https://cdn.test/b.png"]
    if tool == "generate_music":
        job.update({"lyrics": "la la la", "duration": 30})
    if tool == "generate_sound_effect":
        job["duration"] = 5
    schema = wavespeed._schema(FIXTURE.get(model) or {})
    props = schema.get("properties") or {}
    for name in schema.get("required") or []:
        if name in job:
            continue
        typ = (props.get(name) or {}).get("type")
        enum = (props.get(name) or {}).get("enum")
        if enum:
            job.setdefault("params", {})[name] = (props[name].get("default") or enum[0])
        elif typ == "array":
            job[name] = [_url_for(name)]
        elif typ == "string" and any(w in name.lower() for w in ("image", "video", "audio", "url", "mask")):
            job[name] = _url_for(name)
    return job


@pytest.fixture
def catalog(ws, monkeypatch):
    monkeypatch.setattr("test_wavespeed.MODELS", list(FIXTURE.values()))
    monkeypatch.setitem(wavespeed._catalog, "models", {})
    monkeypatch.setitem(wavespeed._catalog, "at", 0.0)
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 1000.0)  # never stop for the confirm dialog here
    return ws


@pytest.mark.parametrize("tool,model", cases())
async def test_quote_equals_charge(catalog, tool, model):
    catalog["prices"][model] = price_of
    job = job_for(tool, model)
    est = await wavespeed.estimate(dict(job))
    assert est["source"] == "quote", est
    quoted_inputs = catalog["quotes"][-1]["inputs"]
    assert catalog["quotes"][-1]["model_id"] == model
    await wavespeed.submit(dict(job))
    sent_model, payload = catalog["submits"][-1]
    assert sent_model == model  # the model that was quoted is the one that runs
    for k in PRICED:
        if k in quoted_inputs:
            assert payload.get(k) == quoted_inputs[k], (k, quoted_inputs, {x: payload.get(x) for x in PRICED})
    if "images" in quoted_inputs:
        assert len(payload.get("images") or []) == len(quoted_inputs["images"])
    assert est["price"] == pytest.approx(charged(payload)), (quoted_inputs, payload)
    EXECUTED.add((tool, model))


def _duration_ok(model: str, value: int) -> bool:
    """Recorded schema has a duration field that accepts `value`: enum contains it, min<=value<=max, or unconstrained."""
    props = wavespeed._schema(FIXTURE.get(model) or {}).get("properties") or {}
    if "duration" not in props:
        return False
    d = props["duration"] or {}
    if d.get("enum") is not None:
        return value in d["enum"]
    lo, hi = d.get("minimum"), d.get("maximum")
    return (lo is None or lo <= value) and (hi is None or value <= hi)


def tier_cases(per_tool: int = 2):
    """Fixed pick: the first `per_tool` models (config order) of each duration tool whose recorded schema has duration."""
    out = []
    for tool in DURATION_TOOLS:
        picked = [c for c in cases() if c.values[0] == tool and not c.marks
                  and _duration_ok(c.values[1], 5) and _duration_ok(c.values[1], 10)][:per_tool]
        out += [pytest.param(*c.values, id=f"{tool}:{c.values[1]}") for c in picked]
    return out


@pytest.mark.parametrize("tool,model", tier_cases())
async def test_other_tier_is_quoted_at_that_tier(catalog, tool, model):
    # breakage check: change the priced field, the quote follows it and still equals the charge
    catalog["prices"][model] = price_of
    job = job_for(tool, model)
    job["duration"] = 5
    est5 = await wavespeed.estimate(dict(job))
    job["duration"] = 10
    est = await wavespeed.estimate(dict(job))
    assert est["source"] == "quote", est
    assert catalog["quotes"][-1]["model_id"] == model
    assert catalog["quotes"][-1]["inputs"].get("duration") == 10, catalog["quotes"][-1]
    await wavespeed.submit(dict(job))
    sent_model, payload = catalog["submits"][-1]
    assert sent_model == model
    assert payload.get("duration") == 10, payload
    assert est["price"] != pytest.approx(est5["price"]), (est5, est)
    assert est["price"] == pytest.approx(charged(payload))


def test_price_function_sees_every_priced_field():
    # the mock must not hide a mismatch: changing any priced field or the image count changes the price
    base = {"duration": 5, "resolution": "720p", "aspect_ratio": "16:9", "size": "1024*1024", "num_images": 1, "quality": "high", "images": ["a"]}
    for k, other in (("duration", 10), ("resolution", "1080p"), ("aspect_ratio", "9:16"), ("size", "2048*2048"), ("num_images", 2), ("quality", "low")):
        assert price_of({**base, k: other}) != price_of(base), k
    assert price_of({**base, "images": ["a", "b"]}) != price_of(base)


def test_every_listed_feature_has_cases():
    tools = {c.values[0] for c in cases()}
    assert tools == set(TOOLS), set(TOOLS) - tools


def test_tier_cases_cover_every_duration_tool():
    tools = {c.values[0] for c in tier_cases()}
    assert tools == set(DURATION_TOOLS), set(DURATION_TOOLS) - tools


def test_coverage_counts_only_executed_cases():
    # runs last in this file: only cases that passed the schema gate and finished count as covered
    all_cases = cases()
    skipped = [c.id for c in all_cases if c.marks]
    assert EXECUTED, "no test_quote_equals_charge case executed (all skipped, or not run before this test)"
    covered = {t for t, _ in EXECUTED}
    print(f"\n#203 coverage: {len(EXECUTED)}/{len(all_cases)} cases executed, {len(skipped)} skipped (no recorded schema): {skipped}")
    assert covered == set(TOOLS), f"tools with 0 executed cases: {sorted(set(TOOLS) - covered)}"
