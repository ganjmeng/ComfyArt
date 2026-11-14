"""#982 — no declared canvas must not fall back to a smaller default.

The $0 audit (#911 comment 6873212793) saw 512x512, but that was the fixed
512 red image in `tests/test_e2e_comment_edit.py` (`RESULT`, line 45), not a
production size. The real page always sends width/height: `GENERATOR_DEFAULTS`
resolution 1K (`GeneratorShape.tsx:22`) -> `targetSize` short side 1024
(`generate.ts:47-53`) -> `pixelSizeOf` (`:62-70`) -> the WaveSpeed request.

Product HOLD 6874283882: keep the floor mechanism, but floor != product default.
- 8 skills are accepted at 1024x1024.
- 25 get a typed default: 16:9 1824x1024, 3:4 1024x1360, multi-ratio packs,
  9:19.5, 4:3, video stills, follow-ref, multi-asset kits.
- 6 pinned skills stay untouched (paired follow-up card).
- A custom/unknown skill gets a neutral 1024x1024 last-resort floor; its explicit
  ratio uses the page's 1024 SHORT side, never a shrunken 1024 long side.

The literals are deliberate: reverting a type to 1:1, or changing
`pixels_for_ratio` back to long-side semantics, turns these red.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
from PIL import Image

from ComfyArt.bot.skill_output import (
    CALL_PLAN_SKILLS,
    CHARACTER_PRESETS_982,
    FALLBACK_OUTPUT_982,
    FOLLOW_REF_SIZES,
    OUTPUTS,
    PRESET_PLAN_SKILLS,
    VIDEO_SKILLS,
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

LOGO_SIZE = (1024, 1024, "1:1", 1)
CHARACTER_EXPECTED = {
    # Design 6874380577: 1024 square made the face ~80 px; 1:1 stays at 1536
    # square, editorial moves to 3:4 2K, the four 16:9 templates stay 2048x1152.
    "turnaround": (1536, 1536, "1:1", 1),
    "expression": (2048, 1152, "16:9", 1),
    "modeling": (2048, 1152, "16:9", 1),
    "outfit": (1536, 1536, "1:1", 1),
    "prop": (1536, 1536, "1:1", 1),
    "basic": (2048, 1152, "16:9", 1),
    "technical": (2048, 1152, "16:9", 1),
    "editorial": (1536, 2048, "3:4", 1),
}

# Product HOLD 6874283882: 8 accepted 1:1, 25 typed. Total 33 unpinned students.
SQUARE_1024 = {
    "logo-abstract", "lifestyle-scene", "crayon-sketch", "fabric-collage",
    "naive-illustration", "commerce-strategist", "promo-ecommerce", "taobao-product",
}
WIDE_16_9 = {
    "banner-design-director", "ppt-visual", "web-product-visual-design",
    "product-website", "premium-website", "restaurant-website",
    "interior-architectural-visualization",
}
PORTRAIT_3_4 = {
    "poster-differentiated-compiler", "photo-split-poster", "yingzao",
}
PACKS = {
    "meta-ads-creative-director", "rednote-cover-maker", "marketing-campaign-generator",
}
PHONE = {"mobile-app-visual-design"}
CRT = {"crt-interface"}
VIDEO = {
    "product-tvc-advertisement-generator", "motion-poster-generator", "flash-cut-video",
    "anim-2d", "animated-poster", "logo-animation",
}
FOLLOW_REF = {"style-transfer", "person-swap"}
MULTI_ASSET = {"creator-identity", "live-promo-decor"}
TYPED = SQUARE_1024 | WIDE_16_9 | PORTRAIT_3_4 | PACKS | PHONE | CRT | VIDEO | FOLLOW_REF | MULTI_ASSET

CALLS = {
    "meta-ads-creative-director": [
        (1024, 1024, "1:1"), (1024, 1280, "4:5"), (1024, 1824, "9:16")],
    "rednote-cover-maker": [
        (1024, 1024, "1:1"), (1024, 1280, "4:5"), (1024, 1824, "9:16")],
    "marketing-campaign-generator": [
        (1824, 1024, "16:9"), (1024, 1024, "1:1"), (1024, 1280, "4:5")],
    # Design 6874380577: 9:19.5 is not enum-supported; 9:21 880x2048 is.
    "mobile-app-visual-design": [
        (880, 2048, "9:21"), (880, 2048, "9:21")],
    "creator-identity": [
        (1024, 1024, "1:1"), (1824, 1024, "16:9"), (1024, 1280, "4:5")],
    "live-promo-decor": [
        (1824, 1024, "16:9"), (1024, 1024, "1:1"), (1024, 1024, "1:1")],
}
VIDEO_STILL = {
    "product-tvc-advertisement-generator": (1824, 1024, "16:9"),
    "motion-poster-generator": (1360, 1024, "4:3"),
    "flash-cut-video": (1824, 1024, "16:9"),
    "anim-2d": (1024, 1024, "1:1"),
    "animated-poster": (1360, 1024, "4:3"),
    "logo-animation": (1024, 1024, "1:1"),
}

# Still missing after this card: only the six pinned skills. Their pins own size
# (#708/#911/#912); a separate gap card covers their product defaults.
PINNED_MISSING = [
    "cover-design-director", "studio-model", "youtube-channel-banner",
    "ai-model", "product-to-packaging", "portrait-studio",
]


def _builtin_ids() -> list[str]:
    start = SKILLS.index("export const BUILTIN_SKILLS")
    end = SKILLS.index("/** #460/#461")
    seen: list[str] = []
    for sid in re.findall(r"id: '([^']+)'", SKILLS[start:end]):
        if sid not in seen:
            seen.append(sid)
    return seen


def test_the_typed_table_covers_every_unpinned_missing_skill():
    ids = _builtin_ids()
    declared = set(OUTPUTS)
    assert len(ids) == 49
    assert len(declared) == 43
    assert [sid for sid in ids if sid not in declared] == PINNED_MISSING
    assert TYPED == set(declared) - {  # 8 existing + 2 (logo/character) + 33 typed
        "before-after", "universal-multi-angle-grid", "pose-fission", "game-art",
        "linkedin-banner", "clothing-swap", "brand-identity-director",
        "packaging-design-director", LOGO, CHARACTER,
    }
    assert CALL_PLAN_SKILLS == set(CALLS)
    assert VIDEO_SKILLS == VIDEO


def test_logo_default_is_one_1024_square_material_study():
    assert (OUTPUTS[LOGO]["width"], OUTPUTS[LOGO]["height"],
            OUTPUTS[LOGO]["ratio"], OUTPUTS[LOGO]["images"]) == LOGO_SIZE
    assert OUTPUTS[LOGO]["names"] == (LOGO, "徽标材质探索器", "Logo Material Explorer")
    args = apply_generate({"skill": LOGO, "prompt": "brushed metal logo",
                           "refs": ["shape:logo"], "count": 1}, LOGO)
    assert (args["width"], args["height"], args["ratio"], args["count"]) == LOGO_SIZE
    assert args["size_lock"] is True and args["skill"] == LOGO
    assert args["refs"] == ["shape:logo"]
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
    assert (OUTPUTS[CHARACTER]["width"], OUTPUTS[CHARACTER]["height"],
            OUTPUTS[CHARACTER]["ratio"], OUTPUTS[CHARACTER]["images"]) == CHARACTER_EXPECTED["turnaround"]
    assert (OUTPUTS[CHARACTER]["width"], OUTPUTS[CHARACTER]["height"]) == (1536, 1536)
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


@pytest.mark.parametrize("sid", sorted(SQUARE_1024))
def test_accepted_square_skills_are_1024(sid):
    args = apply_generate({"skill": sid, "prompt": "a still"}, sid)
    assert (args["width"], args["height"], args["ratio"], args["count"]) == (1024, 1024, "1:1", 1)
    assert args["size_lock"] is True and args["skill"] == sid
    assert is_single(sid) is True


@pytest.mark.parametrize("sid", sorted(WIDE_16_9))
def test_wide_skills_keep_1824x1024(sid):
    args = apply_generate({"skill": sid, "prompt": "a wide frame"}, sid)
    assert (args["width"], args["height"], args["ratio"], args["count"]) == (1824, 1024, "16:9", 1)
    assert args["size_lock"] is True
    assert (args["width"], args["height"]) != (1024, 1024)
    assert is_single(sid) is True


@pytest.mark.parametrize("sid", sorted(PORTRAIT_3_4))
def test_portrait_skills_keep_1024x1360(sid):
    args = apply_generate({"skill": sid, "prompt": "a portrait poster"}, sid)
    assert (args["width"], args["height"], args["ratio"], args["count"]) == (1024, 1360, "3:4", 1)
    assert args["size_lock"] is True
    assert (args["width"], args["height"]) != (1024, 1024)
    # poster's instruction says default 3:4; this is the regression the HOLD named.
    assert args["ratio"] == "3:4"


def test_crt_is_4_3():
    args = apply_generate({"skill": "crt-interface", "prompt": "crt"}, "crt-interface")
    assert (args["width"], args["height"], args["ratio"]) == (1360, 1024, "4:3")
    assert is_single("crt-interface") is True


@pytest.mark.parametrize("sid,want", sorted(VIDEO_STILL.items()))
def test_video_skills_have_a_still_default_not_a_one_image_film(sid, want):
    args = apply_generate({"skill": sid, "prompt": "a still"}, sid)
    assert (args["width"], args["height"], args["ratio"], args["count"]) == (*want, 1)
    assert OUTPUTS[sid]["media"] == "video"
    assert is_single(sid) is False
    # A second still is legitimate for storyboard/style candidates; never skip it.
    assert single_image_skip("generate_image", sid, "en", 1) is None
    hint = run_hint(sid)
    assert "video skill" in hint and "generate_video" in hint and "animate_image" in hint
    assert f"width={want[0]}" in hint and f"height={want[1]}" in hint


@pytest.mark.parametrize("sid", sorted(CALLS))
def test_multi_call_defaults_state_each_canvas(sid):
    row = OUTPUTS[sid]
    calls = CALLS[sid]
    assert len(row["calls"]) == len(calls)
    assert row["images"] == len(calls)
    assert (row["width"], row["height"], row["ratio"]) == calls[0]
    assert is_single(sid) is False
    hint = run_hint(sid)
    assert f"deliver exactly {len(calls)} separate images" in hint
    for i, (w, h, r) in enumerate(calls, 1):
        assert f"call {i}" in hint
        assert f"width={w}" in hint and f"height={h}" in hint and f"ratio={r}" in hint
        got = apply_generate({"skill": sid, "ratio": r, "prompt": f"call {i}"}, sid)
        assert (got["width"], got["height"], got["ratio"], got["count"]) == (w, h, r, 1)
        assert got["size_lock"] is True
    # No ratio → call 1; relay keeps the chosen call.
    first = apply_generate({"skill": sid, "prompt": "first"}, sid)
    assert (first["width"], first["height"], first["ratio"]) == calls[0]
    assert apply_generate(dict(first))["width"] == calls[0][0]


def _png(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 180, 160)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("sid,fallback", [
    ("style-transfer", (1024, 1024, "1:1")),
    ("person-swap", (1024, 1360, "3:4")),
])
def test_follow_ref_skills_take_image_1_size(sid, fallback):
    assert sid in FOLLOW_REF_SIZES
    ref = _png(768, 1024)  # 3:4
    got = apply_generate({"skill": sid, "prompt": "x", "refs": ["shape:1"]}, sid, ref_image=ref)
    assert (got["width"], got["height"], got["ratio"]) == (1024, 1360, "3:4")
    assert got["size_lock"] is True
    bare = apply_generate({"skill": sid, "prompt": "x"}, sid)
    assert (bare["width"], bare["height"], bare["ratio"]) == fallback
    hint = run_hint(sid)
    assert "image 1" in hint
    if sid == "person-swap":
        assert "exactly 3 separate images" in hint


def test_pixels_for_ratio_uses_the_page_short_side_not_a_long_side():
    # Product HOLD: the old 1024-long-edge math shrank 16:9 to 1024x576 and 3:4
    # to 768x1024. The page's targetSize uses a 1024 SHORT side.
    assert pixels_for_ratio("16:9") == (1824, 1024)
    assert pixels_for_ratio("3:4") == (1024, 1360)
    assert pixels_for_ratio("4:5") == (1024, 1280)
    assert pixels_for_ratio("9:16") == (1024, 1824)
    assert pixels_for_ratio("4:3") == (1360, 1024)
    assert pixels_for_ratio("1:1") == (1024, 1024)
    assert pixels_for_ratio("wide") is None and pixels_for_ratio("0:1") is None
    assert pixels_for_ratio("16:9") != (1024, 576)
    assert pixels_for_ratio("3:4") != (768, 1024)


def test_typed_defaults_never_fall_below_the_main_card():
    """HOLD: the floor must not shrink what main already delivered at 1K."""
    card = {"1:1": (1024, 1024), "16:9": (1824, 1024), "3:4": (1024, 1360),
            "4:5": (1024, 1280), "9:16": (1024, 1824), "4:3": (1360, 1024)}
    checked = 0
    for sid, row in OUTPUTS.items():
        if sid in PINNED_MISSING or row.get("ratio") == "9:21":
            continue
        sizes = [row] + list(row.get("calls") or [])
        for item in sizes:
            if not item.get("ratio"):
                continue
            cw, ch = card[item["ratio"]]
            assert item["width"] >= cw and item["height"] >= ch, (sid, item, (cw, ch))
            checked += 1
    assert checked >= 40
    # The one design exception is the enum-supported phone frame.
    assert (OUTPUTS["mobile-app-visual-design"]["width"],
            OUTPUTS["mobile-app-visual-design"]["height"],
            OUTPUTS["mobile-app-visual-design"]["ratio"]) == (880, 2048, "9:21")


def test_mobile_ratio_is_enum_supported_and_aliases_the_old_wording():
    # Design 6874380577: the page must accept 9:21 or startGenerator rejects it.
    assert "'9:21'" in (ROOT / "src/genOptions.ts").read_text(encoding="utf-8")
    got = apply_generate({"prompt": "x", "ratio": "9:19.5"}, "my-custom-skill")
    assert (got["ratio"], got["width"], got["height"]) == ("9:21", 880, 2048)
    assert got["size_lock"] is True


def test_custom_skill_floor_is_neutral_but_ratio_aware():
    custom = apply_generate({"prompt": "a still"}, "my-custom-skill")
    assert (custom["width"], custom["height"], custom["ratio"], custom["skill"]) == \
        (1024, 1024, "1:1", "my-custom-skill")
    assert custom["size_lock"] is True
    wide = apply_generate({"prompt": "x", "ratio": "16:9"}, "my-custom-skill")
    assert (wide["width"], wide["height"], wide["ratio"]) == (1824, 1024, "16:9")
    portrait = apply_generate({"prompt": "x", "ratio": "3:4"}, "my-custom-skill")
    assert (portrait["width"], portrait["height"], portrait["ratio"]) == (1024, 1360, "3:4")
    assert apply_generate({"prompt": "cat"}) == {"prompt": "cat"}
    assert apply_generate({"prompt": "cat", "ratio": "1:1"}) == {"prompt": "cat", "ratio": "1:1"}


@pytest.mark.parametrize("sid", PINNED_MISSING)
def test_pinned_skills_keep_their_pin_owned_size(sid):
    args = apply_generate({"skill": sid, "prompt": "a still"}, sid)
    assert "width" not in args and "height" not in args
    assert "ratio" not in args and "size_lock" not in args


def test_explicit_size_wins_only_for_a_custom_floor():
    # A declared contract wins over a model-invented size (poster must stay 3:4).
    poster = apply_generate({"skill": "poster-differentiated-compiler", "prompt": "x",
                             "width": 1536, "height": 1024, "ratio": "1:1"}, "poster-differentiated-compiler")
    assert (poster["width"], poster["height"], poster["ratio"]) == (1024, 1360, "3:4")
    # A custom skill has no contract: explicit pixels and a tier are honored.
    explicit = apply_generate({"prompt": "x", "width": 1536, "height": 1024}, "my-custom-skill")
    assert (explicit["width"], explicit["height"]) == (1536, 1024)
    assert "size_lock" not in explicit
    tier = apply_generate({"prompt": "x", "resolution": "2k"}, "my-custom-skill")
    assert "width" not in tier and "height" not in tier
    tier_ratio = apply_generate({"prompt": "x", "ratio": "16:9", "resolution": "2k"}, "my-custom-skill")
    assert "width" not in tier_ratio and "height" not in tier_ratio


@needs_node
def test_ts_and_python_typed_rows_agree():
    from test_template_output_979 import js_report
    js = js_report()
    ts = js["skillOutput"]
    assert set(ts) == set(OUTPUTS)
    for sid, row in OUTPUTS.items():
        got = ts[sid]
        for key in ("width", "height", "images"):
            assert got[key] == row[key], (sid, key)
        assert got.get("ratio") == row.get("ratio"), sid
        assert got.get("media") == row.get("media"), sid
        assert got.get("refs") == row.get("refs"), sid
        assert got.get("calls") == row.get("calls"), sid
    assert [p["id"] for p in js["presets"]["character"]] == list(CHARACTER_EXPECTED)


def test_generate_image_description_documents_the_typed_contract():
    from ComfyArt.api.mcp_tools import canvas
    desc = canvas.SPECS["generate_image"]["description"]
    assert "type default" in desc or "typed" in desc or "16:9" in desc
    assert "1024x1024" in desc
    assert "custom" in desc.lower() or "unknown" in desc.lower()


def test_no_declared_or_floored_output_is_512():
    for sid, row in OUTPUTS.items():
        assert (row["width"], row["height"]) != (512, 512), sid
    assert (FALLBACK_OUTPUT_982["width"], FALLBACK_OUTPUT_982["height"]) == (1024, 1024)
