"""cover-design-director Sunburst pin (Angela 07:27 / Lovart 98af4eee).

Lovart's official same-input run (review-assets 98af4eeea2bf3c206d6a73154da4236acaea5e42,
911/lovart-ai/cover-design-director/) used GPT Image 2.6 Sunburst and produced
one 16:9 2k image (no reference). This skill is pinned the same way as
studio-model: text-to-image with no reference, edit when a reference or base is
given. Ratio-only calls fill resolution 2k + aspect_ratio 16:9 (Sunburst has no
size/width/height params). It is not added to _PIN_KEEPS_SIZE. Instructions,
cards, and rules are not changed here.

No WaveSpeed call. $0 static.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTO_MODELS = ROOT / "api/auto_models.json"

SUNBURST_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"

EXPECTED_COVER_DESIGN_DIRECTOR_PIN = {
    "feature": "text_to_image",
    "model": SUNBURST_T2I,
    "edit_model": SUNBURST_EDIT,
    "zh": "cover-design-director 技能固定用 GPT Image 2.6 Sunburst（无参考文生，有参考编辑）",
    "en": "the cover-design-director skill is pinned to GPT Image 2.6 Sunburst (text-to-image with no reference, edit when a reference is given)",
}


def test_cover_design_director_routes_sunburst_t2i_or_edit():
    """No ref → text-to-image; a reference or base → edit. Not in _PIN_KEEPS_SIZE."""
    from ComfyArt.api.mcp_tools import canvas
    from ComfyArt.api.skill_size import EXACT_SKILLS

    skills = json.loads(AUTO_MODELS.read_text(encoding="utf-8")).get("skills") or {}
    assert skills["cover-design-director"] == EXPECTED_COVER_DESIGN_DIRECTOR_PIN
    assert skills["cover-design-director"]["model"] == SUNBURST_T2I
    assert skills["cover-design-director"]["edit_model"] == SUNBURST_EDIT
    assert "cover-design-director" not in EXACT_SKILLS
    assert "cover-design-director" not in canvas._PIN_KEEPS_SIZE

    no_ref = {"prompt": "YouTube thumbnail, 16:9", "skill": "cover-design-director", "ratio": "16:9"}
    c = canvas._auto_choice("generate_image", dict(no_ref))
    assert c["model"] == SUNBURST_T2I
    assert c["category"] == "skill"
    assert "edit_model" not in c
    pinned = canvas._pin_args(dict(no_ref), c)
    assert pinned["model"] == SUNBURST_T2I
    assert pinned.get("auto_model") is True
    assert "edit_model" not in pinned
    assert pinned["edit_resolution"] == "2k"
    assert pinned["ratio"] == "16:9"
    assert "width" not in pinned and "height" not in pinned

    with_ref = {**no_ref, "refs": ["shape:cover-ref"]}
    c = canvas._auto_choice("generate_image", dict(with_ref))
    assert c["model"] == c["edit_model"] == SUNBURST_EDIT
    assert c["category"] == "skill"
    pinned = canvas._pin_args(dict(with_ref), c)
    assert pinned["edit_model"] == SUNBURST_EDIT
    assert pinned.get("model") != SUNBURST_T2I
    assert pinned["edit_resolution"] == "2k"
    assert pinned["ratio"] == "16:9"
    assert "width" not in pinned and "height" not in pinned

    with_base = {"prompt": "YouTube thumbnail, 16:9", "skill": "cover-design-director", "base": "shape:base", "ratio": "16:9"}
    c = canvas._auto_choice("generate_image", dict(with_base))
    assert c["model"] == c["edit_model"] == SUNBURST_EDIT
    pinned = canvas._pin_args(dict(with_base), c)
    assert pinned["edit_model"] == SUNBURST_EDIT
    assert pinned.get("model") != SUNBURST_T2I
    assert pinned["edit_resolution"] == "2k"
    assert pinned["ratio"] == "16:9"
    assert "width" not in pinned and "height" not in pinned
