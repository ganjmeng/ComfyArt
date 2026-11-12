"""product-to-packaging Sunburst pin (Angela 07:27 / Lovart e304e2fa7).

Lovart's official same-input run (review-assets e304e2fa7d22fc6c560d3ba1cb628423f03ebc46,
911/lovart-ai/product-to-packaging/) used GPT Image 2.6 Sunburst. This skill is
pinned the same way as ai-model / studio-model: text-to-image with no reference,
edit when a reference or base is given. It is not added to _PIN_KEEPS_SIZE.

No WaveSpeed call. $0 static.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTO_MODELS = ROOT / "api/auto_models.json"

SUNBURST_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"

EXPECTED_PRODUCT_TO_PACKAGING_PIN = {
    "feature": "text_to_image",
    "model": SUNBURST_T2I,
    "edit_model": SUNBURST_EDIT,
    "zh": "product-to-packaging 技能固定用 GPT Image 2.6 Sunburst（无参考文生，有参考编辑）",
    "en": "the product-to-packaging skill is pinned to GPT Image 2.6 Sunburst (text-to-image with no reference, edit when a reference is given)",
}


def test_product_to_packaging_routes_sunburst_t2i_or_edit():
    """No ref → text-to-image; a reference or base → edit. Not in _PIN_KEEPS_SIZE."""
    from ComfyArt.api.mcp_tools import canvas
    from ComfyArt.api.skill_size import EXACT_SKILLS

    skills = json.loads(AUTO_MODELS.read_text(encoding="utf-8")).get("skills") or {}
    assert skills["product-to-packaging"] == EXPECTED_PRODUCT_TO_PACKAGING_PIN
    assert skills["product-to-packaging"]["model"] == SUNBURST_T2I
    assert skills["product-to-packaging"]["edit_model"] == SUNBURST_EDIT
    assert "product-to-packaging" not in EXACT_SKILLS
    assert "product-to-packaging" not in canvas._PIN_KEEPS_SIZE

    no_ref = {"prompt": "packaging system for this product", "skill": "product-to-packaging"}
    c = canvas._auto_choice("generate_image", dict(no_ref))
    assert c["model"] == SUNBURST_T2I
    assert c["category"] == "skill"
    assert "edit_model" not in c
    pinned = canvas._pin_args(dict(no_ref), c)
    assert pinned["model"] == SUNBURST_T2I
    assert pinned.get("auto_model") is True
    assert "edit_model" not in pinned

    with_ref = {**no_ref, "refs": ["shape:product"]}
    c = canvas._auto_choice("generate_image", dict(with_ref))
    assert c["model"] == c["edit_model"] == SUNBURST_EDIT
    assert c["category"] == "skill"
    pinned = canvas._pin_args(dict(with_ref), c)
    assert pinned["edit_model"] == SUNBURST_EDIT
    assert pinned.get("model") != SUNBURST_T2I

    with_base = {"prompt": "packaging system for this product", "skill": "product-to-packaging", "base": "shape:base"}
    c = canvas._auto_choice("generate_image", dict(with_base))
    assert c["model"] == c["edit_model"] == SUNBURST_EDIT
    pinned = canvas._pin_args(dict(with_base), c)
    assert pinned["edit_model"] == SUNBURST_EDIT
    assert pinned.get("model") != SUNBURST_T2I
