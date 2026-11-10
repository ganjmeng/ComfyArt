"""#868: Krea 2 Turbo is a WaveSpeed picker entry, not a local workflow."""
from __future__ import annotations

import json
from pathlib import Path

from ComfyArt.api import wavespeed

KREA = "wavespeed-ai/krea-v2/turbo"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())


def test_krea_turbo_is_curated_more_not_default():
    curated = wavespeed.load_curated()["text_to_image"]
    cfg = wavespeed.load_config()["features"]["text_to_image"]
    ids = [m["id"] for m in cfg["models"]]
    assert KREA in curated["more"]
    assert KREA not in curated["models"]
    assert KREA in ids
    assert "wavespeed-ai/krea-v2/turbo-lora" not in ids
    assert curated["default"] != KREA
    assert cfg["default"] != KREA
    entry = next(m for m in cfg["models"] if m["id"] == KREA)
    assert entry.get("local") == "Krea 2 Turbo"


def test_krea_turbo_display_and_vendor():
    d = wavespeed.display_of(KREA)
    assert d is not None
    assert d["name"] == "Krea 2 Turbo"
    assert d["blurb"]["zh"] == "8 步快速出图，擅长艺术风格和创意表现"
    assert d["blurb"]["en"] == "Fast 8-step generation, great for expressive, artistic styles"
    assert wavespeed.vendor_of(KREA) == "Krea"


def test_krea_turbo_not_sold_as_ref_in_catalog_caps():
    """Optional schema `image` is I2I; the fixture must not expose an `images` ref cap."""
    meta = FIXTURE[KREA]
    props = meta["api_schema"]["api_schemas"][0]["request_schema"]["properties"]
    assert "images" not in props
    assert "image" in props  # internal I2I only
    assert "loras" not in props


def test_no_local_krea_workflow_or_weights():
    assert not (ROOT / "workflows/krea2-turbo-t2i.api.json").exists()
    blob = "\n".join(p.read_text(errors="ignore") for p in [
        ROOT / "api/wavespeed_models.json",
        ROOT / "api/curated_models.json",
        ROOT / "src/models.ts",
    ])
    for needle in ("krea2_turbo_int8_convrot", "krea2-turbo-t2i.api.json"):
        assert needle not in blob
