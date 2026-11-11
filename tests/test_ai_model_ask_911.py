"""#911 ai-model question chain: drop the frontal identity default and lock the Lovart ask card.

No WaveSpeed call. $0 static. Pins and api/auto_models.json must stay unchanged.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from ComfyArt.api import bot_asks

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
AUTO_MODELS = ROOT / "api/auto_models.json"

# Verbatim from https://github.com/ganjmeng/ComfyArt/issues/911#issuecomment-6797643813
Q1_PROMPT = "模特长相方向（性别 / 气质 / 人种 / 肤色）选哪一档？"
Q2_PROMPT = "头肩底图的背景用哪个？"
Q3_PROMPT = "出图方式要哪种？"
Q1_LABELS = (
    "女 · 清冷东方 · 中国 · 象牙白",
    "女 · 甜美少女 · 中国 · 瓷白",
    "男 · 干净少年感 · 东亚 · 自然肤色",
)
Q2_LABELS = ("纯白", "浅灰", "米白暖调")
Q3_LABELS = ("直接出 1 张 3:4 成品", "先出 4 张面孔候选让我挑")
Q1_OTHER = "其他（请写：性别 / 气质 / 国籍人种 / 肤色）..."
Q2_OTHER = "其他（颜色或渐变说明）..."
Q3_OTHER = "其他想法..."

AI_MODEL_EXAMPLES = "examples: ex643('ai-model', [1, 2, 3, 4, 5, 6], '604e9be57c96010fc6183f89d02c971f612d10e7')"
AI_MODEL_FEATURED = "featured: [pinned('805/reuse/ai-model', '7fbb71bdce30a57f35c367bc949981c00fb2fc10', 'featured.png')]"


# Locked to origin/main 33d28eab5 (do not retune if a local origin/main ref is stale).
AUTO_MODELS_SHA256 = "776c7ff035d679ade4cde30633ccd421244d91bf6798b557aed268ed30986532"
PORTRAIT_SHOTS_708_CONST_SHA256 = "97edb7c18215e4a283b86633908872f3b3c4146d9bb748d71c0d3510798cfc8b"


def _ai_model_instructions() -> str:
    m = re.search(
        r"\{ id: 'ai-model', name: t\('skills.aiModel'\), instructions: '((?:\\.|[^'\\])*)'",
        SKILLS,
    )
    assert m, "ai-model instructions string did not parse"
    return (
        m.group(1)
        .replace("\\\\", "\0")
        .replace("\\n", "\n")
        .replace("\\'", "'")
        .replace("\\t", "\t")
        .replace("\0", "\\")
    )


def _ai_model_entry() -> str:
    m = re.search(r"\{ id: 'ai-model', name: t\('skills.aiModel'\),[\s\S]*?inputs: NEARMISS_INPUTS \},", SKILLS)
    assert m, "ai-model entry missing"
    return m.group(0)


def _portrait_shots_708_const(src: str) -> str:
    m = re.search(
        r"const PORTRAIT_SHOTS_708 = ((?:'(?:\\.|[^'\\])*'(?:\s*\+\s*)?)+)",
        src,
    )
    assert m, "PORTRAIT_SHOTS_708 constant missing"
    return m.group(1)


def test_frontal_identity_sentence_is_gone():
    instr = _ai_model_instructions()
    assert "the identity anchor shot may be frontal eye-level on a plain backdrop (it is the only one)" not in instr
    assert "identity anchor shot may be frontal" not in SKILLS
    assert "every outfit/scene frame after the identity anchor changes angle and light" in instr
    # Do not sneak camera / white-backdrop defaults back in as a shared rule.
    assert "slight two-thirds" not in instr
    assert "clean white studio backdrop" not in instr
    assert "subject left of center" not in instr


def test_ask_card_has_three_questions_in_order_with_verbatim_options_and_no_default():
    instr = _ai_model_instructions()
    assert "ask_user" in instr
    assert "questions[]" in instr and "page_count 3" in instr
    assert "Show all three" in instr
    assert "none are preselected" in instr or "Do not set defaults or recommended" in instr
    assert "defaults or recommended" in instr
    for needle in ("recommended: true", '"recommended"', "defaults: ["):
        assert needle not in instr

    assert instr.index(Q1_PROMPT) < instr.index(Q2_PROMPT) < instr.index(Q3_PROMPT)
    for label in Q1_LABELS + Q2_LABELS + Q3_LABELS:
        assert label in instr, label
    assert Q1_OTHER in instr and Q2_OTHER in instr and Q3_OTHER in instr
    # Order of option labels inside each question.
    for labels in (Q1_LABELS, Q2_LABELS, Q3_LABELS):
        positions = [instr.index(lab) for lab in labels]
        assert positions == sorted(positions), labels

    # One scrollable card: every question stays on page 1; page_count 3 is 1 of 3 chrome only.
    assert "one scrollable card" in instr
    assert "header 1 of 3" in instr
    assert "Do not put questions on separate pages" in instr
    assert "do not paginate with 下一步" in instr
    assert "page 2" not in instr and 'page 3,' not in instr
    assert instr.count("page 1") >= 3

    # Skip / Next and allow_other (D/C 其他 is the other row, not a fourth chip).
    assert "allow_other" in instr
    assert "Skip / Next" in instr or "Skip" in instr
    assert "Skip / Submit" in instr
    assert "换装" in instr and "换背景" in instr and "高清放大" in instr
    assert "only the user's words plus the card answers" in instr
    assert "Do not invent a lens, outfit, makeup" in instr
    assert "Do not state head angle, gaze direction or subject position unless the user's words, a card answer or a reference give one." in instr


def test_lovart_card_spec_validates_without_defaults():
    """The locked card (zh labels, no preselect) is a valid ask_user questions[] spec."""
    def opts(*labels: str):
        return [{"id": letter, "label": label} for letter, label in zip("ABC", labels)]

    spec = bot_asks.validate_spec({
        "questions": [
            {
                "id": "look",
                "prompt": Q1_PROMPT,
                "options": opts(*Q1_LABELS),
                "allow_other": True,
                "placeholder": Q1_OTHER,
                "page": 1,
            },
            {
                "id": "backdrop",
                "prompt": Q2_PROMPT,
                "options": opts(*Q2_LABELS),
                "allow_other": True,
                "placeholder": Q2_OTHER,
                "page": 1,
            },
            {
                "id": "output",
                "prompt": Q3_PROMPT,
                "options": opts(*Q3_LABELS),
                "allow_other": True,
                "placeholder": Q3_OTHER,
                "page": 1,
            },
        ],
        "page_count": 3,
        "allow_skip": True,
    })
    assert "defaults" not in spec
    assert len(spec["questions"]) == 3
    assert [q["id"] for q in spec["questions"]] == ["look", "backdrop", "output"]
    assert [q["page"] for q in spec["questions"]] == [1, 1, 1]
    assert spec["page_count"] == 3
    assert spec["allow_skip"] is True
    for q, labels, other in (
        (spec["questions"][0], Q1_LABELS, Q1_OTHER),
        (spec["questions"][1], Q2_LABELS, Q2_OTHER),
        (spec["questions"][2], Q3_LABELS, Q3_OTHER),
    ):
        assert "defaults" not in q
        assert not any(o.get("recommended") for o in q["options"])
        assert tuple(o["label"] for o in q["options"]) == labels
        assert q["allow_other"] is True
        assert q.get("placeholder") == other


def test_pins_and_auto_models_unchanged():
    entry = _ai_model_entry()
    assert AI_MODEL_EXAMPLES in entry
    assert AI_MODEL_FEATURED in entry
    assert hashlib.sha256(AUTO_MODELS.read_bytes()).hexdigest() == AUTO_MODELS_SHA256
    # Shared #708 block is not edited; only ai-model may stop appending it later.
    assert hashlib.sha256(_portrait_shots_708_const(SKILLS).encode()).hexdigest() == PORTRAIT_SHOTS_708_CONST_SHA256
    # studio-model and clothing-swap still append the shared block.
    for sid in ("studio-model", "clothing-swap"):
        m = re.search(rf"\{{ id: '{sid}'.*?inputs:", SKILLS, re.S)
        assert m and "+ PORTRAIT_SHOTS_708 +" in m.group(0), sid



NO_ANGLE_SENTENCE = (
    "Do not state head angle, gaze direction or subject position unless the "
    "user's words, a card answer or a reference give one."
)


def _main_skills() -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "show", "origin/main:src/skills.ts"],
        text=True,
        encoding="utf-8",
    )


def _skill_entry(src: str, sid: str) -> str:
    m = re.search(
        rf"{{ id: '{re.escape(sid)}', name: t\('[^']+'\), instructions: [\s\S]*?inputs: [^\n]+}},",
        src,
    )
    assert m, f"skill entry missing: {sid}"
    return m.group(0)


def _708_appender_ids(src: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for sid in re.findall(r"\{ id: '([^']+)'", src):
        if sid in seen:
            continue
        try:
            entry = _skill_entry(src, sid)
        except AssertionError:
            continue
        if "+ PORTRAIT_SHOTS_708 +" in entry:
            seen.add(sid)
            ids.append(sid)
    return ids


def test_qa1_ai_model_has_no_portrait_shots_708_or_frontal_sentence():
    """QA (1): ai-model has no PORTRAIT_SHOTS_708 and no frontal identity-anchor sentence."""
    entry = _ai_model_entry()
    instr = _ai_model_instructions()
    assert "+ PORTRAIT_SHOTS_708 +" not in entry
    assert "PORTRAIT_SHOTS_708" not in entry
    assert "Shot rules (#708)" not in entry
    assert "Shot rules (#708)" not in instr
    # 708 slot language must not leak into the ai-model instruction body.
    assert "at most ONE frontal 0° eye-level shot per batch" not in instr
    assert "subject on the left third, negative space on the right" not in instr
    assert "the identity anchor shot may be frontal eye-level on a plain backdrop (it is the only one)" not in instr
    assert "identity anchor shot may be frontal" not in instr
    assert "identity anchor shot may be frontal" not in SKILLS


def test_qa2_other_708_skills_byte_identical_to_origin_main():
    """QA (2): studio-model, clothing-swap, and any other main 708 appender stay byte-identical."""
    main = _main_skills()
    appenders = [sid for sid in _708_appender_ids(main) if sid != "ai-model"]
    assert "studio-model" in appenders
    assert "clothing-swap" in appenders
    # The shared constant itself is also unchanged.
    assert _portrait_shots_708_const(SKILLS) == _portrait_shots_708_const(main)
    for sid in appenders:
        assert _skill_entry(SKILLS, sid) == _skill_entry(main, sid), sid
        assert "+ PORTRAIT_SHOTS_708 +" in _skill_entry(SKILLS, sid)


def test_qa3_ai_model_asks_card_before_generating():
    """QA (3): ask_user card instruction is present, and the no-invented-angle sentence is present."""
    instr = _ai_model_instructions()
    assert "Before generating, call ask_user once with one card of three questions" in instr
    assert "ask_user" in instr
    assert "questions[]" in instr
    assert "page_count 3" in instr
    assert NO_ANGLE_SENTENCE in instr
    assert "only the user's words plus the card answers" in instr


def test_ask_card_renderer_lists_shared_page_questions_in_one_scrollable_card():
    """All questions on one page + page_count > 1 → one scrollable card; multi-page path stays intact."""
    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
    assert "const scrollCard = questions.length > 1 && new Set(questions.map((q) => q.page ?? 1)).size === 1" in chat
    assert "const shown = scrollCard ? questions : onPage" in chat
    assert "onScrollNext" in chat
    assert "atEnd" in chat
    # Existing multi-page Next / last-page Submit path is still in source (pose-fission etc.).
    assert "const showPager = pageCount > 1" in chat
    assert "const isLast = page >= pageCount" in chat
    assert "const onNext = () => { if (!pageOk) return; go(page + 1) }" in chat
    assert "disabled={page >= pageCount || (page >= furthest && !pageOk)}" in chat
