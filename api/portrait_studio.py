"""portrait-studio flow (Lovart reference run review-assets 7fc60c86, skill 2o222a07opvk).

Lovart's Professional Portrait Generation Tool, same input (one person photo):
one ask card with three questions (pager "1 of 3", Skip + Next / Submit, nothing
preselected, no 推荐 marker, last row of each question is free text), then one
generation step on GPT Image 2.6 Sunburst that delivers 3 images (first option of
question 1: close-up + half body + three-quarter body).

Code enforces the card SKELETON (ids, prompts, option labels, free-text placeholders,
nothing preselected) in the ask-card language, and refuses generate_image without a
reference photo (no model call: the user is asked to upload one). The model pin
(api/auto_models.json) is not touched here.

zh text is verbatim from the Lovart card (notes.txt + card-1..3.png at 7fc60c86).
Lovart showed only zh; en is our translation for the en UI (same rule as every
other ask card: `bot_asks.card_lang`).
"""
from __future__ import annotations

SKILL = "portrait-studio"
# Lovart default (question 1, option A): 3 images.
DEFAULT_IMAGES = 3
# Images per question-1 option (A / B / C).
IMAGES_BY_SHOTS = {"A": 3, "B": 4, "C": 1}

PS_SHOTS, PS_OUTFIT, PS_SCENE = "ps_shots", "ps_outfit", "ps_scene"

CARD: dict[str, list[dict]] = {
    "zh": [
        {"id": PS_SHOTS, "prompt": "这组专业形象照想要几张、什么景别组合？",
         "options": [{"id": "A", "label": "3 张：面部特写 + 半身 + 七分身"},
                     {"id": "B", "label": "4 张：特写 + 半身 + 七分身 + 全身"},
                     {"id": "C", "label": "只要 1 张半身标准照"}],
         "placeholder": "其它张数或景别，我来写..."},
        {"id": PS_OUTFIT, "prompt": "服装方向怎么定？（人物长相、发型与身材比例都会锁定参考图不变）",
         "options": [{"id": "A", "label": "保留原有休闲造型"},
                     {"id": "B", "label": "换成商务正装"},
                     {"id": "C", "label": "简约轻正装"}],
         "placeholder": "其它服装，我来描述..."},
        {"id": PS_SCENE, "prompt": "场景与背景用哪种？",
         "options": [{"id": "A", "label": "纯色棚拍背景"},
                     {"id": "B", "label": "现代办公空间"},
                     {"id": "C", "label": "沿用参考图的建筑空间"}],
         "placeholder": "其它场景，我来描述..."},
    ],
    "en": [
        {"id": PS_SHOTS, "prompt": "How many professional portraits, and which shot sizes?",
         "options": [{"id": "A", "label": "3 photos: face close-up + half body + three-quarter body"},
                     {"id": "B", "label": "4 photos: close-up + half body + three-quarter body + full body"},
                     {"id": "C", "label": "Just 1 standard half-body photo"}],
         "placeholder": "Another count or shot size, I'll write it..."},
        {"id": PS_OUTFIT, "prompt": "Which outfit direction? (Face, hairstyle and body proportions stay locked to the reference)",
         "options": [{"id": "A", "label": "Keep the original casual look"},
                     {"id": "B", "label": "Switch to business formal"},
                     {"id": "C", "label": "Simple smart casual"}],
         "placeholder": "Another outfit, I'll describe it..."},
        {"id": PS_SCENE, "prompt": "Which scene and background?",
         "options": [{"id": "A", "label": "Solid-color studio backdrop"},
                     {"id": "B", "label": "Modern office space"},
                     {"id": "C", "label": "Keep the architectural space from the reference"}],
         "placeholder": "Another scene, I'll describe it..."},
    ],
}
PAGE_COUNT = 3

# No reference photo: ask for one, do not generate (no model call).
UPLOAD_PROMPT = {
    "zh": "请先上传一张人物照片作为参考图，我再为你生成专业形象照。",
    "en": "Please upload a photo of the person as the reference first, then I'll make the professional portraits.",
}
NEEDS_REFERENCE_KIND = "portraitNeedsReference"


def card_lang(lang: str | None = None) -> str:
    if lang in CARD:
        return lang
    from . import bot_asks
    got = bot_asks.card_lang()
    return got if got in CARD else "zh"


def _all_prompts() -> dict[str, str]:
    """question id -> id, for every locked prompt in every language."""
    return {q["prompt"]: q["id"] for qs in CARD.values() for q in qs}


def _qid(raw: object) -> str:
    if not isinstance(raw, dict):
        return ""
    qid = str(raw.get("id") or "").strip()
    if qid in (PS_SHOTS, PS_OUTFIT, PS_SCENE):
        return qid
    prompt = str(raw.get("prompt") or "").strip()
    for locked, lid in _all_prompts().items():
        head = locked.split("（")[0].split(" (")[0].rstrip("？?")
        if prompt and prompt.startswith(head):
            return lid
    return ""


def is_portrait_card(args: dict) -> bool:
    questions = (args or {}).get("questions")
    if isinstance(questions, list) and questions:
        return any(_qid(q) for q in questions)
    return bool(_qid({"id": (args or {}).get("id"), "prompt": (args or {}).get("prompt")}))


def card_questions(lang: str | None = None) -> list[dict]:
    lang = card_lang(lang)
    return [{
        "id": q["id"],
        "prompt": q["prompt"],
        "options": [dict(o) for o in q["options"]],
        "allow_other": True,
        "placeholder": q["placeholder"],
        "page": 1,
        "min_selections": 1,
        "max_selections": 1,
    } for q in CARD[lang]]


def card_spec(lang: str | None = None) -> dict:
    """The raw ask_user args for the Lovart card (before bot_asks.validate_spec)."""
    questions = card_questions(lang)
    return {
        "questions": questions,
        "page_count": PAGE_COUNT,
        "allow_skip": True,
        "allow_other": True,
        "prompt": questions[0]["prompt"],
        "options": questions[0]["options"],
    }


def normalize_card(args: dict, lang: str | None = None) -> dict:
    """Force the Lovart 7fc60c86 card skeleton: all three questions, verbatim, one language."""
    args = dict(args or {})
    if not is_portrait_card(args):
        return args
    for k in ("defaults", "id", "placeholder"):
        args.pop(k, None)
    args.update(card_spec(lang))
    return args


def images_for(shots_answer: str | None) -> int:
    """Images for a question-1 answer id; skipped / free text falls back to Lovart's default (3)."""
    return IMAGES_BY_SHOTS.get(str(shots_answer or "").strip().upper(), DEFAULT_IMAGES)


def missing_reference(args: dict) -> bool:
    return str((args or {}).get("skill") or "") == SKILL and not ((args or {}).get("refs") or (args or {}).get("base"))


def needs_reference_result(lang: str | None = None) -> dict:
    lang = card_lang(lang)
    text = UPLOAD_PROMPT[lang]
    return {
        "status": "needs_input",
        "submitted": False,
        "generation_succeeded": False,
        "charged": False,
        "kind": NEEDS_REFERENCE_KIND,
        "lang": lang,
        "user_message": text,
        "note": "No reference photo: nothing was generated. Reply to the user with user_message verbatim "
                "and wait for the upload; do not call ask_user or generate_image until a photo is attached.",
    }


# --- one generate_image per image: same person, same outfit, same scene ------------------------------
# Lovart 7fc60c86 delivered the set in one step: 「只变景别与姿态」「姿态相应重建」. We make one call per
# image, so the server writes each prompt: the same reference photo and the same person / outfit /
# background text on every call of the turn; only the shot-size line and the pose line differ.

SHOT_KEYS = ("closeup", "half", "three_quarter", "full")
SHOTS_BY_OPTION = {"A": ("closeup", "half", "three_quarter"),
                   "B": ("closeup", "half", "three_quarter", "full"),
                   "C": ("half",)}
SHOT_LINE = {  # crops from notes.txt (7fc60c86): 头肩 / 大腿上缘以上 / 小腿中部以上 / 全身
    "closeup": "Shot size: face close-up, head and shoulders.",
    "half": "Shot size: half body, framed from the upper thigh up.",
    "three_quarter": "Shot size: three-quarter body, framed from mid-calf up.",
    "full": "Shot size: full body, head to feet in frame.",
}
# Shared posing from notes.txt (7fc60c86): S 型脊柱 + 一肩微高一肩微低 + 下巴前伸微低拉紧下颌线；手部统一走
# "插兜 / 自然垂落侧手"路线，规避手指畸变，腰侧保留负空间. Every shot uses all of it; each line only says
# what that framing shows. Nothing else is added.
POSE_SHARED = ("S-curve spine, one shoulder slightly higher than the other, chin slightly forward and down "
               "to tighten the jawline, hands in pockets or hanging naturally at the sides (avoid finger "
               "distortion), negative space kept at the sides of the waist.")
POSE_LINE = {
    "closeup": "Pose: " + POSE_SHARED + " In this framing only the shoulders, chin and jawline show.",
    "half": "Pose: " + POSE_SHARED + " In this framing the spine curve, shoulders, hands and waist show.",
    "three_quarter": "Pose: " + POSE_SHARED + " In this framing the S-curve down to the legs, the hands and waist show.",
    "full": "Pose: " + POSE_SHARED + " In this framing the whole S-curve stance shows, head to feet.",
}
IDENTITY_LINE = ("Same person as the reference photo: face, facial features, hairstyle and body proportions "
                 "exactly as in the reference; do not change them.")
SHOT_HEAD, POSE_HEAD = "Shot size:", "Pose:"

# chat id -> {"guard": TurnGuard | None, "subject": str, "refs": list, "base": str, "shots": [shot keys]}
_LOCKS: dict[str, dict] = {}


def compose_prompt(subject: str, shot: str) -> str:
    """identity + shared person/outfit/background text + shot-size line + pose line."""
    return "\n".join([IDENTITY_LINE, subject.strip(), SHOT_LINE[shot], POSE_LINE[shot]])


def applies(args: dict) -> bool:
    return str((args or {}).get("skill") or "") == SKILL and not missing_reference(args)


def _turn_lock() -> dict:
    from . import paid_guard
    chat = paid_guard.resolve_guard_chat_id()
    guard = paid_guard.TURNS.get(chat)
    lock = _LOCKS.get(chat)
    if lock is None or lock["guard"] is not guard:  # a new turn starts a new set
        lock = _LOCKS[chat] = {"guard": guard, "subject": None, "refs": None, "base": None, "shots": []}
    return lock


def lock_request(args: dict) -> dict:
    """Rewrite one portrait-studio generate_image call of this turn. The first call fixes the reference
    photo and the person / outfit / background text (its prompt); later calls reuse both verbatim and
    only get their own shot-size and pose lines. One image per call."""
    args = dict(args)
    lock = _turn_lock()
    shot = str(args.pop("shot", "") or "").strip().lower().replace("-", "_").replace(" ", "_")
    if shot not in SHOT_KEYS:
        shot = next((s for s in SHOT_KEYS if s not in lock["shots"]), SHOT_KEYS[0])
    if lock["subject"] is None:
        lock["subject"] = str(args.get("prompt") or "").strip()
        lock["refs"] = list(args.get("refs") or [])
        lock["base"] = args.get("base") or None
    lock["shots"].append(shot)
    args["prompt"] = compose_prompt(lock["subject"], shot)
    args.pop("refs", None)
    args.pop("base", None)
    if lock["refs"]:
        args["refs"] = list(lock["refs"])
    if lock["base"]:
        args["base"] = lock["base"]
    args["count"] = 1
    return args


# ---------------------------------------------------------------------------------------------
# Replies around the generation and single-image redo (Lovart 7fc60c86 reply, notes.txt).
#
# Lovart's run replies three times: (1) before generating, what is locked from the reference and
# what changes, then lighting / optics / pose and 「现在开始生成三张。」; (2) after generating, a
# shot-size -> image table and the parameters; (3) a closing check asking which image drifted in
# face shape or hair, and redoes only that one. The server writes all three from the card answers
# plus what the agent read off the reference photo, and every listed parameter in the after-generation
# table is taken from the prompts (or ratio / aspect_ratio args) actually recorded for this set — never
# hard-coded when it was not sent (no shutter / ISO / film stock / negative prompt / price).
# Per-image prompts are built by lock_request above (identity, shared subject, shot line, pose line);
# apply_plan adds the card's outfit / scene and the light and lens the replies list.
# ---------------------------------------------------------------------------------------------
import re as _re

SHOTS: dict[str, dict] = {  # reply wording; the prompt's crop is SHOT_LINE above
    "closeup": {"zh": "面部特写", "zh_short": "特写", "zh_frame": "面部特写（头肩）", "en": "Face close-up",
                "en_frame": "Face close-up (head and shoulders)", "aperture": "f/2.0"},
    "half": {"zh": "半身", "zh_frame": "半身（大腿上缘以上）", "en": "Half body",
             "en_frame": "Half body (from the upper thigh up)", "aperture": "f/2.8"},
    "three_quarter": {"zh": "七分身", "zh_frame": "七分身（小腿中部以上）", "en": "Three-quarter body",
                      "en_frame": "Three-quarter body (from mid-calf up)", "aperture": "f/4.0"},
    # Lovart's run did not include a full-body shot (option B); framing and aperture are ours.
    "full": {"zh": "全身", "zh_frame": "全身（头到脚）", "en": "Full body",
             "en_frame": "Full body (head to feet)", "aperture": "f/5.6"},
}
SHOTS_BY_ANSWER = SHOTS_BY_OPTION
FOCAL = "85mm"
RATIO = "3:4"
LIGHT = {
    "zh": "Loop 环形光为主方案，大面积柔光箱从机位左侧 30° 高位切入，辅以弱发丝轮廓光",
    "en": "Loop lighting as the main setup: a large softbox high from camera-left at 30°, plus a soft hair light for rim separation",
    "prompt": "Light: loop lighting, a large softbox high from camera-left at 30 degrees, a soft hair light for rim separation.",
}
LIGHT_SHORT = {"zh": "Loop 环形光 + 柔光", "en": "Loop lighting + softbox"}
POSE = {  # the posing lock_request writes on every shot (POSE_SHARED); zh is Lovart's line verbatim
    "zh": "S 型脊柱 + 一肩微高一肩微低 + 下巴前伸微低拉紧下颌线；手部统一走\"插兜 / 自然垂落侧手\"路线，规避手指畸变，腰侧保留负空间",
    "en": "S-curve spine, one shoulder slightly higher, chin slightly forward and down to tighten the jawline; hands in pockets or hanging naturally at the sides, avoiding finger distortion, with negative space at the sides of the waist",
}
# Card answer -> how the reply echoes it. zh outfit A is Lovart's own echo (「保留原休闲造型」).
ECHO = {
    "zh": {PS_OUTFIT: {"A": "保留原休闲造型", "B": "换成商务正装", "C": "简约轻正装"},
           PS_SCENE: {"A": "纯色棚拍背景", "B": "现代办公空间", "C": "沿用参考图的建筑空间"}},
    "en": {PS_OUTFIT: {"A": "keep the original casual look", "B": "switch to business formal", "C": "simple smart casual"},
           PS_SCENE: {"A": "solid-color studio backdrop", "B": "modern office space", "C": "keep the architectural space from the reference"}},
}
PROMPT_OUTFIT = {"A": "Outfit: exactly the same outfit as in the reference photo.",
                 "B": "Outfit: business formal wear.", "C": "Outfit: simple smart casual wear."}
PROMPT_SCENE = {"A": "Background: seamless solid-color studio backdrop.", "B": "Background: modern office space.",
                "C": "Background: the architectural space from the reference photo."}
NUM_ZH = {1: "一", 2: "两", 3: "三", 4: "四"}
NUM_EN = {1: "one", 2: "two", 3: "three", 4: "four"}
_CJK = _re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")

# chat id -> the set this chat is generating / generated (in memory; a server restart forgets it).
PLANS: dict[str, dict] = {}


class PlanError(ValueError):
    pass


def _answer(raw: object) -> tuple[str, str]:
    """Card answer -> (option id A/B/C or "", free text)."""
    s = str(raw or "").strip()
    return (s.upper(), "") if s.upper() in ("A", "B", "C") else ("", s)


def shots_for(shots_answer: object) -> tuple[str, ...]:
    opt, _ = _answer(shots_answer)
    return SHOTS_BY_ANSWER.get(opt, SHOTS_BY_ANSWER["A"])


def _items(raw: object) -> list[str]:
    if isinstance(raw, str):
        raw = [p for p in _re.split(r"[、,，/;；\n]+", raw)]
    return [str(x).strip() for x in (raw or []) if str(x).strip()]


def _join(lang: str, items: list[str]) -> str:
    return ("、" if lang == "zh" else ", ").join(items)


def _short(lang: str, shot: str) -> str:
    """Shot word inside a sentence: Lovart writes 特写 / 半身 / 七分身 there."""
    return SHOTS[shot].get("zh_short", SHOTS[shot]["zh"]) if lang == "zh" else SHOTS[shot]["en"].lower()


def _shot_list(lang: str, shots: tuple[str, ...]) -> str:
    return " / ".join(_short(lang, s) for s in shots)


def _apertures(lang: str, shots: tuple[str, ...], sep: str) -> str:
    return sep.join(f"{_short(lang, s)} {SHOTS[s]['aperture']}" for s in shots)


def make_plan(args: dict, lang: str | None = None) -> dict:
    """Validate the agent's portrait_studio_plan args into a plan (raises PlanError)."""
    lang = card_lang(lang)
    refs = [str(r) for r in (args.get("refs") or []) if str(r).strip()]
    if not refs:
        raise PlanError("refs is required: the reference photo (shape id or URL)")
    shots = shots_for(args.get("shots"))
    outfit_opt, outfit_text = _answer(args.get("outfit") or "A")
    scene_opt, scene_text = _answer(args.get("scene") or "A")
    locked = _items(args.get("locked"))
    if not locked:
        raise PlanError("locked is required: what you read off the reference photo that stays (face, hair, build...)")
    outfit_desc = str(args.get("outfit_desc") or "").strip()
    ref_bg = str(args.get("reference_background") or "").strip()
    if lang == "en":
        bad = [t for t in [*locked, outfit_desc, ref_bg, outfit_text, scene_text] if t and _CJK.search(t)]
        if bad:
            raise PlanError(f"the reply language is English: resend locked / outfit_desc / reference_background in English (got {bad!r})")
    return {"lang": lang, "refs": refs, "shots": list(shots), "outfit": outfit_opt or outfit_text,
            "outfit_opt": outfit_opt, "outfit_text": outfit_text, "scene_opt": scene_opt, "scene_text": scene_text,
            "locked": locked, "outfit_desc": outfit_desc, "reference_background": ref_bg,
            "prompt": str(args.get("prompt") or "professional portrait of the same person as the reference photo").strip(),
            "subject": None, "slot_args": {}, "images": {}, "redos": []}


def _echo(plan: dict, qid: str) -> str:
    opt, text = (plan["outfit_opt"], plan["outfit_text"]) if qid == PS_OUTFIT else (plan["scene_opt"], plan["scene_text"])
    return ECHO[plan["lang"]][qid][opt] if opt else text


def _outfit_kept(plan: dict) -> bool:
    return plan["outfit_opt"] == "A"


def plan_text(plan: dict) -> str:
    """Reply (1), before generating: locked / changed, lighting, optics, pose, then 「现在开始生成」."""
    lang, shots = plan["lang"], tuple(plan["shots"])
    n = len(shots)
    outfit, scene = _echo(plan, PS_OUTFIT), _echo(plan, PS_SCENE)
    locked = list(plan["locked"])
    changed: list[str] = []
    if lang == "zh":
        if _outfit_kept(plan):
            locked.append(f"服装完整保留（{plan['outfit_desc']}）" if plan["outfit_desc"] else "服装完整保留")
        else:
            changed.append(f"服装换为{outfit}")
        if plan["scene_opt"] == "C":
            locked.append("背景沿用参考图的建筑空间")
        else:
            changed.append(f"背景由{plan['reference_background'] or '原片背景'} → {scene}")
        changed.append(f"景别拆为{_shot_list(lang, shots)}{NUM_ZH[n]}档，姿态相应重建" if n > 1
                       else f"景别为{_shot_list(lang, shots)}，姿态相应重建")
        share = (f"，{NUM_ZH[n]}张共用同一人物身份与服装，只变景别与姿态" if n > 1 else "")
        lines = [
            f"参考图已作为身份锚点分析完毕。按你的选择：{n} 张 / {outfit} / {scene}{share}。",
            f"锁定项：{_join(lang, locked)}",
            f"变更项：{'；'.join(changed)}",
            f"布光：{LIGHT['zh']}",
            f"光学：{FOCAL} 黄金人像焦段；{_apertures(lang, shots, '、')}",
            f"摆姿：{POSE['zh']}",
            f"现在开始生成{NUM_ZH[n]}张。",
        ]
    else:
        if _outfit_kept(plan):
            locked.append(f"outfit kept in full ({plan['outfit_desc']})" if plan["outfit_desc"] else "outfit kept in full")
        else:
            changed.append(f"outfit changed to {outfit}")
        if plan["scene_opt"] == "C":
            locked.append("background kept from the reference's architectural space")
        else:
            changed.append(f"background from {plan['reference_background'] or 'the original background'} → {scene}")
        changed.append(f"shot sizes split into {_shot_list(lang, shots)}, with the pose rebuilt for each" if n > 1
                       else f"shot size {_shot_list(lang, shots)}, with the pose rebuilt for it")
        share = (f"; all {NUM_EN[n]} share the same person and outfit, only the shot size and pose change" if n > 1 else "")
        lines = [
            f"The reference photo has been analyzed as the identity anchor. As you chose: {n} {'photos' if n > 1 else 'photo'} / {outfit} / {scene}{share}.",
            f"Locked: {_join(lang, locked)}",
            f"Changed: {'; '.join(changed)}",
            f"Lighting: {LIGHT['en']}",
            f"Optics: {FOCAL} portrait focal length; {_apertures(lang, shots, ', ')}",
            f"Pose: {POSE['en']}",
            f"Starting the {NUM_EN[n]} {'photos' if n > 1 else 'photo'} now." if n > 1 else "Starting the photo now.",
        ]
    return "\n".join(lines)


def image_name(lang: str, shot: str) -> str:
    return f"专业形象照-{SHOTS[shot]['zh']}" if lang == "zh" else f"Professional portrait - {SHOTS[shot]['en'].lower()}"


def _slot_sent(plan: dict, slot: int) -> dict:
    """The generate_image args recorded for this slot (prompt, ratio / aspect_ratio, …)."""
    return (plan.get("slot_args") or {}).get(slot) or {}


def _sent_prompt(plan: dict, shot: str) -> str:
    if shot not in plan["shots"]:
        return ""
    return str(_slot_sent(plan, plan["shots"].index(shot) + 1).get("prompt") or "")


def _sent_ratio(plan: dict, shot: str) -> str:
    """Aspect ratio actually sent for this image (arg, else a Format: line in the prompt)."""
    if shot not in plan["shots"]:
        return ""
    args = _slot_sent(plan, plan["shots"].index(shot) + 1)
    for key in ("ratio", "aspect_ratio"):
        got = str(args.get(key) or "").strip()
        if got:
            return got
    prompt = str(args.get("prompt") or "")
    m = _re.search(r"Format:\s*(\d+:\d+)", prompt)
    return m.group(1) if m else ""


def _done_param_lines(plan: dict) -> list[str]:
    """Optics / format lines built only from parameters present in the recorded prompts (or ratio args).

    A parameter that was not sent (85mm, a shot's aperture, lighting, 3:4) is omitted. The zh wording
    of each kept item stays the locked phrase (光学参数 / Loop 环形光 + 柔光 / 竖版 …).
    """
    lang, shots = plan["lang"], tuple(plan["shots"])
    n = len(shots)
    optics: list[str] = []
    prompts = [_sent_prompt(plan, s) for s in shots]
    if any(FOCAL in p for p in prompts):
        optics.append(FOCAL)
    if any(LIGHT["prompt"] in p or ("loop lighting" in p.lower() and "softbox" in p.lower()) for p in prompts):
        optics.append(LIGHT_SHORT[lang])
    apertures = [f"{_short(lang, s)} {SHOTS[s]['aperture']}"
                 for s in shots if SHOTS[s]["aperture"] in _sent_prompt(plan, s)]
    if apertures:
        optics.append(" · ".join(apertures))
    lines: list[str] = []
    if optics:
        lines.append(("光学参数：" + " ｜ ".join(optics)) if lang == "zh"
                     else ("Optics: " + " | ".join(optics)))
    ratios = [_sent_ratio(plan, s) for s in shots]
    shown = next((r for r in ratios if r), "")
    if shown:
        lines.append(f"画幅：{shown} 竖版 ×{n}" if lang == "zh" else f"Format: {shown} portrait ×{n}")
    return lines


def done_text(plan: dict) -> str:
    """Reply (2): shot -> image table, then only the parameters actually sent in this set's prompts."""
    lang, shots = plan["lang"], tuple(plan["shots"])
    n = len(shots)
    params = _done_param_lines(plan)
    param_block = (["⚙️ 参数" if lang == "zh" else "⚙️ Parameters", *params] if params else [])
    if lang == "zh":
        rows = [f"| {SHOTS[s]['zh_frame']} | 第 {i} 张：{image_name(lang, s)} |" for i, s in enumerate(shots, 1)]
        return "\n".join([
            f"{NUM_ZH[n]}张已完成：" if n > 1 else "这张已完成：", "| 景别 | 产物 |", "|---|---|", *rows,
            *param_block,
        ])
    rows = [f"| {SHOTS[s]['en_frame']} | Image {i}: {image_name(lang, s)} |" for i, s in enumerate(shots, 1)]
    return "\n".join([
        f"All {NUM_EN[n]} are done:" if n > 1 else "The photo is done:", "| Shot size | Image |", "|---|---|", *rows,
        *param_block,
    ])


def closing_text(plan: dict) -> str:
    """Reply (3): ask which one drifted in face shape or hair; only that one is redone."""
    lang, n = plan["lang"], len(plan["shots"])
    anchors = _join(lang, list(plan["locked"]))
    if lang == "zh":
        if n > 1:
            return (f"验收提示：{NUM_ZH[n]}张的身份锚点（{anchors}）都按参考图锁定了，但我无法逐像素核对实际一致性。"
                    f"请你过一眼这{NUM_ZH[n]}张，如果某张的脸型或发型偏离原片，告诉我具体是哪张、偏在哪里，我针对那一张重做；也可以顺手换背景色（米白 / 深灰）或补一版横版构图。")
        return (f"验收提示：这张的身份锚点（{anchors}）都按参考图锁定了，但我无法逐像素核对实际一致性。"
                "请你过一眼，如果脸型或发型偏离原片，告诉我偏在哪里，我重做这一张；也可以顺手换背景色（米白 / 深灰）或补一版横版构图。")
    if n > 1:
        return (f"Check: the identity anchors of all {NUM_EN[n]} ({anchors}) are locked to the reference, but I can't verify "
                f"the match pixel by pixel. Please look over the {NUM_EN[n]} photos; if one drifts from the original in face shape "
                "or hair, tell me which one and where, and I'll redo just that one. I can also swap the background color (ivory / dark gray) or add a landscape version.")
    return (f"Check: the identity anchors ({anchors}) are locked to the reference, but I can't verify the match pixel by pixel. "
            "Please look it over; if the face shape or hair drifts from the original, tell me where and I'll redo this one. I can also swap the background color (ivory / dark gray) or add a landscape version.")


def plan_lines(plan: dict, shot: str) -> str:
    """What this server adds to one image's prompt: the card's outfit / scene and the light, lens and format
    the replies list. Nothing in the replies is missing here."""
    outfit = PROMPT_OUTFIT.get(plan["outfit_opt"]) or f"Outfit: {plan['outfit_text']}."
    scene = PROMPT_SCENE.get(plan["scene_opt"]) or f"Background: {plan['scene_text']}."
    aperture = SHOTS[shot]["aperture"] if shot in SHOTS else SHOTS["half"]["aperture"]
    return "\n".join([outfit, scene, LIGHT["prompt"], f"Lens: {FOCAL} portrait lens at {aperture}.",
                       f"Format: {RATIO} vertical portrait."])



FOLLOWUP_LANDSCAPE_RATIO = "4:3"
FOLLOWUP_COLORS = {
    "ivory": {
        "zh": "米白", "en": "ivory",
        "keys": ("米白", "ivory", "off-white", "offwhite", "off white"),
        "prompt": "Background: an ivory off-white solid studio backdrop.",
    },
    "dark_gray": {
        "zh": "深灰", "en": "dark gray",
        "keys": ("深灰", "dark gray", "dark grey", "charcoal"),
        "prompt": "Background: a dark gray solid studio backdrop.",
    },
}
FOLLOWUP_TEXT = {
    "zh": {
        "ivory": "好的，给你换一版米白背景（基于第 {i} 张（{shot}）），原图保留，新图放在旁边。",
        "dark_gray": "好的，给你换一版深灰背景（基于第 {i} 张（{shot}）），原图保留，新图放在旁边。",
        "landscape": "好的，补一版横版构图（基于第 {i} 张（{shot}）），原图保留，新图放在旁边。",
    },
    "en": {
        "ivory": "OK, making an ivory-background version from image {i} ({shot}). The original is kept; the new one goes next to it.",
        "dark_gray": "OK, making a dark-gray-background version from image {i} ({shot}). The original is kept; the new one goes next to it.",
        "landscape": "OK, adding a landscape version from image {i} ({shot}). The original is kept; the new one goes next to it.",
    },
}


def resolve_followup(kind: object = None, color: object = None) -> tuple[str, str | None]:
    """kind is background or landscape; color (米白 / 深灰 / ivory / dark gray) is required for background."""
    k = str(kind or "").strip().lower().replace("-", "_").replace(" ", "_")
    raw = str(color or "").strip().lower()
    if k in ("landscape", "horizontal", "横版", "横版构图"):
        return "landscape", None
    if k in ("background", "backdrop", "换背景", "换背景色", "背景色"):
        k = "background"
    if k != "background":
        raise PlanError('kind must be "background" (with color 米白 / 深灰) or "landscape"')
    blob = f"{k} {raw}"
    for key, meta in FOLLOWUP_COLORS.items():
        if raw == key or any(n.lower() in blob for n in meta["keys"]):
            return "background", key
    raise PlanError("name a background color: 米白 / 深灰 (ivory / dark gray)")


def current_shot() -> str:
    """The shot lock_request just gave this call."""
    shots = _turn_lock()["shots"]
    return shots[-1] if shots else SHOT_KEYS[0]


def apply_plan(args: dict, chat_id: str) -> dict:
    """After lock_request: add the plan's lines to this image's prompt and remember the call for a redo."""
    plan = PLANS.get(chat_id)
    if not plan:
        return args
    args = dict(args)
    shot = current_shot()
    follow = args.pop("ps_followup", None)
    extra = plan_lines(plan, shot)
    if isinstance(follow, dict) and follow.get("kind") == "background" and follow.get("color") in FOLLOWUP_COLORS:
        color_line = FOLLOWUP_COLORS[follow["color"]]["prompt"]
        rebuilt = []
        replaced = False
        for line in extra.split("\n"):
            scene_line = PROMPT_SCENE.get(plan.get("scene_opt"))
            if line.startswith("Background:") or (scene_line and line == scene_line):
                rebuilt.append(color_line)
                replaced = True
            else:
                rebuilt.append(line)
        if not replaced:
            rebuilt.append(color_line)
        extra = "\n".join(rebuilt)
    if isinstance(follow, dict) and follow.get("kind") == "landscape":
        extra = extra.replace(
            f"Format: {RATIO} vertical portrait.",
            f"Format: {FOLLOWUP_LANDSCAPE_RATIO} landscape.",
        )
        args["ratio"] = FOLLOWUP_LANDSCAPE_RATIO
        args["_ratio_override"] = FOLLOWUP_LANDSCAPE_RATIO
    args["prompt"] = f"{str(args.get('prompt') or '').rstrip()}\n{extra}"
    args["count"] = 1
    # Follow-up must not overwrite the original slot snapshot; redo still uses the first set.
    if shot in plan["shots"] and not follow:
        slot = plan["shots"].index(shot) + 1
        if plan.get("subject") is None:
            plan["subject"] = _turn_lock()["subject"]
        plan["slot_args"][slot] = {k: v for k, v in args.items() if k not in ("near", "frame")}
    return args


SHOT_WORDS = (("three_quarter", ("七分身", "七分", "three-quarter", "three quarter", "3/4")),
              ("half", ("半身", "half")),
              ("closeup", ("面部特写", "特写", "close-up", "closeup", "close up")),
              ("full", ("全身", "full body", "full-body")))
_NUM_WORDS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "first": 1, "second": 2, "third": 3, "fourth": 4}


def resolve_slot(plan: dict, slot: object = None, shot: object = None) -> int:
    """Slot number from a number (1-based) or a shot-size word in zh/en (raises PlanError)."""
    n = len(plan["shots"])
    if slot not in (None, ""):
        s = str(slot).strip().lstrip("#")
        num = _NUM_WORDS.get(s.lower()) or (int(s) if s.isdigit() else 0)
        if 1 <= num <= n:
            return num
        raise PlanError(f"slot must be 1..{n}")
    words = str(shot or "").strip().lower()
    if words in SHOTS and words in plan["shots"]:
        return plan["shots"].index(words) + 1
    for key, needles in SHOT_WORDS:
        if any(w in words for w in needles):
            if key in plan["shots"]:
                return plan["shots"].index(key) + 1
            break
    raise PlanError(f"name one image: slot 1..{n} or one of {', '.join(plan['shots'])}")


REDO_TEXT = {
    "zh": "好的，只重做第 {i} 张（{shot}），其它几张不动；新图放在原图旁边，原图保留。",
    "en": "OK, redoing only image {i} ({shot}); the others stay as they are. The new one goes next to the original, which is kept.",
}
# In-memory plan is gone (server restart): reply this, generate nothing, no quote.
NO_REDO = {
    "zh": "没有可重做的一组",
    "en": "There is no set to redo.",
}


def redo_args(plan: dict, slot: int, fix: str = "") -> dict:
    """The ONE generate_image call that redoes a slot: same reference, same shot, same subject / outfit /
    scene / light / lens (lock_request + apply_plan rebuild the same prompt), next to the original."""
    subject = plan.get("subject") or plan["prompt"]
    if fix:
        subject = f"{subject.rstrip()} Correction for this redo: {fix.strip()}."
    out = {"prompt": subject, "shot": plan["shots"][slot - 1], "refs": list(plan["refs"]), "skill": SKILL, "count": 1}
    near = plan["images"].get(slot)
    if near:
        out["near"] = near
        out["near_fit"] = True  # page: right of the original when free, else below / above / left; never on top
    return out


def followup_args(plan: dict, slot: int, kind: str, color: str | None = None) -> dict:
    """ONE generate_image for a post-set follow-up: swap background color or add a landscape version.
    Same reference and shot as the named image; the original stays, the new one is placed next to it."""
    out = redo_args(plan, slot)
    out["ps_followup"] = {"kind": kind, "color": color}
    if kind == "landscape":
        out["ratio"] = FOLLOWUP_LANDSCAPE_RATIO
        out["_ratio_override"] = FOLLOWUP_LANDSCAPE_RATIO
    return out
