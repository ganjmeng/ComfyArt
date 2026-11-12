"""portrait-studio replies around the set + single-image redo (Lovart 7fc60c86 reply, notes.txt).

Product acceptance (modeled on Lovart's replies, nothing extra):
1. before generating: locked from the reference / what changes, then lighting, optics, pose, then 「现在开始生成」;
   built from the card answers + what the agent read off the reference, not a fixed text.
2. after generating: a shot-size -> image table, then only the parameters actually written into the prompts
   (focal length, aperture, lighting, aspect ratio). No shutter, ISO, film stock, negative prompt or price.
3. closing: look at the images, name the one whose face shape or hair drifted, only that one is redone;
   also offer to swap the background color (米白 / 深灰) or add a landscape version.
4. single redo: exactly ONE paid call (same reference, same shot, same outfit/scene, count 1), placed next to
   the original; the original and the other images untouched.
5. en UI is all English.

$0: submit_command and the run approval are mocked; no WaveSpeed call.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path

import pytest

from ComfyArt.api import portrait_studio as ps
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from test_portrait_studio_flow import SUNBURST_EDIT, _with_lang

CJK = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")
BANNED = ("ISO", "1/250", "Portra", "Kodak", "Negative", "负面", "$", "¥", "美元", "费用", "price", "film")

ZH_ARGS = {"refs": ["shape:person"], "shots": "A", "outfit": "A", "scene": "A",
           "locked": ["五官轮廓", "眼神气质", "黑色中长微卷发", "暖调自然亚洲肤色", "纤细高挑身材比例"],
           "outfit_desc": "白长袖打底 + 黑 V 领针织背心 + 卡其宽腿工装裤",
           "reference_background": "罗马柱建筑空间", "prompt": "young East Asian woman, black shoulder-length wavy hair"}
EN_ARGS = {"refs": ["shape:person"], "shots": "A", "outfit": "A", "scene": "A",
           "locked": ["facial features", "black shoulder-length wavy hair", "warm natural skin tone", "slim build"],
           "outfit_desc": "white long-sleeve top, black V-neck knit vest, khaki wide-leg cargo pants",
           "reference_background": "a columned hall", "prompt": "young East Asian woman, black shoulder-length wavy hair"}

# Lock: zh A/A/A, Lovart's reply shape with this run's answers (notes.txt «Lovart reply (verbatim, in order)»).
ZH_PLAN = "\n".join([
    "参考图已作为身份锚点分析完毕。按你的选择：3 张 / 保留原休闲造型 / 纯色棚拍背景，三张共用同一人物身份与服装，只变景别与姿态。",
    "锁定项：五官轮廓、眼神气质、黑色中长微卷发、暖调自然亚洲肤色、纤细高挑身材比例、服装完整保留（白长袖打底 + 黑 V 领针织背心 + 卡其宽腿工装裤）",
    "变更项：背景由罗马柱建筑空间 → 纯色棚拍背景；景别拆为特写 / 半身 / 七分身三档，姿态相应重建",
    "布光：Loop 环形光为主方案，大面积柔光箱从机位左侧 30° 高位切入，辅以弱发丝轮廓光",
    "光学：85mm 黄金人像焦段；特写 f/2.0、半身 f/2.8、七分身 f/4.0",
    "摆姿：S 型脊柱 + 一肩微高一肩微低 + 下巴前伸微低拉紧下颌线；手部统一走\"插兜 / 自然垂落侧手\"路线，规避手指畸变，腰侧保留负空间",
    "现在开始生成三张。",
])
ZH_DONE = "\n".join([
    "三张已完成：",
    "| 景别 | 产物 |",
    "|---|---|",
    "| 面部特写（头肩） | 第 1 张：专业形象照-面部特写 |",
    "| 半身（大腿上缘以上） | 第 2 张：专业形象照-半身 |",
    "| 七分身（小腿中部以上） | 第 3 张：专业形象照-七分身 |",
    "⚙️ 参数",
    "光学参数：85mm ｜ Loop 环形光 + 柔光 ｜ 特写 f/2.0 · 半身 f/2.8 · 七分身 f/4.0",
    "画幅：3:4 竖版 ×3",
])
ZH_CLOSE = ("验收提示：三张的身份锚点（五官轮廓、眼神气质、黑色中长微卷发、暖调自然亚洲肤色、纤细高挑身材比例）都按参考图锁定了，"
            "但我无法逐像素核对实际一致性。请你过一眼这三张，如果某张的脸型或发型偏离原片，告诉我具体是哪张、偏在哪里，我针对那一张重做；也可以顺手换背景色（米白 / 深灰）或补一版横版构图。")
EN_PLAN = "\n".join([
    "The reference photo has been analyzed as the identity anchor. As you chose: 3 photos / keep the original casual look / "
    "solid-color studio backdrop; all three share the same person and outfit, only the shot size and pose change.",
    "Locked: facial features, black shoulder-length wavy hair, warm natural skin tone, slim build, outfit kept in full "
    "(white long-sleeve top, black V-neck knit vest, khaki wide-leg cargo pants)",
    "Changed: background from a columned hall → solid-color studio backdrop; shot sizes split into face close-up / half body / "
    "three-quarter body, with the pose rebuilt for each",
    "Lighting: Loop lighting as the main setup: a large softbox high from camera-left at 30°, plus a soft hair light for rim separation",
    "Optics: 85mm portrait focal length; face close-up f/2.0, half body f/2.8, three-quarter body f/4.0",
    "Pose: S-curve spine, one shoulder slightly higher, chin slightly forward and down to tighten the jawline; hands in pockets "
    "or hanging naturally at the sides, avoiding finger distortion, with negative space at the sides of the waist",
    "Starting the three photos now.",
])
EN_DONE = "\n".join([
    "All three are done:",
    "| Shot size | Image |",
    "|---|---|",
    "| Face close-up (head and shoulders) | Image 1: Professional portrait - face close-up |",
    "| Half body (from the upper thigh up) | Image 2: Professional portrait - half body |",
    "| Three-quarter body (from mid-calf up) | Image 3: Professional portrait - three-quarter body |",
    "⚙️ Parameters",
    "Optics: 85mm | Loop lighting + softbox | face close-up f/2.0 · half body f/2.8 · three-quarter body f/4.0",
    "Format: 3:4 portrait ×3",
])
EN_CLOSE = ("Check: the identity anchors of all three (facial features, black shoulder-length wavy hair, warm natural skin tone, "
            "slim build) are locked to the reference, but I can't verify the match pixel by pixel. Please look over the three "
            "photos; if one drifts from the original in face shape or hair, tell me which one and where, and I'll redo just that one. I can also swap the background color (ivory / dark gray) or add a landscape version.")
LOCK = {"zh": (ZH_ARGS, ZH_PLAN, ZH_DONE, ZH_CLOSE), "en": (EN_ARGS, EN_PLAN, EN_DONE, EN_CLOSE)}
# One marker per reply part; each must appear exactly once in the whole set's chat text.
MARKERS = {"zh": ("现在开始生成", "| 景别 | 产物 |", "验收提示："), "en": ("Starting the", "| Shot size | Image |", "Check: ")}


@pytest.fixture(autouse=True)
def no_paid_keys(monkeypatch):
    for key in ("WAVESPEED_API_KEY", "DEEPSEEK_API_KEY", "REPLICATE_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)


SENT: list = []
APPROVALS: list = []


@pytest.fixture
def relay(monkeypatch):
    """Mocked page/WaveSpeed hop: every generate_image that would reach the provider lands in SENT."""
    SENT.clear()
    APPROVALS.clear()
    ps.PLANS.clear()

    async def submit(action, args, project, timeout, chat=""):
        SENT.append((action, dict(args)))
        return {"ids": [f"gen:{len(SENT)}"], "model": args.get("edit_model") or args.get("model")}

    async def approval(label):
        APPROVALS.append(label)
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", approval)
    yield
    ps.PLANS.clear()


def _tool(name, args, lang, chat):
    async def run():
        token = BOT_CHAT_ID.set(chat)
        try:
            return await canvas.TOOLS[name]["handler"](dict(args))
        finally:
            BOT_CHAT_ID.reset(token)
    return _with_lang(lang, "", lambda: asyncio.run(run()))


def _run_set(lang, args, chat):
    """The agent's whole set: plan -> one generate_image per slot -> done. Returns (messages, plan result)."""
    plan = _tool("portrait_studio_plan", args, lang, chat)
    assert plan["status"] == "planned", plan
    msgs = [plan["user_message"]]
    for s in plan["slots"]:
        out = _tool("generate_image", {"prompt": args["prompt"], "skill": "portrait-studio", "refs": args["refs"],
                                       "count": 1, "shot": s["shot"]}, lang, chat)
        assert out.get("ids"), out
    done = _tool("portrait_studio_done", {"images": [f"shape:img{s['slot']}" for s in plan["slots"]]}, lang, chat)
    assert done["status"] == "done", done
    msgs.append(done["user_message"])
    return msgs, plan


def _seed_sent(plan):
    """Record the prompts and ratio this server would send, so done_text reads them rather than constants."""
    for i, shot in enumerate(plan["shots"], 1):
        plan["slot_args"][i] = {
            "prompt": f"{ps.compose_prompt(plan['prompt'], shot)}\n{ps.plan_lines(plan, shot)}",
            "ratio": "3:4",
        }
    return plan


# --- reply text (lock) ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["zh", "en"])
def test_reply_text_is_locked(lang):
    args, want_plan, want_done, want_close = LOCK[lang]
    plan = _seed_sent(ps.make_plan(args, lang))
    assert ps.plan_text(plan) == want_plan
    assert ps.done_text(plan) == want_done
    assert ps.closing_text(plan) == want_close


def test_zh_reply_keeps_lovart_7fc60c86_wording():
    """The fixed phrases come from Lovart's reply in notes.txt (the run's own answers were A/A/A)."""
    plan = _seed_sent(ps.make_plan(ZH_ARGS, "zh"))
    text = ps.plan_text(plan) + "\n" + ps.done_text(plan) + "\n" + ps.closing_text(plan)
    for lovart in ("参考图已作为身份锚点分析完毕。按你的选择：3 张 / 保留原休闲造型 / 纯色棚拍背景，三张共用同一人物身份与服装，只变景别与姿态。",
                   "景别拆为特写 / 半身 / 七分身三档，姿态相应重建",
                   "Loop 环形光为主方案，大面积柔光箱从", "辅以弱发丝轮廓光",
                   "85mm 黄金人像焦段；特写 f/2.0、半身 f/2.8、七分身 f/4.0",
                   "S 型脊柱 + 一肩微高一肩微低 + 下巴前伸微低拉紧下颌线；手部统一走\"插兜 / 自然垂落侧手\"路线，规避手指畸变，腰侧保留负空间",
                   "三张已完成：", "| 面部特写（头肩） |", "| 半身（大腿上缘以上） |", "| 七分身（小腿中部以上） |",
                   "专业形象照-面部特写", "专业形象照-半身", "专业形象照-七分身",
                   "85mm ｜ Loop 环形光 + 柔光 ｜ 特写 f/2.0 · 半身 f/2.8 · 七分身 f/4.0", "3:4 竖版 ×3",
                   "都按参考图锁定了，但我无法逐像素核对实际一致性。请你过一眼这三张，如果某张的脸型或发型偏离原片，告诉我具体是哪张、偏在哪里，我针对那一张重做"):
        assert lovart in text, lovart


@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("shots,outfit,scene", [("A", "A", "A"), ("B", "B", "B"), ("C", "C", "C"), ("", "B", "C"),
                                                ("我要 2 张", "A", "B")])
def test_reply_follows_the_answers_and_the_reference(lang, shots, outfit, scene):
    args = {**LOCK[lang][0], "shots": shots, "outfit": outfit, "scene": scene}
    plan = _seed_sent(ps.make_plan(args, lang))
    want = ps.shots_for(shots)
    assert tuple(plan["shots"]) == want
    n = len(want)
    before, after, close = ps.plan_text(plan), ps.done_text(plan), ps.closing_text(plan)
    for item in args["locked"]:  # what the agent read off the reference is in the reply, not a fixed list
        assert item in before and item in close
    echo = ps.ECHO[lang]
    assert echo[ps.PS_OUTFIT][outfit] in before and echo[ps.PS_SCENE][scene] in before
    if outfit == "A":
        assert args["outfit_desc"] in before
    else:
        assert args["outfit_desc"] not in before
    if scene == "C":
        assert args["reference_background"] not in before
    else:
        assert args["reference_background"] in before
    for s in want:  # only the shots in this set, each with its aperture, in both replies
        assert ps.SHOTS[s]["aperture"] in before and ps.SHOTS[s]["aperture"] in after
        assert (ps.SHOTS[s]["zh_frame"] if lang == "zh" else ps.SHOTS[s]["en_frame"]) in after
    for s in set(ps.SHOTS) - set(want):
        assert (ps.SHOTS[s]["zh_frame"] if lang == "zh" else ps.SHOTS[s]["en_frame"]) not in after
    assert len(re.findall(r"\| 第 \d 张：" if lang == "zh" else r"\| Image \d: ", after)) == n
    assert (f"×{n}") in after and "3:4" in after and "85mm" in before and "85mm" in after


@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("shots", ["A", "B", "C"])
def test_listed_parameters_are_the_ones_written_into_every_prompt(relay, lang, shots):
    plan = ps.make_plan({**LOCK[lang][0], "shots": shots}, lang)
    text = ps.plan_text(plan) + ps.done_text(plan) + ps.closing_text(plan)
    for bad in BANNED:
        assert bad not in text, bad
    _run_set(lang, {**LOCK[lang][0], "shots": shots}, f"ps-{uuid.uuid4().hex}")
    assert len(SENT) == len(plan["shots"])
    for (_, sent), s in zip(SENT, plan["shots"]):
        prompt = sent["prompt"]
        assert ps.SHOT_LINE[s] in prompt and ps.POSE_LINE[s] in prompt and ps.IDENTITY_LINE in prompt
        assert f"85mm portrait lens at {ps.SHOTS[s]['aperture']}" in prompt and "loop lighting" in prompt
        assert "softbox" in prompt and "3:4 vertical portrait" in prompt
        assert ps.PROMPT_OUTFIT["A"] in prompt and ps.PROMPT_SCENE["A"] in prompt
        for other in set(ps.SHOT_KEYS) - {s}:
            assert ps.SHOT_LINE[other] not in prompt and f"at {ps.SHOTS[other]['aperture']}" not in prompt


def test_en_reply_is_all_english_and_rejects_chinese_reference_notes():
    for shots in ("A", "B", "C"):
        plan = _seed_sent(ps.make_plan({**EN_ARGS, "shots": shots, "outfit": "B", "scene": "B"}, "en"))
        for text in (ps.plan_text(plan), ps.done_text(plan), ps.closing_text(plan)):
            assert not CJK.search(text), text
        assert not CJK.search(ps.REDO_TEXT["en"])
    with pytest.raises(ps.PlanError):
        ps.make_plan({**EN_ARGS, "locked": ["五官轮廓"]}, "en")


def test_one_image_set_reads_as_one():
    zh = _seed_sent(ps.make_plan({**ZH_ARGS, "shots": "C"}, "zh"))
    assert "现在开始生成一张。" in ps.plan_text(zh) and "共用" not in ps.plan_text(zh)
    assert ps.done_text(zh).startswith("这张已完成：") and "×1" in ps.done_text(zh)
    assert "我重做这一张" in ps.closing_text(zh)
    en = _seed_sent(ps.make_plan({**EN_ARGS, "shots": "C"}, "en"))
    assert "Starting the photo now." in ps.plan_text(en) and "redo this one" in ps.closing_text(en)


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_done_table_parameters_are_substrings_of_the_sent_prompts(relay, lang):
    """Every parameter listed after generating is in that image's actually sent prompt (or its ratio arg)."""
    chat = f"ps-{uuid.uuid4().hex}"
    msgs, _ = _run_set(lang, LOCK[lang][0], chat)
    done = msgs[1]
    assert len(SENT) == 3
    plan = ps.PLANS[chat]
    shots = list(plan["shots"])
    # tokens shown on the shared optics / format lines
    listed = []
    if "85mm" in done:
        listed.append(("85mm", None))  # must be in every sent prompt
    light = ps.LIGHT_SHORT[lang]
    if light in done:
        listed.append((ps.LIGHT["prompt"], None))  # display label maps to the sent light line
    for shot in shots:
        ap = ps.SHOTS[shot]["aperture"]
        if ap in done:
            listed.append((ap, shot))
    if "3:4" in done:
        listed.append(("3:4", "ratio"))
    assert listed, done
    for token, scope in listed:
        for (_, sent), shot in zip(SENT, shots):
            if scope is None:
                assert token in sent["prompt"], (token, shot, sent["prompt"])
            elif scope == "ratio":
                assert token in sent["prompt"] or sent.get("ratio") == token or sent.get("aspect_ratio") == token, sent
            elif scope == shot:
                assert token in sent["prompt"], (token, shot, sent["prompt"])


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_done_table_omits_lens_and_lighting_when_the_prompt_lacks_them(lang):
    """Stubbed composition: no lens / lighting / format in the recorded prompts → the table omits them."""
    plan = ps.make_plan(LOCK[lang][0], lang)
    for i, shot in enumerate(plan["shots"], 1):
        plan["slot_args"][i] = {
            "prompt": "\n".join([plan["prompt"], ps.PROMPT_OUTFIT["A"], ps.PROMPT_SCENE["A"], ps.SHOT_LINE[shot]]),
        }
    after = ps.done_text(plan)
    assert "85mm" not in after and "3:4" not in after
    assert ps.LIGHT_SHORT[lang] not in after
    assert "Loop 环形光" not in after and "Loop lighting" not in after
    for shot in plan["shots"]:
        assert ps.SHOTS[shot]["aperture"] not in after
    # the shot table itself is still written
    frame = ps.SHOTS[plan["shots"][0]]["zh_frame" if lang == "zh" else "en_frame"]
    assert frame in after
    assert "⚙️" not in after  # no parameter block at all


# --- the set through the real tool handlers ------------------------------------------------------

@pytest.mark.parametrize("lang", ["zh", "en"])
def test_each_reply_part_appears_exactly_once(relay, lang):
    chat = f"ps-{uuid.uuid4().hex}"
    msgs, _ = _run_set(lang, LOCK[lang][0], chat)
    chat_text = "\n\n".join(msgs)
    for marker in MARKERS[lang]:
        assert chat_text.count(marker) == 1, (marker, chat_text)
    assert chat_text.index(MARKERS[lang][0]) < chat_text.index(MARKERS[lang][1]) < chat_text.index(MARKERS[lang][2])
    assert msgs == [LOCK[lang][1], LOCK[lang][2] + "\n\n" + LOCK[lang][3]]
    assert len(SENT) == 3  # the set itself: one call per slot


def test_each_slot_is_one_image_with_its_own_shot(relay):
    chat = f"ps-{uuid.uuid4().hex}"
    _run_set("zh", {**ZH_ARGS, "shots": "B"}, chat)
    assert [a for a, _ in SENT] == ["generate_image"] * 4
    for (_, sent), shot in zip(SENT, ("closeup", "half", "three_quarter", "full")):
        assert sent["count"] == 1 and sent["refs"] == ["shape:person"]
        assert sent["edit_model"] == SUNBURST_EDIT and sent.get("ratio") == "3:4"
        assert ps.SHOT_LINE[shot] in sent["prompt"] and f"at {ps.SHOTS[shot]['aperture']}." in sent["prompt"]
        assert "shot" not in sent


def test_without_a_plan_generate_image_is_unchanged_and_done_checks_the_count(relay):
    chat = f"ps-{uuid.uuid4().hex}"
    _tool("generate_image", {"prompt": "p", "skill": "portrait-studio", "refs": ["shape:person"], "shot": "half"}, "zh", chat)
    assert len(SENT) == 1 and "85mm" not in SENT[0][1]["prompt"]  # #926's per-image prompt only
    assert _tool("portrait_studio_done", {"images": ["shape:a"]}, "zh", chat)["status"] == "failed"
    _tool("portrait_studio_plan", ZH_ARGS, "zh", chat)
    assert _tool("portrait_studio_done", {"images": ["shape:a"]}, "zh", chat)["status"] == "failed"  # 3 slots


def test_plan_needs_a_reference_and_what_stays_locked(relay):
    chat = f"ps-{uuid.uuid4().hex}"
    assert _tool("portrait_studio_plan", {**ZH_ARGS, "refs": []}, "zh", chat)["status"] == "failed"
    assert _tool("portrait_studio_plan", {**ZH_ARGS, "locked": []}, "zh", chat)["status"] == "failed"
    assert _tool("portrait_studio_plan", {**EN_ARGS, "locked": ["黑发"]}, "en", chat)["status"] == "failed"
    assert SENT == [] and APPROVALS == []


# --- single redo ---------------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("ask,slot", [({"shot": "半身"}, 2), ({"shot": "半身那张脸不像"}, 2), ({"slot": 2}, 2),
                                      ({"shot": "half body, the face looks off"}, 2), ({"shot": "七分身"}, 3), ({"shot": "特写"}, 1),
                                      ({"slot": 1}, 1), ({"shot": "three-quarter"}, 3)])
def test_redo_one_issues_exactly_one_call_with_that_slots_shot(relay, lang, ask, slot):
    chat = f"ps-{uuid.uuid4().hex}"
    _run_set(lang, LOCK[lang][0], chat)
    first = [dict(a) for _, a in SENT]
    SENT.clear()
    APPROVALS.clear()
    out = _tool("portrait_studio_redo", {**ask, "fix": "match the face shape of the reference"}, lang, chat)
    assert len(SENT) == 1, SENT  # exactly one paid call
    assert len(APPROVALS) == 1  # the run approval covers that one image
    action, sent = SENT[0]
    assert action == "generate_image" and sent["count"] == 1
    assert sent["refs"] == ["shape:person"] and sent["edit_model"] == SUNBURST_EDIT
    assert sent["near"] == f"shape:img{slot}"  # placed next to the original; nothing deletes or replaces it
    shot = ps.PLANS[chat]["shots"][slot - 1]
    assert ps.SHOT_LINE[shot] in sent["prompt"] and f"at {ps.SHOTS[shot]['aperture']}." in sent["prompt"]
    # the same prompt as that slot's first run, plus only the correction
    fixed = sent["prompt"].replace(" Correction for this redo: match the face shape of the reference.", "")
    assert fixed == first[slot - 1]["prompt"]
    assert "match the face shape of the reference" in sent["prompt"]
    for other in set(ps.SHOT_KEYS) - {shot}:
        assert ps.SHOT_LINE[other] not in sent["prompt"]
    assert out["slot"] == slot and out["near"] == f"shape:img{slot}" and out.get("ids")
    msg = out["user_message"]
    assert bool(CJK.search(msg)) is (lang == "zh"), msg
    assert str(slot) in msg
    assert "delete" not in sent and "replace" not in sent


def test_redo_keeps_the_answers_outfit_and_scene(relay):
    chat = f"ps-{uuid.uuid4().hex}"
    _run_set("en", {**EN_ARGS, "outfit": "B", "scene": "B"}, chat)
    SENT.clear()
    _tool("portrait_studio_redo", {"slot": 3}, "en", chat)
    assert len(SENT) == 1
    prompt = SENT[0][1]["prompt"]
    assert ps.PROMPT_OUTFIT["B"] in prompt and ps.PROMPT_SCENE["B"] in prompt and ps.SHOT_LINE["three_quarter"] in prompt


@pytest.mark.parametrize("ask", [{}, {"slot": 5}, {"slot": 0}, {"shot": "全身"}, {"shot": "背景"}])
def test_redo_that_names_no_single_image_submits_nothing(relay, ask):
    chat = f"ps-{uuid.uuid4().hex}"
    _run_set("zh", ZH_ARGS, chat)  # A: no full-body slot
    SENT.clear()
    APPROVALS.clear()
    out = _tool("portrait_studio_redo", ask, "zh", chat)
    assert out["status"] == "failed" and SENT == [] and APPROVALS == []


def test_redo_without_a_set_submits_nothing(relay):
    out = _tool("portrait_studio_redo", {"slot": 1}, "zh", f"ps-{uuid.uuid4().hex}")
    assert out["status"] == "failed" and SENT == [] and APPROVALS == []
    assert out["user_message"] == "没有可重做的一组"


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_redo_after_server_restart_replies_no_set_and_generates_nothing(relay, lang):
    """Clearing the in-memory store simulates a restart: exact no-set reply, 0 submit, 0 quote."""
    chat = f"ps-{uuid.uuid4().hex}"
    _run_set(lang, LOCK[lang][0], chat)
    SENT.clear()
    APPROVALS.clear()
    ps.PLANS.clear()
    out = _tool("portrait_studio_redo", {"slot": 2}, lang, chat)
    assert out["user_message"] == ps.NO_REDO[lang]
    assert out["user_message"] == ("没有可重做的一组" if lang == "zh" else "There is no set to redo.")
    assert SENT == [] and APPROVALS == []
    assert out.get("submitted") is False and out.get("generation_succeeded") is False


@pytest.mark.parametrize("lang,goal,warn", [
    ("zh", "半身那张脸不像，重做一下", "目标核对未通过"),
    ("en", "Make 1 image: the half-body one doesn't look like me, redo it", "Goal check failed"),
])
def test_goal_check_passes_a_successful_redo_placement(lang, goal, warn):
    """A redo placed via wait_generation (no generate_image tool_use on the turn) must pass."""
    import json as _json
    from ComfyArt.bot import self_check
    assert self_check.parse_goal(goal) is not None
    blocks = [
        {"type": "tool_use", "id": "t1", "name": "mcp__comfyart__portrait_studio_redo",
         "input": {"shot": "半身" if lang == "zh" else "half body"}},
        {"type": "tool_result", "id": "t1", "name": "mcp__comfyart__portrait_studio_redo",
         "text": _json.dumps({"ids": ["gen:1"], "slot": 2, "near": "shape:img2",
                              "user_message": "ok"})},
        {"type": "tool_use", "id": "t2", "name": "mcp__comfyart__wait_generation",
         "input": {"ids": ["gen:1"]}},
        {"type": "tool_result", "id": "t2", "name": "mcp__comfyart__wait_generation",
         "text": _json.dumps({"results": [{"id": "gen:1", "status": "done", "placed": True,
                                           "generation_succeeded": True, "shapes": ["shape:redo1"]}]})},
        {"type": "text", "text": "好的，只重做第 2 张（半身），其它几张不动；新图放在原图旁边，原图保留。"
         if lang == "zh" else "OK, redoing only image 2 (half body)."},
    ]
    canvas = {"shape:img1", "shape:img2", "shape:img3", "shape:redo1"}
    sc = self_check.check(goal, blocks, canvas_ids=canvas)
    assert sc.generated == 1 and sc.placed == 1 and sc.passed, sc.to_dict()
    out, info = self_check.apply_to_blocks(goal, blocks, lang, canvas_ids=canvas)
    assert info["self_check"] == "pass", info
    assert not any(b.get("type") == "notice" for b in out)
    assert not any(warn in str(b.get("text") or "") for b in out)


@pytest.mark.parametrize("lang,goal,warn", [
    ("zh", "帮我生成 1 张图", "目标核对未通过"),
    ("en", "Make 1 image for me", "Goal check failed"),
])
@pytest.mark.parametrize("skill", ["studio-model", None])
def test_goal_check_still_fails_a_generic_shape_from_other_skills(lang, goal, warn, skill):
    """wait_generation reporting a generic `shape` is not a placed image for studio-model or no skill,
    even when the canvas is not re-read (canvas_ids is None) and when the canvas is empty."""
    import json as _json
    from ComfyArt.bot import self_check
    blocks = [
        {"type": "tool_use", "id": "t1", "name": "mcp__comfyart__wait_generation",
         "input": {"ids": ["j1"], **({"skill": skill} if skill else {})}},
        {"type": "tool_result", "id": "t1", "name": "mcp__comfyart__wait_generation",
         "text": _json.dumps({"results": [{"id": "j1", "status": "done", "placed": True,
                                           "generation_succeeded": True, "shapes": ["shape:ghost"]}]})},
        {"type": "text", "text": "完成。" if lang == "zh" else "Done."},
    ]
    for canvas in (None, set()):
        sc = self_check.check(goal, blocks, canvas_ids=canvas)
        assert sc.generated == 1 and sc.placed == 0 and not sc.passed, (skill, canvas, sc.to_dict())
        out, info = self_check.apply_to_blocks(goal, blocks, lang, canvas_ids=canvas)
        assert info["self_check"] == "fail" and info["placed"] == 0 and info["missing"] == 1, info
        notes = [b for b in out if b.get("type") == "notice"]
        assert len(notes) == 1 and warn in notes[0]["text"], notes


@pytest.mark.parametrize("lang,goal,warn", [
    ("zh", "帮我生成 1 张图", "目标核对未通过"),
    ("en", "Make 1 image for me", "Goal check failed"),
])
@pytest.mark.parametrize("owner", ["generate_video", "add_text"])
def test_goal_check_still_fails_when_only_a_non_image_node_is_placed(lang, goal, warn, owner):
    """A 1-image goal is not met by the turn's only wait_generation result being a video- or text-typed
    node, even when that node is on the canvas."""
    import json as _json
    from ComfyArt.bot import self_check
    sid = "shape:vid1" if owner == "generate_video" else "shape:txt1"
    result = {"ids": ["j1"]} if owner == "generate_video" else {"id": sid}
    blocks = [
        {"type": "tool_use", "id": "t0", "name": f"mcp__comfyart__{owner}",
         "input": {"prompt": "a clip"} if owner == "generate_video" else {"text": "hello"}},
        {"type": "tool_result", "id": "t0", "name": f"mcp__comfyart__{owner}",
         "text": _json.dumps(result)},
        {"type": "tool_use", "id": "t1", "name": "mcp__comfyart__wait_generation",
         "input": {"ids": ["j1"]}},
        {"type": "tool_result", "id": "t1", "name": "mcp__comfyart__wait_generation",
         "text": _json.dumps({"results": [{"id": "j1", "status": "done", "placed": True,
                                           "generation_succeeded": True, "shapes": [sid]}]})},
        {"type": "text", "text": "完成。" if lang == "zh" else "Done."},
    ]
    sc = self_check.check(goal, blocks, canvas_ids={sid})
    assert sc.generated == 1 and sc.placed == 0 and not sc.passed, sc.to_dict()
    out, info = self_check.apply_to_blocks(goal, blocks, lang, canvas_ids={sid})
    assert info["self_check"] == "fail" and info["placed"] == 0 and info["missing"] == 1, info
    notes = [b for b in out if b.get("type") == "notice"]
    assert len(notes) == 1 and warn in notes[0]["text"], notes


def test_tools_are_exposed_to_the_built_in_agent():
    from ComfyArt.bot.guide import CORE_MCP_TOOLS
    for name in ("portrait_studio_plan", "portrait_studio_done", "portrait_studio_redo", "portrait_studio_followup"):
        assert name in CORE_MCP_TOOLS and name in canvas.TOOLS
    assert "shot" in canvas.TOOLS["generate_image"]["inputSchema"]["properties"]

@pytest.mark.parametrize("lang", ["zh", "en"])
def test_closing_offers_background_swap_or_landscape(lang):
    plan = ps.make_plan(LOCK[lang][0], lang)
    close = ps.closing_text(plan)
    if lang == "zh":
        assert close.endswith("也可以顺手换背景色（米白 / 深灰）或补一版横版构图。")
        assert "我针对那一张重做；也可以顺手" in close
    else:
        assert "I can also swap the background color (ivory / dark gray) or add a landscape version." in close
        assert not CJK.search(close)


@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("ask,kind,color,needle", [
    ({"kind": "background", "color": "米白"}, "background", "ivory", "ivory off-white solid studio backdrop"),
    ({"kind": "background", "color": "ivory"}, "background", "ivory", "ivory off-white solid studio backdrop"),
    ({"kind": "background", "color": "深灰"}, "background", "dark_gray", "dark gray solid studio backdrop"),
    ({"kind": "landscape"}, "landscape", None, "Format: 4:3 landscape."),
    ({"kind": "横版构图"}, "landscape", None, "Format: 4:3 landscape."),
])
def test_followup_issues_exactly_one_call_and_keeps_the_original(relay, lang, ask, kind, color, needle):
    chat = f"ps-{uuid.uuid4().hex}"
    _run_set(lang, LOCK[lang][0], chat)
    SENT.clear()
    APPROVALS.clear()
    out = _tool("portrait_studio_followup", {**ask, "slot": 2}, lang, chat)
    assert len(SENT) == 1, SENT
    assert len(APPROVALS) == 1
    action, sent = SENT[0]
    assert action == "generate_image" and sent["count"] == 1
    assert sent["refs"] == ["shape:person"]
    assert sent["near"] == "shape:img2" and sent.get("near_fit") is True
    assert needle in sent["prompt"]
    if kind == "landscape":
        assert sent.get("ratio") == "4:3"
        assert "Format: 3:4 vertical portrait." not in sent["prompt"]
    else:
        assert ps.FOLLOWUP_COLORS[color]["prompt"] in sent["prompt"]
        scene = ps.PROMPT_SCENE.get(ps.PLANS[chat]["scene_opt"])
        if scene:
            assert scene not in sent["prompt"]
    assert out["slot"] == 2 and out["near"] == "shape:img2" and out.get("ids")
    assert out["kind"] == kind
    msg = out["user_message"]
    assert bool(CJK.search(msg)) is (lang == "zh"), msg
    assert "delete" not in sent and "replace" not in sent


def test_followup_without_a_set_submits_nothing(relay):
    SENT.clear()
    out = _tool("portrait_studio_followup", {"kind": "landscape"}, "zh", f"ps-{uuid.uuid4().hex}")
    assert SENT == []
    assert out["submitted"] is False and out["user_message"] == "没有可重做的一组"


def test_skill_text_routes_followup_to_the_tool():
    root = Path(__file__).resolve().parents[1]
    m = re.search(
        r"\{ id: 'portrait-studio', name: t\('skills.portraitStudio'\), instructions: '((?:\\.|[^'\\])*)'",
        (root / "src/skills.ts").read_text(encoding="utf-8"),
    )
    assert m, "portrait-studio instructions did not parse"
    instr = m.group(1).replace("\\n", "\n").replace("\\'", "'")
    assert "portrait_studio_followup" in instr
    assert 'kind "background"' in instr and 'kind "landscape"' in instr
    assert "never call generate_image yourself for this follow-up" in instr


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_followup_does_not_overwrite_original_slot_args(relay, lang):
    chat = f"ps-{uuid.uuid4().hex}"
    _run_set(lang, LOCK[lang][0], chat)
    original = dict(ps.PLANS[chat]["slot_args"][2])
    SENT.clear()
    APPROVALS.clear()
    _tool("portrait_studio_followup", {"kind": "landscape", "slot": 2}, lang, chat)
    assert ps.PLANS[chat]["slot_args"][2] == original
    SENT.clear()
    APPROVALS.clear()
    _tool("portrait_studio_redo", {"slot": 2}, lang, chat)
    action, sent = SENT[0]
    assert action == "generate_image" and sent.get("ratio") != "4:3"
    assert "Format: 4:3 landscape." not in sent["prompt"]
    assert ps.PROMPT_SCENE["A"] in sent["prompt"]
