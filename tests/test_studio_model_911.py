"""#911 studio-model: Lovart question STRUCTURE (not this garment's options) and detach 708.

Options on Lovart's official "E-commerce Premium Studio On-Body Shot Designer"
card are generated live from the uploaded garment, so they must not be copied
into src/skills.ts. This file may name those words only to forbid them in the
skill entry; they may appear in a validation chat's user message.

No WaveSpeed call. $0 static. Pins and api/auto_models.json must stay unchanged.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
AUTO_MODELS = ROOT / "api/auto_models.json"

# Locked to origin/main 33d28eab5 (same bytes as PR #912's lock).
AUTO_MODELS_SHA256 = "776c7ff035d679ade4cde30633ccd421244d91bf6798b557aed268ed30986532"
PORTRAIT_SHOTS_708_CONST_SHA256 = "97edb7c18215e4a283b86633908872f3b3c4146d9bb748d71c0d3510798cfc8b"

STUDIO_EXAMPLES = "examples: ex643('studio-model', [1, 2], '9ca3c35db7868e9fe73fb98bf85058c8fa2e048e')"
STUDIO_VIDEO = "video: pinned('805/reuse/studio-model', '44a5caa051ad8c4bd51152afba8ef853e9c77fd8', 'cover.mp4')"
STUDIO_COVER = "cover: cover643('studio-model')"

# Structural zh prompts / options that are not garment-specific.
GENDER_A = "女模特"
GENDER_B = "男模特"
ETHNICITY_LABELS = ("亚洲人", "白人", "黑人")
SELLING_POINTS_PROMPT = "详情页这张图，你最想让买家第一眼看到什么？"
ETHNICITY_PROMPT = "模特族裔："
STUDIO_DIRECTION_PROMPT = "选一个棚拍方向继续生成："
RECOMMENDED_SUFFIX = "（推荐）"
OTHER_PLACEHOLDER = "以上都不符合，我自己补充...（自填）"
DIRECTION_OTHER_PLACEHOLDER = "以上都不符合，我自己描述方向…"

NO_ANGLE_SENTENCE = (
    "Do not state head angle, gaze direction or subject position unless the "
    "user's words, a card answer, a reference or this skill's base-image layout give one."
)

# This garment's live card / output words. Forbidden in the studio-model skill entry.
GARMENT_FORBIDDEN = (
    "royal blue",
    "皇家蓝",
    "drop shoulder",
    "落肩",
    "rib collar",
    "罗纹领",
    "印花",
    "米色",
    "beige",
)
# "print" is a common English word in other skills (print-ready, etc.); forbid
# only as a whole word inside the studio-model entry.
GARMENT_FORBIDDEN_WORD = ("print",)

# Do not hardcode Lovart's observed framing / angle from the sample output.
HARDCODED_FRAMING = (
    "thigh-up",
    "thigh",
    "slight body turn",
    "off-camera gaze",
    "gaze off-camera",
    "看向画外",
    "身体略侧",
    "微侧",
    "七分身",
    "大腿",
)


def _unescape_ts_string(s: str) -> str:
    return (
        s.replace("\\\\", "\0")
        .replace("\\n", "\n")
        .replace("\\'", "'")
        .replace("\\t", "\t")
        .replace("\0", "\\")
    )


def _studio_model_instructions(src: str = SKILLS) -> str:
    m = re.search(
        r"\{ id: 'studio-model', name: t\('skills.studioModel'\), instructions: '((?:\\.|[^'\\])*)'",
        src,
    )
    assert m, "studio-model instructions string did not parse"
    return _unescape_ts_string(m.group(1))


def _skill_entry(src: str, sid: str) -> str:
    m = re.search(
        rf"{{ id: '{re.escape(sid)}', name: t\('[^']+'\), instructions: [\s\S]*?inputs: [^\n]+}},",
        src,
    )
    assert m, f"skill entry missing: {sid}"
    return m.group(0)


def _portrait_shots_708_const(src: str) -> str:
    m = re.search(
        r"const PORTRAIT_SHOTS_708 = ((?:'(?:\\.|[^'\\])*'(?:\s*\+\s*)?)+)",
        src,
    )
    assert m, "PORTRAIT_SHOTS_708 constant missing"
    return m.group(1)


MAIN_SHA = "33d28eab5d75b8ab0526776abd496f4565d6e756"


def _main_skills() -> str:
    # Pin the exact main tip (do not use a possibly stale local origin/main ref).
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "show", f"{MAIN_SHA}:src/skills.ts"],
        text=True,
        encoding="utf-8",
    )


def _forbidden_hits(entry: str) -> list[str]:
    hits: list[str] = []
    lower = entry.lower()
    for needle in GARMENT_FORBIDDEN:
        if needle.lower() in lower:
            hits.append(needle)
    for word in GARMENT_FORBIDDEN_WORD:
        if re.search(rf"\b{re.escape(word)}\b", entry, flags=re.I):
            hits.append(word)
    return hits


def _framing_hits(entry: str) -> list[str]:
    hits: list[str] = []
    lower = entry.lower()
    for needle in HARDCODED_FRAMING:
        if needle.lower() in lower:
            hits.append(needle)
    return hits


def _studio_has_no_708(src: str) -> None:
    entry = _skill_entry(src, "studio-model")
    instr = _studio_model_instructions(src)
    assert "+ PORTRAIT_SHOTS_708 +" not in entry
    assert "PORTRAIT_SHOTS_708" not in entry
    assert "Shot rules (#708)" not in entry
    assert "Shot rules (#708)" not in instr
    assert "at most ONE frontal 0° eye-level shot per batch" not in instr
    assert "Default 4 stills of the same model" not in instr
    assert "Rembrandt" not in instr
    assert "beauty dish" not in instr
    assert "just above the knee" not in instr


def _clothing_swap_and_708_const_match_main(src: str, main: str) -> None:
    assert _portrait_shots_708_const(src) == _portrait_shots_708_const(main)
    assert hashlib.sha256(_portrait_shots_708_const(src).encode()).hexdigest() == PORTRAIT_SHOTS_708_CONST_SHA256
    assert _skill_entry(src, "clothing-swap") == _skill_entry(main, "clothing-swap")
    assert "+ PORTRAIT_SHOTS_708 +" in _skill_entry(src, "clothing-swap")


def test_ask_card_is_two_steps_with_structure_and_order():
    """Two ask_user steps: first card (gender, selling points, ethnicity), then direction."""
    instr = _studio_model_instructions()
    assert "call ask_user twice" in instr
    assert "two steps" in instr
    assert "Do not combine both cards into one ask_user call" in instr
    # Not the previous single four-question card.
    assert "one card of four questions" not in instr
    assert "page_count 4" not in instr
    assert "1 of 4" not in instr
    assert "header 1 of 4" not in instr
    assert "allow_skip" in instr
    assert "none are preselected" in instr or "Do not set defaults or recommended" in instr
    for needle in ("recommended: true", '"recommended"', "defaults: ["):
        assert needle not in instr

    assert instr.index("First card") < instr.index("Second card")
    assert instr.index('id "gender"') < instr.index('id "selling_points"') < instr.index(
        'id "ethnicity"'
    ) < instr.index('id "studio_direction"')
    assert instr.index('id "gender"') < instr.index("Second card") < instr.index(
        'id "studio_direction"'
    )
    for qid in ("gender", "selling_points", "ethnicity", "studio_direction"):
        chunk_start = instr.index(f'id "{qid}"')
        chunk = instr[chunk_start:chunk_start + 80]
        assert "page 1" in chunk, qid

    assert instr.index(SELLING_POINTS_PROMPT) < instr.index(ETHNICITY_PROMPT) < instr.index(
        STUDIO_DIRECTION_PROMPT
    )
    assert GENDER_A in instr and GENDER_B in instr
    assert instr.index(GENDER_A) < instr.index(GENDER_B)
    for label in ETHNICITY_LABELS:
        assert label in instr, label
    positions = [instr.index(lab) for lab in ETHNICITY_LABELS]
    assert positions == sorted(positions)

    assert "selling points visible on the uploaded garment" in instr
    assert "never invent features that are not on the garment" in instr or "never invent garment features" in instr
    assert OTHER_PLACEHOLDER in instr
    assert "allow_other" in instr
    assert "If the user skips or does not answer a question, use the user's own words" in instr
    assert "otherwise take the first option" in instr


def test_first_card_option_count_follows_the_question():
    """Gender is two chips + free text; do not pad a short question to four options."""
    instr = _studio_model_instructions()
    assert "Option counts must follow the question" in instr
    assert "do not pad a short question to four chips" in instr
    assert "gender is two options plus the free-text other row, not four options" in instr
    assert "exactly A 女模特, B 男模特" in instr
    assert "do not add a third or fourth chip" in instr
    first = instr[instr.index("First card"):instr.index("Second card")]
    assert "page_count 3" in first
    assert "1 of 3" in first
    assert "2 of 3" in first and "do not paginate" in first.lower() or "do not paginate with 下一步 into 2 of 3 or 3 of 3" in first
    assert "questions[] of three questions" in first


def test_direction_card_title_footer_recommended_and_other_row():
    """Lovart direction card (review-assets 87857c35): exact title, no pager, Skip+Submit, (推荐) on A text only."""
    instr = _studio_model_instructions()
    second = instr[instr.index("Second card"):]
    assert STUDIO_DIRECTION_PROMPT in second
    assert f'prompt exactly "{STUDIO_DIRECTION_PROMPT}"' in second
    assert "page_count 1" in second
    assert "no 1 of N pager" in second
    assert "only Skip and Submit" in second
    assert "Skip / Next" not in second
    assert DIRECTION_OTHER_PLACEHOLDER in second
    assert f'the last option is "{DIRECTION_OTHER_PLACEHOLDER}"' in second
    # Older wording with ASCII dots + （自填） must not remain.
    assert "以上都不符合，我自己描述方向...（自填）" not in instr
    assert RECOMMENDED_SUFFIX in second
    assert "Append" in second and RECOMMENDED_SUFFIX in second and "option A" in second
    assert "do not set recommended, defaults, or any preselect" in second
    assert "each stating a background + a pose" in second
    assert "framing words such as 半身 are optional" in second
    assert "正面 is allowed" in second
    assert "exactly 3 options" in second
    # Second card stays a single-question card with no 1 of N pager.
    assert "page_count 1" in second
    assert "no 1 of N pager" in second
    # First card (not this card) uses page_count 3 only for the 1 of 3 header.
    first = instr[instr.index("First card"):instr.index("Second card")]
    assert "page_count 3" in first and "1 of 3" in first
    assert "page_count 4" not in instr and "1 of 4" not in instr


def test_default_output_is_one_image_and_prompt_rules():
    instr = _studio_model_instructions()
    assert "Default output is 1 image" in instr
    assert "not 4" in instr
    assert "Default 4 stills" not in instr
    assert "only the user's words, the card answers, the reference garment" in instr
    assert "inherent layout purpose" in instr
    assert "e-commerce detail-page on-body studio still" in instr
    assert "Do not invent a lens, lighting setup" in instr
    assert "shot length" in instr
    assert 'Do not write "even soft studio lighting" or "full-length".' in instr
    assert NO_ANGLE_SENTENCE in instr
    # Old rule-8 tail without the layout exception must not remain.
    assert (
        "unless the user's words, a card answer, a reference or this skill's base-image layout give one."
        in instr
    )
    assert "unless the user's words, a card answer or a reference give one." not in instr


def test_generate_image_requires_skill_studio_model():
    """Every generate_image call must pass skill: studio-model; apply_generate backfills if omitted."""
    from ComfyArt.bot.skill_output import apply_generate

    instr = _studio_model_instructions()
    assert 'skill: "studio-model"' in instr
    assert "Every generate_image call must pass skill:" in instr
    assert "Every generate_image call must include skill:" in instr

    filled = apply_generate({"prompt": "on-body still", "ratio": "3:4"}, "studio-model")
    assert filled["skill"] == "studio-model"
    assert filled["prompt"] == "on-body still"
    assert filled["ratio"] == "3:4"
    assert "width" not in filled and "height" not in filled
    assert "size_lock" not in filled
    assert "count" not in filled

    already = apply_generate({"prompt": "x", "skill": "studio-model", "ratio": "3:4"}, "studio-model")
    assert already == {"prompt": "x", "skill": "studio-model", "ratio": "3:4"}

    bare = apply_generate({"prompt": "cat", "ratio": "1:1"})
    assert bare == {"prompt": "cat", "ratio": "1:1"}
    other = apply_generate({"prompt": "x"}, "ai-model")
    assert other == {"prompt": "x"}


def test_prompt_forbids_invented_lighting_and_full_length():
    instr = _studio_model_instructions()
    assert 'Do not write "even soft studio lighting" or "full-length".' in instr
    lighting_idx = instr.index("even soft studio lighting")
    length_idx = instr.index("full-length")
    assert "Do not write" in instr[max(0, lighting_idx - 40):lighting_idx]
    assert "Do not write" in instr[max(0, length_idx - 80):length_idx]


def test_studio_model_entry_forbids_garment_specific_words_and_hardcoded_framing():
    """皇家蓝 / 落肩 / 印花 / 罗纹领 / beige etc. must not live in the skill."""
    entry = _skill_entry(SKILLS, "studio-model")
    assert _forbidden_hits(entry) == []
    assert _framing_hits(entry) == []
    # Also not in the parsed instructions alone.
    instr = _studio_model_instructions()
    assert _forbidden_hits(instr) == []
    assert _framing_hits(instr) == []


def test_qa_no_708_on_studio_model():
    _studio_has_no_708(SKILLS)


def test_qa_708_constant_and_clothing_swap_byte_identical_to_origin_main():
    _clothing_swap_and_708_const_match_main(SKILLS, _main_skills())


def test_pins_and_auto_models_unchanged():
    entry = _skill_entry(SKILLS, "studio-model")
    main_entry = _skill_entry(_main_skills(), "studio-model")
    assert STUDIO_EXAMPLES in entry and STUDIO_EXAMPLES in main_entry
    assert STUDIO_VIDEO in entry and STUDIO_VIDEO in main_entry
    assert STUDIO_COVER in entry
    # Everything from category: onward (cover, examples, featured, video, presets, inputs)
    # stays byte-identical to origin/main. Only the instructions string (and the
    # dropped 708 append) may change.
    ours_tail = entry[entry.find("category:"):]
    main_tail = main_entry[main_entry.find("category:"):]
    assert ours_tail == main_tail
    assert hashlib.sha256(AUTO_MODELS.read_bytes()).hexdigest() == AUTO_MODELS_SHA256
    main_auto = subprocess.check_output(
        ["git", "-C", str(ROOT), "show", f"{MAIN_SHA}:api/auto_models.json"]
    )
    assert AUTO_MODELS.read_bytes() == main_auto


def test_ai_model_untouched_on_this_branch():
    """This PR branches from main, not #912; ai-model stays byte-identical."""
    main = _main_skills()
    assert _skill_entry(SKILLS, "ai-model") == _skill_entry(main, "ai-model")


def test_mutation_red_then_green():
    """Re-adding 708, editing clothing-swap, or baking in garment words turns red; restore is green."""
    main = _main_skills()
    # Green on the real tree first.
    _studio_has_no_708(SKILLS)
    _clothing_swap_and_708_const_match_main(SKILLS, main)
    assert _forbidden_hits(_skill_entry(SKILLS, "studio-model")) == []

    # Red: re-append 708 on studio-model only (in memory).
    entry = _skill_entry(SKILLS, "studio-model")
    mutated_708 = SKILLS.replace(
        entry,
        entry.replace(",\n    category:", " + PORTRAIT_SHOTS_708 + '',\n    category:", 1)
        if "+ PORTRAIT_SHOTS_708 +" not in entry
        else entry,
        1,
    )
    # The instructions line ends with "',\\n    category:" after our patch.
    if "+ PORTRAIT_SHOTS_708 +" not in _skill_entry(mutated_708, "studio-model"):
        mutated_708 = SKILLS.replace(
            "Default output is 1 image of the same model (not 4).",
            "Default output is 1 image of the same model (not 4).' + PORTRAIT_SHOTS_708 + '",
            1,
        )
    red = False
    try:
        _studio_has_no_708(mutated_708)
    except AssertionError:
        red = True
    assert red, "re-adding 708 to studio-model should fail the no-708 lock"

    # Red: clothing-swap assembly drifted.
    swap = _skill_entry(SKILLS, "clothing-swap")
    mutated_swap = SKILLS.replace(swap, swap.replace("You are a production", "You are a MUTATED production", 1), 1)
    red = False
    try:
        _clothing_swap_and_708_const_match_main(mutated_swap, main)
    except AssertionError:
        red = True
    assert red, "editing clothing-swap should fail the byte-identical lock"

    # Red: garment-specific word leaks into the studio-model entry.
    mutated_word = SKILLS.replace(
        'id "selling_points"',
        'id "selling_points" 皇家蓝',
        1,
    )
    hits = _forbidden_hits(_skill_entry(mutated_word, "studio-model"))
    assert "皇家蓝" in hits

    # Green: the on-disk tree is unchanged and still passes.
    _studio_has_no_708(SKILLS)
    _clothing_swap_and_708_const_match_main(SKILLS, main)
    assert _forbidden_hits(_skill_entry(SKILLS, "studio-model")) == []
    assert SKILLS == (ROOT / "src/skills.ts").read_text(encoding="utf-8")
