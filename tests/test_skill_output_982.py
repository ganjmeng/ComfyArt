"""#982 — no-size fallback: no skill run may submit an undeclared canvas.

The $0 audit (#911 comment 6873212793) found `logo-material-explorer` and
`character-sheet-design` had no output declaration anywhere: `SKILL_OUTPUT`,
`bot/skill_output.py::OUTPUTS`, `run_hint` and the skill read `output` were all
empty. The model's `generate_image` therefore carried no width/height/ratio, the
page built a 1:1 card, and the provider schema default decided the delivered
pixels (the audit's mock returned 512x512).

This file locks the two product-minimal defaults plus the pipeline floor for every
other unpinned skill:
  logo-material-explorer: 1 x 1024x1024 (1:1), count=1. Additional Details may
  change the finish, never the count/frame.
  character-sheet-design: 8 templates x 1 sheet each, at each template's own
  media ratio (1:1 turnaround/outfit/prop/editorial, 16:9 expression/modeling/
  basic/technical), 1024x1024 or 2048x1152.
  every other unpinned skill without OUTPUTS: 1024x1024 (1:1), size-locked, until
  product rules its own default (#982 PR lists them).

The literals are deliberate: reverting a default to 512, or dropping the floor,
turns these red.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from ComfyArt.bot.skill_output import (
    CHARACTER_PRESETS_982,
    FALLBACK_OUTPUT_982,
    OUTPUTS,
    PRESET_PLAN_SKILLS,
    apply_generate,
    is_single,
    pixels_for_ratio,
    plan_for,
    preset_from_text,
    run_hint,
    single_image_skip,
)

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
LOGO = "logo-material-explorer"
CHARACTER = "character-sheet-design"

needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists(),
    reason="needs node + node_modules",
)

# Product-minimal ruling for this card. The two source rows are the contract.
LOGO_SIZE = (1024, 1024, "1:1", 1)
CHARACTER_EXPECTED = {
    "turnaround": (1024, 1024, "1:1", 1),
    "expression": (2048, 1152, "16:9", 1),
    "modeling": (2048, 1152, "16:9", 1),
    "outfit": (1024, 1024, "1:1", 1),
    "prop": (1024, 1024, "1:1", 1),
    "basic": (2048, 1152, "16:9", 1),
    "technical": (2048, 1152, "16:9", 1),
    "editorial": (1024, 1024, "1:1", 1),
}

# Built-in skills that still have no OUTPUTS row after this card. Two are pinned
# here; the rest are the product-ruling list in the PR. A new built-in skill fails
# the list test below until it is triaged (declared, pinned, or floored).
MISSING_AFTER_982 = [
    "poster-differentiated-compiler", "rednote-cover-maker", "cover-design-director",
    "banner-design-director", "product-tvc-advertisement-generator",
    "motion-poster-generator", "meta-ads-creative-director",
    "mobile-app-visual-design", "web-product-visual-design",
    "marketing-campaign-generator", "flash-cut-video", "style-transfer",
    "person-swap", "commerce-strategist", "lifestyle-scene",
    "naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual",
    "promo-ecommerce", "yingzao", "crt-interface", "crayon-sketch",
    "fabric-collage", "taobao-product", "anim-2d", "creator-identity",
    "product-website", "studio-model", "youtube-channel-banner", "ai-model",
    "product-to-packaging", "portrait-studio", "premium-website",
    "animated-poster", "live-promo-decor", "logo-animation",
    "restaurant-website", "interior-architectural-visualization",
]
# #708/#911 pins own the size of these; the floor must not fight a pin.
PINNED_MISSING = [
    "cover-design-director", "studio-model", "youtube-channel-banner",
    "ai-model", "product-to-packaging", "portrait-studio",
]
UNPINNED_MISSING = [sid for sid in MISSING_AFTER_982 if sid not in PINNED_MISSING]


def _builtin_ids() -> list[str]:
    start = SKILLS.index("export const BUILTIN_SKILLS")
    end = SKILLS.index("/** #460/#461")
    seen: list[str] = []
    for sid in re.findall(r"id: '([^']+)'", SKILLS[start:end]):
        if sid not in seen:
            seen.append(sid)
    return seen


def test_the_skill_list_still_matches_this_card():
    declared = set(OUTPUTS)
    missing = [sid for sid in _builtin_ids() if sid not in declared]
    assert missing == MISSING_AFTER_982
    assert len(_builtin_ids()) == 49
    assert len(declared) == 10


def test_logo_default_is_one_1024_square_material_study():
    assert (OUTPUTS[LOGO]["width"], OUTPUTS[LOGO]["height"],
            OUTPUTS[LOGO]["ratio"], OUTPUTS[LOGO]["images"]) == LOGO_SIZE
    assert OUTPUTS[LOGO]["names"] == (LOGO, "徽标材质探索器", "Logo Material Explorer")
    args = apply_generate({"skill": LOGO, "prompt": "brushed metal logo",
                           "refs": ["shape:logo"], "count": 1}, LOGO)
    assert (args["width"], args["height"], args["ratio"], args["count"]) == LOGO_SIZE
    assert args["size_lock"] is True and args["skill"] == LOGO
    assert args["refs"] == ["shape:logo"]  # the logo ref is not dropped by the lock
    # Relay pass (no current skill): the same pixels, no drift.
    again = apply_generate(dict(args))
    assert (again["width"], again["height"], again["ratio"], again["count"]) == LOGO_SIZE
    hint = run_hint("Logo Material Explorer")
    assert "exactly once" in hint and "width=1024 height=1024 ratio=1:1" in hint
    assert "skill='logo-material-explorer'" in hint and "count=1" in hint
    assert is_single(LOGO) is True
    second = single_image_skip("generate_image", LOGO, "en", 1)
    assert second and "did not submit" in second


def test_character_has_one_plan_per_template():
    assert set(CHARACTER_PRESETS_982) == set(CHARACTER_EXPECTED)
    assert PRESET_PLAN_SKILLS == {"brand-identity-director",
                                  "packaging-design-director", CHARACTER}
    # Flat row = default turnaround, never a square placeholder for every template.
    assert (OUTPUTS[CHARACTER]["width"], OUTPUTS[CHARACTER]["height"],
            OUTPUTS[CHARACTER]["ratio"], OUTPUTS[CHARACTER]["images"]) == CHARACTER_EXPECTED["turnaround"]
    for pid, want in CHARACTER_EXPECTED.items():
        plan = plan_for(CHARACTER, pid)
        assert (plan["width"], plan["height"], plan["ratio"], plan["images"]) == want, pid
        assert plan["preset"] == pid and plan["total_images"] == 1


@pytest.mark.parametrize("pid", list(CHARACTER_EXPECTED))
def test_character_each_template_fills_and_states_its_own_canvas(pid):
    want = CHARACTER_EXPECTED[pid]
    args = apply_generate({"skill": CHARACTER, "preset": pid, "prompt": "character sheet"}, CHARACTER)
    assert (args["width"], args["height"], args["ratio"], args["count"]) == want
    assert args["size_lock"] is True and args["preset"] == pid and args["stage"] == 1
    # Relay pass is idempotent.
    again = apply_generate(dict(args))
    assert (again["width"], again["height"], again["ratio"],
            again["preset"], again["stage"]) == (*want[:3], pid, 1)
    hint = run_hint(CHARACTER, "", preset_id=pid)
    assert preset_from_text(hint) == pid
    assert f"template={pid}" in hint
    assert f"width={want[0]}" in hint and f"height={want[1]}" in hint and f"ratio={want[2]}" in hint
    assert "exactly once" in hint and "count=1" in hint
    assert is_single(CHARACTER, pid) is True


def test_character_without_a_template_uses_turnaround():
    args = apply_generate({"skill": CHARACTER, "prompt": "a character"}, CHARACTER)
    assert (args["width"], args["height"], args["ratio"], args["preset"]) == \
        (*CHARACTER_EXPECTED["turnaround"][:3], "turnaround")
    hint = run_hint(CHARACTER)
    assert "template=turnaround" in hint and "skill default template" in hint


@pytest.mark.parametrize("sid", UNPINNED_MISSING)
def test_every_unpinned_undeclared_skill_gets_the_1024_floor(sid):
    args = apply_generate({"skill": sid, "prompt": "a still"}, sid)
    assert (args["width"], args["height"], args["ratio"]) == \
        (FALLBACK_OUTPUT_982["width"], FALLBACK_OUTPUT_982["height"], FALLBACK_OUTPUT_982["ratio"])
    assert args["size_lock"] is True and args["skill"] == sid
    assert args["width"] != 512 and args["height"] != 512  # the old provider default
    again = apply_generate(dict(args))
    assert (again["width"], again["height"], again["ratio"]) == (1024, 1024, "1:1")


@pytest.mark.parametrize("sid", PINNED_MISSING)
def test_pinned_skills_keep_their_pin_owned_size(sid):
    args = apply_generate({"skill": sid, "prompt": "a still"}, sid)
    assert "width" not in args and "height" not in args
    assert "ratio" not in args and "size_lock" not in args


def test_custom_skill_run_gets_the_floor_but_direct_generation_does_not():
    custom = apply_generate({"prompt": "a still"}, "my-custom-skill")
    assert (custom["width"], custom["height"], custom["ratio"], custom["skill"]) == \
        (1024, 1024, "1:1", "my-custom-skill")
    assert custom["size_lock"] is True
    # No skill (or explicit Auto text-to-image): nothing is invented.
    assert apply_generate({"prompt": "cat"}) == {"prompt": "cat"}
    assert apply_generate({"prompt": "cat", "ratio": "1:1"}) == {"prompt": "cat", "ratio": "1:1"}


def test_explicit_size_or_ratio_still_wins_over_the_floor():
    sid = UNPINNED_MISSING[0]
    explicit = apply_generate({"skill": sid, "prompt": "x", "width": 1536, "height": 1024}, sid)
    assert (explicit["width"], explicit["height"]) == (1536, 1024)
    assert "size_lock" not in explicit
    # A ratio is an aspect, not a pixel size: keep the ratio and give it pixels.
    ratio = apply_generate({"skill": sid, "prompt": "x", "ratio": "16:9"}, sid)
    assert ratio["ratio"] == "16:9"
    assert (ratio["width"], ratio["height"]) == pixels_for_ratio("16:9") == (1024, 576)
    assert ratio["size_lock"] is True
    # A resolution tier already constrains size; nothing is invented.
    tier = apply_generate({"skill": sid, "prompt": "x", "resolution": "2k"}, sid)
    assert "width" not in tier and "height" not in tier
    tier_ratio = apply_generate({"skill": sid, "prompt": "x", "ratio": "16:9", "resolution": "2k"}, sid)
    assert "width" not in tier_ratio and "height" not in tier_ratio
    assert pixels_for_ratio("1:1") == (1024, 1024)
    assert pixels_for_ratio("3:4") == (768, 1024)
    assert pixels_for_ratio("wide") is None and pixels_for_ratio("0:1") is None


@needs_node
def test_character_preset_ids_are_the_ones_the_page_has():
    """The Python table keys must be the real applyRaw748 template ids."""
    from test_template_output_979 import js_report
    js = js_report()
    assert [p["id"] for p in js["presets"]["character"]] == list(CHARACTER_EXPECTED)
    for pid, want in CHARACTER_EXPECTED.items():
        ts = js["skillOutput"][CHARACTER]["presets"][pid]
        assert (ts["width"], ts["height"], ts["ratio"], ts["images"]) == want, pid


def test_generate_image_description_documents_the_floor():
    from ComfyArt.api.mcp_tools import canvas
    desc = canvas.SPECS["generate_image"]["description"]
    assert "1024x1024 fallback" in desc
    assert "size-locked to 1024x1024" in desc
    assert "never submitted with no size" in desc


def test_no_declared_or_floored_output_is_512():
    for sid, row in OUTPUTS.items():
        assert (row["width"], row["height"]) != (512, 512), sid
    assert (FALLBACK_OUTPUT_982["width"], FALLBACK_OUTPUT_982["height"]) == (1024, 1024)
