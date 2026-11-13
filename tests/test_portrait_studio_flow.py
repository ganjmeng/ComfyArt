"""portrait-studio flow (Lovart 7fc60c86a25765e778614fd8d608dfe8deaab166, skill 2o222a07opvk).

Lovart's Professional Portrait Generation Tool on one person photo: one ask card of three
questions (1 of 3, nothing preselected, no 推荐, free-text last row), then GPT Image 2.6
Sunburst delivers 3 images (question 1, option A). Without a reference photo the flow asks
the user to upload one and does not generate.

$0: no WaveSpeed call. submit_command and the run approval are mocked; the no-ref path is
asserted to submit nothing and ask for no approval. Pins, api/auto_models.json and
api/skill_size.py are compared byte for byte with main 30ade316.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import subprocess
import uuid
from pathlib import Path

import pytest

from ComfyArt.api import bot_asks, paid_guard
from ComfyArt.api import portrait_studio as ps
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import GUARD_CHAT_ID

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
MAIN = "30ade316437f7cb9afe941c5d737fdd78f063566"
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"

# Lovart 7fc60c86 card (911/lovart-ai/portrait-studio/notes.txt + card-1..3.png), verbatim.
LOVART_ZH = [
    ("ps_shots", "这组专业形象照想要几张、什么景别组合？",
     ["3 张：面部特写 + 半身 + 七分身", "4 张：特写 + 半身 + 七分身 + 全身", "只要 1 张半身标准照"],
     "其它张数或景别，我来写..."),
    ("ps_outfit", "服装方向怎么定？（人物长相、发型与身材比例都会锁定参考图不变）",
     ["保留原有休闲造型", "换成商务正装", "简约轻正装"],
     "其它服装，我来描述..."),
    ("ps_scene", "场景与背景用哪种？",
     ["纯色棚拍背景", "现代办公空间", "沿用参考图的建筑空间"],
     "其它场景，我来描述..."),
]
# en UI only (Lovart showed zh): our translation, locked the same way.
OURS_EN = [
    ("ps_shots", "How many professional portraits, and which shot sizes?",
     ["3 photos: face close-up + half body + three-quarter body",
      "4 photos: close-up + half body + three-quarter body + full body",
      "Just 1 standard half-body photo"],
     "Another count or shot size, I'll write it..."),
    ("ps_outfit", "Which outfit direction? (Face, hairstyle and body proportions stay locked to the reference)",
     ["Keep the original casual look", "Switch to business formal", "Simple smart casual"],
     "Another outfit, I'll describe it..."),
    ("ps_scene", "Which scene and background?",
     ["Solid-color studio backdrop", "Modern office space", "Keep the architectural space from the reference"],
     "Another scene, I'll describe it..."),
]
EXPECTED = {"zh": LOVART_ZH, "en": OURS_EN}
UPLOAD = {
    "zh": "请先上传一张人物照片作为参考图，我再为你生成专业形象照。",
    "en": "Please upload a photo of the person as the reference first, then I'll make the professional portraits.",
}


@pytest.fixture(autouse=True)
def no_paid_keys(monkeypatch):
    for key in ("WAVESPEED_API_KEY", "DEEPSEEK_API_KEY", "REPLICATE_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def _instructions() -> str:
    m = re.search(r"\{ id: 'portrait-studio', name: t\('skills.portraitStudio'\), instructions: '((?:\\.|[^'\\])*)'", SKILLS)
    assert m, "portrait-studio instructions did not parse"
    return m.group(1).replace("\\n", "\n").replace("\\'", "'").replace("\\\\", "\\")


def _with_lang(lang: str | None, goal_text: str, fn):
    chat = paid_guard.noturn_key(f"ps-{uuid.uuid4().hex}")
    token = GUARD_CHAT_ID.set(chat)
    try:
        if lang is not None:
            paid_guard.begin_turn(chat, text=goal_text, provider_text="", lang=lang)
        return fn()
    finally:
        GUARD_CHAT_ID.reset(token)
        paid_guard.TURNS.pop(chat, None)


def _assert_card(spec: dict, expected: list) -> None:
    assert spec["page_count"] == 3
    assert spec["allow_skip"] is True
    assert "defaults" not in spec
    assert [q["id"] for q in spec["questions"]] == [e[0] for e in expected]
    for q, (qid, prompt, labels, placeholder) in zip(spec["questions"], expected):
        assert q["prompt"] == prompt, qid
        assert q["page"] == 1, qid
        assert q["allow_other"] is True, qid
        assert q["placeholder"] == placeholder, qid
        assert "defaults" not in q, qid
        assert q["min_selections"] == 1 and q["max_selections"] == 1, qid
        assert [o["id"] for o in q["options"]] == ["A", "B", "C"], qid
        assert [o["label"] for o in q["options"]] == labels, qid
        assert not any(o.get("recommended") for o in q["options"]), qid
        assert not any("推荐" in o["label"] or "ecommended" in o["label"] for o in q["options"]), qid


# --- card ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["zh", "en"])
def test_card_text_is_exactly_the_locked_text(lang):
    spec = _with_lang(lang, "", lambda: bot_asks.validate_spec(ps.card_spec(lang)))
    _assert_card(spec, EXPECTED[lang])
    assert spec["prompt"] == EXPECTED[lang][0][1]


def test_zh_card_is_lovart_7fc60c86_verbatim():
    got = [(q["id"], q["prompt"], [o["label"] for o in q["options"]], q["placeholder"]) for q in ps.CARD["zh"]]
    assert got == LOVART_ZH
    assert ps.PAGE_COUNT == 3


@pytest.mark.parametrize("lang,ui,goal", [("zh", "zh", ""), ("en", "en", ""), ("zh", "en", "帮我用这张照片做一组专业形象照。"),
                                          ("en", "zh", "make a professional portrait set from this photo")])
def test_model_card_is_rewritten_to_the_locked_card_in_the_ask_card_language(lang, ui, goal):
    # What a model might send: a partial card in the wrong language, a default, a recommended flag,
    # short prompts, pages 1/2/3 and an extra invented question.
    raw = {
        "questions": [
            {"id": "count", "prompt": "How many professional portraits?", "options": [{"id": "1", "label": "3"}, {"id": "2", "label": "4"}],
             "defaults": ["1"], "page": 1},
            {"id": "q2", "prompt": "服装方向怎么定？", "options": [{"id": "a", "label": "休闲", "recommended": True}, {"id": "b", "label": "正装"}],
             "page": 2},
            {"id": "q4", "prompt": "要不要美颜？", "options": [{"id": "a", "label": "要"}, {"id": "b", "label": "不要"}], "page": 3},
        ],
        "page_count": 4,
        "allow_skip": False,
    }
    spec = _with_lang(ui, goal, lambda: bot_asks.validate_spec(raw))
    _assert_card(spec, EXPECTED[lang])


def test_unknown_ui_language_defaults_to_zh():
    spec = _with_lang(None, "", lambda: bot_asks.validate_spec({"questions": [{"id": "ps_scene", "prompt": "x", "allow_other": True}]}))
    _assert_card(spec, LOVART_ZH)


def test_other_skill_cards_are_untouched():
    raw = {"questions": [{"id": "look", "prompt": "模特长相方向选哪一档？", "options": [{"id": "A", "label": "x"}, {"id": "B", "label": "y"}],
                          "defaults": ["A"]}], "page_count": 3}
    assert ps.normalize_card(dict(raw)) == raw
    spec = bot_asks.validate_spec(dict(raw))
    assert spec["questions"][0]["prompt"] == "模特长相方向选哪一档？"
    assert spec["questions"][0]["defaults"] == ["A"]


def _visible(payload: dict) -> list[str]:
    """User-visible ask-card strings (prompt, placeholder, labels, descriptions)."""
    out: list[str] = []
    for key in ("prompt", "placeholder", "user_message"):
        if payload.get(key):
            out.append(str(payload[key]))
    for q in payload.get("questions") or []:
        for key in ("prompt", "placeholder", "title"):
            if q.get(key):
                out.append(str(q[key]))
        for opt in q.get("options") or []:
            for key in ("label", "description"):
                if opt.get(key):
                    out.append(str(opt[key]))
    return out


_DEBUG = ("ps_shots", "ps_outfit", "ps_scene", "7fc60c86", "review-assets", "Lovart", "portraitNeedsReference",
          "portrait-studio", "dry-run", "skill", "debug", "id ")


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_card_and_upload_prompt_are_one_language_and_have_no_debug_copy(lang):
    other = "en" if lang == "zh" else "zh"
    card = _with_lang(lang, "", lambda: bot_asks.validate_spec(ps.card_spec(lang)))
    upload = _with_lang(lang, "", ps.needs_reference_result)
    visible = "\n".join(_visible(card) + _visible(upload))
    for _, prompt, labels, placeholder in EXPECTED[lang]:
        assert prompt in visible and placeholder in visible
    assert UPLOAD[lang] in visible
    for _, prompt, labels, placeholder in EXPECTED[other]:
        assert prompt not in visible and placeholder not in visible
        assert not any(label in visible for label in labels if len(label) > 4)
    assert UPLOAD[other] not in visible
    cjk = re.compile(r"[\u4e00-\u9fff]")
    assert bool(cjk.search(visible)) is (lang == "zh")
    for needle in _DEBUG:
        assert needle not in visible, needle


# --- skill text ----------------------------------------------------------------------------------

def test_skill_text_carries_the_card_the_upload_prompt_and_default_3():
    instr = _instructions()
    for qid, prompt, labels, placeholder in LOVART_ZH:
        assert f'id "{qid}"' in instr and prompt in instr and placeholder in instr, qid
        for label in labels:
            assert f'label:"{label}"' in instr, label
    assert instr.index('id "ps_shots"') < instr.index('id "ps_outfit"') < instr.index('id "ps_scene"')
    assert "page_count 3, so the header is 1 of 3" in instr
    assert "Do not set defaults or recommended" in instr and "none is marked 推荐" in instr
    assert "default 3 images" in instr and "One generate_image call per image with count 1" in instr
    assert 'skill: "portrait-studio"' in instr
    assert UPLOAD["zh"] in instr and UPLOAD["en"] in instr
    assert instr.index("If the user attached no reference photo") < instr.index('id "ps_shots"')
    assert "do not call ask_user: call generate_image once with skill: \"portrait-studio\" and no refs" in instr
    assert "Reply with that user_message verbatim and stop" in instr
    for needle in ("recommended: true", '"recommended"', "defaults: [", "PORTRAIT_SHOTS_708"):
        assert needle not in instr
    # The original craft lines 1)-4) are kept as they were on main.
    for line in ("1) Brief: subject cues, beauty and location from portraitBrief + refs.",
                 "2) Craft: studio or environmental light; focal-length feel as asked.",
                 "3) Subject: single person primary; honest skin and styling.",
                 "4) Division: portrait craft — leave apparel product-in-hand studio sets to studio-model."):
        assert line in instr
    assert "5) Refs: pass refs in refs on every generate_image call." not in instr


def test_default_output_is_3_images():
    assert ps.DEFAULT_IMAGES == 3
    assert ps.images_for("A") == 3 and ps.images_for("B") == 4 and ps.images_for("C") == 1
    assert ps.images_for(None) == 3 and ps.images_for("") == 3 and ps.images_for("其它") == 3  # skipped / free text
    assert paid_guard.DEFAULT_CAP >= max(ps.IMAGES_BY_SHOTS.values())  # option B (4) fits the default turn cap


# --- no reference photo: ask to upload, $0 -------------------------------------------------------

SENT: list = []
APPROVALS: list = []


@pytest.fixture
def relay(monkeypatch):
    SENT.clear()
    APPROVALS.clear()

    async def submit(action, args, project, timeout, chat=""):
        SENT.append((action, dict(args)))
        return {"ids": ["shape:g1"], "model": args.get("edit_model") or args.get("model")}

    async def approval(label):
        APPROVALS.append(label)
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", approval)


def _gen(lang, goal, args):
    return _with_lang(lang, goal, lambda: asyncio.run(canvas.TOOLS["generate_image"]["handler"](dict(args))))


@pytest.mark.parametrize("lang,ui,goal", [("zh", "zh", ""), ("en", "en", ""), ("zh", "en", "帮我做一组专业形象照"),
                                          ("en", "zh", "make me professional headshots")])
@pytest.mark.parametrize("extra", [{}, {"refs": []}, {"refs": [], "base": ""}, {"count": 3, "ratio": "3:4"}])
def test_no_reference_asks_to_upload_and_submits_nothing(relay, lang, ui, goal, extra):
    out = _gen(ui, goal, {"prompt": "professional portrait set", "skill": "portrait-studio", **extra})
    assert SENT == [] and APPROVALS == []  # no model call, no cost confirm
    assert out["status"] == "needs_input"
    assert out["submitted"] is False and out["generation_succeeded"] is False and out["charged"] is False
    assert out["kind"] == ps.NEEDS_REFERENCE_KIND and out["lang"] == lang
    assert out["user_message"] == UPLOAD[lang]


@pytest.mark.parametrize("lang,goal", [("zh", "帮我用这张照片做一组专业形象照。"), ("en", "Make a professional portrait set from my photo.")])
def test_goal_check_waits_for_the_upload_instead_of_failing(lang, goal):
    """The upload request is not a failed delivery: the self-check skips (awaiting_input), no warn notice."""
    import json as _json

    from ComfyArt.bot import self_check
    result = ps.needs_reference_result(lang)
    blocks = [{"type": "tool_use", "id": "t1", "name": "mcp__comfyart__generate_image", "input": {"skill": "portrait-studio"}},
              {"type": "tool_result", "id": "t1", "name": "mcp__comfyart__generate_image", "text": _json.dumps(result, ensure_ascii=False)},
              {"type": "text", "text": result["user_message"]}]
    assert self_check.parse_goal(goal) is not None  # the request alone would expect an image
    out, info = self_check.apply_to_blocks(goal, blocks, lang)
    assert info == {"self_check": "skip", "reason": "awaiting_input"}
    assert out == blocks and not any(b.get("type") == "notice" for b in out)
    # A real failure (submitted and failed) still fails the check.
    failed = [b if b.get("type") != "tool_result" else {**b, "text": _json.dumps({"status": "failed", "submitted": True})} for b in blocks]
    assert self_check.apply_to_blocks(goal, failed, lang)[1]["self_check"] == "fail"


def test_with_reference_submits_one_sunburst_edit_per_image(relay):
    out = _gen("zh", "", {"prompt": "面部特写，保留原有休闲造型，纯色棚拍背景", "skill": "portrait-studio",
                          "refs": ["shape:person"], "count": 1, "shot": "closeup"})
    assert out.get("status") != "needs_input", out
    assert len(SENT) == 1 and SENT[0][0] == "generate_image"
    sent = SENT[0][1]
    assert sent["edit_model"] == SUNBURST_EDIT
    assert sent.get("edit_resolution") == "2k" and sent.get("ratio") == "3:4"
    assert sent["refs"] == ["shape:person"]


def test_no_reference_rule_is_only_for_portrait_studio(relay):
    out = _gen("zh", "", {"prompt": "a cat", "count": 1})
    assert out.get("kind") != ps.NEEDS_REFERENCE_KIND
    assert len(SENT) == 1


# --- goal self-check: waiting for input vs real failures (all skills; Tech on #926) --------------

def _blocks(*results):
    """tool_use + tool_result pairs; each item is (tool, result dict, block status or None)."""
    import json as _json
    out = []
    for n, (tool, data, status) in enumerate(results):
        out.append({"type": "tool_use", "id": f"t{n}", "name": f"mcp__comfyart__{tool}", "input": {}})
        res = {"type": "tool_result", "id": f"t{n}", "name": f"mcp__comfyart__{tool}", "text": _json.dumps(data, ensure_ascii=False)}
        if status:
            res["status"] = status
        out.append(res)
    return out


_NEEDS_INPUT = {"status": "needs_input", "submitted": False, "generation_succeeded": False, "charged": False}
_SELF_CHECK_SKILLS = ["portrait-studio", "youtube-channel-banner", "game-art", None]  # None: no skill


@pytest.mark.parametrize("lang,goal", [("zh", "帮我生成 3 张图"), ("en", "Make 3 images for me")])
@pytest.mark.parametrize("tool", ["generate_image", "edit_image", "generate_video"])
def test_self_check_skips_any_tool_that_only_asked_for_input(lang, goal, tool):
    """Any skill / tool: a needs_input result with nothing submitted waits for the user, no warn notice."""
    from ComfyArt.bot import self_check
    blocks = _blocks((tool, {**_NEEDS_INPUT, "user_message": "please upload"}, None)) + [{"type": "text", "text": "please upload"}]
    out, info = self_check.apply_to_blocks(goal, blocks, lang)
    assert info == {"self_check": "skip", "reason": "awaiting_input"}
    assert out == blocks and not any(b.get("type") == "notice" for b in out)


def _fail_cases():
    submitted_zero = [("generate_image", {"ids": ["j1"], "submitted": True}, None),
                      ("wait_generation", {"results": [{"id": "j1", "status": "error", "error": "content filter"}]}, "error")]
    call_errored = [("generate_image", {"status": "failed", "generation_succeeded": False, "error": "HTTP 500"}, "error")]
    submitted_none_back = [("generate_image", {"ids": ["j1"]}, None),
                           ("wait_generation", {"results": []}, None)]
    return {"submitted_0_images": submitted_zero, "call_errored": call_errored, "submitted_none_back": submitted_none_back}


@pytest.mark.parametrize("case", list(_fail_cases()))
@pytest.mark.parametrize("with_needs_input", [False, True])
@pytest.mark.parametrize("skill", _SELF_CHECK_SKILLS)
@pytest.mark.parametrize("lang,goal,warn", [("zh", "帮我生成 3 张图", "目标核对未通过"), ("en", "Make 3 images for me", "Goal check failed")])
def test_self_check_still_reports_real_failures(lang, goal, warn, skill, with_needs_input, case):
    """0 images after a submit, or an errored generation call, still fail and show the warn notice,
    for portrait-studio and other skills, even when a needs_input result is in the same turn."""
    from ComfyArt.bot import self_check
    steps = list(_fail_cases()[case])
    if with_needs_input:
        steps.insert(0, ("generate_image", dict(_NEEDS_INPUT), None))
    blocks = _blocks(*steps)
    for b in blocks:
        if b["type"] == "tool_use" and b["name"].endswith("generate_image") and skill:
            b["input"] = {"skill": skill}
    blocks.append({"type": "text", "text": "完成。" if lang == "zh" else "Done."})
    out, info = self_check.apply_to_blocks(goal, blocks, lang)
    assert info["self_check"] == "fail" and info["generated"] == 0 and info["expected"] == 3, info
    notes = [b for b in out if b.get("type") == "notice"]
    assert len(notes) == 1 and notes[0]["level"] == "warn" and notes[0]["text"].startswith(warn), notes


@pytest.mark.parametrize("skill", _SELF_CHECK_SKILLS)
def test_self_check_passes_a_full_delivery_after_an_input_request(skill):
    """Asked for the photo, then generated all 3 in the same turn: the normal check runs and passes."""
    from ComfyArt.bot import self_check
    steps = [("generate_image", dict(_NEEDS_INPUT), None)]
    steps += [("generate_image", {"ids": [f"j{n}"]}, None) for n in range(3)]
    steps += [("wait_generation", {"results": [{"id": f"j{n}", "status": "done", "shapes": [{"id": f"shape:{n}"}]} for n in range(3)]}, None)]
    sc = self_check.check("帮我生成 3 张图", _blocks(*steps))
    assert sc.awaiting_input is False and sc.applies
    assert sc.generated == 3


# --- one call per image: same reference, same person / outfit / background; only shot + pose differ -

def _run_turn(lang, calls):
    """Several generate_image calls in ONE turn (same paid-guard turn), like the agent loop."""
    async def go():
        out = []
        for args in calls:
            out.append(await canvas.TOOLS["generate_image"]["handler"](dict(args)))
        return out
    return _with_lang(lang, "", lambda: asyncio.run(go()))


SUBJECT = ("Professional portrait of the woman in the reference photo, wearing a navy business suit with a white shirt, "
           "solid light-grey studio backdrop, soft key light from the left.")


def _split(prompt: str) -> tuple[list[str], str, str]:
    lines = prompt.split("\n")
    shot = [ln for ln in lines if ln.startswith(ps.SHOT_HEAD)]
    pose = [ln for ln in lines if ln.startswith(ps.POSE_HEAD)]
    assert len(shot) == 1 and len(pose) == 1, prompt
    return [ln for ln in lines if ln not in shot and ln not in pose], shot[0], pose[0]


def _assert_only_shot_and_pose_differ(sent: list, shots: tuple) -> None:
    assert [a for a, _ in sent] == ["generate_image"] * len(shots)
    reqs = [args for _, args in sent]
    shared, shot_lines, pose_lines = zip(*(_split(r["prompt"]) for r in reqs))
    assert all(sh == shared[0] for sh in shared)  # identical person + outfit + background text
    assert ps.IDENTITY_LINE in shared[0] and SUBJECT in shared[0]
    assert list(shot_lines) == [ps.SHOT_LINE[s] for s in shots]
    assert list(pose_lines) == [ps.POSE_LINE[s] for s in shots]
    assert len(set(shot_lines)) == len(shots)  # each image its own shot size
    for r in reqs:
        assert r["refs"] == ["shape:person"]  # the same single reference photo on every call
        assert r.get("count", 1) == 1 and "shot" not in r
        assert r["edit_model"] == SUNBURST_EDIT
    # Everything except the prompt's shot/pose lines is the same request.
    rest = [{k: v for k, v in r.items() if k != "prompt"} for r in reqs]
    assert all(x == rest[0] for x in rest), rest


@pytest.mark.parametrize("option", ["A", "B", "C"])
def test_per_image_calls_share_reference_and_description_only_shot_and_pose_differ(relay, option):
    shots = ps.SHOTS_BY_OPTION[option]
    assert len(shots) == ps.IMAGES_BY_SHOTS[option]
    calls = [{"prompt": SUBJECT, "skill": "portrait-studio", "refs": ["shape:person"], "count": 1, "shot": s} for s in shots]
    outs = _run_turn("zh", calls)
    assert all(o.get("status") != "needs_input" for o in outs), outs
    _assert_only_shot_and_pose_differ(SENT, shots)


def test_per_image_calls_lock_the_first_description_and_reference_when_the_model_drifts(relay):
    """The model rewrites the person/outfit or swaps refs on a later call: the server keeps the first call's."""
    calls = [{"prompt": SUBJECT, "skill": "portrait-studio", "refs": ["shape:person"], "count": 1, "shot": "closeup"},
             {"prompt": "Half body portrait of a man in a red hoodie, office background", "skill": "portrait-studio",
              "refs": ["shape:other"], "count": 2, "shot": "half"},
             {"prompt": SUBJECT + " Three-quarter body.", "skill": "portrait-studio", "refs": ["shape:person", "shape:x"],
              "count": 1, "shot": "three_quarter"}]
    _run_turn("en", calls)
    _assert_only_shot_and_pose_differ(SENT, ("closeup", "half", "three_quarter"))


def test_per_image_calls_without_shot_are_refused_and_submit_nothing(relay):
    """#957: a missing shot is refused before submit; the server does not guess the Lovart order."""
    calls = [{"prompt": SUBJECT, "skill": "portrait-studio", "refs": ["shape:person"], "count": 1}] * 4
    outs = _run_turn("zh", calls)
    assert SENT == []
    assert all(o.get("submitted") is False and o.get("charged") is False for o in outs)
    assert all(o.get("kind") == "missingSkillParams" and "shot" in (o.get("missing") or []) for o in outs)


def test_a_new_turn_starts_a_new_set(relay):
    _run_turn("zh", [{"prompt": SUBJECT, "skill": "portrait-studio", "refs": ["shape:person"], "count": 1, "shot": "closeup"}])
    _run_turn("zh", [{"prompt": "Portrait of the man in the reference, grey suit, modern office.", "skill": "portrait-studio",
                      "refs": ["shape:p2"], "count": 1, "shot": "closeup"}])
    assert "grey suit" in SENT[1][1]["prompt"] and SENT[1][1]["refs"] == ["shape:p2"]


def test_shot_and_pose_are_the_only_per_image_lines():
    """Lovart 7fc60c86: 「只变景别与姿态」「姿态相应重建」: per shot, exactly a shot-size line and a pose line."""
    assert set(ps.SHOT_LINE) == set(ps.POSE_LINE) == set(ps.SHOT_KEYS)
    for s in ps.SHOT_KEYS:
        p = ps.compose_prompt("X", s)
        assert p.split("\n") == [ps.IDENTITY_LINE, "X", ps.SHOT_LINE[s], ps.POSE_LINE[s]]
    instr = _instructions()
    assert "only shot size and pose change between the images" in instr
    assert canvas.SPECS["generate_image"]["inputSchema"]["properties"]["shot"]["enum"] == list(ps.SHOT_KEYS)


def test_shot_crops_follow_the_reference_notes():
    """notes.txt 7fc60c86: 面部特写（头肩） / 半身（大腿上缘以上） / 七分身（小腿中部以上）."""
    assert ps.SHOT_LINE["closeup"] == "Shot size: face close-up, head and shoulders."
    assert ps.SHOT_LINE["half"] == "Shot size: half body, framed from the upper thigh up."
    assert ps.SHOT_LINE["three_quarter"] == "Shot size: three-quarter body, framed from mid-calf up."
    assert ps.SHOT_LINE["full"] == "Shot size: full body, head to feet in frame."
    assert "waist up" not in ps.SHOT_LINE["half"] and "mid-thigh" not in ps.SHOT_LINE["three_quarter"]


_SHARED_POSE_POINTS = ("S-curve spine", "one shoulder slightly higher than the other",
                       "chin slightly forward and down to tighten the jawline",
                       "hands in pockets or hanging naturally at the sides", "avoid finger distortion",
                       "negative space kept at the sides of the waist")


@pytest.mark.parametrize("shot", ps.SHOT_KEYS)
def test_every_pose_line_is_the_shared_reference_posing(shot):
    """notes.txt 摆姿: S 型脊柱 + 一肩微高一肩微低 + 下巴前伸微低拉紧下颌线；插兜 / 自然垂落侧手，规避手指畸变，腰侧保留负空间."""
    pose = ps.POSE_LINE[shot]
    for point in _SHARED_POSE_POINTS:
        assert point in pose, (shot, point)
    assert pose.startswith(ps.POSE_HEAD + " " + ps.POSE_SHARED)
    for line in (pose, ps.SHOT_LINE[shot]):
        low = line.lower()
        for banned in ("cross", "eyes to the lens", "weight on one leg", "lens", "confident"):
            assert banned not in low, (shot, banned)


def test_other_skills_prompts_are_not_rewritten(relay):
    _run_turn("zh", [{"prompt": "a cat", "count": 1, "refs": ["shape:a"], "shot": "closeup"},
                     {"prompt": "a dog", "count": 1, "skill": "youtube-channel-banner", "refs": ["shape:b"]}])
    assert [a["prompt"] for _, a in SENT] == ["a cat", "a dog"]
    assert all("shot" not in a for _, a in SENT)



_OTHER_SKILL_IDS = sorted(set(re.findall(r"\{ id: '([a-z0-9-]+)'", SKILLS)) - {"portrait-studio"})


def test_other_skill_ids_cover_every_skill():
    assert len(_OTHER_SKILL_IDS) >= 40 and "youtube-channel-banner" in _OTHER_SKILL_IDS


@pytest.mark.parametrize("skill", [None] + _OTHER_SKILL_IDS)
def test_shot_never_reaches_the_request_for_other_skills(relay, skill):
    """Tech #926: `shot` is portrait-studio only; every other skill (and no skill) must not carry it in the request."""
    args = {"prompt": "a cat on a sofa", "count": 1, "refs": ["shape:a"], "shot": "half"}
    if skill:
        args["skill"] = skill
    _run_turn("zh", [args])
    assert all("shot" not in a for _, a in SENT), (skill, SENT)
    lines = list(ps.SHOT_LINE.values()) + list(ps.POSE_LINE.values())
    assert not any(l in str(a.get("prompt", "")) for _, a in SENT for l in lines), (skill, SENT)

# --- untouched -----------------------------------------------------------------------------------

def _main_bytes(path: str) -> bytes:
    return subprocess.run(["git", "show", f"{MAIN}:{path}"], cwd=ROOT, check=True, capture_output=True).stdout


@pytest.mark.parametrize("path", ["api/auto_models.json", "api/skill_size.py", "api/curated_models.json",
                                  "api/wavespeed_models.json"])
def test_pins_sizes_and_model_tables_are_unchanged_from_main(path):
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == hashlib.sha256(_main_bytes(path)).hexdigest(), path


def test_skill_output_keeps_follow_ref_and_905_user_ratio():
    """#926 locked skill_output.py to main; #905/#908 also lives in this file.

    Keep clothing-swap FOLLOW_REF_SIZES from main, plus before-after USER_RATIOS.
    Full wording/size locks live in test_clothing_swap_911 / test_before_after_905.
    """
    from ComfyArt.bot import skill_output as so
    assert "clothing-swap" in so.FOLLOW_REF_SIZES
    assert "before-after" in so.USER_RATIOS
    assert so.follows_ref("clothing-swap") and not so.follows_ref("before-after")
