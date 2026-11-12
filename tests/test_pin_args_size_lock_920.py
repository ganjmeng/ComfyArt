"""#920: lock ai-model and pose-fission sizing to main d3f5ca4b.

#920 changes ``canvas._pin_args`` so the clothing-swap and studio-model
Sunburst pins keep the width/height apply_generate set (image-1-following
3:4 1536×2048). That change must not reach ai-model (accepted on d3f5ca4b) or
pose-fission (pin names 2k 3:4).

EXPECTED was captured by running the d3f5ca4b code (detached worktree at
d3f5ca4b2c76b591cda812746a0b55df6fcc0ba7) through the same pipeline as
``_pipeline`` below: ``apply_generate`` -> ``_auto_choice`` -> ``_pin_args``
(only for a ``skill`` / ``skill_fallback`` choice). Every size-related key is
compared, including absence (main drops width/height/size_lock for ai-model).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from ComfyArt.api import wavespeed

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json").read_text(encoding="utf-8"))
SUNBURST_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"

MAIN_SHA = "d3f5ca4b2c76b591cda812746a0b55df6fcc0ba7"
SIZE_KEYS = ("model", "edit_model", "auto_model", "width", "height", "ratio", "size_lock",
             "size_candidates", "edit_resolution", "resolution", "count")

# (skill, reference kind, size args passed in, choice category on main, pinned args on main)
EXPECTED = [
    ('ai-model', 'base', {}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit'}),
    ('ai-model', 'base', {'height': 2048, 'ratio': '3:4', 'width': 1536}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit', 'ratio': '3:4'}),
    ('ai-model', 'base', {'height': 1024, 'ratio': '1:1', 'width': 1024}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit', 'ratio': '1:1'}),
    ('ai-model', 'base', {'height': 1152, 'ratio': '16:9', 'width': 2048}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit', 'ratio': '16:9'}),
    ('ai-model', 'base', {'ratio': '3:4'}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit', 'ratio': '3:4'}),
    ('ai-model', 'base', {'height': 1536, 'width': 1024}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit'}),
    ('ai-model', 'base', {'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit', 'ratio': '3:4'}),
    ('ai-model', 'none', {}, 'skill', {'auto_model': True, 'model': 'openai/gpt-image-2.6-sunburst/text-to-image'}),
    ('ai-model', 'none', {'height': 2048, 'ratio': '3:4', 'width': 1536}, 'skill', {'auto_model': True, 'model': 'openai/gpt-image-2.6-sunburst/text-to-image', 'ratio': '3:4'}),
    ('ai-model', 'none', {'height': 1024, 'ratio': '1:1', 'width': 1024}, 'skill', {'auto_model': True, 'model': 'openai/gpt-image-2.6-sunburst/text-to-image', 'ratio': '1:1'}),
    ('ai-model', 'none', {'height': 1152, 'ratio': '16:9', 'width': 2048}, 'skill', {'auto_model': True, 'model': 'openai/gpt-image-2.6-sunburst/text-to-image', 'ratio': '16:9'}),
    ('ai-model', 'none', {'ratio': '3:4'}, 'skill', {'auto_model': True, 'model': 'openai/gpt-image-2.6-sunburst/text-to-image', 'ratio': '3:4'}),
    ('ai-model', 'none', {'height': 1536, 'width': 1024}, 'skill', {'auto_model': True, 'model': 'openai/gpt-image-2.6-sunburst/text-to-image'}),
    ('ai-model', 'none', {'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}, 'skill', {'auto_model': True, 'model': 'openai/gpt-image-2.6-sunburst/text-to-image', 'ratio': '3:4'}),
    ('ai-model', 'refs', {}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit'}),
    ('ai-model', 'refs', {'height': 2048, 'ratio': '3:4', 'width': 1536}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit', 'ratio': '3:4'}),
    ('ai-model', 'refs', {'height': 1024, 'ratio': '1:1', 'width': 1024}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit', 'ratio': '1:1'}),
    ('ai-model', 'refs', {'height': 1152, 'ratio': '16:9', 'width': 2048}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit', 'ratio': '16:9'}),
    ('ai-model', 'refs', {'ratio': '3:4'}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit', 'ratio': '3:4'}),
    ('ai-model', 'refs', {'height': 1536, 'width': 1024}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit'}),
    ('ai-model', 'refs', {'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}, 'skill', {'edit_model': 'openai/gpt-image-2.6-sunburst/edit', 'ratio': '3:4'}),
    ('pose-fission', 'base', {}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'base', {'height': 2048, 'ratio': '3:4', 'width': 1536}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'base', {'height': 1024, 'ratio': '1:1', 'width': 1024}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'base', {'height': 1152, 'ratio': '16:9', 'width': 2048}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'base', {'ratio': '3:4'}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'base', {'height': 1536, 'width': 1024}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'base', {'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'none', {}, 'need_person_photo', {'count': 1, 'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}),
    ('pose-fission', 'none', {'height': 2048, 'ratio': '3:4', 'width': 1536}, 'need_person_photo', {'count': 1, 'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}),
    ('pose-fission', 'none', {'height': 1024, 'ratio': '1:1', 'width': 1024}, 'need_person_photo', {'count': 1, 'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}),
    ('pose-fission', 'none', {'height': 1152, 'ratio': '16:9', 'width': 2048}, 'need_person_photo', {'count': 1, 'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}),
    ('pose-fission', 'none', {'ratio': '3:4'}, 'need_person_photo', {'count': 1, 'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}),
    ('pose-fission', 'none', {'height': 1536, 'width': 1024}, 'need_person_photo', {'count': 1, 'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}),
    ('pose-fission', 'none', {'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}, 'need_person_photo', {'count': 1, 'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}),
    ('pose-fission', 'refs', {}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'refs', {'height': 2048, 'ratio': '3:4', 'width': 1536}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'refs', {'height': 1024, 'ratio': '1:1', 'width': 1024}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'refs', {'height': 1152, 'ratio': '16:9', 'width': 2048}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'refs', {'ratio': '3:4'}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'refs', {'height': 1536, 'width': 1024}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
    ('pose-fission', 'refs', {'height': 2048, 'ratio': '3:4', 'size_lock': True, 'width': 1536}, 'skill', {'count': 1, 'edit_model': 'google/nano-banana-pro/edit', 'edit_resolution': '2k', 'ratio': '3:4'}),
]


def _pipeline(skill: str, refk: str, size: dict) -> tuple[str | None, dict]:
    from ComfyArt.api.mcp_tools import canvas
    from ComfyArt.bot.skill_output import apply_generate

    args = {"prompt": "p", "skill": skill, **size}
    if refk == "refs":
        args["refs"] = ["shape:r1"]
    if refk == "base":
        args["base"] = "shape:b"
    args = apply_generate(args)
    choice = canvas._auto_choice("generate_image", dict(args))
    category = choice and choice.get("category")
    out = canvas._pin_args(dict(args), choice) if category in ("skill", "skill_fallback") else args
    return category, {k: out[k] for k in SIZE_KEYS if k in out}


def _sunburst_schema(mid: str) -> dict:
    return FIXTURE[mid]["api_schema"]["api_schemas"][0]["request_schema"]


def sunburst_submitted_payload(pinned: dict) -> dict:
    """WaveSpeed payload for a Sunburst pin. Maps edit_resolution → resolution.

    Width/height are forwarded only when _pin_args kept an explicit canvas
    (studio-model / clothing-swap). Ratio-only 2k fill must not invent pixels:
    Sunburst has no size/width/height, only aspect_ratio + resolution.
    """
    mid = pinned.get("edit_model") or pinned.get("model")
    inputs = {"prompt": "x"}
    if pinned.get("ratio"):
        inputs["ratio"] = pinned["ratio"]
    res = pinned.get("edit_resolution") or pinned.get("resolution")
    if res:
        inputs["resolution"] = res
    if pinned.get("width") and pinned.get("height"):
        inputs["width"] = pinned["width"]
        inputs["height"] = pinned["height"]
    return asyncio.run(wavespeed.build_payload(None, _sunburst_schema(mid), inputs, mid))


def assert_sunburst_2k(pinned: dict, aspect: str) -> None:
    mid = pinned.get("edit_model") or pinned.get("model")
    assert mid in (SUNBURST_T2I, SUNBURST_EDIT)
    props = (_sunburst_schema(mid).get("properties") or {})
    assert "size" not in props and "width" not in props and "height" not in props
    payload = sunburst_submitted_payload(pinned)
    assert payload.get("resolution") == "2k"
    assert payload.get("aspect_ratio") == aspect
    assert "size" not in payload and "width" not in payload and "height" not in payload


@pytest.mark.parametrize("skill,refk,size,category,pinned", EXPECTED,
                         ids=[f"{s}-{r}-{i}" for i, (s, r, *_rest) in enumerate(EXPECTED)])
def test_pin_args_size_matches_main_d3f5ca4b(skill, refk, size, category, pinned):
    got_category, got = _pipeline(skill, refk, dict(size))
    assert got_category == category
    assert got == pinned


def test_ai_model_pin_drops_width_height_size_lock_like_main():
    """ai-model keeps only ratio; pixels and size_lock are dropped exactly as on d3f5ca4b."""
    for refk in ("none", "refs", "base"):
        _, got = _pipeline("ai-model", refk, {"ratio": "3:4", "width": 1536, "height": 2048, "size_lock": True})
        assert "width" not in got and "height" not in got and "size_lock" not in got
        assert got["ratio"] == "3:4"


def test_pose_fission_pin_stays_2k_3x4():
    for refk in ("refs", "base"):
        for size in ({}, {"ratio": "1:1", "width": 1024, "height": 1024}, {"ratio": "16:9", "width": 2048, "height": 1152}):
            _, got = _pipeline("pose-fission", refk, dict(size))
            assert got["edit_model"] == "google/nano-banana-pro/edit"
            assert (got["edit_resolution"], got["ratio"]) == ("2k", "3:4")
            assert "width" not in got and "height" not in got and "size_lock" not in got


def test_only_clothing_swap_and_studio_model_keep_canvas():
    from ComfyArt.api.mcp_tools import canvas

    assert canvas._PIN_KEEPS_SIZE == frozenset({"clothing-swap", "studio-model"})
    _, got = _pipeline("studio-model", "refs", {"ratio": "3:4", "width": 1536, "height": 2048})
    assert got["edit_model"] == "openai/gpt-image-2.6-sunburst/edit"
    assert (got["width"], got["height"], got["ratio"]) == (1536, 2048, "3:4")
    _, got = _pipeline("studio-model", "none", {"ratio": "3:4", "width": 1536, "height": 2048})
    assert got["model"] == "openai/gpt-image-2.6-sunburst/text-to-image"
    assert (got["width"], got["height"], got["ratio"]) == (1536, 2048, "3:4")
    _, got = _pipeline("clothing-swap", "refs", {})
    assert got["edit_model"] == "openai/gpt-image-2.6-sunburst/edit"
    assert (got["width"], got["height"], got["ratio"], got["size_lock"]) == (1536, 2048, "3:4", True)



def test_studio_model_ratio_only_fills_2k_aspect_ratio():
    """Ratio-only studio-model (no width/height/resolution) fills resolution 2k.

    The submitted Sunburst payload is resolution 2k + aspect_ratio 3:4, not
    exact pixels. 2k 3:4 natively outputs 1664×2224, not 1536×2048. EXPECTED
    above stays the d3f5ca4b capture for ai-model and pose-fission and is not
    edited. The keep-canvas cases in
    test_only_clothing_swap_and_studio_model_keep_canvas already pass an
    explicit 1536×2048, so they are unchanged.
    """
    for refk, model_key, model_id in (
        ("none", "model", SUNBURST_T2I),
        ("refs", "edit_model", SUNBURST_EDIT),
        ("base", "edit_model", SUNBURST_EDIT),
    ):
        _, got = _pipeline("studio-model", refk, {"ratio": "3:4"})
        assert got[model_key] == model_id
        assert got["edit_resolution"] == "2k"
        assert got["ratio"] == "3:4"
        assert "width" not in got and "height" not in got
        assert_sunburst_2k(got, "3:4")


def test_studio_model_explicit_size_untouched():
    """An explicit width/height/resolution on studio-model is not rewritten."""
    # 3:4 1536×2048 already set: pixels stay, and 2k is not injected (the
    # 2048 long side already maps to 2k on submit).
    _, got = _pipeline("studio-model", "none", {"ratio": "3:4", "width": 1536, "height": 2048})
    assert (got["width"], got["height"], got["ratio"]) == (1536, 2048, "3:4")
    assert "edit_resolution" not in got
    assert got["model"] == SUNBURST_T2I
    assert_sunburst_2k(got, "3:4")

    # A non-default explicit canvas must stay as given.
    _, got = _pipeline("studio-model", "refs", {"ratio": "1:1", "width": 1024, "height": 1024})
    assert (got["width"], got["height"], got["ratio"]) == (1024, 1024, "1:1")
    assert "edit_resolution" not in got
    assert got["edit_model"] == "openai/gpt-image-2.6-sunburst/edit"

    # Pixels only, no ratio: still untouched, no 2k fill.
    _, got = _pipeline("studio-model", "none", {"width": 1024, "height": 1536})
    assert (got["width"], got["height"]) == (1024, 1536)
    assert "ratio" not in got
    assert "edit_resolution" not in got


def test_ratio_only_2k_fill_does_not_change_other_skills():
    """ai-model, pose-fission, and clothing-swap are unchanged by the 2k fill.

    product-to-packaging is not in _PIN_KEEPS_SIZE (incoming pixels still drop)
    but it does get the ratio-only 2k fill; that is locked in
    test_product_to_packaging_ratio_only_fills_2k_both_ratios.
    """
    from ComfyArt.api.mcp_tools import canvas

    assert "product-to-packaging" not in canvas._PIN_KEEPS_SIZE
    assert "cover-design-director" not in canvas._PIN_KEEPS_SIZE
    assert "youtube-channel-banner" not in canvas._PIN_KEEPS_SIZE
    assert "portrait-studio" not in canvas._PIN_KEEPS_SIZE
    assert canvas._PIN_KEEPS_SIZE == frozenset({"clothing-swap", "studio-model"})
    assert canvas._RATIO_ONLY_2K_SKILLS == frozenset(
        {"studio-model", "product-to-packaging", "cover-design-director", "youtube-channel-banner", "portrait-studio"}
    )

    # ai-model ratio-only still has no 2k fill and no invented pixels (d3f5ca4b).
    _, got = _pipeline("ai-model", "none", {"ratio": "3:4"})
    assert got == {"auto_model": True, "model": "openai/gpt-image-2.6-sunburst/text-to-image", "ratio": "3:4"}

    # pose-fission still comes from its own pin (2k 3:4), not this fill.
    _, got = _pipeline("pose-fission", "refs", {"ratio": "3:4"})
    assert (got["edit_resolution"], got["ratio"]) == ("2k", "3:4")
    assert "width" not in got and "height" not in got

    # clothing-swap without a passed size still follows apply_generate (1536×2048),
    # not the ratio-only 2k fill (no edit_resolution injected).
    _, got = _pipeline("clothing-swap", "refs", {})
    assert (got["width"], got["height"], got["ratio"], got["size_lock"]) == (1536, 2048, "3:4", True)
    assert "edit_resolution" not in got



def test_cover_design_director_ratio_only_fills_2k_aspect_ratio():
    """Ratio-only cover-design-director (no width/height/resolution) fills 2k.

    The submitted Sunburst payload is resolution 2k + aspect_ratio 16:9, not
    exact pixels (Lovart review-assets 98af4eee used 16:9 at 2k). The skill is
    not in _PIN_KEEPS_SIZE. This fill is the same ratio-only path as studio-model.
    """
    from ComfyArt.api.mcp_tools import canvas

    assert "cover-design-director" not in canvas._PIN_KEEPS_SIZE
    assert canvas._PIN_KEEPS_SIZE == frozenset({"clothing-swap", "studio-model"})
    assert "cover-design-director" in canvas._RATIO_ONLY_2K_SKILLS

    for refk, model_key, model_id in (
        ("none", "model", SUNBURST_T2I),
        ("refs", "edit_model", SUNBURST_EDIT),
        ("base", "edit_model", SUNBURST_EDIT),
    ):
        _, got = _pipeline("cover-design-director", refk, {"ratio": "16:9"})
        assert got[model_key] == model_id
        assert got["edit_resolution"] == "2k"
        assert got["ratio"] == "16:9"
        assert "width" not in got and "height" not in got
        assert_sunburst_2k(got, "16:9")


def test_product_to_packaging_ratio_only_fills_2k_both_ratios():
    """Ratio-only product-to-packaging fills resolution 2k (Lovart e304e2fa7).

    The Lovart same-input run used 3:4 and 4:3 at 2k. The skill is not in
    _PIN_KEEPS_SIZE; the fill runs after incoming pixels are dropped. The
    submitted payload is resolution 2k + the given aspect_ratio, not exact
    pixels (2k 3:4 natively outputs 1664×2224).
    """
    from ComfyArt.api.mcp_tools import canvas

    assert "product-to-packaging" not in canvas._PIN_KEEPS_SIZE
    assert "product-to-packaging" in canvas._RATIO_ONLY_2K_SKILLS

    cases = (
        ("none", "model", SUNBURST_T2I, "3:4"),
        ("refs", "edit_model", SUNBURST_EDIT, "3:4"),
        ("base", "edit_model", SUNBURST_EDIT, "3:4"),
        ("none", "model", SUNBURST_T2I, "4:3"),
        ("refs", "edit_model", SUNBURST_EDIT, "4:3"),
        ("base", "edit_model", SUNBURST_EDIT, "4:3"),
    )
    for refk, model_key, model_id, ratio in cases:
        _, got = _pipeline("product-to-packaging", refk, {"ratio": ratio})
        assert got[model_key] == model_id
        assert got["edit_resolution"] == "2k"
        assert got["ratio"] == ratio
        assert "width" not in got and "height" not in got
        assert_sunburst_2k(got, ratio)


def test_youtube_channel_banner_ratio_only_fills_2k_aspect_ratio():
    """Ratio-only youtube-channel-banner fills resolution 2k (Lovart d7672d03).

    Both Sunburst artifacts in the same-input run were 16:9 at 2k
    (review-assets 911/lovart-ai/youtube-channel-banner/). The skill is not
    in _PIN_KEEPS_SIZE; the fill runs after incoming pixels are dropped.
    The submitted payload is resolution 2k + aspect_ratio 16:9, not exact
    pixels. Card / direction-board / final-text flow is not changed here.
    """
    from ComfyArt.api.mcp_tools import canvas

    assert "youtube-channel-banner" not in canvas._PIN_KEEPS_SIZE
    assert "youtube-channel-banner" in canvas._RATIO_ONLY_2K_SKILLS

    for refk, model_key, model_id in (
        ("none", "model", SUNBURST_T2I),
        ("refs", "edit_model", SUNBURST_EDIT),
        ("base", "edit_model", SUNBURST_EDIT),
    ):
        _, got = _pipeline("youtube-channel-banner", refk, {"ratio": "16:9"})
        assert got[model_key] == model_id
        assert got["edit_resolution"] == "2k"
        assert got["ratio"] == "16:9"
        assert "width" not in got and "height" not in got
        assert_sunburst_2k(got, "16:9")


def test_portrait_studio_ratio_only_fills_2k_aspect_ratio():
    """Ratio-only portrait-studio fills resolution 2k + 3:4 (Lovart 7fc60c86).

    Lovart baseline review-assets 7fc60c86a25765e778614fd8d608dfe8deaab166
    (911/lovart-ai/portrait-studio) used GPT Image 2.6 Sunburst and produced
    3 images at 1536×2048. The skill is pinned to
    openai/gpt-image-2.6-sunburst/edit only (no t2i / edit_model split) at
    resolution 2k and ratio 3:4. It is not in _PIN_KEEPS_SIZE; incoming
    pixels drop and the pin supplies 2k + 3:4. The submitted payload is
    resolution 2k + aspect_ratio 3:4, not exact pixels (native 2k 3:4 is
    1664×2224). No-ref behavior, cards, and default count are not changed
    here (later flow PR).
    """
    from ComfyArt.api.mcp_tools import canvas

    assert "portrait-studio" not in canvas._PIN_KEEPS_SIZE
    assert "portrait-studio" in canvas._RATIO_ONLY_2K_SKILLS

    for refk in ("refs", "base"):
        _, got = _pipeline("portrait-studio", refk, {"ratio": "3:4"})
        assert got["edit_model"] == SUNBURST_EDIT
        assert got.get("model") != SUNBURST_T2I
        assert got["edit_resolution"] == "2k"
        assert got["ratio"] == "3:4"
        assert "width" not in got and "height" not in got
        assert_sunburst_2k(got, "3:4")

        # The pin names ratio 3:4, so a different incoming ratio is overwritten.
        _, got = _pipeline("portrait-studio", refk, {"ratio": "16:9"})
        assert got["edit_resolution"] == "2k"
        assert got["ratio"] == "3:4"
        assert "width" not in got and "height" not in got
        assert_sunburst_2k(got, "3:4")


# --- feat/packaging-sunburst-2k: lock the product-to-packaging / studio-model pins and 2k sizing ---
# Lovart baseline review-assets e304e2fa7d22fc6c560d3ba1cb628423f03ebc46
# (911/lovart-ai/product-to-packaging): GPT Image 2.6 Sunburst, 4 outputs,
# result-01 1536×2048 (3:4), result-02..04 2048×1536 (4:3).

AUTO_MODELS = Path(__file__).resolve().parent.parent / "api" / "auto_models.json"


def _sunburst_ratios() -> list[str]:
    a = (_sunburst_schema(SUNBURST_T2I)["properties"]["aspect_ratio"]["enum"])
    b = (_sunburst_schema(SUNBURST_EDIT)["properties"]["aspect_ratio"]["enum"])
    assert a == b
    return list(a)


def test_packaging_and_studio_model_pins_use_full_sunburst_ids():
    skills = json.loads(AUTO_MODELS.read_text(encoding="utf-8"))["skills"]
    for skill in ("studio-model", "product-to-packaging"):
        row = skills[skill]
        assert row["model"] == SUNBURST_T2I
        assert row["edit_model"] == SUNBURST_EDIT
        assert row["feature"] == "text_to_image"
        # The pin row names no size; 2k comes from the ratio-only fill.
        assert "resolution" not in row and "ratio" not in row and "fallback" not in row


def test_lovart_packaging_ratios_fill_2k_on_sunburst():
    """Lovart e304e2fa: 3:4 anchor + 4:3 extensions, both at 2k (1536×2048 / 2048×1536 on Lovart)."""
    assert {"3:4", "4:3"} <= set(_sunburst_ratios())
    for ratio in ("3:4", "4:3"):
        for refk, model_key, model_id in (("none", "model", SUNBURST_T2I),
                                          ("refs", "edit_model", SUNBURST_EDIT),
                                          ("base", "edit_model", SUNBURST_EDIT)):
            for skill in ("product-to-packaging", "studio-model"):
                category, got = _pipeline(skill, refk, {"ratio": ratio})
                assert category == "skill"
                assert got[model_key] == model_id
                assert (got["edit_resolution"], got["ratio"]) == ("2k", ratio)
                assert "width" not in got and "height" not in got and "size_lock" not in got
                assert_sunburst_2k(got, ratio)


@pytest.mark.parametrize("ratio", _sunburst_ratios())
def test_packaging_and_studio_model_any_sunburst_ratio_fills_2k(ratio):
    """Every aspect ratio the Sunburst schema accepts goes out as resolution 2k + that ratio."""
    for skill in ("product-to-packaging", "studio-model"):
        for refk in ("none", "refs"):
            _, got = _pipeline(skill, refk, {"ratio": ratio})
            assert (got["edit_resolution"], got["ratio"]) == ("2k", ratio)
            assert "width" not in got and "height" not in got
            assert_sunburst_2k(got, ratio)


def test_4x3_fill_does_not_reach_other_skills():
    """4:3 ratio-only: ai-model gets no 2k, pose-fission keeps its own 2k 3:4 pin."""
    from ComfyArt.api.mcp_tools import canvas

    assert canvas._PIN_KEEPS_SIZE == frozenset({"clothing-swap", "studio-model"})
    _, got = _pipeline("ai-model", "none", {"ratio": "4:3"})
    assert got == {"auto_model": True, "model": SUNBURST_T2I, "ratio": "4:3"}
    _, got = _pipeline("ai-model", "refs", {"ratio": "4:3"})
    assert got == {"edit_model": SUNBURST_EDIT, "ratio": "4:3"}
    _, got = _pipeline("pose-fission", "refs", {"ratio": "4:3"})
    assert (got["edit_model"], got["edit_resolution"], got["ratio"]) == ("google/nano-banana-pro/edit", "2k", "3:4")


def test_models_doc_lists_full_pin_ids_matching_auto_models():
    skills = json.loads(AUTO_MODELS.read_text(encoding="utf-8"))["skills"]
    root = Path(__file__).resolve().parent.parent / "docs-site"
    for doc in (root / "guides" / "models.mdx", root / "zh" / "guides" / "models.mdx"):
        text = doc.read_text(encoding="utf-8")
        for skill in ("studio-model", "product-to-packaging"):
            line = next(ln for ln in text.splitlines() if ln.startswith(f"| {skill} |"))
            assert f"`{skills[skill]['model']}`" in line
            assert f"`{skills[skill]['edit_model']}`" in line
