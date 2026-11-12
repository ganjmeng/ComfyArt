"""portrait-studio Sunburst edit pin (Angela 07:27 / Lovart 7fc60c86).

Lovart's official same-input baseline (review-assets
7fc60c86a25765e778614fd8d608dfe8deaab166, 911/lovart-ai/portrait-studio)
used GPT Image 2.6 Sunburst and produced 3 images at 1536×2048. This skill
is pinned to openai/gpt-image-2.6-sunburst/edit only (feature image_edit,
resolution 2k, ratio 3:4). There is no text-to-image / edit_model split
and no t2i path. It is not added to _PIN_KEEPS_SIZE or EXACT_SKILLS.

Ratio-only (and pin-supplied) requests submit resolution 2k + aspect_ratio
3:4. Sunburst has no size/width/height params; 2k 3:4 natively outputs
1664×2224, not 1536×2048. No-ref behavior (ask the user to upload; do not
reject and do not fall back to t2i), the three-question card, and the
default count of 3 are left to a later flow PR.

No WaveSpeed call. $0 static.
"""
from __future__ import annotations

import json
from pathlib import Path

from test_pin_args_size_lock_920 import assert_sunburst_2k, _pipeline

ROOT = Path(__file__).resolve().parent.parent
AUTO_MODELS = ROOT / "api/auto_models.json"

SUNBURST_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"

EXPECTED_PORTRAIT_STUDIO_PIN = {
    "feature": "image_edit",
    "model": SUNBURST_EDIT,
    "resolution": "2k",
    "ratio": "3:4",
    "zh": "portrait-studio 技能固定用 GPT Image 2.6 Sunburst 编辑（2K，3:4）",
    "en": "the portrait-studio skill is pinned to GPT Image 2.6 Sunburst edit at 2K 3:4",
}


def test_portrait_studio_with_ref_routes_sunburst_edit():
    """A reference or base routes to openai/gpt-image-2.6-sunburst/edit.

    The pin has no t2i / edit_model split. portrait-studio is not in
    EXACT_SKILLS or _PIN_KEEPS_SIZE, so a missing ref is not refused here
    (flow PR) and incoming pixels still drop.
    """
    from ComfyArt.api.mcp_tools import canvas
    from ComfyArt.api.skill_size import EXACT_SKILLS

    skills = json.loads(AUTO_MODELS.read_text(encoding="utf-8")).get("skills") or {}
    assert skills["portrait-studio"] == EXPECTED_PORTRAIT_STUDIO_PIN
    assert skills["portrait-studio"]["model"] == SUNBURST_EDIT
    assert skills["portrait-studio"]["feature"] == "image_edit"
    assert skills["portrait-studio"]["resolution"] == "2k"
    assert skills["portrait-studio"]["ratio"] == "3:4"
    assert "edit_model" not in skills["portrait-studio"]
    assert skills["portrait-studio"]["model"] != SUNBURST_T2I
    assert "text-to-image" not in skills["portrait-studio"]["model"]
    assert "portrait-studio" not in EXACT_SKILLS
    assert "portrait-studio" not in canvas._PIN_KEEPS_SIZE
    assert "portrait-studio" in canvas._RATIO_ONLY_2K_SKILLS

    with_ref = {
        "prompt": "professional portrait set from this photo",
        "skill": "portrait-studio",
        "refs": ["shape:model"],
        "ratio": "3:4",
    }
    c = canvas._auto_choice("generate_image", dict(with_ref))
    assert c["model"] == c["edit_model"] == SUNBURST_EDIT
    assert c["category"] == "skill"
    assert c.get("resolution") == "2k"
    assert c.get("ratio") == "3:4"
    pinned = canvas._pin_args(dict(with_ref), c)
    assert pinned["edit_model"] == SUNBURST_EDIT
    assert pinned.get("model") != SUNBURST_T2I
    assert pinned["edit_resolution"] == "2k"
    assert pinned["ratio"] == "3:4"

    with_base = {
        "prompt": "professional portrait set from this photo",
        "skill": "portrait-studio",
        "base": "shape:base",
        "ratio": "3:4",
    }
    c = canvas._auto_choice("generate_image", dict(with_base))
    assert c["model"] == c["edit_model"] == SUNBURST_EDIT
    assert c["category"] == "skill"
    pinned = canvas._pin_args(dict(with_base), c)
    assert pinned["edit_model"] == SUNBURST_EDIT
    assert pinned.get("model") != SUNBURST_T2I

    # No-ref is not a need_person_photo refusal in this PR (not EXACT_SKILLS).
    no_ref = {"prompt": "professional portrait set from this photo", "skill": "portrait-studio"}
    assert canvas._exact_skill_missing_ref(no_ref) is False
    c = canvas._auto_choice("generate_image", dict(no_ref))
    assert (c or {}).get("category") != "need_person_photo"
    assert (c or {}).get("model") != SUNBURST_T2I


def test_portrait_studio_request_body_is_2k_3x4_no_pixels():
    """Submitted Sunburst payload is resolution 2k + aspect_ratio 3:4.

    Lovart review-assets 7fc60c86a25765e778614fd8d608dfe8deaab166
    (911/lovart-ai/portrait-studio) used GPT Image 2.6 Sunburst at
    1536×2048. WaveSpeed Sunburst has no size/width/height; 2k 3:4
    natively outputs 1664×2224. The payload must not invent those pixels.
    """
    from ComfyArt.api.mcp_tools import canvas

    for refk in ("refs", "base"):
        category, got = _pipeline("portrait-studio", refk, {"ratio": "3:4"})
        assert category == "skill"
        assert got["edit_model"] == SUNBURST_EDIT
        assert got["edit_resolution"] == "2k"
        assert got["ratio"] == "3:4"
        assert "width" not in got and "height" not in got
        assert "size" not in got
        assert_sunburst_2k(got, "3:4")

        # Incoming pixels drop (not in _PIN_KEEPS_SIZE); pin still supplies 2k 3:4.
        category, got = _pipeline(
            "portrait-studio", refk, {"ratio": "3:4", "width": 1536, "height": 2048}
        )
        assert category == "skill"
        assert "width" not in got and "height" not in got
        assert got["edit_resolution"] == "2k"
        assert got["ratio"] == "3:4"
        assert_sunburst_2k(got, "3:4")
        assert "portrait-studio" not in canvas._PIN_KEEPS_SIZE
