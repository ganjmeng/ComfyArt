"""#905 before-after: Lovart layout (two side-by-side photos), reference angle/crop, mild flaw,
verbatim user copy, 16:9 1920x1080 on the unchanged qwen edit pin. Static, $0."""
from __future__ import annotations

from pathlib import Path

from ComfyArt.bot.guide import AGENT_GUIDE
from ComfyArt.bot.skill_output import OUTPUTS, apply_generate
from tests.test_skill_output_707 import SKILLS, _instr

ROOT = Path(__file__).resolve().parents[1]


def test_905_layout_two_separate_panels_never_split_face():
    ba = _instr("before-after")
    assert "two separate photo panels of the same subject placed side by side" in ba
    assert "visible gap between them" in ba and "Each panel is a complete photo" in ba
    assert "Never split one face down the middle" in ba and "mirror one photo into two symmetric halves" in ba
    assert "fixed split" not in ba


def test_905_camera_follows_reference_angle_and_crop():
    ba = _instr("before-after")
    assert "state in the prompt which features its frame includes and where it cuts, and copy that angle and crop exactly in both panels; never widen or tighten it" in ba
    assert "90 degree profile" not in ba


def test_905_mild_before_flaw_and_verbatim_copy():
    ba = _instr("before-after")
    # _instr reads the raw TS string, so the apostrophe is escaped as \'
    rule2 = (
        "2) Lock: the same person, the same camera, and the same light in both panels. "
        "Only the effect changes (treatment, remodel, makeup, fitness). "
        "Keep the user\\'s own words for what changes. "
        "Describe both panels as finished states: Before is a slight, everyday version of that change, "
        "still noticeable at thumbnail size. "
        "Describe Before\\'s darkness or unevenness only as a soft shade slightly deeper than the person\\'s own surrounding skin tone; "
        "do not name a color for it and do not use intensifiers like \"distinct\", \"clearly visible\" or \"deep\". "
        "Describe After\\'s area only as the person\\'s own surrounding skin tone, even and natural, with texture kept. "
        "After is a modest, realistic improvement of the same change, with natural texture kept. "
        "Describe only the change the user named, at the intensity the user stated; if the user gave no intensity, keep it slight and everyday. "
        "Do not add symptoms, colors, causes or intensifiers the user did not mention."
    )
    assert rule2 in ba
    assert "slight, everyday version of that change" in ba
    # Product lock (PR #908 comment 6840013211): soft shade, no color, no intensifiers
    assert "only as a soft shade slightly deeper than the person\\'s own surrounding skin tone" in ba
    assert (
        "Describe Before\\'s darkness or unevenness only as a soft shade slightly deeper than the person\\'s own surrounding skin tone; "
        "do not name a color for it and do not use intensifiers like \"distinct\", \"clearly visible\" or \"deep\"."
    ) in ba
    # Product ruling (PR #908 comment 6840099658): After wording + default label typography
    assert "Describe After\\'s area only as the person\\'s own surrounding skin tone, even and natural, with texture kept." in ba
    assert (
        "Typography: use the typography the user specifies; otherwise match the headline and label typography of the reference. "
        "When the user specifies no typography, set the labels as small, thin-weight, widely letter-spaced grey sans-serif capitals "
        "\"BEFORE\" and \"AFTER\"."
    ) in ba
    assert "serif capitals" in ba and "thin serif" not in ba
    assert "still noticeable at thumbnail size" in ba
    assert "faint dullness or slight unevenness on otherwise natural skin" not in ba
    assert "modest, realistic improvement of the same change" in ba
    assert "natural texture kept" in ba
    assert "Keep the user\\'s own words for what changes" in ba
    assert "under the eyes" not in ba.lower()
    assert "forbidden words" not in ba
    assert "Never use bruise" not in ba
    assert "use the typography the user specifies" in ba
    assert "use it word for word and add no other text" in ba
    assert "Never invent brand names, product names, percentages or efficacy numbers" in ba


def test_905_size_is_16_9_1920x1080_everywhere():
    row = OUTPUTS["before-after"]
    assert (row["width"], row["height"], row["ratio"]) == (1920, 1080, "16:9")
    assert "'before-after': { width: 1920, height: 1080, ratio: '16:9', images: 1 }" in SKILLS
    assert 'default ratio "16:9", width 1920, height 1080' in _instr("before-after")
    assert SKILLS.count("Style: one 16:9 comparison card 1920x1080") == 3
    assert "16:9 comparison card (1920x1080)" in AGENT_GUIDE
    assert "before-after 1920x1080" in (ROOT / "api/mcp_tools/canvas.py").read_text(encoding="utf-8")
    args = apply_generate({"skill": "before-after", "ratio": "4:5", "width": 1024, "height": 1280})
    assert (args["width"], args["height"], args["ratio"], args["size_lock"]) == (1920, 1080, "16:9", True)



def _ba(user_text, **extra):
    return apply_generate({"skill": "before-after", "prompt": "card", **extra}, user_text=user_text)


def _px(a):
    return a["width"], a["height"], a["ratio"]


def test_905_no_ratio_in_user_message_is_16_9():
    assert _px(_ba("帮我做一张祛黑眼圈前后对比图")) == (1920, 1080, "16:9")


def test_905_user_ratio_wins_from_the_whitelist():
    assert _px(_ba("做一张前后对比，比例 4:5")) == (1024, 1280, "4:5")
    assert _px(_ba("1：1 的对比图")) == (1024, 1024, "1:1")
    assert _px(_ba("before after, 9:16 please")) == (1080, 1920, "9:16")
    assert _px(_ba("要竖版")) == (1080, 1920, "9:16")
    assert _px(_ba("横版就好")) == (1920, 1080, "16:9")


def test_905_model_invented_ratio_is_overridden():
    a = _ba("帮我做一张前后对比图", ratio="4:5", width=1024, height=1280)
    assert _px(a) == (1920, 1080, "16:9") and "_user_ratio" not in a
    forged = _ba("帮我做一张前后对比图", ratio="1:1", _user_ratio="1:1")
    assert _px(forged) == (1920, 1080, "16:9") and "_user_ratio" not in forged


def test_905_ratio_outside_table_falls_back_to_16_9():
    assert _px(_ba("比例 3:2")) == (1920, 1080, "16:9")
    assert _px(_ba("21:9 超宽")) == (1920, 1080, "16:9")
    assert _px(_ba("1920x1080 的图")) == (1920, 1080, "16:9")


def test_905_app_injected_hint_is_not_the_users_ratio():
    hint = "Output lock: call generate_image exactly once with skill='before-after', width=1024 height=1280 ratio=4:5, count=1."
    assert _px(_ba("做个对比图\n" + hint)) == (1920, 1080, "16:9")


def test_905_relay_keeps_a_valid_user_marker_only():
    first = _ba("比例 4:5")
    assert first["_user_ratio"] == "4:5"
    relayed = apply_generate(dict(first))  # the relay has no user text
    assert _px(relayed) == (1024, 1280, "4:5") and relayed["size_lock"] is True
    bad = apply_generate({"skill": "before-after", "_user_ratio": "3:2", "ratio": "3:2"})
    assert _px(bad) == (1920, 1080, "16:9") and "_user_ratio" not in bad


def test_905_other_exact_skills_ignore_user_ratio():
    g = apply_generate({"skill": "game-art", "ratio": "16:9"}, user_text="横版 16:9")
    assert (g["width"], g["height"], g["ratio"]) == (1024, 1824, "9:16") and "_user_ratio" not in g
    lb = apply_generate({"skill": "linkedin-banner", "_user_ratio": "1:1"}, user_text="1:1")
    assert (lb["width"], lb["height"]) == (1584, 396) and "ratio" not in lb and "_user_ratio" not in lb
    p = apply_generate({"skill": "pose-fission"}, user_text="4:5")
    assert (p["width"], p["height"], p["ratio"]) == (1536, 2048, "3:4")


def test_run_hint_states_the_user_ratio():
    from ComfyArt.bot.skill_output import run_hint
    assert "width=1920 height=1080 ratio=16:9" in run_hint("before-after")
    assert "width=1920 height=1080 ratio=16:9" in run_hint("before-after", "做一张前后对比图")
    assert "width=1024 height=1280 ratio=4:5" in run_hint("before-after", "做一张前后对比图，比例 4:5")
    assert "ratio=16:9" in run_hint("before-after", "比例 3:2")
    assert "4:5" not in run_hint("game-art", "比例 4:5")


def test_provider_text_lock_follows_user_ratio():
    from ComfyArt.api.bot_send import compose_provider_text
    text = compose_provider_text("做一张眼霜前后对比图，比例 4:5。", skill_name="before-after")
    assert "width=1024 height=1280 ratio=4:5" in text
    assert "width=1920" not in text


def test_toast_layer_lifts_above_generator_panel():
    css = (Path(__file__).resolve().parent.parent / "src/styles/canvas.css").read_text(encoding="utf-8")
    assert ".tlui-layout:has(.tlui-toast__viewport > *) { z-index: 302; }" in css
    assert "z-index: 301;" in css  # the panel layer itself is unchanged


def test_rule6_and_headline_lines():
    from tests.test_skill_output_707 import _instr
    text = _instr("before-after")
    assert "Only when there is no reference: frontal, eye-level, head-and-shoulders, identical framing in both panels." in text
    assert "45 degree" not in text
    assert "never draw separator characters" in text
    assert "Typography: use the typography the user specifies; otherwise match the headline and label typography of the reference." in text
    assert "Headline and label type follow the reference" not in text
    assert "sans-serif with wide letter-spacing" not in text
