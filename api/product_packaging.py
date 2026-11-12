"""product-to-packaging flow (Lovart reference run review-assets e304e2fa, skill 2q60dfulue4g).

Lovart's Product to Packaging System, same input (one product photo, 「用这张产品图做一套包装。」):
one ask card with three questions (pager "1 of 3", Skip + Next / Submit, nothing preselected,
last row of each question is free text), then GPT Image 2.6 Sunburst delivers 4 images: one
anchor image (box + product together, 3:4, 1536x2048) and three extensions of that anchor
(4:3, 2048x1536).

Question 1 and 2 are written by Lovart from the uploaded product: the product noun in the
question 1 title (「这瓶滴管产品」 for the dropper bottle) and the options of questions 1 and 2.
Question 3 is the same scope list for the product. Code enforces the card SKELETON in the
ask-card language: ids, the fixed title text, question 3's options, the free-text placeholders,
question 3 multi-select, nothing preselected. Question 1's product noun and the options of
questions 1 and 2 stay as the model wrote them from the photo (the same split as the
clothing-swap card: live labels, locked skeleton).

zh text is verbatim from the Lovart card (question-card-1-*.png at e304e2fa; where notes.txt
differs from the screenshot, the screenshot wins). Lovart showed only zh; en is our translation
for the en UI (same rule as every other ask card: `bot_asks.card_lang`).

Per image: the server sets the ratio (image 1 of the turn 3:4, later images 4:3) and count 1, and
keeps the turn's first product photo in refs. The pin (api/auto_models.json, Sunburst edit with
refs / text-to-image without) and its 2k fill (canvas._pin_args) are not touched here.
"""
from __future__ import annotations

import re

SKILL = "product-to-packaging"
# Lovart default: 1 anchor + 3 extensions.
DEFAULT_IMAGES = 4
ANCHOR_RATIO, EXTENSION_RATIO = "3:4", "4:3"
RATIOS = (ANCHOR_RATIO,) + (EXTENSION_RATIO,) * (DEFAULT_IMAGES - 1)

PK_PRODUCT, PK_COLOR, PK_SCOPE = "pk_product", "pk_color", "pk_scope"
QUESTION_IDS = (PK_PRODUCT, PK_COLOR, PK_SCOPE)
PAGE_COUNT = 3
LIVE_MAX = 3  # Lovart wrote three options for questions 1 and 2

# Question 1 title: "<product noun><rest>". Lovart's noun for its dropper-bottle input is
# 「这瓶滴管产品」; the model writes the noun for the uploaded product.
PRODUCT_REST = {
    "zh": "具体是什么？品牌名/产品名怎么定（直接决定包装上的文案与必要信息版面）",
    "en": "? How should the brand name / product name be set (it decides the copy and the required-info layout on the packaging)",
}
PRODUCT_HEAD = {"zh": "", "en": "What exactly is "}
LOVART_SUBJECT = {"zh": "这瓶滴管产品", "en": "this dropper product"}

CARD: dict[str, list[dict]] = {
    "zh": [
        {"id": PK_PRODUCT, "prompt": LOVART_SUBJECT["zh"] + PRODUCT_REST["zh"], "options": None,
         "placeholder": "自己填：品类 ＋ 品牌名 ＋ 产品名（不给的话我会先提案一版）..."},
        {"id": PK_COLOR, "prompt": "包装的主色方向选哪个？", "options": None,
         "placeholder": "其它方向..."},
        {"id": PK_SCOPE, "prompt": "这套包装要交付到哪个范围？（可多选）",
         "options": [{"id": "A", "label": "核心三件：外盒 ＋ 瓶标 ＋ 内托"},
                     {"id": "B", "label": "延伸件：运输箱 ＋ 手提袋 ＋ 封条/感谢卡"},
                     {"id": "C", "label": "变体家族：同系列多支 / 多香型陈列"},
                     {"id": "D", "label": "技术件：标注尺寸的结构的构图纸 ＋ 平面刀版稿"}],
         "placeholder": "其它，请直接输入..."},
    ],
    "en": [
        {"id": PK_PRODUCT, "prompt": PRODUCT_HEAD["en"] + LOVART_SUBJECT["en"] + PRODUCT_REST["en"], "options": None,
         "placeholder": "Write your own: category + brand name + product name (if not, I'll propose one first)..."},
        {"id": PK_COLOR, "prompt": "Which main color direction for the packaging?", "options": None,
         "placeholder": "Another direction..."},
        {"id": PK_SCOPE, "prompt": "Which scope should this packaging set cover? (multi-select)",
         "options": [{"id": "A", "label": "Core three: outer box + bottle label + inner tray"},
                     {"id": "B", "label": "Extensions: shipping carton + tote bag + seal / thank-you card"},
                     {"id": "C", "label": "Variant family: several in the same line / multi-scent display"},
                     {"id": "D", "label": "Technical: dimensioned structural drawing + flat dieline"}],
         "placeholder": "Other, type it here..."},
    ],
}
_RECOMMENDED = ("（推荐）", "(推荐)", "推荐", "(recommended)", "(Recommended)")
_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
_SUBJECT_MAX = {"zh": 20, "en": 60}


def card_lang(lang: str | None = None) -> str:
    if lang in CARD:
        return lang
    from . import bot_asks
    got = bot_asks.card_lang()
    return got if got in CARD else "zh"


def _locked(lang: str, qid: str) -> dict:
    return next(q for q in CARD[lang] if q["id"] == qid)


def _qid(raw: object) -> str:
    """Which locked question a model question is: by id, else by its fixed title text (zh or en)."""
    if not isinstance(raw, dict):
        return ""
    qid = str(raw.get("id") or "").strip()
    if qid in QUESTION_IDS:
        return qid
    prompt = str(raw.get("prompt") or "").strip()
    if not prompt:
        return ""
    low = prompt.lower()
    if "品牌名/产品名怎么定" in prompt or ("what exactly is" in low and "brand name" in low):
        return PK_PRODUCT
    if prompt.startswith("包装的主色方向") or "main color direction for the packaging" in low:
        return PK_COLOR
    if prompt.startswith("这套包装要交付到哪个范围") or low.startswith("which scope should this packaging set cover"):
        return PK_SCOPE
    return ""


def is_packaging_card(args: dict) -> bool:
    questions = (args or {}).get("questions")
    if isinstance(questions, list) and questions:
        return any(_qid(q) for q in questions)
    return bool(_qid({"id": (args or {}).get("id"), "prompt": (args or {}).get("prompt")}))


def product_subject(prompt: object, lang: str) -> str:
    """The product noun the model wrote in front of question 1's fixed text, in the card language.
    Lovart's own noun (「这瓶滴管产品」 / "this dropper product") when there is none to keep."""
    text = str(prompt or "").strip()
    subject = ""
    if lang == "zh":
        cut = text.find("具体是什么")
        subject = text[:cut].strip() if cut > 0 else ""
        ok = bool(subject) and bool(_CJK.search(subject))
    else:
        m = re.match(r"(?i)\s*what exactly is\s+(.+?)\s*\?", text)
        subject = m.group(1).strip() if m else ""
        ok = bool(subject) and not _CJK.search(subject)
    if ok and len(subject) <= _SUBJECT_MAX[lang] and not any(ch in subject for ch in "？?（）()\n"):
        return subject
    return LOVART_SUBJECT[lang]


def product_prompt(subject: str, lang: str) -> str:
    return PRODUCT_HEAD[lang] + subject + PRODUCT_REST[lang]


def _strip_rec(text: object) -> str:
    out = str(text or "")
    for mark in _RECOMMENDED:
        out = out.replace(mark, "")
    return out.strip()


def live_options(raw_opts: object) -> list[dict]:
    """The model's options from the product photo: at most three, ids A/B/C, nothing recommended."""
    out: list[dict] = []
    for o in raw_opts if isinstance(raw_opts, list) else []:
        if isinstance(o, dict):
            label, desc = _strip_rec(o.get("label")), _strip_rec(o.get("description"))
        else:
            label, desc = _strip_rec(o), ""
        if not label:
            continue
        item = {"id": "ABC"[len(out)], "label": label}
        if desc:
            item["description"] = desc
        out.append(item)
        if len(out) == LIVE_MAX:
            break
    return out if len(out) >= 2 else []


def card_questions(raw_questions: list | None = None, lang: str | None = None) -> list[dict]:
    lang = card_lang(lang)
    by_id: dict[str, dict] = {}
    for q in raw_questions or []:
        qid = _qid(q)
        if qid and qid not in by_id:
            by_id[qid] = q
    out = []
    for locked in CARD[lang]:
        raw = by_id.get(locked["id"]) or {}
        if locked["options"] is not None:
            options = [dict(o) for o in locked["options"]]
            min_sel, max_sel = 1, len(options)  # 可多选
        else:
            options = live_options(raw.get("options"))
            min_sel, max_sel = (1, 1) if options else (0, 0)
        prompt = locked["prompt"]
        if locked["id"] == PK_PRODUCT:
            prompt = product_prompt(product_subject(raw.get("prompt"), lang), lang)
        out.append({
            "id": locked["id"],
            "prompt": prompt,
            "options": options,
            "allow_other": True,
            "placeholder": locked["placeholder"],
            "page": 1,
            "min_selections": min_sel,
            "max_selections": max_sel,
        })
    return out


def card_spec(raw_questions: list | None = None, lang: str | None = None) -> dict:
    """The raw ask_user args for the card (before bot_asks.validate_spec)."""
    questions = card_questions(raw_questions, lang)
    return {
        "questions": questions,
        "page_count": PAGE_COUNT,
        "allow_skip": True,
        "allow_other": True,
        "prompt": questions[0]["prompt"],
        "options": questions[0]["options"],
    }


def normalize_card(args: dict, lang: str | None = None) -> dict:
    """Force the card skeleton: all three questions in one language, fixed text, live options for 1 and 2."""
    args = dict(args or {})
    if not is_packaging_card(args):
        return args
    raw = args.get("questions")
    if not isinstance(raw, list) or not raw:
        raw = [{"id": args.get("id"), "prompt": args.get("prompt"), "options": args.get("options")}]
    for k in ("defaults", "id", "placeholder", "min_selections", "max_selections"):
        args.pop(k, None)
    args.update(card_spec(raw, lang))
    return args


# --- one generate_image per image: image 1 anchor 3:4, images 2-4 4:3 -----------------------------

# chat id -> {"guard": TurnGuard | None, "refs": list | None, "n": calls so far this turn}
_LOCKS: dict[str, dict] = {}
_SIZE_KEYS = ("width", "height", "ratio", "resolution", "edit_resolution", "size_lock", "size_candidates")


def applies(args: dict) -> bool:
    return str((args or {}).get("skill") or "") == SKILL


def ratio_for(index: int) -> str:
    """Ratio of the index-th image of a turn (0-based): the anchor is 3:4, every later image 4:3."""
    return ANCHOR_RATIO if index <= 0 else EXTENSION_RATIO


def _turn_lock() -> dict:
    from . import paid_guard
    chat = paid_guard.resolve_guard_chat_id()
    guard = paid_guard.TURNS.get(chat)
    lock = _LOCKS.get(chat)
    if lock is None or lock["guard"] is not guard:  # a new turn starts a new set
        lock = _LOCKS[chat] = {"guard": guard, "refs": None, "n": 0}
    return lock


def lock_request(args: dict) -> dict:
    """One product-to-packaging generate_image call of this turn: ratio by its place in the set
    (anchor 3:4, then 4:3), count 1, and the first call's product photo kept first in refs
    (later calls add the anchor image to it)."""
    args = dict(args)
    lock = _turn_lock()
    # A fallback_for retry re-submits the same image on another model: same place in the set.
    retry = bool(args.get("fallback_for")) and lock["n"] > 0
    if lock["refs"] is None:
        lock["refs"] = [str(r) for r in (args.get("refs") or [])]
    refs = list(lock["refs"])
    for r in args.get("refs") or []:
        if str(r) not in refs:
            refs.append(str(r))
    if refs:
        args["refs"] = refs
    else:
        args.pop("refs", None)
    for k in _SIZE_KEYS:
        args.pop(k, None)
    args["ratio"] = ratio_for(lock["n"] - 1 if retry else lock["n"])
    args["count"] = 1
    if not retry:
        lock["n"] += 1
    return args
