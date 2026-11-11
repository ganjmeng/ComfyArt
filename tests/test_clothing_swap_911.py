"""#911 clothing-swap: Lovart single-question card skeleton, prompt keep-from-image-1, detach 708.

Options are generated live from what the person in image 1 is wearing, so they
must not be copied into src/skills.ts. This file may name Lovart fixture words
only to forbid them in the skill entry.

No WaveSpeed call. $0 static. Pins and api/auto_models.json stay unchanged.
The shared PORTRAIT_SHOTS_708 constant is untouched; clothing-swap no longer
appends it. compose_provider_text is intentionally not changed in this slice.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

from ComfyArt.bot.skill_output import OUTPUTS, apply_generate

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
AUTO_MODELS = ROOT / "api/auto_models.json"
BOT_SEND = ROOT / "api/bot_send.py"

# Same lock as tests/test_studio_model_911.py — the shared block must not drift.
PORTRAIT_SHOTS_708_CONST_SHA256 = "97edb7c18215e4a283b86633908872f3b3c4146d9bb748d71c0d3510798cfc8b"
MAIN_SHA = "dbed74e11b158917e7cf82b44bd4dbf6829af90d"

# Lovart person photo for this skill (review-assets 9967bf48). Exactly 3:4.
PERSON_PHOTO_SIZE = (1776, 2368)
# In-limit declared canvas (same 3:4 as Lovart's 1536x2048 result / pose-fission).
DECLARED_SIZE = (1536, 2048)
DECLARED_RATIO = "3:4"

# Fixture-specific wording must not be baked into the skill or the card skeleton.
GARMENT_FORBIDDEN = ("宝蓝", "宝蓝色", "royal blue", "cobalt")

OTHER_SKILL_IDS = (
    "studio-model",
    "ai-model",
    "pose-fission",
    "before-after",
    "game-art",
    "linkedin-banner",
    "person-swap",
)


def _skill_entry(src: str, sid: str) -> str:
    m = re.search(
        rf"{{ id: '{re.escape(sid)}', name: t\('[^']+'\), instructions: [\s\S]*?inputs: [^\n]+}},",
        src,
    )
    assert m, f"skill entry {sid} did not parse"
    return m.group(0)


def _clothing_swap_instructions(src: str = SKILLS) -> str:
    m = re.search(
        r"\{ id: 'clothing-swap', name: t\('skills.clothingSwap'\), instructions: '((?:\\.|[^'\\])*)'",
        src,
    )
    assert m, "clothing-swap instructions string did not parse"
    # JS single-quoted string: \n is a newline escape, quotes inside are raw ".
    return m.group(1).replace("\\n", chr(10)).replace("\\t", chr(9))


def _portrait_shots_708_const(src: str) -> str:
    m = re.search(
        r"const PORTRAIT_SHOTS_708 = ((?:'(?:\\.|[^'\\])*'(?:\s*\+\s*)?)+)",
        src,
    )
    assert m, "PORTRAIT_SHOTS_708 constant missing"
    return m.group(1)


def _main_skills() -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "show", f"{MAIN_SHA}:src/skills.ts"],
        text=True,
        encoding="utf-8",
    )


def test_rule6_and_708_detached_from_clothing_swap_only():
    """1: clothing-swap no longer appends Rule 6 or PORTRAIT_SHOTS_708; the const stays."""
    entry = _skill_entry(SKILLS, "clothing-swap")
    instr = _clothing_swap_instructions()
    main = _main_skills()

    assert "+ PORTRAIT_SHOTS_708 +" not in entry
    assert "PORTRAIT_SHOTS_708" not in entry
    assert "Shot rules (#708)" not in entry
    assert "Shot rules (#708)" not in instr
    assert "6) Angles:" not in entry
    assert "6) Angles:" not in instr
    assert "must not be all front-on and centered" not in instr
    assert "A single-image run is never frontal-centered" not in instr
    assert "subject on the left third" not in instr
    assert "45°" not in instr and "45 deg" not in instr.lower()

    # Shared block itself is untouched (initializer bytes + sha).
    assert _portrait_shots_708_const(SKILLS) == _portrait_shots_708_const(main)
    assert hashlib.sha256(_portrait_shots_708_const(SKILLS).encode()).hexdigest() == PORTRAIT_SHOTS_708_CONST_SHA256
    assert "const PORTRAIT_SHOTS_708 =" in SKILLS

    # Other skill entries stay byte-identical to the branch base.
    for sid in OTHER_SKILL_IDS:
        assert _skill_entry(SKILLS, sid) == _skill_entry(main, sid), sid


def test_card_skeleton_is_one_live_upper_body_question():
    """2: ONE how-to-replace-the-top question; live options; free-text; nothing preselected."""
    instr = _clothing_swap_instructions()
    assert "call ask_user exactly once" in instr
    assert "ONE question about how to replace the upper-body garment" in instr
    assert "Generated the options live from what the person in image 1 is wearing" not in instr  # typo guard
    assert "Generate the options live from what the person in image 1 is wearing" in instr
    assert "do not hard-code option labels" in instr
    assert "allow_other" in instr
    assert "free-text" in instr
    assert "Nothing is preselected" in instr or "do not set defaults or recommended" in instr
    assert "Never ask gender, ethnicity, or angle" in instr
    assert 'id "upper_body_swap"' in instr
    assert "page_count 1" in instr
    # Not a multi-card / gender path.
    assert "call ask_user twice" not in instr
    assert 'id "gender"' not in instr
    assert 'id "ethnicity"' not in instr
    for word in GARMENT_FORBIDDEN:
        assert word not in instr
        assert word not in _skill_entry(SKILLS, "clothing-swap")


def test_prompt_rules_keep_image1_and_describe_only_the_swap():
    """2/3: prompt describes only the garment swap; keep person/pose/composition from image 1."""
    instr = _clothing_swap_instructions()
    assert "describe only the garment swap" in instr
    assert "keep the person, pose, composition, background, and all other clothing from image 1" in instr
    assert "Garment description comes only from image 2" in instr
    assert "Do not invent or write angle, shot-size, background, or lighting words" in instr
    assert "Do not change pose or framing" in instr
    assert "Output aspect follows image 1" in instr


def test_output_aspect_follows_person_photo_3x4():
    """3: 1776x2368 person photo is 3:4; path fills the in-limit 1536x2048 3:4 canvas."""
    w, h = PERSON_PHOTO_SIZE
    assert w * 4 == h * 3
    assert DECLARED_SIZE[0] * 4 == DECLARED_SIZE[1] * 3

    row = OUTPUTS["clothing-swap"]
    assert (row["width"], row["height"], row["ratio"], row["images"]) == (*DECLARED_SIZE, DECLARED_RATIO, 1)
    assert "clothing-swap" in row["names"]
    assert "AI服装换装" in row["names"]
    assert "AI Clothing Swap" in row["names"]

    # TS table stays in sync (same check as test_skill_output_707, scoped to this skill).
    block = re.search(r"export const SKILL_OUTPUT[\s\S]*?\n\}", SKILLS).group(0)
    assert "'clothing-swap'" in block
    assert "width: 1536" in block and "height: 2048" in block
    assert "ratio: '3:4'" in block and "images: 1" in block

    filled = apply_generate({"prompt": "swap the top", "ratio": "16:9", "width": 1024, "height": 1024}, "clothing-swap")
    assert filled["skill"] == "clothing-swap"
    assert (filled["width"], filled["height"], filled["ratio"], filled["count"]) == (*DECLARED_SIZE, DECLARED_RATIO, 1)
    assert filled["size_lock"] is True

    named = apply_generate({"prompt": "x"}, "AI服装换装")
    assert named["skill"] == "clothing-swap"
    assert (named["width"], named["height"], named["ratio"]) == (*DECLARED_SIZE, DECLARED_RATIO)

    already = apply_generate({"prompt": "x", "skill": "clothing-swap"}, "clothing-swap")
    assert already["skill"] == "clothing-swap"
    assert already["size_lock"] is True

    # Unrelated sessions stay untouched.
    bare = apply_generate({"prompt": "cat", "ratio": "1:1"})
    assert bare == {"prompt": "cat", "ratio": "1:1"}


def test_card_normalizer_locks_skeleton_not_option_contents():
    """Code enforces only the card skeleton; live option labels and a live title stay."""
    from ComfyArt.api import bot_asks

    live_prompt = "这件宝蓝T恤要怎么替换模特的上身？"
    live_opts = [
        {"id": "A", "label": "整套上身都换成它"},
        {"id": "B", "label": "换掉黑色背心，留白色长袖内搭"},
        {"id": "C", "label": "换掉白色长袖，留黑色背心"},
    ]

    # Legacy prompt+options, plus a preselected recommended flag the model should not set.
    legacy = bot_asks.validate_spec({
        "prompt": live_prompt,
        "options": [
            {**live_opts[0], "recommended": True},
            live_opts[1],
            live_opts[2],
        ],
        "defaults": ["A"],
        "allow_other": False,
        "page_count": 2,
    })
    q = legacy["questions"][0]
    assert q["id"] == "upper_body_swap"
    assert q["prompt"] == live_prompt  # live title kept (garment-specific)
    assert q["allow_other"] is True
    assert q["placeholder"] == "以上都不符合，我自己补充...（自填）"
    assert legacy["allow_skip"] is True
    assert legacy["page_count"] == 1
    assert [o["label"] for o in q["options"]] == [o["label"] for o in live_opts]
    assert "recommended" not in q["options"][0]
    assert "defaults" not in q
    assert "defaults" not in legacy

    # Extra gender / ethnicity / angle questions are dropped; one swap question remains.
    messy = bot_asks.validate_spec({
        "questions": [
            {
                "id": "gender",
                "prompt": "由哪种性别的模特上身？",
                "options": [{"id": "A", "label": "女模特"}, {"id": "B", "label": "男模特"}],
                "page": 1,
            },
            {
                "id": "_",
                "prompt": live_prompt,
                "options": list(live_opts),
                "allow_other": False,
                "defaults": ["B"],
                "page": 1,
            },
            {
                "id": "angle",
                "prompt": "要用哪个角度？",
                "options": [{"id": "A", "label": "正面居中"}, {"id": "B", "label": "45度"}],
                "page": 2,
            },
        ],
        "page_count": 2,
    })
    assert len(messy["questions"]) == 1
    q2 = messy["questions"][0]
    assert q2["id"] == "upper_body_swap"
    assert q2["prompt"] == live_prompt
    assert [o["label"] for o in q2["options"]] == [o["label"] for o in live_opts]
    assert messy["page_count"] == 1
    assert "defaults" not in q2

    # Unrelated studio / gender cards must not be rewritten by this skeleton.
    other = bot_asks.validate_spec({
        "questions": [{
            "id": "gender",
            "prompt": "由哪种性别的模特上身？",
            "options": [
                {"id": "A", "label": "女模特", "recommended": True},
                {"id": "B", "label": "男模特"},
            ],
            "allow_other": True,
            "placeholder": "以上都不符合，我自己补充...（自填）",
            "page": 1,
        }],
        "allow_skip": True,
        "page_count": 1,
    })
    g = other["questions"][0]
    assert g["id"] == "gender"
    assert g["prompt"] == "由哪种性别的模特上身？"
    assert g["options"][0]["label"] == "女模特"
    assert "recommended" in g["options"][0]
    assert other.get("defaults") == ["A"]


def test_pins_and_auto_models_and_empty_text_fallback_unchanged():
    """No pin change, auto_models.json untouched, compose_provider_text not edited."""
    main_entry = _skill_entry(_main_skills(), "clothing-swap")
    entry = _skill_entry(SKILLS, "clothing-swap")
    ours_tail = entry[entry.find("category:"):]
    main_tail = main_entry[main_entry.find("category:"):]
    assert ours_tail == main_tail

    ours_auto = AUTO_MODELS.read_bytes()
    main_auto = subprocess.check_output(
        ["git", "-C", str(ROOT), "show", f"{MAIN_SHA}:api/auto_models.json"]
    )
    assert ours_auto == main_auto
    skills = json.loads(ours_auto.decode("utf-8")).get("skills") or {}
    assert "clothing-swap" not in skills

    ours_send = BOT_SEND.read_bytes()
    main_send = subprocess.check_output(
        ["git", "-C", str(ROOT), "show", f"{MAIN_SHA}:api/bot_send.py"]
    )
    assert ours_send == main_send
    send_txt = BOT_SEND.read_text(encoding="utf-8")
    assert "Look at the attached images and tell me what you see." in send_txt


def test_mutation_red_then_green():
    """Re-appending 708 or baking in option labels turns red; the on-disk tree stays green."""
    main = _main_skills()
    entry = _skill_entry(SKILLS, "clothing-swap")
    instr = _clothing_swap_instructions()
    assert "+ PORTRAIT_SHOTS_708 +" not in entry
    assert all(word not in entry for word in GARMENT_FORBIDDEN)

    mutated_708 = SKILLS.replace(
        entry,
        entry.replace("',\n    category:", "' + PORTRAIT_SHOTS_708 + '',\n    category:", 1),
        1,
    )
    red = False
    try:
        assert "+ PORTRAIT_SHOTS_708 +" not in _skill_entry(mutated_708, "clothing-swap")
    except AssertionError:
        red = True
    assert red, "re-adding 708 to clothing-swap should fail the detach lock"

    mutated_word = SKILLS.replace(
        'Use question id "upper_body_swap"',
        'Use question id "upper_body_swap" 宝蓝T恤',
        1,
    )
    assert "宝蓝" in _skill_entry(mutated_word, "clothing-swap")
    assert "宝蓝" not in entry

    # Green: on-disk tree still passes the 708-const and detach locks.
    assert _portrait_shots_708_const(SKILLS) == _portrait_shots_708_const(main)
    assert "+ PORTRAIT_SHOTS_708 +" not in _skill_entry(SKILLS, "clothing-swap")
    assert SKILLS == (ROOT / "src/skills.ts").read_text(encoding="utf-8")
    assert instr == _clothing_swap_instructions()


def _all_skill_ids(src: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\{ id: '([^']+)', name: t\(", src)))


def _shared_const(src: str, name: str) -> str:
    m = re.search(rf"^(?:export )?const {re.escape(name)}\b[^\n]*(?:\n  [^\n]*)*", src, re.M)
    assert m, f"shared const {name} missing"
    # Ignore an added `export ` keyword; the initializer bytes are what is locked.
    return m.group(0).removeprefix("export ")


SHARED_BLOCKS = ("PORTRAIT_SHOTS_708", "NEARMISS_INPUTS", "EFFECT_INPUTS", "REF_CARD_INPUTS_687")


def test_qa4_clothing_swap_drops_rule6_and_708_others_unchanged():
    """QA 4: clothing-swap has no Rule 6 / #708 content; every other skill and shared block unchanged."""
    main = _main_skills()
    entry = _skill_entry(SKILLS, "clothing-swap")
    instr = _clothing_swap_instructions()
    for needle in (
        "PORTRAIT_SHOTS_708",
        "Shot rules (#708)",
        "6) Angles:",
        "must not be all front-on and centered",
        "at most ONE frontal 0° eye-level shot per batch",
        "A single-image run is never frontal-centered",
        "subject on the left third",
        "Write each image prompt in English with these slots",
        "35mm f/2.8",
        "named directional light",
        "editorial color grade",
    ):
        assert needle not in entry, needle
        assert needle not in instr, needle

    # Shared blocks: initializer bytes identical to base.
    for name in SHARED_BLOCKS:
        assert _shared_const(SKILLS, name) == _shared_const(main, name), name
    assert hashlib.sha256(_portrait_shots_708_const(SKILLS).encode()).hexdigest() == PORTRAIT_SHOTS_708_CONST_SHA256

    # Every other skill entry (studio-model, ai-model, and the rest) byte-identical to base.
    ids = _all_skill_ids(main)
    assert "studio-model" in ids and "ai-model" in ids and "clothing-swap" in ids
    assert _all_skill_ids(SKILLS) == ids
    changed = []
    for sid in ids:
        if sid == "clothing-swap":
            continue
        try:
            ours, base = _skill_entry(SKILLS, sid), _skill_entry(main, sid)
        except AssertionError:
            # Entries this regex cannot parse: compare the raw id line instead.
            line = rf"^.*\{{ id: '{re.escape(sid)}'.*$"
            ours = re.search(line, SKILLS, re.M).group(0)
            base = re.search(line, main, re.M).group(0)
        if ours != base:
            changed.append(sid)
    assert changed == []


def test_qa5_output_ratio_follows_image1_1776x2368_is_3x4_never_16x9():
    """QA 5: a 1776x2368 person photo yields 3:4, never the 16:9 default, even if the model asks for 16:9."""
    w, h = PERSON_PHOTO_SIZE
    assert (w, h) == (1776, 2368) and w * 4 == h * 3
    for model_args in (
        {"prompt": "swap the top"},
        {"prompt": "swap the top", "ratio": "16:9"},
        {"prompt": "swap the top", "ratio": "16:9", "width": 1820, "height": 1024},
        {"prompt": "swap the top", "width": 1024, "height": 1024},
        {"prompt": "swap the top", "skill": "clothing-swap", "ratio": "16:9"},
    ):
        out = apply_generate(dict(model_args), "clothing-swap")
        assert out["ratio"] == "3:4", model_args
        assert out["ratio"] != "16:9"
        assert out["width"] * 4 == out["height"] * 3
        assert (out["width"], out["height"]) == DECLARED_SIZE
        assert out["width"] <= 2048 and out["height"] <= 2048
        assert out["size_lock"] is True and out["count"] == 1


# --- Future QA 1-3 (empty-text provider line), pending tech's decision. ---
# compose_provider_text is NOT changed in this PR. Once tech decides, drop the
# skip and fill PENDING_PROVIDER_CASES expectations. Design rule: any injected
# line is model-only — never in the user bubble or chat history.
EMPTY_TEXT_LINE = "Look at the attached images and tell me what you see."
PENDING_PROVIDER_CASES = [
    # (case id, text, skill_name, expect_empty_line_in_provider_text)
    ("qa1_skill_empty_text_no_look_line", "", "clothing-swap", False),
    ("qa2_no_skill_empty_text_unchanged", "", "", True),
    ("qa3_skill_nonempty_text_not_rewritten", "换成第二张图的T恤", "clothing-swap", False),
]


@pytest.mark.skip(reason="#911 pending tech decision on compose_provider_text empty-text fallback")
@pytest.mark.parametrize("case,text,skill,expect_line", PENDING_PROVIDER_CASES, ids=[c[0] for c in PENDING_PROVIDER_CASES])
def test_pending_empty_text_provider_line(case, text, skill, expect_line):
    from ComfyArt.api.bot_send import compose_provider_text

    out = compose_provider_text(text, skill_name=skill, memory="", lines=[], review=True)
    assert (EMPTY_TEXT_LINE in out) is expect_line, case
    if text:
        assert text in out, case
    # Bubble / history must keep the user's own text (model-only injection) — add
    # a send-path assertion here once the fix lands (user_msg blocks == text).
