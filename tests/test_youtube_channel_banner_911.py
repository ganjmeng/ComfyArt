"""youtube-channel-banner Sunburst pin (Angela 07:27 / Lovart d7672d03).

Lovart's same-input run (review-assets d7672d038e6705b2399981c0bb775c5406c7460e,
911/lovart-ai/youtube-channel-banner/) used GPT Image 2.6 Sunburst and produced
16:9 2048×1152 images (direction board and no-text background; no reference
images were attached). This skill is pinned the same way as studio-model:
text-to-image with no reference, edit when a reference or base is given.
Ratio-only calls fill resolution 2k (16:9 → 2048×1152). It is not added to
_PIN_KEEPS_SIZE. The card, direction-board, and final-text flow are not
changed here (pending Angela).

No WaveSpeed call. $0 static.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTO_MODELS = ROOT / "api/auto_models.json"

SUNBURST_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"

EXPECTED_YOUTUBE_CHANNEL_BANNER_PIN = {
    "feature": "text_to_image",
    "model": SUNBURST_T2I,
    "edit_model": SUNBURST_EDIT,
    "zh": "youtube-channel-banner 技能固定用 GPT Image 2.6 Sunburst（无参考文生，有参考编辑）",
    "en": "the youtube-channel-banner skill is pinned to GPT Image 2.6 Sunburst (text-to-image with no reference, edit when a reference is given)",
}


def test_youtube_channel_banner_routes_sunburst_t2i_or_edit():
    """No ref → text-to-image; a reference or base → edit. Not in _PIN_KEEPS_SIZE."""
    from ComfyArt.api.mcp_tools import canvas
    from ComfyArt.api.skill_size import EXACT_SKILLS

    skills = json.loads(AUTO_MODELS.read_text(encoding="utf-8")).get("skills") or {}
    assert skills["youtube-channel-banner"] == EXPECTED_YOUTUBE_CHANNEL_BANNER_PIN
    assert skills["youtube-channel-banner"]["model"] == SUNBURST_T2I
    assert skills["youtube-channel-banner"]["edit_model"] == SUNBURST_EDIT
    assert "youtube-channel-banner" not in EXACT_SKILLS
    assert "youtube-channel-banner" not in canvas._PIN_KEEPS_SIZE

    no_ref = {"prompt": "YouTube channel banner, 16:9", "skill": "youtube-channel-banner", "ratio": "16:9"}
    c = canvas._auto_choice("generate_image", dict(no_ref))
    assert c["model"] == SUNBURST_T2I
    assert c["category"] == "skill"
    assert "edit_model" not in c
    pinned = canvas._pin_args(dict(no_ref), c)
    assert pinned["model"] == SUNBURST_T2I
    assert pinned.get("auto_model") is True
    assert "edit_model" not in pinned
    assert pinned["edit_resolution"] == "2k"
    assert (pinned["width"], pinned["height"], pinned["ratio"]) == (2048, 1152, "16:9")

    with_ref = {**no_ref, "refs": ["shape:banner-ref"]}
    c = canvas._auto_choice("generate_image", dict(with_ref))
    assert c["model"] == c["edit_model"] == SUNBURST_EDIT
    assert c["category"] == "skill"
    pinned = canvas._pin_args(dict(with_ref), c)
    assert pinned["edit_model"] == SUNBURST_EDIT
    assert pinned.get("model") != SUNBURST_T2I
    assert pinned["edit_resolution"] == "2k"
    assert (pinned["width"], pinned["height"], pinned["ratio"]) == (2048, 1152, "16:9")

    with_base = {
        "prompt": "YouTube channel banner, 16:9",
        "skill": "youtube-channel-banner",
        "base": "shape:base",
        "ratio": "16:9",
    }
    c = canvas._auto_choice("generate_image", dict(with_base))
    assert c["model"] == c["edit_model"] == SUNBURST_EDIT
    pinned = canvas._pin_args(dict(with_base), c)
    assert pinned["edit_model"] == SUNBURST_EDIT
    assert pinned.get("model") != SUNBURST_T2I
    assert (pinned["width"], pinned["height"], pinned["ratio"]) == (2048, 1152, "16:9")
