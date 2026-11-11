"""#911 clothing-swap: Lovart single-question card skeleton, prompt keep-from-image-1, detach 708.

Options are generated live from what the person in image 1 is wearing, so they
must not be copied into src/skills.ts. This file may name Lovart fixture words
only to forbid them in the skill entry.

No WaveSpeed call. $0 static. Pins and api/auto_models.json stay unchanged.
The shared PORTRAIT_SHOTS_708 constant is untouched; clothing-swap no longer
appends it. Output ratio follows image 1 (the person photo) on the server.
compose_provider_text: skill + empty text gets a neutral model-only line.
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
    assert "in the UI language when the user typed no text" in instr
    assert "in the language of the user when they typed text" in instr
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
    assert "Do not invent or write angle, shot-size, or background words" in instr
    assert "Do not change pose or framing" in instr
    assert "Output aspect follows image 1" in instr
    assert "Do not transcribe or spell out any text, letters, or words printed on the garment" in instr
    assert "T 恤图案照第二张图保留" in instr
    assert "Keep the T-shirt pattern as shown in image 2" in instr
    assert "consistent lighting with the original photo" in instr
    assert "KARO" not in instr
    assert "KARO" not in _skill_entry(SKILLS, "clothing-swap")



def test_prompt_rule_forbids_transcribing_garment_print_text():
    """Print/graphic letters stay on image 2; the prompt must not spell them out."""
    instr = _clothing_swap_instructions()
    entry = _skill_entry(SKILLS, "clothing-swap")
    assert "Do not transcribe or spell out any text, letters, or words printed on the garment" in instr
    assert "T-shirt pattern is kept as in image 2" in instr or "T 恤图案照第二张图保留" in instr
    assert "T 恤图案照第二张图保留" in instr
    assert "Keep the T-shirt pattern as shown in image 2" in instr
    # Lighting of the original photo may stay; do not invent a new setup.
    assert "consistent lighting with the original photo" in instr
    # Fixture print text must not be baked into the skill.
    for word in ("KARO", "karo"):
        assert word not in instr
        assert word not in entry


def test_output_fallback_row_is_3x4_and_ts_table_in_sync():
    """3: the declared row is the 3:4 fallback used when image 1 cannot be read."""
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
    assert not q.get("placeholder")
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



def test_ask_card_language_follows_ui_when_empty_and_user_when_typed():
    """Generic rule: empty text -> UI language; typed text -> user's language."""
    from ComfyArt.bot.local_llm import ask_card_lang, system_prompt_for_turn

    assert ask_card_lang("", "zh") == "zh"
    assert ask_card_lang("", "en") == "en"
    assert ask_card_lang("换成第二张图的T恤", "en") == "zh"
    assert ask_card_lang("swap the top", "zh") == "en"
    # The English model-only provider line is not the user's typed text.
    assert ask_card_lang("", "zh") == "zh"
    prompt = system_prompt_for_turn("", "zh")
    assert "Ask-card language for this turn is Chinese (zh)" in prompt
    instr = _clothing_swap_instructions()
    assert "in the UI language when the user typed no text" in instr
    assert "in the language of the user when they typed text" in instr



def test_empty_text_card_skip_and_submit_follow_ui_locale_table():
    """(1) Empty text: skip/submit wording comes from the UI-language table, not a hardcoded string."""
    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
    card = chat.split("function QuestionCard")[1].split("function Ask(")[0]
    assert "t('chatMessage.skip')" in card
    assert "t('chatMessage.submit')" in card
    # The zh/en labels live in the locale table; the component does not hardcode them.
    assert "跳过" not in chat
    assert "提交" not in chat
    zh = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))
    assert zh["chatMessage.skip"] == "跳过"
    assert zh["chatMessage.submit"] == "提交"
    assert en["chatMessage.skip"] == "Skip"
    assert en["chatMessage.submit"] == "Submit"
    # Free-text row is not hardcoded here; wording comes from the UI i18n table
    # (see test_clothing_swap_free_text_row_uses_shared_ui_i18n).
    from ComfyArt.api import bot_asks
    zh_card = bot_asks.validate_spec({
        "prompt": "这件衣服要怎么替换模特的上身？",
        "options": [
            {"id": "A", "label": "整体换成图2的蓝色T恤"},
            {"id": "B", "label": "只把黑色背心换成图2蓝色T恤"},
        ],
        "allow_other": True,
    })
    assert not zh_card["questions"][0].get("placeholder")
    assert zh_card["questions"][0]["allow_other"] is True
    assert zh_card["allow_skip"] is True


def test_turn_path_passes_goal_text_not_provider_text_into_ask_card_lang():
    """(2) Empty-text skill turn, UI zh: the turn path must use goal_text, not the English provider line."""
    from ComfyArt.api.bot_send import compose_provider_text
    from ComfyArt.bot.local_llm import ask_card_lang, system_prompt_for_turn
    from ComfyArt.bot.providers import TurnRequest

    provider = compose_provider_text("", skill_name="clothing-swap")
    assert "Process the attached images with the selected skill." in provider

    # Same construction as api/bot_turns.py: user_text is provider_text, goal_text is the typed text.
    turn = TurnRequest(
        chat_id="lock-911-ask-lang",
        user_text=provider,
        lang="zh",
        goal_text="",
    )
    # Same call as bot/local_llm.py (the built-in turn path).
    prompt = system_prompt_for_turn(turn.goal_text, turn.lang)
    assert ask_card_lang(turn.goal_text, turn.lang) == "zh"
    assert "Ask-card language for this turn is Chinese (zh)" in prompt

    # Passing provider_text / user_text would wrongly switch the card to English.
    assert ask_card_lang(turn.user_text, turn.lang) == "en"
    wrong = system_prompt_for_turn(turn.user_text, turn.lang)
    assert "Ask-card language for this turn is English (en)" in wrong

    src = (ROOT / "bot/local_llm.py").read_text(encoding="utf-8")
    assert "system_prompt_for_turn(turn.goal_text, turn.lang)" in src
    assert "system_prompt_for_turn(turn.user_text" not in src
    turns = (ROOT / "api/bot_turns.py").read_text(encoding="utf-8")
    assert "goal_text=text," in turns


def test_clothing_swap_free_text_row_uses_shared_ui_i18n():
    """(a)(b) Other-row text is the shared ChatMessage i18n, not a skill-specific constant."""
    from ComfyArt.api import bot_asks

    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
    # Choice cards (options + allow_other) use this fallback when placeholder is absent.
    assert "placeholder={q.placeholder || t('chatMessage.other')}" in chat
    zh_i18n = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
    en_i18n = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))
    zh_other = zh_i18n["chatMessage.other"]
    en_other = en_i18n["chatMessage.other"]
    assert zh_other == "其他（输入你的答案）…"
    assert en_other == "Other (type your answer)..."
    assert any("\u3400" <= ch <= "\u9fff" for ch in zh_other)
    assert not any("\u3400" <= ch <= "\u9fff" for ch in en_other)
    # Must not regress to the unreviewed typo wording.
    assert "其它穿法，我来说呢" not in zh_other
    assert "其它穿法，我来说呢" not in en_other

    # Normalizer must not hardcode a placeholder; UI then renders t('chatMessage.other').
    src = (ROOT / "api/bot_asks.py").read_text(encoding="utf-8")
    assert "CLOTHING_SWAP_PLACEHOLDER" not in src
    assert "其它穿法，我来说呢" not in src

    zh = bot_asks.validate_spec({
        "prompt": "这件衣服要怎么替换模特的上身？",
        "options": [
            {"id": "A", "label": "整套上身都换成它"},
            {"id": "B", "label": "只换掉外面的背心"},
        ],
        "allow_other": True,
        "placeholder": "其它穿法，我来说呢...",
    })
    assert zh["questions"][0]["allow_other"] is True
    assert not zh["questions"][0].get("placeholder")

    en = bot_asks.validate_spec({
        "prompt": "How should I replace the upper-body garment?",
        "options": [
            {"id": "A", "label": "Replace the whole upper body with the blue graphic tee"},
            {"id": "B", "label": "Replace only the black vest"},
        ],
        "allow_other": True,
        "placeholder": "None of these fit, I'll write my own...",
    })
    assert not en["questions"][0].get("placeholder")
    assert en["questions"][0]["prompt"] == "How should I replace the upper-body garment?"
    assert en["questions"][0]["allow_other"] is True

    # Empty title + English options -> English fallback title, still no placeholder.
    blank = bot_asks.validate_spec({
        "id": "upper_body_swap",
        "prompt": "",
        "options": [
            {"id": "A", "label": "Replace the whole upper body with the tee"},
            {"id": "B", "label": "Layer the tee over the long sleeve"},
        ],
        "allow_other": True,
    })
    assert blank["questions"][0]["prompt"] == "How should I replace the upper-body garment?"
    assert not blank["questions"][0].get("placeholder")
    assert blank["questions"][0]["allow_other"] is True


def test_pins_and_auto_models_unchanged():
    """No pin change and api/auto_models.json byte-identical to the base."""
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


def _png(w: int, h: int) -> bytes:
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize(
    "size,ratio,pixels",
    [
        ((1776, 2368), "3:4", (1536, 2048)),   # Lovart person photo, exactly 3:4
        ((2368, 1776), "4:3", (2048, 1536)),   # same photo landscape
        ((1920, 1080), "16:9", (2048, 1152)),  # landscape 16:9
        ((1080, 1920), "9:16", (1152, 2048)),
        ((1024, 1024), "1:1", (1536, 1536)),
    ],
)
def test_qa5_output_ratio_follows_image1(size, ratio, pixels):
    """QA 5: ratio follows image 1's pixels, snapped to the closest supported ratio; model ratio ignored."""
    data = _png(*size)
    for model_args in (
        {"prompt": "swap the top"},
        {"prompt": "swap the top", "ratio": "16:9" if ratio != "16:9" else "3:4"},
        {"prompt": "swap the top", "width": 1024, "height": 1024, "skill": "clothing-swap"},
    ):
        out = apply_generate(dict(model_args), "clothing-swap", ref_image=data)
        assert out["skill"] == "clothing-swap"
        assert out["ratio"] == ratio, (size, model_args)
        assert (out["width"], out["height"]) == pixels
        assert max(pixels) <= 2048
        assert out["size_lock"] is True and out["count"] == 1
        # Relay pass (no bytes) keeps the ratio the chat loop read.
        again = apply_generate(dict(out))
        assert (again["width"], again["height"], again["ratio"]) == (*pixels, ratio)


def test_qa5_1776x2368_is_3x4_never_16x9_and_landscape_is_landscape():
    portrait = apply_generate({"prompt": "x", "ratio": "16:9"}, "clothing-swap", ref_image=_png(1776, 2368))
    assert portrait["ratio"] == "3:4" and portrait["ratio"] != "16:9"
    assert portrait["width"] * 4 == portrait["height"] * 3
    landscape = apply_generate({"prompt": "x"}, "clothing-swap", ref_image=_png(2368, 1776))
    assert landscape["width"] > landscape["height"] and landscape["ratio"] == "4:3"
    wide = apply_generate({"prompt": "x"}, "clothing-swap", ref_image=_png(1920, 1080))
    assert wide["width"] > wide["height"] and wide["ratio"] == "16:9"


@pytest.mark.parametrize("ref_image", [None, b"", b"not an image"])
def test_qa5_unreadable_image1_falls_back_to_3x4(ref_image):
    out = apply_generate({"prompt": "x", "ratio": "16:9"}, "clothing-swap", ref_image=ref_image)
    assert (out["width"], out["height"], out["ratio"]) == (1536, 2048, "3:4")
    assert "_ref_ratio" not in out


def test_qa5_image1_bytes_come_from_first_ref_or_first_attachment():
    """Reuses #905's ref_image_bytes: first ref, else the turn's first attached image; never a later one."""
    import base64

    from ComfyArt.bot.ref_orientation import ref_image_bytes

    person, garment = _png(2368, 1776), _png(960, 970)
    atts = [
        {"data": base64.b64encode(person).decode(), "media_type": "image/png"},
        {"data": base64.b64encode(garment).decode(), "media_type": "image/png"},
    ]
    got = ref_image_bytes(["shape:unknown-person"], "", atts)
    assert got == person
    out = apply_generate({"prompt": "x", "refs": ["shape:unknown-person", "shape:g"]}, "clothing-swap", ref_image=got)
    assert out["ratio"] == "4:3"
    assert ref_image_bytes(None, "", None) is None


def test_qa5_other_skills_do_not_follow_ref():
    from ComfyArt.bot.skill_output import FOLLOW_REF_SIZES, follows_ref

    assert list(FOLLOW_REF_SIZES) == ["clothing-swap"]
    assert follows_ref("clothing-swap") and follows_ref("AI服装换装")
    for sid in ("pose-fission", "before-after", "game-art", "linkedin-banner", "studio-model", "ai-model", ""):
        assert not follows_ref(sid)
    pose = apply_generate({"prompt": "x"}, "pose-fission", ref_image=_png(1920, 1080))
    assert (pose["width"], pose["height"], pose["ratio"]) == (1536, 2048, "3:4")
    assert "_ref_ratio" not in pose


def test_run_hint_does_not_lock_a_fixed_size_for_clothing_swap():
    from ComfyArt.bot.skill_output import run_hint

    hint = run_hint("clothing-swap")
    assert "size and ratio of image 1" in hint
    assert "1536" not in hint and "2048" not in hint and "3:4" not in hint
    instr = _clothing_swap_instructions()
    assert "width=1536" not in instr and "ratio=3:4" not in instr
    assert "refs in order [person image 1, garment image 2]" in instr


# --- QA 1-3: empty-text provider line (tech option one). ---
EMPTY_TEXT_LINE = "Look at the attached images and tell me what you see."
SKILL_EMPTY_LINE = "Process the attached images with the selected skill."


def _main_compose():
    """compose_provider_text as it was on the base, exec'd standalone (no package import)."""
    src = subprocess.check_output(
        ["git", "-C", str(ROOT), "show", f"{MAIN_SHA}:api/bot_send.py"], text=True, encoding="utf-8"
    )
    m = re.search(r"^def compose_provider_text\(.*?(?=^def )", src, re.M | re.S)
    assert m
    # Package context so its relative `run_hint` import resolves (this branch's run_hint on
    # both sides; the comparison is about compose_provider_text's own text handling).
    ns: dict = {"__name__": "ComfyArt.api.bot_send", "__package__": "ComfyArt.api"}
    exec(m.group(0), ns)  # noqa: S102 — test harness
    return ns["compose_provider_text"]


def test_qa1_skill_and_empty_text_gets_neutral_line():
    from ComfyArt.api.bot_send import compose_provider_text

    for review in (True, False, None):
        out = compose_provider_text("", skill_name="clothing-swap", memory="", lines=[], review=review)
        assert SKILL_EMPTY_LINE in out
        assert EMPTY_TEXT_LINE not in out
        assert "tell me what you see" not in out
        assert "Use the ComfyArt skill 'clothing-swap'" in out
    # Neutral: no image-content words.
    for word in ("person", "garment", "shirt", "describe", "see", "model", "woman", "T恤"):
        assert word not in SKILL_EMPTY_LINE.lower()


def test_qa2_no_skill_and_empty_text_is_byte_identical_to_base():
    from ComfyArt.api.bot_send import compose_provider_text

    base = _main_compose()
    for kw in ({}, {"review": True}, {"review": False}, {"memory": "MEM", "lines": ["[ctx]"]}):
        assert compose_provider_text("", **kw) == base("", **kw)
    assert EMPTY_TEXT_LINE in compose_provider_text("")
    assert SKILL_EMPTY_LINE not in compose_provider_text("")


def test_qa3_skill_and_text_is_not_rewritten():
    from ComfyArt.api.bot_send import compose_provider_text

    base = _main_compose()
    for text in ("换成第二张图的T恤", "swap the top", " "):
        for skill in ("clothing-swap", "studio-model", ""):
            ours = compose_provider_text(text, skill_name=skill, review=True)
            assert ours == base(text, skill_name=skill, review=True), (text, skill)
            assert SKILL_EMPTY_LINE not in ours


async def test_neutral_line_is_model_only_not_in_bubble_or_history(bot_client, fake_provider, monkeypatch):
    """Design: the injected line reaches the provider, never the stored user bubble or replayed history."""
    from conftest import wait_bot_done

    from ComfyArt.api import bot_send, chat_store
    from ComfyArt.api.bot_turns import _replay_history

    async def no_files(refs, kits, docs, page_images=True):
        return [], []

    monkeypatch.setattr(bot_send, "prepare_attachments", no_files)
    chat = (await (await bot_client.post("/comfyart/bot/chats", json={"project": "p", "provider": "fake-test"})).json())["chat"]
    resp = await bot_client.post(
        f"/comfyart/bot/chats/{chat['id']}/send",
        json={
            "text": "",
            "skill": "clothing-swap",
            "refs": [
                {"id": "shape:person", "src": "/api/view?filename=person.png&type=input"},
                {"id": "shape:garment", "src": "/api/view?filename=garment.png&type=input"},
            ],
        },
    )
    assert resp.status == 200
    data = await wait_bot_done(bot_client, chat["id"])
    assert SKILL_EMPTY_LINE in fake_provider.last_turn.user_text
    assert EMPTY_TEXT_LINE not in fake_provider.last_turn.user_text

    user = data["messages"][0]
    assert user["role"] == "user"
    assert [b["type"] for b in user["blocks"]] == ["image", "image", "skill"]
    stored = json.dumps(chat_store.list_messages(chat["id"]), ensure_ascii=False)
    assert SKILL_EMPTY_LINE not in stored
    assert "Use the ComfyArt skill" not in stored
    replay = json.dumps(_replay_history(chat["id"], "none"), ensure_ascii=False)
    assert SKILL_EMPTY_LINE not in replay
