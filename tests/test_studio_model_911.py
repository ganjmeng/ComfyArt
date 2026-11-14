"""#911 studio-model: Lovart question STRUCTURE (not this garment's options) and detach 708.

Options on Lovart's official "E-commerce Premium Studio On-Body Shot Designer"
card are generated live from the uploaded garment, so they must not be copied
into src/skills.ts. This file may name those words only to forbid them in the
skill entry; they may appear in a validation chat's user message.

No WaveSpeed call. $0 static. Angela 07:27 pins studio-model to GPT Image 2.6 Sunburst (text-to-image with no reference, edit when a reference is given). The ai-model Rule 5 lock is a fixed presence check, not a diff against origin/main.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
AUTO_MODELS = ROOT / "api/auto_models.json"

# Locked to origin/main 33d28eab5 (same bytes as PR #912's lock), except skills.ai-model.
# #935: literal hashes of the base bytes; no git object is opened.
PORTRAIT_SHOTS_708_CONST_SHA256 = "97edb7c18215e4a283b86633908872f3b3c4146d9bb748d71c0d3510798cfc8b"
STUDIO_MODEL_TAIL_SHA256 = "ae5a43e7574fd1939edcb7217d8f434e07ffc094cd3d14d217e0f1b3b7090cf2"
AUTO_MODELS_SHA256 = "9ef106b6133d427f04347d0c31c31931e641e1cd47d2a86c0d0769cde48c5d7b"

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


def _708_const_matches_pinned(src: str) -> None:
    """Shared #708 block stays byte-identical; clothing-swap no longer appends it (#911)."""
    assert hashlib.sha256(_portrait_shots_708_const(src).encode()).hexdigest() == PORTRAIT_SHOTS_708_CONST_SHA256


def _clothing_swap_has_no_708(src: str) -> None:
    entry = _skill_entry(src, "clothing-swap")
    assert "+ PORTRAIT_SHOTS_708 +" not in entry
    assert "PORTRAIT_SHOTS_708" not in entry
    assert "Shot rules (#708)" not in entry
    assert "6) Angles:" not in entry


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
    assert "header is 1 of 3" in first
    assert "one scrollable card" in first
    assert "page_count 3 only drives the header 1 of 3" in first
    assert "Do not put these three questions on separate pages" in first
    assert "do not paginate with 下一步 into 2 of 3 or 3 of 3" in first
    assert "Skip + Next until the bottom" in first
    assert "then Skip + Submit" in first
    assert "page_count 1" not in first
    assert "questions[] of three questions" in first
    assert "all page 1" in first
    assert "Do not set page_count above 1 on either card" not in instr
    assert "This is transitional" not in instr


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
    # First card is page_count 3 / header 1 of 3 on one scrollable page;
    # the direction follow-up stays page_count 1 (no 1 of N pager).
    first = instr[instr.index("First card"):instr.index("Second card")]
    assert "page_count 3" in first
    assert "header is 1 of 3" in first
    assert "one scrollable card" in first
    assert "page_count 1" not in first
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
    # After stacking #912, an ai-model session also fills skill= (no size).
    other = apply_generate({"prompt": "x"}, "ai-model")
    assert other == {"prompt": "x", "skill": "ai-model"}
    # #911 clothing-swap now declares a 3:4 canvas (person-photo ratio, in-limit size).
    swap = apply_generate({"prompt": "x"}, "clothing-swap")
    assert swap["skill"] == "clothing-swap"
    assert (swap["width"], swap["height"], swap["ratio"], swap["count"]) == (1536, 2048, "3:4", 1)
    assert swap["size_lock"] is True

    # Explicit model: do not auto-fill skill (and never invent or pin a model).
    explicit = apply_generate(
        {"prompt": "x", "model": "openai/gpt-image-2.6-sunburst"}, "studio-model"
    )
    assert explicit == {"prompt": "x", "model": "openai/gpt-image-2.6-sunburst"}


SUNBURST_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"

EXPECTED_STUDIO_MODEL_PIN = {
    "feature": "text_to_image",
    "model": SUNBURST_T2I,
    "edit_model": SUNBURST_EDIT,
    "zh": "studio-model 技能固定用 GPT Image 2.6 Sunburst（无参考文生，有参考编辑）",
    "en": "the studio-model skill is pinned to GPT Image 2.6 Sunburst (text-to-image with no reference, edit when a reference is given)",
}

EXPECTED_CLOTHING_SWAP_PIN = {
    "feature": "image_edit",
    "model": SUNBURST_EDIT,
    "zh": "clothing-swap 技能固定用 GPT Image 2.6 Sunburst 编辑",
    "en": "the clothing-swap skill is pinned to GPT Image 2.6 Sunburst edit",
}

EXPECTED_PRODUCT_TO_PACKAGING_PIN = {
    "feature": "text_to_image",
    "model": SUNBURST_T2I,
    "edit_model": SUNBURST_EDIT,
    "zh": "product-to-packaging 技能固定用 GPT Image 2.6 Sunburst（无参考文生，有参考编辑）",
    "en": "the product-to-packaging skill is pinned to GPT Image 2.6 Sunburst (text-to-image with no reference, edit when a reference is given)",
}

EXPECTED_COVER_DESIGN_DIRECTOR_PIN = {
    "feature": "text_to_image",
    "model": SUNBURST_T2I,
    "edit_model": SUNBURST_EDIT,
    "zh": "cover-design-director 技能固定用 GPT Image 2.6 Sunburst（无参考文生，有参考编辑）",
    "en": "the cover-design-director skill is pinned to GPT Image 2.6 Sunburst (text-to-image with no reference, edit when a reference is given)",
}

EXPECTED_YOUTUBE_CHANNEL_BANNER_PIN = {
    "feature": "text_to_image",
    "model": SUNBURST_T2I,
    "edit_model": SUNBURST_EDIT,
    "zh": "youtube-channel-banner 技能固定用 GPT Image 2.6 Sunburst（无参考文生，有参考编辑）",
    "en": "the youtube-channel-banner skill is pinned to GPT Image 2.6 Sunburst (text-to-image with no reference, edit when a reference is given)",
}

EXPECTED_PORTRAIT_STUDIO_PIN = {
    "feature": "image_edit",
    "model": SUNBURST_EDIT,
    "resolution": "2k",
    "ratio": "3:4",
    "zh": "portrait-studio 技能固定用 GPT Image 2.6 Sunburst 编辑（2K，3:4）",
    "en": "the portrait-studio skill is pinned to GPT Image 2.6 Sunburst edit at 2K 3:4",
}


def test_studio_model_routes_sunburst_edit_or_t2i_3x4():
    """Rewritten lock (Angela 07:27): studio-model is pinned to Sunburst.

    No reference -> text-to-image; a reference or base -> edit. The pin has no
    resolution/ratio, so an explicit 3:4 1536×2048 canvas is kept by _pin_args
    (_PIN_KEEPS_SIZE). The submitted Sunburst payload is still resolution 2k
    + aspect_ratio 3:4, not exact pixels (native 2k 3:4 is 1664×2224).
    studio-model stays out of EXACT_SKILLS, so the exact-size path is not used.
    Ratio-only calls fill edit_resolution 2k and do not invent pixels.
    """
    import json

    from ComfyArt.api.mcp_tools import canvas
    from ComfyArt.api.skill_size import EXACT_SKILLS

    skills = json.loads(AUTO_MODELS.read_text(encoding="utf-8")).get("skills") or {}
    assert skills["studio-model"] == EXPECTED_STUDIO_MODEL_PIN
    assert "studio-model" not in EXACT_SKILLS

    size = {"ratio": "3:4", "width": 1536, "height": 2048, "count": 1}
    no_ref = {"prompt": "on-body studio still", "skill": "studio-model", **size}
    c = canvas._auto_choice("generate_image", dict(no_ref))
    assert c["model"] == SUNBURST_T2I
    assert c["category"] == "skill"
    assert "edit_model" not in c
    pinned = canvas._pin_args(dict(no_ref), c)
    assert pinned["model"] == SUNBURST_T2I
    assert (pinned["width"], pinned["height"], pinned["ratio"]) == (1536, 2048, "3:4")

    with_ref = {**no_ref, "refs": ["shape:studio-model-garment"]}
    c = canvas._auto_choice("generate_image", dict(with_ref))
    assert c["model"] == c["edit_model"] == SUNBURST_EDIT
    assert c["category"] == "skill"
    pinned = canvas._pin_args(dict(with_ref), c)
    assert pinned["edit_model"] == SUNBURST_EDIT
    assert pinned.get("model") != SUNBURST_T2I
    assert (pinned["width"], pinned["height"], pinned["ratio"]) == (1536, 2048, "3:4")

    with_base = {"prompt": "on-body studio still", "skill": "studio-model", "base": "shape:base", **size}
    c = canvas._auto_choice("generate_image", dict(with_base))
    assert c["model"] == c["edit_model"] == SUNBURST_EDIT
    pinned = canvas._pin_args(dict(with_base), c)
    assert (pinned["width"], pinned["height"], pinned["ratio"]) == (1536, 2048, "3:4")


def test_direction_card_is_normalized_in_ask_user_validate_spec():
    """Code enforces only the direction-card skeleton; live option text is left alone."""
    from ComfyArt.api import bot_asks

    live_opts = [
        {"id": "a", "label": "浅灰无缝背景 + 正面站姿半身"},
        {"id": "b", "label": "纯白无缝背景 + 正面全身站姿"},
        {"id": "c", "label": "米白背景 + 侧身微转半身"},
    ]

    # Legacy prompt+options (the $0 miss: id became "_", no placeholder).
    legacy = bot_asks.validate_spec({
        "prompt": STUDIO_DIRECTION_PROMPT,
        "options": live_opts,
        "page_count": 3,
        "allow_skip": False,
    })
    q = legacy["questions"][0]
    assert q["id"] == "studio_direction"
    assert q["prompt"] == STUDIO_DIRECTION_PROMPT
    assert q["placeholder"] == DIRECTION_OTHER_PLACEHOLDER
    assert q["allow_other"] is True
    assert legacy["allow_skip"] is True
    assert legacy["page_count"] == 1
    # Option contents stay the model's live labels — no （推荐） appended in code.
    assert [o["label"] for o in q["options"]] == [o["label"] for o in live_opts]
    assert RECOMMENDED_SUFFIX not in q["options"][0]["label"]

    # questions[] with the wrong id / missing placeholder / a title typo via id.
    messy = bot_asks.validate_spec({
        "questions": [{
            "id": "_",
            "prompt": STUDIO_DIRECTION_PROMPT,
            "options": [
                {"id": "A", "label": "浅灰无缝背景 + 正面站姿半身（推荐）"},
                {"id": "B", "label": "纯白无缝背景 + 正面全身站姿"},
                {"id": "C", "label": "米白背景 + 侧身微转半身"},
            ],
            "allow_other": False,
            "page": 1,
        }],
        "page_count": 2,
    })
    q2 = messy["questions"][0]
    assert q2["id"] == "studio_direction"
    assert q2["prompt"] == STUDIO_DIRECTION_PROMPT
    assert q2["placeholder"] == DIRECTION_OTHER_PLACEHOLDER
    assert q2["allow_other"] is True
    assert messy["allow_skip"] is True
    assert messy["page_count"] == 1
    assert q2["options"][0]["label"] == "浅灰无缝背景 + 正面站姿半身（推荐）"
    assert q2["options"][0]["label"].count(RECOMMENDED_SUFFIX) == 1

    # Id already correct but title drifted — force the locked title, keep options.
    drifted = bot_asks.validate_spec({
        "questions": [{
            "id": "studio_direction",
            "prompt": "选一个方向：",
            "options": list(live_opts),
            "page": 1,
        }],
    })
    q3 = drifted["questions"][0]
    assert q3["id"] == "studio_direction"
    assert q3["prompt"] == STUDIO_DIRECTION_PROMPT
    assert q3["placeholder"] == DIRECTION_OTHER_PLACEHOLDER
    assert [o["label"] for o in q3["options"]] == [o["label"] for o in live_opts]

    # Unrelated cards must not be rewritten.
    other = bot_asks.validate_spec({
        "questions": [{
            "id": "gender",
            "prompt": "由哪种性别的模特上身？",
            "options": [
                {"id": "A", "label": "女模特", "recommended": True},
                {"id": "B", "label": "男模特"},
            ],
            "allow_other": True,
            "placeholder": OTHER_PLACEHOLDER,
            "page": 1,
        }],
        "allow_skip": True,
        "page_count": 1,
    })
    g = other["questions"][0]
    assert g["id"] == "gender"
    assert g["placeholder"] == OTHER_PLACEHOLDER
    assert g["options"][0]["label"] == "女模特"
    assert "recommended" in g["options"][0]
    assert other.get("defaults") == ["A"]


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


def test_qa_708_constant_byte_identical_and_clothing_swap_detached():
    _708_const_matches_pinned(SKILLS)
    _clothing_swap_has_no_708(SKILLS)


def test_pins_and_auto_models_unchanged():
    entry = _skill_entry(SKILLS, "studio-model")
    assert STUDIO_EXAMPLES in entry
    assert STUDIO_VIDEO in entry
    assert STUDIO_COVER in entry
    # Everything from category: onward (cover, examples, featured, video, presets, inputs)
    # stays byte-identical to the pinned base. Only the instructions string (and the
    # dropped 708 append) may change. The hashes are literal (#935); no git object.
    ours_tail = entry[entry.find("category:"):]
    assert hashlib.sha256(ours_tail.encode()).hexdigest() == STUDIO_MODEL_TAIL_SHA256
    import json
    assert hashlib.sha256(AUTO_MODELS.read_bytes()).hexdigest() == AUTO_MODELS_SHA256
    ours_auto = json.loads(AUTO_MODELS.read_text(encoding="utf-8"))
    assert ours_auto["skills"]["studio-model"] == EXPECTED_STUDIO_MODEL_PIN
    assert ours_auto["skills"]["studio-model"]["model"] == SUNBURST_T2I
    assert ours_auto["skills"]["studio-model"]["edit_model"] == SUNBURST_EDIT
    assert ours_auto["skills"]["clothing-swap"] == EXPECTED_CLOTHING_SWAP_PIN
    assert ours_auto["skills"]["clothing-swap"]["model"] == SUNBURST_EDIT
    assert ours_auto["skills"]["product-to-packaging"] == EXPECTED_PRODUCT_TO_PACKAGING_PIN
    assert ours_auto["skills"]["product-to-packaging"]["model"] == SUNBURST_T2I
    assert ours_auto["skills"]["product-to-packaging"]["edit_model"] == SUNBURST_EDIT
    assert ours_auto["skills"]["cover-design-director"] == EXPECTED_COVER_DESIGN_DIRECTOR_PIN
    assert ours_auto["skills"]["cover-design-director"]["model"] == SUNBURST_T2I
    assert ours_auto["skills"]["cover-design-director"]["edit_model"] == SUNBURST_EDIT
    assert ours_auto["skills"]["youtube-channel-banner"] == EXPECTED_YOUTUBE_CHANNEL_BANNER_PIN
    assert ours_auto["skills"]["youtube-channel-banner"]["model"] == SUNBURST_T2I
    assert ours_auto["skills"]["youtube-channel-banner"]["edit_model"] == SUNBURST_EDIT
    assert ours_auto["skills"]["portrait-studio"] == EXPECTED_PORTRAIT_STUDIO_PIN
    assert ours_auto["skills"]["portrait-studio"]["model"] == SUNBURST_EDIT
    assert ours_auto["skills"]["portrait-studio"]["resolution"] == "2k"
    assert ours_auto["skills"]["portrait-studio"]["ratio"] == "3:4"
    assert "edit_model" not in ours_auto["skills"]["portrait-studio"]

def test_ai_model_rule5_names_registered_sunburst():
    """#915 Rule 5 must name the registered Sunburst model; the pre-#915 wording must not remain."""
    ours = _skill_entry(SKILLS, "ai-model")
    old = 'pass skill: "ai-model" and shape ids in refs on every generate_image call.'
    new = (
        'pass skill: "ai-model" and shape ids in refs on every generate_image call '
        "(the skill runs on its registered model, GPT Image 2.6 Sunburst)."
    )
    assert new in ours
    assert old not in ours
    assert "5) Refs:" in ours
    assert "GPT Image 2.6 Sunburst" in ours


def test_mutation_red_then_green():
    """Re-adding 708, editing clothing-swap, or baking in garment words turns red; restore is green."""
    # Green on the real tree first.
    _studio_has_no_708(SKILLS)
    _708_const_matches_pinned(SKILLS)
    _clothing_swap_has_no_708(SKILLS)
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

    # Red: re-append 708 on clothing-swap (in memory).
    swap = _skill_entry(SKILLS, "clothing-swap")
    mutated_swap = SKILLS.replace(
        swap,
        swap.replace("',\n    category:", "' + PORTRAIT_SHOTS_708 + '',\n    category:", 1),
        1,
    )
    red = False
    try:
        _clothing_swap_has_no_708(mutated_swap)
    except AssertionError:
        red = True
    assert red, "re-adding 708 to clothing-swap should fail the detach lock"

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
    _708_const_matches_pinned(SKILLS)
    _clothing_swap_has_no_708(SKILLS)
    assert _forbidden_hits(_skill_entry(SKILLS, "studio-model")) == []
    assert SKILLS == (ROOT / "src/skills.ts").read_text(encoding="utf-8")

def test_first_card_reuses_912_same_page_scroll_renderer():
    """First card page_count 3 + all questions on page 1 uses #912's scrollCard path."""
    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
    css = (ROOT / "src/styles/shell.css").read_text(encoding="utf-8")
    assert "const scrollCard = questions.length > 1 && new Set(questions.map((q) => q.page ?? 1)).size === 1" in chat
    assert "const shown = scrollCard ? questions : onPage" in chat
    assert "onScrollNext" in chat
    assert "data-scroll-card={scrollCard || undefined}" in chat
    assert ".ca-chat__dock .ca-q__body { max-height: none; }" in css
    instr = _studio_model_instructions()
    first = instr[instr.index("First card"):instr.index("Second card")]
    assert "page_count 3" in first
    assert "all page 1" in first
    assert "one scrollable card" in first
