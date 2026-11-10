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


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def test_krea_turbo_dropdown_only_not_auto_or_skill_pin():
    """#868 / product: Krea 2 Turbo is a user-selectable picker entry only.

    It must not enter Auto routing and must not become a skill pin or default.
    api/auto_models.json and src/skills.ts stay unchanged vs main for this PR.
    """
    auto_path = ROOT / "api/auto_models.json"
    skills_path = ROOT / "src/skills.ts"
    auto_text = auto_path.read_text(encoding="utf-8")
    skills_text = skills_path.read_text(encoding="utf-8")
    needles = (KREA, "krea-v2/turbo", "krea-v2/turbo-lora", "Krea 2 Turbo")
    for needle in needles:
        assert needle not in auto_text
        assert needle not in skills_text

    auto = json.loads(auto_text)
    for s in _walk_strings(auto):
        assert "krea" not in s.lower()

    # Skill pins / fallbacks in the Auto table (currently pose-fission only).
    for skill, row in (auto.get("skills") or {}).items():
        if skill.startswith("_") or not isinstance(row, dict):
            continue
        for key in ("model", "fallback", "default"):
            val = row.get(key)
            if val:
                assert val != KREA, f"skill {skill} {key} is pinned to Krea 2 Turbo"

    # Feature Auto defaults and category models.
    for feature, spec in (auto.get("features") or {}).items():
        if not isinstance(spec, dict):
            continue
        default = spec.get("default")
        if isinstance(default, str):
            assert default != KREA, f"features.{feature}.default is Krea 2 Turbo"
        for cat in spec.get("categories") or []:
            if isinstance(cat, dict):
                assert cat.get("model") != KREA, f"auto category {feature}/{cat.get('id')} uses Krea 2 Turbo"
        for section in ("multi_reference", "masked"):
            row = spec.get(section) or {}
            if isinstance(row, dict):
                assert row.get("model") != KREA and row.get("fallback") != KREA

    # Present in the user-selectable dropdown (curated more + assembled picker list).
    curated = wavespeed.load_curated()["text_to_image"]
    cfg = wavespeed.load_config()["features"]["text_to_image"]
    ids = [m["id"] for m in cfg["models"]]
    names = [m.get("name") or m.get("local") for m in cfg["models"]]
    assert KREA in curated["more"]
    assert KREA not in curated["models"]
    assert KREA in ids
    assert "Krea 2 Turbo" in names
    assert curated["default"] != KREA
    assert cfg["default"] != KREA
