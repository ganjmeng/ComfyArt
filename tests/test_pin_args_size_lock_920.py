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

import pytest

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
