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
