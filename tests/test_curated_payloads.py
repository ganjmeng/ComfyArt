"""#95: every curated model (models + more) gets a valid request from build_payload on a typical input.
Mock only: schemas come from the catalog fixture, media are URLs (no upload), nothing is sent."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from ComfyArt.api import wavespeed

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())
CURATED = wavespeed.load_curated()
IMG = "https://example.com/ref-{}.png"

# one typical request per feature family; extra keys are ignored by models that do not take them
BASE = {"prompt": "a red fox in the snow, cinematic light", "seed": 7}
VIDEO = {"duration": 5, "resolution": "720p", "ratio": "16:9"}
TYPICAL = {
    "text_to_image": {"width": 1024, "height": 1536},
    # six refs: more than most edit models accept, so the cap is exercised too
    "image_edit": {"images": [IMG.format(i) for i in range(6)], "width": 1024, "height": 1024},
    "text_to_video": VIDEO,
    "image_to_video": {**VIDEO, "image": IMG.format(0)},
}
GENERIC = {"image": IMG.format(0), "video": "https://example.com/in.mp4", "audio": "https://example.com/in.mp3",
           "text": "hello there", "duration": 5, "width": 1024, "height": 1024}

CASES = [(f, m) for f, c in CURATED.items() for m in c["models"] + c.get("more", [])]


def _schema(mid):
    return FIXTURE[mid]["api_schema"]["api_schemas"][0]["request_schema"]


def _valid(key, value, spec):
    if spec.get("enum"):
        return value in spec["enum"]
    if spec.get("type") in ("integer", "number"):
        lo, hi = spec.get("minimum"), spec.get("maximum")
        return isinstance(value, (int, float)) and (lo is None or value >= lo) and (hi is None or value <= hi)
    if spec.get("type") == "array":
        return isinstance(value, list) and (spec.get("maxItems") is None or len(value) <= spec["maxItems"])
    if spec.get("type") == "string":
        return isinstance(value, str)
    return True


@pytest.mark.parametrize("feature,mid", CASES)
def test_payload_valid_against_schema(feature, mid):
    schema = _schema(mid)
    props = schema.get("properties") or {}
    inputs = {**BASE, **(TYPICAL.get(feature) or GENERIC)}
    try:
        payload = asyncio.run(wavespeed.build_payload(None, schema, inputs))
    except wavespeed.WaveSpeedError as e:
        # only acceptable for families outside the typical inputs (e.g. a mask-only tool): never for image/video
        assert feature not in TYPICAL, f"{mid}: {e}"
        pytest.skip(f"{feature} needs inputs beyond the generic set: {e}")
    for k in schema.get("required") or []:
        assert k in payload, f"{mid}: required {k} missing"
    for k, v in payload.items():
        assert k in props, f"{mid}: {k} not in schema"
        assert _valid(k, v, props[k]), f"{mid}: {k}={v!r} invalid for {props[k]}"


@pytest.mark.parametrize("mid", CURATED["image_edit"]["models"] + CURATED["image_edit"].get("more", []))
def test_extra_refs_are_dropped_not_errored(mid):
    schema = _schema(mid)
    payload = asyncio.run(wavespeed.build_payload(None, schema, {**BASE, "images": [IMG.format(i) for i in range(20)]}))
    cap = (schema["properties"].get("images") or {}).get("maxItems")
    sent = payload.get("images") or [payload.get("image")]
    assert sent[0] == IMG.format(0)
    if cap:
        assert sent == [IMG.format(i) for i in range(cap)]
