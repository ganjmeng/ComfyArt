"""product-to-packaging flow (Lovart reference run review-assets e304e2fa, skill 2q60dfulue4g).

Lovart's Product to Packaging System, same input (one product photo, 「用这张产品图做一套包装。」):
one ask card with three questions (pager "1 of 3", Skip + Next / Submit, nothing preselected,
last row of each question is free text), then GPT Image 2.6 Sunburst delivers 4 images: one
anchor image (box + product together, 3:4, 1536x2048) and three extensions of that anchor
(4:3, 2048x1536).

Question 1 and 2 are written by Lovart from the uploaded product: the product noun in the
question 1 title (「这瓶滴管产品」 for the dropper bottle) and the options of questions 1 and 2.
Question 3 is four fixed scopes (A core three, B extensions, C variant family, D technical) whose
wording names the parts for that product (瓶标 / 多香型 for the bottle). Code enforces the card
SKELETON in the ask-card language: ids, the fixed title text, question 3's letters / order / count,
the free-text placeholders, question 3 multi-select, nothing preselected. Question 1's product noun,
the options of questions 1 and 2 and the wording of question 3's options stay as the model wrote
them from the photo (the same split as the clothing-swap card: live labels, locked skeleton); a
missing or wrong-language question 3 label falls back to the reference wording for that letter.

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


def _right_lang(text: str, lang: str) -> bool:
    return bool(_CJK.search(text)) is (lang == "zh")


def scope_options(raw_opts: object, locked: list[dict], lang: str) -> list[dict]:
    """Question 3: the skeleton is locked (A-D, the four scopes in that order, no more, no fewer);
    each label is the model's wording for this product when it gives one in the card language,
    else the reference wording for that letter. A model option is matched by its letter id, else
    by its position; anything past D is dropped."""
    raw = [o for o in raw_opts] if isinstance(raw_opts, list) else []
    letters = [o["id"] for o in locked]
    by_letter: dict[str, object] = {}
    for o in raw:
        oid = str(o.get("id") or "").strip().upper() if isinstance(o, dict) else ""
        if oid in letters and oid not in by_letter:
            by_letter[oid] = o
    for i, o in enumerate(raw[:len(letters)]):
        oid = str(o.get("id") or "").strip().upper() if isinstance(o, dict) else ""
        if oid not in letters:
            by_letter.setdefault(letters[i], o)
    out = []
    for lk in locked:
        o = by_letter.get(lk["id"])
        label = _strip_rec(o.get("label") if isinstance(o, dict) else o) if o is not None else ""
        if not label or not _right_lang(label, lang):
            label = lk["label"]
        out.append({"id": lk["id"], "label": label})
    return out


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
            options = scope_options(raw.get("options"), locked["options"], lang)
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

# chat id -> {"guard": TurnGuard | None, "refs": list | None, "n": calls so far this turn,
#             "scopes": Q3 scopes answered on this turn's card, or None when no card answer was seen}
# Only live turns are kept: an entry whose turn ended (or was replaced by a newer turn) is dropped.
_LOCKS: dict[str, dict] = {}
_SIZE_KEYS = ("width", "height", "ratio", "resolution", "edit_resolution", "size_lock", "size_candidates")
EXTENSION_IMAGES = DEFAULT_IMAGES - 1

# What each Q3 scope shows on the extension images (A: what the reference run delivered for 核心三件).
SCOPE_ITEMS: dict[str, tuple[str, ...]] = {
    "A": ("the outer box from several angles", "the label close up", "the unboxing with the inner tray"),
    "B": ("the shipping carton", "the tote bag", "the seal and thank-you card"),
    "C": ("several products of the same line together", "a multi-scent display of the line"),
    "D": ("a structural drawing with dimensions", "the flat dieline"),
}
SCOPE_ORDER = ("A", "B", "C", "D")
DEFAULT_SCOPE = "A"  # Q3 skipped / not answered: 核心三件
SHOWS_HEAD = "This image shows:"


def applies(args: dict) -> bool:
    return str((args or {}).get("skill") or "") == SKILL


def ratio_for(index: int) -> str:
    """Ratio of the index-th image of a turn (0-based): the anchor is 3:4, every later image 4:3."""
    return ANCHOR_RATIO if index <= 0 else EXTENSION_RATIO


def _turn_lock() -> dict:
    from . import paid_guard
    chat = paid_guard.resolve_guard_chat_id()
    guard = paid_guard.TURNS.get(chat)
    for stale in [c for c, lk in _LOCKS.items() if paid_guard.TURNS.get(c) is not lk["guard"]]:
        del _LOCKS[stale]  # ended or replaced turns (this chat's previous turn included)
    lock = _LOCKS.get(chat)
    if lock is None:  # a new turn starts a new set
        lock = _LOCKS[chat] = {"guard": guard, "refs": None, "n": 0, "scopes": None, "items": None}
    return lock


def scopes_from_answers(answers: object) -> list[str]:
    """Q3 answer -> scopes in A-D order, then the free-text answer. Nothing chosen -> [A]."""
    ans = (answers or {}).get(PK_SCOPE) if isinstance(answers, dict) else None
    ans = ans if isinstance(ans, dict) else {}
    picked = {str(s).strip().upper() for s in ans.get("selected") or []}
    scopes = [s for s in SCOPE_ORDER if s in picked]
    other = str(ans.get("other_text") or "").strip()
    if other:
        scopes.append(other)
    return scopes or [DEFAULT_SCOPE]


def label_items(label: str) -> tuple[str, ...]:
    """Parts named in a question-3 label: the text after the scope name, split on ＋ / +."""
    body = re.split(r"[：:]", str(label or ""), maxsplit=1)[-1]
    parts = tuple(p.strip() for p in re.split(r"\s*[＋+]\s*", body) if p.strip())
    return parts


def _items(scope: str, items_map: dict | None = None) -> tuple[str, ...]:
    if items_map and items_map.get(scope):
        return tuple(items_map[scope])  # the wording the user saw on the card
    return SCOPE_ITEMS.get(scope, (scope,))  # a free-text scope is shown as the user wrote it


def extension_plan(scopes: list[str] | None, items_map: dict | None = None) -> list[str]:
    """What images 2-4 show, one line each. Scopes take the extension images round-robin in A-D order
    (free text last). One scope per image shows all of that scope; a scope with several images splits
    its items across them (round-robin); more scopes than images share images (scope i -> image i mod 3)."""
    scopes = list(scopes or [DEFAULT_SCOPE])
    slots: list[list[str]] = [[] for _ in range(EXTENSION_IMAGES)]
    if len(scopes) >= EXTENSION_IMAGES:
        for i, sc in enumerate(scopes):
            slots[i % EXTENSION_IMAGES].extend(_items(sc, items_map))
        return ["; ".join(s) for s in slots]
    owner = [scopes[k % len(scopes)] for k in range(EXTENSION_IMAGES)]
    for sc in scopes:
        mine = [k for k, o in enumerate(owner) if o == sc]
        items = _items(sc, items_map)
        if len(mine) == 1:
            slots[mine[0]].extend(items)
        else:
            for j, it in enumerate(items):
                slots[mine[j % len(mine)]].append(it)
            for j, k in enumerate(mine):  # a scope with fewer items than images repeats them
                if not slots[k]:
                    slots[k].append(items[j % len(items)])
    return ["; ".join(s) for s in slots]


ANCHOR_PLAN = "the anchor: the package and the product together in one key visual"


def plan_lines(scopes: list[str] | None, items_map: dict | None = None) -> tuple[str | None, list[str]]:
    """(what the anchor shows, what images 2-4 show). More than three scopes with A among them: the
    anchor is A and the other scopes fill images 2-4 (extension_plan, round-robin past three).
    Otherwise the anchor has no scope line and every scope goes to images 2-4."""
    scopes = list(scopes or [DEFAULT_SCOPE])
    if len(scopes) > EXTENSION_IMAGES and "A" in scopes:
        rest = [sc for sc in scopes if sc != "A"]
        return "; ".join(_items("A", items_map)), extension_plan(rest, items_map)
    return None, extension_plan(scopes, items_map)


def image_plan(scopes: list[str] | None, items_map: dict | None = None) -> list[str]:
    """All 4 images: the anchor, then the 3 extensions."""
    anchor, ext = plan_lines(scopes, items_map)
    return [ANCHOR_PLAN + (f"; it shows {anchor}" if anchor else "")] + ext


def is_card_spec(spec: dict) -> bool:
    return any(isinstance(q, dict) and q.get("id") == PK_SCOPE for q in (spec or {}).get("questions") or [])


def record_card_answer(spec: dict, answers: object) -> list[str] | None:
    """Called by ask_user after this card was answered (Skip included): remember the Q3 scopes for
    this turn's extension images. Returns the image plan for the agent; None for other cards."""
    if not is_card_spec(spec):
        return None
    lock = _turn_lock()
    lock["scopes"] = scopes_from_answers(answers)
    q3 = next(q for q in spec["questions"] if isinstance(q, dict) and q.get("id") == PK_SCOPE)
    lock["items"] = {str(o.get("id")): label_items(o.get("label")) for o in q3.get("options") or [] if isinstance(o, dict)}
    return image_plan(lock["scopes"], lock["items"])


def _with_shows(prompt: str, shows: str) -> str:
    lines = [ln for ln in str(prompt or "").split("\n") if not ln.startswith(SHOWS_HEAD)]
    return "\n".join(lines + [f"{SHOWS_HEAD} {shows}."]).strip()


def lock_request(args: dict) -> dict:
    """One product-to-packaging generate_image call of this turn: ratio by its place in the set
    (anchor 3:4, then 4:3), count 1, and the first call's product photo kept first in refs
    (later calls add the anchor image to it). When this turn's card was answered, images 2-4 get a
    "This image shows:" line from the Q3 scopes (extension_plan)."""
    args = dict(args)
    lock = _turn_lock()
    # A fallback_for retry re-submits the same image on another model: same place in the set.
    retry = bool(args.get("fallback_for")) and lock["n"] > 0
    index = lock["n"] - 1 if retry else lock["n"]
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
    args["ratio"] = ratio_for(index)
    args["count"] = 1
    if lock["scopes"] is not None and 0 <= index <= EXTENSION_IMAGES:
        anchor, ext = plan_lines(lock["scopes"], lock["items"])
        shows = anchor if index == 0 else ext[index - 1]
        if shows:
            args["prompt"] = _with_shows(args.get("prompt") or "", shows)
    if not retry:
        lock["n"] += 1
    return args
