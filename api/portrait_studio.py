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
SHOT_LINE = {
    "closeup": "Shot size: face close-up, head and shoulders, the face fills most of the frame.",
    "half": "Shot size: half body, framed from the waist up.",
    "three_quarter": "Shot size: three-quarter body, framed from mid-thigh up.",
    "full": "Shot size: full body, head to feet in frame.",
}
POSE_LINE = {
    "closeup": "Pose: face toward the camera or turned slightly, eyes to the lens, shoulders relaxed.",
    "half": "Pose: torso angled slightly, arms relaxed or lightly crossed, natural expression.",
    "three_quarter": "Pose: weight on one leg, one hand relaxed at the side or in a pocket, confident stance.",
    "full": "Pose: standing naturally, full stance visible, rebuilt for the full-body framing.",
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
