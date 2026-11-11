"""#911 ai-model question chain: drop the frontal identity default, lock the Lovart ask card,
and pin the skill to GPT Image 2.6 Sunburst.

No WaveSpeed call. $0 static. Example/featured pins and the shared #708 constant stay
unchanged. Auto-table and 708 locks compare to a fixed snapshot of main
dbed74e11b158917e7cf82b44bd4dbf6829af90d, not a moving origin/main ref.
"""
from __future__ import annotations

import hashlib
import json
import re
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


# Locked to main dbed74e11 (same bytes as 33d28eab5). Do not retune unless the constant changes.
PORTRAIT_SHOTS_708_CONST_SHA256 = "97edb7c18215e4a283b86633908872f3b3c4146d9bb748d71c0d3510798cfc8b"
# Remaining 708 appenders on that same main tip. ai-model and studio-model stay off this list.
EXPECTED_708_APPENDER_SHA256 = {
    "clothing-swap": "3ac12958fac29ab0d33067aafa98b67292ff2b8e577a88043491d451c1125bca",
}

NO_ANGLE_SENTENCE = (
    "Do not state head angle, gaze direction or subject position unless the "
    "user's words, a card answer, a reference or this skill's base-image layout give one."
)
LAYOUT_SENTENCE = (
    "As a detail-page base image, leave clear empty space for later copy: "
    "subject off to one side with generous headroom."
)
SKILL_PASS_SENTENCE = (
    'pass skill: "ai-model" and shape ids in refs on every generate_image call '
    "(the skill runs on its registered model, GPT Image 2.6 Sunburst)."
)
SUNBURST_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"
# api/auto_models.json snapshot copied from main dbed74e11. Update the fixture when the
# table (features / non-ai-model skill rows) is intentionally changed.
AUTO_MODELS_LOCK_SHA = "dbed74e11b158917e7cf82b44bd4dbf6829af90d"
AUTO_MODELS_LOCK = ROOT / "tests/fixtures/auto_models_lock_dbed74e1.json"
EXPECTED_AI_MODEL_PIN = {
    "feature": "text_to_image",
    "model": SUNBURST_T2I,
    "edit_model": SUNBURST_EDIT,
    "zh": "ai-model 技能固定用 GPT Image 2.6 Sunburst（无参考文生，有参考编辑）",
    "en": "the ai-model skill is pinned to GPT Image 2.6 Sunburst (text-to-image with no reference, edit when a reference is given)",
}


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
    assert "Do not state head angle, gaze direction or subject position unless the user's words, a card answer, a reference or this skill's base-image layout give one." in instr
    assert LAYOUT_SENTENCE in instr
    assert 'pass skill: "ai-model"' in instr


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
    # Example/featured asset pins stay. The Auto table may add skills.ai-model only.
    # Shared #708 block is not edited; ai-model and studio-model stop appending it.
    assert hashlib.sha256(_portrait_shots_708_const(SKILLS).encode()).hexdigest() == PORTRAIT_SHOTS_708_CONST_SHA256
    # clothing-swap still appends the shared block. studio-model detaches 708 in #914.
    m = re.search(r"\{ id: 'clothing-swap'.*?inputs:", SKILLS, re.S)
    assert m and "+ PORTRAIT_SHOTS_708 +" in m.group(0)
    sm = re.search(r"\{ id: 'studio-model'.*?inputs:", SKILLS, re.S)
    assert sm and "+ PORTRAIT_SHOTS_708 +" not in sm.group(0)




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


def test_qa2_other_708_skills_match_fixed_snapshot():
    """QA (2): remaining 708 appenders match the dbed74e11 snapshot; ai-model and studio-model stay detached."""
    appenders = _708_appender_ids(SKILLS)
    assert "studio-model" not in appenders
    assert "ai-model" not in appenders
    assert "+ PORTRAIT_SHOTS_708 +" not in _skill_entry(SKILLS, "studio-model")
    assert "+ PORTRAIT_SHOTS_708 +" not in _skill_entry(SKILLS, "ai-model")
    assert hashlib.sha256(_portrait_shots_708_const(SKILLS).encode()).hexdigest() == PORTRAIT_SHOTS_708_CONST_SHA256
    assert appenders == list(EXPECTED_708_APPENDER_SHA256)
    for sid, expected_sha in EXPECTED_708_APPENDER_SHA256.items():
        entry = _skill_entry(SKILLS, sid)
        assert "+ PORTRAIT_SHOTS_708 +" in entry, sid
        assert hashlib.sha256(entry.encode()).hexdigest() == expected_sha, sid


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


def test_layout_and_rule8_sentences_locked():
    """Exact product/tech wording: layout sentence + updated rule 8 tail."""
    instr = _ai_model_instructions()
    assert LAYOUT_SENTENCE in instr
    assert NO_ANGLE_SENTENCE in instr
    # Old tail (no base-image layout exception) must not remain.
    assert (
        "unless the user's words, a card answer or a reference give one."
        not in instr
    )


def test_generate_image_must_pass_skill_ai_model():
    """Mirror pose-fission rule 8: every generate_image call must pass skill: "ai-model"."""
    instr = _ai_model_instructions()
    assert SKILL_PASS_SENTENCE in instr
    assert 'pass skill: "ai-model"' in instr
    assert "GPT Image 2.6 Sunburst" in instr


def test_auto_models_ai_model_is_sunburst_and_rest_matches_fixed_snapshot():
    """skills.ai-model is the Sunburst pin; every other skills row, features, and the
    file comment match the fixed snapshot copied from main dbed74e11.
    """
    ours = json.loads(AUTO_MODELS.read_text(encoding="utf-8"))
    snap = json.loads(AUTO_MODELS_LOCK.read_text(encoding="utf-8"))
    assert AUTO_MODELS_LOCK_SHA == "dbed74e11b158917e7cf82b44bd4dbf6829af90d"
    assert "ai-model" in ours["skills"]
    ours_ai = ours["skills"]["ai-model"]
    assert ours_ai == EXPECTED_AI_MODEL_PIN
    assert ours_ai["model"] == SUNBURST_T2I
    assert ours_ai["edit_model"] == SUNBURST_EDIT
    assert not ours_ai.get("fallback")
    # Snapshot itself must carry the same pin, so a stale fixture cannot silently drift.
    assert snap["skills"]["ai-model"] == EXPECTED_AI_MODEL_PIN
    ours_rest = dict(ours["skills"])
    snap_rest = dict(snap["skills"])
    ours_rest.pop("ai-model")
    snap_rest.pop("ai-model")
    assert ours_rest == snap_rest
    assert ours["skills"]["pose-fission"] == snap["skills"]["pose-fission"]
    assert ours["skills"]["_comment"] == snap["skills"]["_comment"]
    assert ours["features"] == snap["features"]
    assert json.dumps(ours["features"], ensure_ascii=False, sort_keys=True) == json.dumps(
        snap["features"], ensure_ascii=False, sort_keys=True
    )
    assert ours.get("_comment") == snap.get("_comment")


def test_ai_model_pin_no_ref_is_sunburst_t2i():
    from ComfyArt.api.mcp_tools import canvas

    args = {"prompt": "head-and-shoulders base image", "skill": "ai-model", "ratio": "3:4", "count": 1}
    c = canvas._auto_choice("generate_image", dict(args))
    assert c["model"] == SUNBURST_T2I
    assert c["category"] == "skill"
    assert "edit_model" not in c
    pinned = canvas._pin_args(dict(args), c)
    assert pinned["model"] == SUNBURST_T2I
    assert pinned.get("auto_model") is True
    assert "edit_model" not in pinned


def test_ai_model_pin_with_ref_is_sunburst_edit():
    from ComfyArt.api.mcp_tools import canvas

    args = {
        "prompt": "head-and-shoulders base image",
        "skill": "ai-model",
        "refs": ["shape:ref1"],
        "ratio": "3:4",
        "count": 1,
    }
    c = canvas._auto_choice("generate_image", dict(args))
    assert c["model"] == c["edit_model"] == SUNBURST_EDIT
    assert c["category"] == "skill"
    pinned = canvas._pin_args(dict(args), c)
    assert pinned["edit_model"] == SUNBURST_EDIT
    # t2i id must not be submitted on a ref call
    assert pinned.get("model") != SUNBURST_T2I


def test_ai_model_pin_with_base_is_sunburst_edit():
    from ComfyArt.api.mcp_tools import canvas

    args = {"prompt": "x", "skill": "ai-model", "base": "shape:base"}
    c = canvas._auto_choice("generate_image", dict(args))
    assert c["model"] == c["edit_model"] == SUNBURST_EDIT
    assert c["category"] == "skill"


def test_ai_model_pin_has_no_fallback_and_failure_does_not_switch():
    """If Sunburst fails, error out. Never silently switch to Flare or Seedream."""
    import json

    from ComfyArt.api.mcp_tools import canvas

    row = json.loads(AUTO_MODELS.read_text(encoding="utf-8"))["skills"]["ai-model"]
    assert "fallback" not in row or not row.get("fallback")
    flare_t2i = "openai/gpt-image-2.6-flare/text-to-image"
    flare_edit = "openai/gpt-image-2.6-flare/edit"
    seedream = "bytedance/seedream-v5.0-pro"
    no_ref = {"prompt": "x", "skill": "ai-model"}
    with_ref = {"prompt": "x", "skill": "ai-model", "refs": ["shape:r"]}
    for args, failed in ((no_ref, SUNBURST_T2I), (with_ref, SUNBURST_EDIT)):
        choice = canvas._fallback_choice("generate_image", dict(args), failed)
        assert choice is None, choice
    # A user-named model still wins over the pin (unchanged pin rule).
    named = canvas._auto_choice("generate_image", {**no_ref, "model": seedream})
    assert named["category"] != "skill"
    # The no-fallback path must not resolve to Flare/Seedream either.
    for bad in (flare_t2i, flare_edit, seedream, "openai/gpt-image-2.6-flare/edit"):
        assert canvas._fallback_choice("generate_image", dict(no_ref), SUNBURST_T2I) is None
        assert canvas._fallback_choice("generate_image", dict(with_ref), SUNBURST_EDIT) is None
        # choice is None so those ids cannot be selected as a fallback
        del bad


def test_pose_fission_pin_behavior_unchanged():
    """Dual-pin routing must not change pose-fission (edit pin + fallback)."""
    from ComfyArt.api.mcp_tools import canvas

    pro = "google/nano-banana-pro/edit"
    nano = "google/nano-banana-2.1/edit"
    args = {"prompt": "Change only: profile", "refs": ["shape:base"], "skill": "pose-fission"}
    c = canvas._auto_choice("generate_image", dict(args))
    assert c["model"] == c["edit_model"] == pro and c["category"] == "skill" and c["resolution"] == "2k"
    fb = canvas._fallback_choice("generate_image", dict(args), pro)
    assert fb["model"] == fb["edit_model"] == nano and fb["fallback"] == pro and fb["category"] == "skill_fallback"


def test_apply_generate_fills_omitted_ai_model_skill_without_size_lock():
    from ComfyArt.bot.skill_output import apply_generate

    out = apply_generate({"prompt": "x"}, "ai-model")
    assert out["skill"] == "ai-model"
    assert "width" not in out and "height" not in out
    assert "size_lock" not in out
    kept = apply_generate({"prompt": "x", "skill": "ai-model"}, "ai-model")
    assert kept["skill"] == "ai-model"
    assert "size_lock" not in kept
    # An Auto token is not an explicit model, so skill is still filled.
    auto = apply_generate({"prompt": "x", "model": "auto"}, "ai-model")
    assert auto["skill"] == "ai-model"
    assert auto.get("model") == "auto"


def test_apply_generate_does_not_fill_skill_outside_ai_model_sessions(monkeypatch):
    """A no-skill session and a non-#911 session must not get skill filled.

    The fill is not a generic skill_pin() hook: even if clothing-swap were
    pinned, it must stay unfilled. studio-model is the second #911 slice and
    now fills skill= with no size, same as ai-model. pose-fission keeps its
    pre-existing OUTPUTS size fill only.
    """
    from ComfyArt.api import auto_models
    from ComfyArt.bot.skill_output import apply_generate

    def fake_pin(skill):
        if str(skill) in {"studio-model", "clothing-swap"}:
            return {"feature": "text_to_image", "model": "other/pin"}
        return auto_models.skill_pin(skill)

    monkeypatch.setattr(auto_models, "skill_pin", fake_pin)

    none = apply_generate({"prompt": "x"}, "")
    assert "skill" not in none

    swap = apply_generate({"prompt": "x"}, "clothing-swap")
    assert "skill" not in swap

    # #914: studio-model fills skill= without inventing a size or using skill_pin.
    studio = apply_generate({"prompt": "x"}, "studio-model")
    assert studio["skill"] == "studio-model"
    assert "width" not in studio and "height" not in studio
    assert "size_lock" not in studio

    # Pre-existing OUTPUTS path: skill + size_lock, not the ai-model pin fill.
    pf = apply_generate({"prompt": "x"}, "pose-fission")
    assert pf["skill"] == "pose-fission"
    assert pf.get("size_lock") is True
    assert pf.get("width") == 1536 and pf.get("height") == 2048


def test_apply_generate_does_not_override_explicit_model_on_ai_model():
    """An ai-model call that already names a model must not get skill filled."""
    from ComfyArt.bot.skill_output import apply_generate

    named = "bytedance/seedream-v5.0-pro"
    out = apply_generate({"prompt": "x", "model": named}, "ai-model")
    assert "skill" not in out
    assert out["model"] == named
    assert "size_lock" not in out

    kept = apply_generate({"prompt": "x", "skill": "ai-model", "model": named}, "ai-model")
    assert kept["skill"] == "ai-model"
    assert kept["model"] == named

    edited = apply_generate(
        {"prompt": "x", "edit_model": "openai/gpt-image-2.6-flare/edit"}, "ai-model"
    )
    assert "skill" not in edited
    assert edited["edit_model"] == "openai/gpt-image-2.6-flare/edit"
