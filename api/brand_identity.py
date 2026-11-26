"""brand-identity-director default path (#1019).

Two entries share one skill id:

- No template selected (plaza「品牌识别」): three locked ask cards and eight images.
  Moodboard 2048×1152, three logo boards 2048×2048, then spec / cup / bag at
  1536×2048 and a storefront at 2048×1152.
- A Logo System industry template selected: the #979 3+1 contract. This module
  does not change that path.

Cards lock the skeleton (count, order, multi/single, free-text last row, no
preselect). Card 1 and 2 fall back to the measured zh wording when the model
does not send a usable option list. Card 3 keeps the model's direction titles
when it sent three, marks exactly one recommended, and does not preselect it.

Images cannot be submitted before the card for that stage has been answered.
Logo calls receive the moodboard shape as a reference. Deliverables receive the
chosen logo and the moodboard. Qwen Image 2.0 submits the exact size string so
a tier-only model is not charged and then size-rejected. PNG alpha is flattened
onto white before the file is saved.
"""
from __future__ import annotations

import contextvars
import hashlib
import io
import json
import re
import time
import uuid

SKILL = "brand-identity-director"
# Confirmation lifetime of a brand quote card. It starts when the card is created.
# Pressing Start does not move it. 700s past creation is past this deadline.
BRAND_CONFIRM_TTL_S = 600.0
BRAND_CURRENCY = "USD"
EXPIRED_TEXT = {
    "zh": "报价已过期，请重新取价",
    "en": "This quote has expired. Request a new price.",
}
FIXED_SIZE_NOTE = {
    "zh": "尺寸固定，不可修改。",
    "en": "Size is fixed and cannot be edited.",
}
_GRANT_FILE = "brand-confirm.json"
_EXEC_SKIP = {
    "brand_slot", "width", "height", "count", "prompt", "base", "refs", "mask",
    "model", "edit_model", "skill", "stage", "preset", "_brand_block",
}
QWEN_T2I = "wavespeed-ai/qwen-image-2.0/text-to-image"
QWEN_EDIT = "wavespeed-ai/qwen-image-2.0/edit"

# Industry templates keep the #979 plan. An empty preset is the default path.
TEMPLATE_IDS = ("geometric", "handmade", "tech", "beauty", "foodbev", "pet")

# slot, stage, width, height, ratio, row, col
SLOTS: tuple[dict, ...] = (
    {"id": "moodboard", "stage": 1, "width": 2048, "height": 1152, "ratio": "16:9", "row": 1, "col": 0},
    {"id": "logo_a", "stage": 2, "width": 2048, "height": 2048, "ratio": "1:1", "row": 2, "col": 0},
    {"id": "logo_b", "stage": 2, "width": 2048, "height": 2048, "ratio": "1:1", "row": 2, "col": 1},
    {"id": "logo_c", "stage": 2, "width": 2048, "height": 2048, "ratio": "1:1", "row": 2, "col": 2},
    {"id": "spec", "stage": 3, "width": 1536, "height": 2048, "ratio": "3:4", "row": 3, "col": 0},
    {"id": "cup", "stage": 3, "width": 1536, "height": 2048, "ratio": "3:4", "row": 3, "col": 1},
    {"id": "bag", "stage": 3, "width": 1536, "height": 2048, "ratio": "3:4", "row": 3, "col": 2},
    {"id": "storefront", "stage": 3, "width": 2048, "height": 1152, "ratio": "16:9", "row": 3, "col": 3},
)
_BY_ID = {s["id"]: s for s in SLOTS}
LOGO_IDS = ("logo_a", "logo_b", "logo_c")
FINAL_IDS = ("spec", "cup", "bag", "storefront")

# Canvas rows. The bottom row is the widest; the moodboard and the three logos
# are centered in that width. GAP matches src/jobs.ts.
GAP = 40


def _row_width(row: int) -> int:
    cols = [s for s in SLOTS if s["row"] == row]
    return sum(int(s["width"]) for s in cols) + GAP * (len(cols) - 1)


def _row_y(row: int) -> int:
    y = 0
    for r in range(1, row):
        h = max(int(s["height"]) for s in SLOTS if s["row"] == r)
        y += h + GAP
    return y


def slot_origin(slot_id: str) -> tuple[int, int]:
    """Page offset of a default-path image inside the chat frame, centered per row."""
    slot = _BY_ID[slot_id]
    widest = max(_row_width(r) for r in (1, 2, 3))
    x = (widest - _row_width(slot["row"])) // 2
    for s in SLOTS:
        if s["row"] != slot["row"]:
            continue
        if s["col"] >= slot["col"]:
            break
        x += int(s["width"]) + GAP
    return x, _row_y(slot["row"])


def is_template(preset_id: object) -> bool:
    return str(preset_id or "").strip() in TEMPLATE_IDS


def stage_of(slot_id: object) -> int:
    slot = _BY_ID.get(str(slot_id or ""))
    return int(slot["stage"]) if slot else 0


def same_stage(slot_ids: list) -> bool:
    stages = {stage_of(s) for s in slot_ids if stage_of(s)}
    return len(stages) == 1


# --- measured card skeleton (zh verbatim from #1019 §2.1; en is our translation) ---

_CARD1 = "bi_card1"
_Q_DELIVERY, _Q_COLOR, _Q_MARK, _Q_SOURCE = "bi_delivery", "bi_color", "bi_mark", "bi_source"
_CARD2 = "bi_moodboard"
_CARD3 = "bi_direction"

_CARD1_ZH = [
    {
        "id": _Q_DELIVERY,
        "prompt": "这次「基础品牌视觉系统」要交付哪些物料？",
        "options": [
            {"id": "A", "label": "核心套装：Logo + 规范卡 + 外带杯/杯套 + 纸袋 + 门头"},
            {"id": "B", "label": "菜单板 / 价格表"},
            {"id": "C", "label": "社媒模板（小红书 / Instagram 封面与内页）"},
            {"id": "D", "label": "名片 / 会员卡"},
        ],
        "placeholder": "其它物料，我来说…",
        "max_selections": 4,
        "page": 1,
    },
    {
        "id": _Q_COLOR,
        "prompt": "色彩方向选哪一种？",
        "options": [
            {"id": "A", "label": "暖土色为主 + 低饱和靛蓝点缀"},
            {"id": "B", "label": "纯暖土色系：陶土橘 / 焦糖 / 米白 / 深焙棕"},
            {"id": "C", "label": "鼠尾草绿 + 原木 + 米白，自然感更强"},
        ],
        "placeholder": "我有指定色值或品牌色…",
        "page": 2,
    },
    {
        "id": _Q_MARK,
        "prompt": "Logo 的构成方向偏好？",
        "options": [
            {"id": "A", "label": "图形符号 + 中英文字标"},
            {"id": "B", "label": "纯文字标，靠字体气质成立"},
            {"id": "C", "label": "圆形徽章 / 印章式，手作感更重"},
        ],
        "placeholder": "三个方向都出，我看完再挑…",
        "page": 3,
    },
    {
        "id": _Q_SOURCE,
        "prompt": "门店与产品素材怎么处理？",
        "options": [
            {"id": "A", "label": "没有实拍图，用 AI 生成示意场景与容器"},
            {"id": "B", "label": "我有实拍图，稍后上传给你"},
            {"id": "C", "label": "这次只要平面物料，不含场景实拍"},
        ],
        "placeholder": "其它，请直接输入…",
        "page": 4,
    },
]
_CARD1_EN = [
    {
        "id": _Q_DELIVERY,
        "prompt": "Which pieces should this basic brand system deliver?",
        "options": [
            {"id": "A", "label": "Core set: logo + guideline card + takeaway cup and sleeve + paper bag + storefront"},
            {"id": "B", "label": "Menu board / price list"},
            {"id": "C", "label": "Social templates (RedNote / Instagram cover and inner pages)"},
            {"id": "D", "label": "Business card / membership card"},
        ],
        "placeholder": "Other pieces, I'll say…",
        "max_selections": 4,
        "page": 1,
    },
    {
        "id": _Q_COLOR,
        "prompt": "Which color direction?",
        "options": [
            {"id": "A", "label": "Warm earth as the base, with a low-saturation indigo accent"},
            {"id": "B", "label": "Warm earth only: terracotta / caramel / rice white / dark roast"},
            {"id": "C", "label": "Sage green + wood + rice white, more natural"},
        ],
        "placeholder": "I have hex values or a brand color…",
        "page": 2,
    },
    {
        "id": _Q_MARK,
        "prompt": "Which logo construction do you prefer?",
        "options": [
            {"id": "A", "label": "A symbol plus a Chinese and English wordmark"},
            {"id": "B", "label": "Wordmark only: the brand name, carried by the type"},
            {"id": "C", "label": "A round badge / seal, with more of a handmade feel"},
        ],
        "placeholder": "Show all three directions, I'll choose after…",
        "page": 3,
    },
    {
        "id": _Q_SOURCE,
        "prompt": "How should the store and product visuals be handled?",
        "options": [
            {"id": "A", "label": "No photos; generate the scene and containers"},
            {"id": "B", "label": "I have photos and will upload them"},
            {"id": "C", "label": "Flat artwork only, no scene photography"},
        ],
        "placeholder": "Other, type it here…",
        "page": 4,
    },
]
_CARD2_ZH = {
    "id": _CARD2,
    "prompt": "这张情绪板可以作为后续全套物料的视觉基准吗？",
    "options": [
        {"id": "A", "label": "就这版，通过"},
        {"id": "B", "label": "重出情绪板，加强靛蓝点缀"},
        {"id": "C", "label": "告诉我要改哪几格"},
    ],
    "placeholder": "其它，请直接输入…",
}
_CARD2_EN = {
    "id": _CARD2,
    "prompt": "Can this moodboard be the visual baseline for the rest of the system?",
    "options": [
        {"id": "A", "label": "Yes, approve this one"},
        {"id": "B", "label": "Regenerate the moodboard and strengthen the indigo accent"},
        {"id": "C", "label": "Tell me which cells to change"},
    ],
    "placeholder": "Other, type it here…",
}
_CARD3_ZH = {
    "id": _CARD3,
    "prompt": "选定哪个 Logo 方向作为最终标识（logo_primary）？",
    "options": [
        {"id": "A", "label": "单线鸟停枝", "description": "一根连续的线，画出停在枝上的鸟"},
        {"id": "B", "label": "木牌加圆印", "description": "实心木牌，旁边一枚圆形印章"},
        {"id": "C", "label": "杯形负空间", "description": "杯子外形，停着的鸟是杯中的负空间"},
    ],
}
_CARD3_EN = {
    "id": _CARD3,
    "prompt": "Which logo direction should be the final mark (logo_primary)?",
    "options": [
        {"id": "A", "label": "Single-line bird on a branch", "description": "One continuous line draws a bird perched on a branch"},
        {"id": "B", "label": "Wooden signboard and round seal", "description": "A solid wooden signboard plus a separate round seal"},
        {"id": "C", "label": "Cup-shaped negative space", "description": "A cup-shaped badge; a perched bird is the negative space inside the cup"},
    ],
}

_HEADS = {
    _Q_DELIVERY: ("要交付哪些物料", "which pieces should this basic brand"),
    _Q_COLOR: ("色彩方向选哪一种", "which color direction"),
    _Q_MARK: ("构成方向偏好", "which logo construction"),
    _Q_SOURCE: ("素材怎么处理", "how should the store and product"),
    _CARD2: ("视觉基准", "visual baseline"),
    _CARD3: ("logo_primary", "final mark", "Logo 方向", "logo direction"),
}


def card_lang(lang: str | None = None) -> str:
    if lang in ("zh", "en"):
        return lang
    from . import bot_asks
    got = bot_asks.card_lang()
    return got if got in ("zh", "en") else "zh"


def _cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _locked_options(fallback: list[dict]) -> list[dict]:
    """Cards 1 and 2 always show the measured labels. A matching count must not keep the model's copy."""
    rows = []
    for opt in fallback:
        row = {"id": str(opt.get("id") or ""), "label": str(opt.get("label") or "")}
        if opt.get("description"):
            row["description"] = str(opt["description"])
        rows.append(row)
    return rows


def _live_options(raw: object, fallback: list[dict], lang: str) -> list[dict]:
    """Card 3 still reads the model's option count. Its titles are replaced from the lock afterwards."""
    got: list[dict] = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            desc = str(item.get("description") or "").strip()
        else:
            label, desc = str(item or "").strip(), ""
        if not label:
            continue
        if _cjk(label) != (lang == "zh"):
            continue
        row = {"id": "ABCDEFGHIJKL"[len(got)], "label": label}
        if desc and (_cjk(desc) == (lang == "zh")):
            row["description"] = desc
        got.append(row)
        if len(got) == len(fallback):
            break
    if len(got) != len(fallback):
        return [dict(o) for o in fallback]
    return got


def _question(locked: dict, lang: str, raw: dict | None, *, multi: bool = False) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    options = _locked_options(locked["options"])
    # Never carry a recommended flag from the model onto card 1 or 2.
    for opt in options:
        opt.pop("recommended", None)
    q = {
        "id": locked["id"],
        "prompt": locked["prompt"],
        "options": options,
        "allow_other": True,
        "placeholder": locked["placeholder"],
        "page": int(locked.get("page") or 1),
        "min_selections": 1,
        "max_selections": int(locked.get("max_selections") or 1),
    }
    if multi:
        q["max_selections"] = int(locked.get("max_selections") or len(locked["options"]))
    return q


def _card1(lang: str, raw_questions: list) -> list[dict]:
    locked = _CARD1_ZH if lang == "zh" else _CARD1_EN
    by_id = {}
    for q in raw_questions:
        if isinstance(q, dict):
            by_id[str(q.get("id") or "")] = q
    out = []
    for spec in locked:
        out.append(_question(spec, lang, by_id.get(spec["id"]), multi=spec["id"] == _Q_DELIVERY))
    return out


def _card2(lang: str, raw: dict | None) -> dict:
    locked = _CARD2_ZH if lang == "zh" else _CARD2_EN
    return _question(locked, lang, raw)


def _card3(lang: str, raw: dict | None) -> dict:
    locked = _CARD3_ZH if lang == "zh" else _CARD3_EN
    options = _live_options((raw or {}).get("options"), locked["options"], lang)
    raw_opts = (raw or {}).get("options") if isinstance((raw or {}).get("options"), list) else []
    wanted = ""
    for opt in raw_opts:
        if isinstance(opt, dict) and opt.get("recommended"):
            wanted = str(opt.get("id") or "").strip().upper()[:1]
            break
    if wanted not in {o["id"] for o in options}:
        wanted = "A"
    # Titles follow the image lock. A model title such as 手刻印章 cannot disagree with the sheet.
    locked_by_id = {opt["id"]: opt for opt in locked["options"]}
    for opt in options:
        src = locked_by_id.get(opt["id"])
        if not src:
            continue
        opt["label"] = src["label"]
        if src.get("description"):
            opt["description"] = src["description"]
    for opt in options:
        if opt["id"] == wanted:
            opt["recommended"] = True
    for opt, slot in zip(options, LOGO_IDS):
        url = _logo_option_url(raw_opts, opt["id"], slot)
        if not url:
            _refuse_card3_without_thumbs(lang)
        opt["image_url"] = url
    _progress()["card3_thumb_miss"] = 0
    return {
        "id": _CARD3,
        "prompt": locked["prompt"],
        "options": options,
        "allow_other": False,
        "page": 1,
        "min_selections": 1,
        "max_selections": 1,
        "preselect": False,
    }


def _match_id(raw: object) -> str:
    if not isinstance(raw, dict):
        return ""
    qid = str(raw.get("id") or "").strip()
    if qid in {_Q_DELIVERY, _Q_COLOR, _Q_MARK, _Q_SOURCE, _CARD2, _CARD3}:
        return qid
    prompt = str(raw.get("prompt") or "")
    low = prompt.lower()
    for ident, heads in _HEADS.items():
        if any(h.lower() in low or h in prompt for h in heads):
            return ident
    return ""


def which_card(args: dict) -> str:
    """'card1' / 'card2' / 'card3' / ''."""
    questions = args.get("questions")
    rows = questions if isinstance(questions, list) and questions else [
        {"id": args.get("id"), "prompt": args.get("prompt"), "options": args.get("options")}
    ]
    ids = [_match_id(q) for q in rows]
    if _CARD3 in ids or any(i == _CARD3 for i in ids):
        return "card3"
    if _CARD2 in ids:
        return "card2"
    if any(i in {_Q_DELIVERY, _Q_COLOR, _Q_MARK, _Q_SOURCE} for i in ids):
        return "card1"
    return ""


def normalize_card(args: dict, lang: str | None = None) -> dict:
    """Force a brand card skeleton. Unrelated asks are returned unchanged."""
    args = dict(args or {})
    kind = which_card(args)
    if not kind:
        return args
    lang = card_lang(lang)
    raw_q = args.get("questions") if isinstance(args.get("questions"), list) else []
    if kind == "card1":
        questions = _card1(lang, raw_q)
        page_count = 4
    elif kind == "card2":
        found = next((q for q in raw_q if _match_id(q) == _CARD2), raw_q[0] if raw_q else {})
        questions = [_card2(lang, found if isinstance(found, dict) else {})]
        page_count = 1
    else:
        found = next((q for q in raw_q if _match_id(q) == _CARD3), raw_q[0] if raw_q else {})
        questions = [_card3(lang, found if isinstance(found, dict) else {})]
        page_count = 1
    for key in ("defaults", "id", "placeholder", "min_selections", "max_selections", "recommended"):
        args.pop(key, None)
    args["questions"] = questions
    args["allow_skip"] = True
    args["page_count"] = page_count
    args["allow_other"] = bool(questions[0].get("allow_other"))
    args["prompt"] = questions[0]["prompt"]
    args["options"] = questions[0]["options"]
    return args


def unselect_recommended(spec: dict) -> dict:
    """Card 3 wears the recommended badge and is not preselected."""
    if not isinstance(spec, dict):
        return spec
    for q in spec.get("questions") or []:
        if isinstance(q, dict) and q.get("id") == _CARD3:
            q.pop("defaults", None)
    if (spec.get("questions") or [{}])[0].get("id") == _CARD3:
        spec.pop("defaults", None)
    return spec


# --- run progress (one chat, across turns) -------------------------------------------------------

_PROGRESS: dict[str, dict] = {}
_HELD_WRAPUP: dict[str, str] = {}
# Per-turn wrap-up flags. Cleared by end_turn so a later turn cannot replay them.
_TURN: dict[str, dict] = {}
BRAND_PLANNED_IMAGES = 8


def _clock() -> float:
    return time.time()


_BRAND_CHAT: contextvars.ContextVar[str] = contextvars.ContextVar("comfyart_brand_chat", default="")


def drop_memory_for_tests() -> None:
    """Forget the in-memory stage rows so the next read comes back from disk."""
    _PROGRESS.clear()


def brand_progress_scope(chat_id: str):
    """Bind brand progress to this chat. Reset the returned token when the work ends."""
    return _BRAND_CHAT.set(str(chat_id or ""))


def reset_brand_progress_scope(token) -> None:
    _BRAND_CHAT.reset(token)


def reset_for_tests() -> None:
    _PROGRESS.clear()
    _HELD_WRAPUP.clear()
    _TURN.clear()
    try:
        _write_grant_file({"chats": {}})
    except BrandGrantPersistError:
        pass


def _chat() -> str:
    scoped = str(_BRAND_CHAT.get() or "")
    if scoped:
        return scoped
    try:
        from . import paid_guard
        chat = str(paid_guard.resolve_guard_chat_id() or "")
    except Exception:
        chat = ""
    return chat or "_brand"


def _progress() -> dict:
    chat = _chat()
    row = _PROGRESS.get(chat)
    if row is None:
        row = _PROGRESS[chat] = {
            "phase": "need_card1",
            "mood_inflight": False,
            "redo": False,
            "chosen": "logo_a",
            "shapes": {},
            "urls": {},
            "holders": {},
            "inflight": [],
            "failed": [],
            "spent": 0.0,
            "batch": 0,
        }
        _hydrate_grants(chat, row)
    return row


def _logo_urls() -> dict:
    return dict(_progress().get("urls") or {})


_LOGO_ALIASES = {
    "logo_a": "logo_a", "a": "logo_a",
    "logo_b": "logo_b", "b": "logo_b",
    "logo_c": "logo_c", "c": "logo_c",
}


def _logo_alias(value: object) -> str:
    return _LOGO_ALIASES.get(str(value or "").strip().lower(), "")


def _slot_of_wait_row(row: dict, holders: dict) -> str:
    """Holder id first. A logo row can also name its slot when the holder id does not match."""
    holder = str((holders or {}).get(str(row.get("id") or "")) or "")
    if holder:
        return holder
    for key in ("brand_slot", "slot", "id"):
        slot = _logo_alias(row.get(key))
        if slot:
            return slot
    return ""


def _logo_option_url(raw_opts: list, option_id: str, slot: str) -> str:
    url = str((_logo_urls().get(slot) or "")).strip()
    if url:
        return url
    wanted = {option_id.lower(), slot.lower()}
    for raw_opt in raw_opts:
        if not isinstance(raw_opt, dict):
            continue
        rid = str(raw_opt.get("id") or "").strip().lower()
        if rid not in wanted and not (len(rid) == 1 and rid == option_id.lower()):
            continue
        found = str(raw_opt.get("image_url") or "").strip()
        if found:
            return found
    return ""


_CARD3_WAIT = {
    "zh": "还不能出方向卡：三个 Logo 的结果图还没到齐。请先等待 logo_a、logo_b、logo_c 的 wait_generation 结果，再调用 ask_user 出 bi_direction。不要出只有文字的方向卡。",
    "en": "Card 3 cannot be shown yet: the three logo results are not all in. Wait for wait_generation of logo_a, logo_b, and logo_c, then call ask_user for bi_direction. Do not send a text-only direction card.",
}


def _refuse_card3_without_thumbs(lang: str) -> None:
    """One miss tells the model to wait. The second miss is non-retryable so it cannot loop."""
    progress = _progress()
    misses = int(progress.get("card3_thumb_miss") or 0) + 1
    progress["card3_thumb_miss"] = misses
    text = _CARD3_WAIT["zh" if lang == "zh" else "en"]
    if misses >= 2:
        text = "[non-retryable] " + text
    raise ValueError(text)


_HEX_TOKEN = re.compile(r"#[0-9A-Fa-f]{3,8}")


def _strip_hex(text: str) -> str:
    cleaned = _HEX_TOKEN.sub("", str(text or ""))
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" ，,;；、")


def color_hue_hint() -> str:
    """The saved color answer as words. Never a hex value and never a ratio."""
    color = _progress().get("color") if isinstance(_progress().get("color"), dict) else {}
    selected = color.get("selected") or []
    key = str(selected[0]).upper()[:1] if selected else ""
    other = _strip_hex(str(color.get("other") or ""))
    label = ""
    for row in _CARD1_ZH:
        if row["id"] != _Q_COLOR:
            continue
        for opt in row["options"]:
            if str(opt.get("id") or "") == key:
                label = _strip_hex(str(opt.get("label") or ""))
    return other or label


def _spec_lock() -> str:
    hint = color_hue_hint()
    hint_line = ""
    if hint:
        hint_line = (
            "Soft hue-family hint from the color answer, never a hex value and never a printed swatch: "
            f"{hint}. It does not add a color. "
        )
    return (
        "The spec card is exactly 7 panels. Each heading appears once, in this order: "
        "标识 / LOGO (the approved mark; 「最小使用尺寸」 is an annotation inside this panel, not a separate panel), "
        "色彩 / COLOR (a proportional color strip sampled from the moodboard 色彩 cell; "
        "each swatch has a Chinese color name, a role, and a percentage; "
        "any accent is at most about 5%; "
        "the names, roles, and ratios are sampled from that cell; "
        "do not hardcode a palette and do not invent hex values), "
        "变体 / VARIANTS (the approved variants, each with a short label), "
        "字体 / TYPE (this panel carries its full bilingual heading 字体 / TYPE, not clipped to 字; "
        "hierarchy and annotation density follow the gold; "
        "the Chinese brand name and the English brand name are copied character for character; "
        "Do not drop a character and do not substitute a character), "
        "版式 / LAYOUT (one filled layout diagram), "
        "使用禁忌 / MISUSE (uses only the brand colors, draws a red X, and keeps short captions of the same kind as the gold), "
        "影像与材质 / IMAGE (keeps short captions of the same kind as the gold). "
        "No heading is repeated. Do not add an eighth panel. Do not clip a heading. "
        "Where the gold shows an English counterpart, write the heading as Chinese and English side by side. "
        "Annotation density follows the gold. "
        "Allowed on-card text includes the bilingual headings, a Chinese color name plus a role plus a percentage on each swatch, "
        "the in-panel 「最小使用尺寸」 annotation, short captions on 使用禁忌 / MISUSE and 影像与材质 / IMAGE of the same kind as the gold, "
        "short labels on the approved variants, and the real Chinese brand name and the real English brand name from the brief, copied character for character. "
        "Do not write invented body copy. Do not invent English. "
        "Any text that does appear anywhere must be spelled correctly (one garbled character is not acceptable). "
        "Do not print an English instruction label."
        + (f" {hint_line.strip()}" if hint_line else "")
        + " Paper ground, not black."
    )


def begin_batch() -> None:
    """A new assistant step assigns slots from what has actually been submitted."""
    _progress()["batch"] = 0


def _selected(answers: object, qid: str) -> tuple[list[str], str]:
    if not isinstance(answers, dict):
        return [], ""
    row = answers.get(qid)
    if not isinstance(row, dict):
        return [], ""
    selected = [str(s).strip().upper()[:1] for s in (row.get("selected") or []) if str(s).strip()]
    return selected, str(row.get("other_text") or "").strip()


def _skipped(answers: object, ids: tuple[str, ...]) -> bool:
    if not isinstance(answers, dict):
        return True
    for qid in ids:
        selected, other = _selected(answers, qid)
        if selected or other:
            return False
    return True


def record_card_answer(spec: dict, answers: object) -> str | None:
    """Advance the phase when one of our cards is answered. None for other cards."""
    kind = which_card(spec or {})
    if not kind:
        return None
    progress = _progress()
    if kind == "card1":
        selected, other = _selected(answers, _Q_COLOR)
        progress["color"] = {"selected": selected[:1], "other": other}
        if progress["phase"] in {"need_card1", "done"}:
            progress["phase"] = "moodboard"
            progress["mood_inflight"] = False
            progress["redo"] = False
        return "moodboard"
    if kind == "card2":
        selected, other = _selected(answers, _CARD2)
        approve = (_skipped(answers, (_CARD2,)) or "A" in selected) and not other
        if approve:
            progress["phase"] = "logos"
            progress["redo"] = False
            return "logos"
        progress["phase"] = "moodboard"
        progress["mood_inflight"] = False
        progress["redo"] = True
        # Drop the previous board so the replacement can be stored.
        progress["shapes"].pop("moodboard", None)
        progress["urls"].pop("moodboard", None)
        return "moodboard"
    selected, _other = _selected(answers, _CARD3)
    pick = selected[0] if selected else "A"
    progress["chosen"] = {"A": "logo_a", "B": "logo_b", "C": "logo_c"}.get(pick, "logo_a")
    progress["phase"] = "finals"
    return "finals"


def _next_slot(progress: dict) -> dict | None:
    phase = progress["phase"]
    if phase == "moodboard":
        # One board per step. A submitted board stays in inflight until wait_generation.
        if int(progress.get("batch") or 0) > 0 or "moodboard" in (progress.get("inflight") or []):
            return None
        return _BY_ID["moodboard"]
    if phase == "logos":
        done = sum(1 for slot in LOGO_IDS if slot in progress["shapes"] or slot in progress["inflight"])
        index = done + int(progress.get("batch") or 0)
        if index >= len(LOGO_IDS):
            return None
        return _BY_ID[LOGO_IDS[index]]
    if phase == "finals":
        done = sum(1 for slot in FINAL_IDS if slot in progress["shapes"] or slot in progress["inflight"])
        index = done + int(progress.get("batch") or 0)
        if index >= len(FINAL_IDS):
            return None
        return _BY_ID[FINAL_IDS[index]]
    return None


def _block(phase: str) -> dict:
    zh = {
        "need_card1": "还没提交问询卡 1，不能出图，也没有扣费。请先 ask_user 问询卡 1。",
        "need_card2": "情绪板还没确认，不能出 Logo，也没有扣费。请先 ask_user 确认情绪板。",
        "need_card3": "还没选定 Logo 方向，不能出成品，也没有扣费。请先 ask_user 选择方向。",
        "done": "默认路径的 8 张已经出完，这次没有提交，也没有扣费。",
    }.get(phase, "这一步还不能出图，没有扣费。")
    en = {
        "need_card1": "Card 1 has not been answered; nothing was submitted or charged. Call ask_user for card 1 first.",
        "need_card2": "The moodboard is not confirmed; no logo was submitted or charged. Call ask_user to confirm it first.",
        "need_card3": "No logo direction is chosen; no deliverable was submitted or charged. Call ask_user to pick one first.",
        "done": "The default path already delivered 8 images. This call was not submitted and nothing was charged.",
    }.get(phase, "This image cannot be submitted yet. Nothing was charged.")
    return {
        "status": "failed",
        "submitted": False,
        "generation_succeeded": False,
        "error": f"{zh} / {en}",
        "user_message": f"{zh} / {en}",
    }


def _refs_for(slot: dict, progress: dict) -> list[str]:
    shapes = progress.get("shapes") or {}
    mood = str(shapes.get("moodboard") or "")
    if slot["stage"] == 2 and mood:
        return [mood]
    if slot["stage"] == 3:
        chosen = str(shapes.get(progress.get("chosen") or "logo_a") or "")
        refs = [r for r in (chosen, mood) if r]
        return refs
    return []


# Internal labels that an image model has printed onto a board. They must never
# remain in the prompt that is submitted.
_INTERNAL_MARK = re.compile(
    r"(?i)(?:\b(?:STRUCTURE|GUIDELINE|LAYOUT|APPLICATION)\s+LOCK(?:\s*[ABC])?\s*:?|\bOutput lock:)"
)


def scrub_internal_marks(text: str) -> str:
    """Remove internal lock labels from an image prompt."""
    cleaned = _INTERNAL_MARK.sub("", str(text or ""))
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    return cleaned.strip()


# Appended to the image prompt. The three logos must not share one bird-on-a-branch drawing.
_SLOT_LOCK = {
    "moodboard": (
        "The board is exactly 3 equal columns and 3 equal rows, nine cells in row order from the top left. "
        "Each cell has exactly one Chinese label and is filled with an image that matches that label. "
        "One label per cell. Never put several labels in one cell, and never join labels with a separator "
        "such as ｜, |, /, 、, or +. No empty cell, no blank cell, no merged cell. "
        "Every cell's content is full-bleed, filling its cell edge to edge: photos and layouts, "
        "no inner margin and no half-empty cell. The label is a small caption in the cell's bottom-left corner. "
        "The nine labels, in this order, are: 质感, 色彩, 符号, 字标, 版式, 材料, 外带杯, 门头, 数字. "
        "No English sentences, no lorem, no tiny Latin captions, no cell numbers such as 9. "
        "Exactly three cells in each row. Warm paper ground, not a black field."
    ),
    "logo_a": (
        "The mark is one open single-line drawing of a bird perched on a branch. "
        "No filled plaque, no circular seal, no cup silhouette. "
        "The sheet has exactly four labelled zones, in this order: 主组合, 符号构造, 横版, 小尺寸. "
        "Each of the four zone labels appears exactly once. "
        "符号构造 shows the actual symbol construction. No empty placeholder box and no X box. "
        "小尺寸 includes the symbol, not the wordmark alone, as three small applications side by side: "
        "a rounded-square icon, a circular stamp, and a solid square badge. "
        "横版 appears once. Do not draw a second landscape treatment. "
        "In each zone the Chinese brand name and the English brand name appear together exactly once. "
        "No other small text. No bottom caption. Do not print an English instruction label."
    ),
    "logo_b": (
        "The mark is two separate parts, a solid filled wood plaque and a circular seal. "
        "Not a line-drawing bird standing on a branch. "
        "The sheet has exactly four labelled zones, in this order: 主组合, 符号构造, 横版, 小尺寸. "
        "Each of the four zone labels appears exactly once. "
        "符号构造 shows the actual symbol construction. No empty placeholder box and no X box. "
        "小尺寸 includes the symbol, not the wordmark alone, as the seal, a horizontal plaque, a circle, and a square. "
        "横版 appears once. Do not draw a second landscape treatment. "
        "In each zone the Chinese brand name and the English brand name appear together exactly once. "
        "No other small text. No garbled English captions. No bottom caption. Do not print an English instruction label."
    ),
    "logo_c": (
        "The badge is a cup-shaped container, not a picture of a handled cup. "
        "The cup silhouette has no handle. "
        "The badge uses the accent color or the dark color from the confirmed color direction, "
        "and the bird is reversed out inside it as negative space. "
        "A perched bird is the negative space inside the cup, "
        "not a bird drawn as a positive shape and not a bird standing on a branch outside it. "
        "Not a circular seal, not a wood plaque. "
        "The sheet has exactly four labelled zones, in this order: 主组合, 符号构造, 横版, 小尺寸. "
        "Each of the four zone labels appears exactly once. "
        "横版 appears once. Do not draw a second landscape treatment. "
        "符号构造 shows the actual symbol construction. No empty placeholder box and no X box. "
        "小尺寸 includes the symbol, not the wordmark alone, as an icon, a cup-lid sticker, and an emboss. "
        "The wordmark appears exactly once per zone. "
        "No other small text. No garbled English captions. No bottom caption. Do not print an English instruction label."
    ),
    "cup": (
        "The takeaway cup must wear a cup sleeve (杯套). A bare cup with no sleeve is wrong. "
        "Show two vessels: a paper takeaway cup wearing the sleeve, and a clear iced cup with the mark on the cup. "
        "A flat sleeve lies in front. The sleeve carries one thin stripe in the accent color of the confirmed color direction. "
        "One plain white cup alone is wrong. "
        "The print shows the Chinese brand name and the English brand name, both readable. "
        "Do not print the English name alone. "
        "No extra English captions. A real cup on a light ground, not a black void."
    ),
    "bag": (
        "Paper bag. Show two paper bags: a large bag standing and a smaller bag lying in front of it. "
        "A thin vertical stripe in the accent color of the confirmed color direction runs down the side of the standing bag. "
        "The Chinese name and the English name are both readable. "
        "Not English only. No garbled captions. Real paper, not a black void."
    ),
    "storefront": (
        "The full shopfront, front view, the facade filling the frame edge to edge. "
        "The fascia eave is the accent color or the dark color from the confirmed color direction, not bare wood. "
        "The fascia carries the Chinese brand name and the English brand name once. "
        "An A-frame standing sign stands on the pavement in front of the entrance. "
        "Not a hanging-sign close-up. No garbled small type."
    ),
}


# Generation preface for the spec image. This is not the locked brief. The brief stays
# in _spec_lock(), default_hint(), and the skill instructions, and is still appended last.
_SPEC_PREFACE = (
    "Draw seven separate panels, one heading each, in this order: "
    "标识 / LOGO, 色彩 / COLOR, 变体 / VARIANTS, 字体 / TYPE, 版式 / LAYOUT, "
    "使用禁忌 / MISUSE, 影像与材质 / IMAGE. "
    "字体 / TYPE is its own panel with a type hierarchy. "
    "版式 / LAYOUT is a different panel with one filled layout diagram. "
    "Do not merge them and do not write a heading such as 版式 / TYPE. "
    "色彩 / COLOR is flat color swatches sampled from the moodboard, not a wood-grain texture. "
    "Each swatch prints one correctly spelled simplified-Chinese color name, a role, and a percentage, "
    "and the percentages sum to 100%. "
    "标识 / LOGO contains a drawn 「最小使用尺寸」 diagram of the mark at its smallest size, "
    "inside that panel, not only the quoted words. "
    "Warm paper ground with a soft vignette. Not a black background and not a sparse empty card."
)


def _mood_color_line() -> str:
    """The confirmed card-1 color label, so the moodboard is not painted from the model's own wording."""
    hint = color_hue_hint()
    if not hint:
        return ""
    return (
        "Confirmed color direction, keep it in the 色彩 cell and do not replace it: " + hint + ". "
        "Paint that cell as flat swatches from this direction, including its accent, "
        "and print this direction as the cell annotation. Do not swap the accent for a different hue."
    )


def _logo_c_accent_line() -> str:
    """Runtime only. The badge follows the confirmed answer; the shared lock names no palette."""
    hint = color_hue_hint()
    if not hint:
        return ""
    return (
        "The confirmed color direction for this badge's accent is: " + hint + ". "
        "Fill the badge with that accent or the dark color in this direction. "
        "Do not invent a hue that is outside this direction."
    )


def _apply_color_line(part: str) -> str:
    """Runtime only. Name the confirmed direction for one application. No palette is hardcoded."""
    hint = color_hue_hint()
    if not hint:
        return ""
    return "The confirmed color direction for the " + part + " is: " + hint + "."


def _spec_assembly_line() -> str:
    """Runtime only. The locked brief stays byte-identical and still ends the lock."""
    hint = color_hue_hint()
    named = ""
    if hint:
        named = " Sample the swatches from the confirmed color direction: " + hint + "."
    return (
        "Do not copy the reference moodboard into a 3 by 3 grid. "
        "Spell each heading exactly once. Do not write COLR, TISUS, or INMAGE. "
        "使用禁忌 / MISUSE is an independent panel, not merged into another panel. "
        "The hue hint is not a swatch and it does not remove the swatches. "
        "色彩 / COLOR is flat swatches, each with one simplified-Chinese color name, a role, and a percentage, "
        "and the percentages sum to 100%, including the accent from the confirmed color direction. "
        "标识 / LOGO draws a minimum-size diagram of the mark with measurement lines, "
        "not only the words 「最小使用尺寸」."
        + named
    )


def _without_exact_line(prompt: str, line: str) -> str:
    """Drop one runtime line so a second fill puts it back in the same place."""
    if not line or line not in prompt:
        return prompt
    prompt = prompt.replace(line, "")
    prompt = re.sub(r"[ \t]{2,}", " ", prompt)
    prompt = re.sub(r"\n{2,}", "\n", prompt)
    return prompt.strip()


def _bind_lock(prompt: str, lock: str, preface: str = "") -> str:
    """Put the slot lock last. A caller who already pasted it, then added other words, does not bury it."""
    body = str(prompt or "")
    for piece in (lock, preface):
        if piece and piece in body:
            body = body.replace(piece, " ")
    body = re.sub(r"[ \t]{2,}", " ", body).strip()
    parts = [part for part in (preface.strip(), body, lock.strip()) if part]
    return "\n".join(parts)


def fill_default(args: dict) -> dict:
    """Size, slot and refs for one default-path generate. Idempotent when brand_slot is already set.

    A missing card leaves `_brand_block` and does not submit. Template presets never reach here.
    """
    args = dict(args or {})
    progress = _progress()
    slot_id = str(args.get("brand_slot") or "")
    slot = _BY_ID.get(slot_id)
    if slot is None:
        slot = _next_slot(progress)
        if slot is None:
            args["_brand_block"] = _block(str(progress["phase"]))
            return args
        if slot["stage"] == 2 and progress["phase"] != "logos":
            args["_brand_block"] = _block("need_card2")
            return args
        if slot["stage"] == 3 and progress["phase"] != "finals":
            args["_brand_block"] = _block("need_card3")
            return args
        if progress["phase"] == "need_card1":
            args["_brand_block"] = _block("need_card1")
            return args
        args["brand_slot"] = slot["id"]
        progress["batch"] = int(progress.get("batch") or 0) + 1
    args["skill"] = SKILL
    args["width"] = int(slot["width"])
    args["height"] = int(slot["height"])
    args["ratio"] = slot["ratio"]
    args["count"] = 1
    args["size_lock"] = True
    args["brand_opaque"] = True
    args.pop("preset", None)
    args.pop("stage", None)
    lock = _spec_lock() if str(slot["id"]) == "spec" else _SLOT_LOCK.get(str(slot["id"]))
    preface = _SPEC_PREFACE if str(slot["id"]) == "spec" else ""
    raw_prompt = str(args.get("prompt") or "")
    if str(slot["id"]) == "moodboard":
        color_line = _mood_color_line()
    elif str(slot["id"]) == "logo_c":
        color_line = _logo_c_accent_line()
    elif str(slot["id"]) == "cup":
        color_line = _apply_color_line("sleeve stripe")
    elif str(slot["id"]) == "bag":
        color_line = _apply_color_line("side stripe")
    elif str(slot["id"]) == "storefront":
        color_line = _apply_color_line("fascia eave")
    elif str(slot["id"]) == "spec":
        color_line = _spec_assembly_line()
    else:
        color_line = ""
    # The confirmed color is a runtime line after the lock. Strip it before rebinding
    # so a second fill, the one the grant freezes and the one dispatch submits, match.
    raw_prompt = _without_exact_line(raw_prompt, color_line)
    prompt = _bind_lock(raw_prompt, str(lock or ""), preface)
    if color_line:
        prompt = (prompt.rstrip() + "\n" + color_line).strip()
    args["prompt"] = scrub_internal_marks(prompt)
    refs = _refs_for(slot, progress)
    if refs:
        # The moodboard / chosen logo lead. A caller-supplied ref stays behind them.
        extra = [str(r) for r in (args.get("refs") or []) if str(r) not in refs]
        args["refs"] = refs + extra
    missing = missing_base_message(str(slot["id"]))
    if missing:
        args["_brand_block"] = {"error": missing, "user_message": missing}
        args.pop("model", None)
        args.pop("edit_model", None)
        return args
    return pin_exact_model(args)


def pin_exact_model(args: dict) -> dict:
    """Qwen Image 2.0 submits size=W*H, including the hidden edit size field."""
    args = dict(args)
    if args.get("refs") or args.get("base"):
        args.pop("model", None)
        args["edit_model"] = QWEN_EDIT
        args["size_candidates"] = [QWEN_EDIT]
    else:
        args.pop("edit_model", None)
        args["model"] = QWEN_T2I
        args["auto_model"] = True
        args["size_candidates"] = [QWEN_T2I]
    args["size_lock"] = True
    args["brand_opaque"] = True
    return args


def record_submitted(args: dict, result: object) -> None:
    if not isinstance(result, dict) or result.get("cancelled") or result.get("submitted") is False:
        return
    slot_id = str((args or {}).get("brand_slot") or "")
    if slot_id not in _BY_ID:
        return
    ids = result.get("ids") if isinstance(result.get("ids"), list) else []
    progress = _progress()
    if ids:
        progress["holders"][str(ids[0])] = slot_id
    if slot_id not in progress["inflight"]:
        progress["inflight"].append(slot_id)
    progress["batch"] = max(0, int(progress.get("batch") or 0) - 1)


def record_wait(result: object) -> None:
    if not isinstance(result, dict):
        return
    progress = _progress()
    for row in result.get("results") or []:
        if not isinstance(row, dict):
            continue
        slot_id = _slot_of_wait_row(row, progress.get("holders") or {})
        if not slot_id:
            continue
        shapes = row.get("shapes") or []
        urls = row.get("urls") or []
        placed = ""
        if isinstance(shapes, list):
            for shape in shapes:
                if str(shape or "").strip():
                    placed = str(shape).strip()
                    break
        url = ""
        if isinstance(urls, list):
            for item in urls:
                if str(item or "").strip():
                    url = str(item).strip()
                    break
        failed = progress.setdefault("failed", [])
        unknown = progress.setdefault("unknown", [])
        unplaced = progress.setdefault("unplaced", {})
        status = str(row.get("status") or "").lower()
        open_wait = {"running", "pending", "queued"}
        done_wait = {"done", "complete", "completed", "success"}

        def _clear_open(slot: str) -> None:
            if slot in progress["inflight"]:
                progress["inflight"].remove(slot)

        # A shape is on the canvas. A URL with no shape was generated and not placed.
        # Only running / pending / queued stay in flight.
        if placed:
            progress["shapes"][slot_id] = placed
            if slot_id in failed:
                failed.remove(slot_id)
            if slot_id in unknown:
                unknown.remove(slot_id)
            unplaced.pop(slot_id, None)
            if url:
                progress["urls"][slot_id] = url
            _clear_open(slot_id)
        elif status in open_wait:
            if slot_id not in progress["inflight"]:
                progress["inflight"].append(slot_id)
        else:
            _clear_open(slot_id)
            if slot_id in progress["shapes"]:
                pass
            elif status in done_wait and url:
                if slot_id in failed:
                    failed.remove(slot_id)
                if slot_id in unknown:
                    unknown.remove(slot_id)
                unplaced[slot_id] = url
                progress["urls"][slot_id] = url
            elif status in {"unknown", "unknown id"} or (
                status and status not in done_wait | {"error", "failed", "cancelled", "canceled", "declined"}
                and not row.get("error")
            ):
                unplaced.pop(slot_id, None)
                if slot_id not in failed and slot_id not in unknown:
                    unknown.append(slot_id)
            elif slot_id not in failed:
                # Terminal and no usable output: explicit error, or done with no URL.
                unplaced.pop(slot_id, None)
                failed.append(slot_id)
                if slot_id in unknown:
                    unknown.remove(slot_id)
        _advance(progress)


def _advance(progress: dict) -> None:
    if "moodboard" in progress["shapes"] and progress["phase"] == "moodboard":
        progress["phase"] = "need_card2"
        progress["mood_inflight"] = False
        progress["redo"] = False
    if all(slot in progress["shapes"] for slot in LOGO_IDS) and progress["phase"] == "logos":
        progress["phase"] = "need_card3"
    if all(slot in progress["shapes"] for slot in FINAL_IDS) and progress["phase"] == "finals":
        progress["phase"] = "done"


def finals_placed() -> bool:
    shapes = _progress().get("shapes") or {}
    return all(slot in shapes for slot in FINAL_IDS)


def should_hold_wrapup() -> bool:
    """The delivery list stays hidden until the four deliverables are on the canvas."""
    return str(_progress().get("phase") or "") == "finals" and not finals_placed()


def hold_wrapup(text: str) -> None:
    text = str(text or "").strip()
    if text and should_hold_wrapup():
        _HELD_WRAPUP[_chat()] = text


def _turn() -> dict:
    chat = _chat()
    row = _TURN.get(chat)
    if row is None:
        row = _TURN[chat] = {"released": False, "extra": []}
    return row


def _explicit_failed_finals(progress: dict) -> list[str]:
    """Finals with an explicit terminal failure. A running or pending wait is not one."""
    shapes = progress.get("shapes") or {}
    failed = progress.get("failed") or []
    return [slot for slot in FINAL_IDS if slot in failed and slot not in shapes]


def _inflight_finals(progress: dict) -> list[str]:
    return [slot for slot in FINAL_IDS if slot in (progress.get("inflight") or [])]


def _unknown_finals(progress: dict) -> list[str]:
    """Terminal waits we cannot classify as placed or failed. Not still generating."""
    shapes = progress.get("shapes") or {}
    failed = progress.get("failed") or []
    unknown = progress.get("unknown") or []
    return [slot for slot in FINAL_IDS if slot in unknown and slot not in shapes and slot not in failed]


def _unplaced_finals(progress: dict) -> list[tuple[str, str]]:
    """Generated URLs that never became a canvas shape. Not a failure and not in flight."""
    shapes = progress.get("shapes") or {}
    unplaced = progress.get("unplaced") or {}
    rows = []
    for slot in FINAL_IDS:
        url = str(unplaced.get(slot) or "").strip()
        if url and slot not in shapes:
            rows.append((slot, url))
    return rows


def _final_names(slot_ids: list[str], lang: str) -> list[str]:
    names = _QUOTE_NAME["en" if lang == "en" else "zh"]
    return [names.get(slot) or slot for slot in slot_ids]


def failure_wrapup(lang: str = "zh") -> str:
    """Name finals that failed terminally. Does not claim they were delivered."""
    missing = _explicit_failed_finals(_progress())
    if not missing:
        return ""
    listed = _final_names(missing, lang)
    if lang == "en":
        return "Did not place: " + ", ".join(listed) + "."
    return "没有落图：" + "、".join(listed) + "。"


# A heading opens a block. A link is either an http(s) URL or a file path such
# as /download/qimu.zip. The words that introduce that link stay with it.
_HEADING_RE = re.compile(r"^(?:本次交付清单|delivery list)\b", re.IGNORECASE)
_LINK_RE = re.compile(r"https?://\S+|/(?:[\w.-]+/)+[\w.-]+")
_LABEL_TAIL_RE = re.compile(
    r"(?:下载地址|下载链接|下载|链接|文件地址|download(?:\s+link)?|link|url)\s*[:：]?\s*$",
    re.IGNORECASE,
)
_QUESTION_RE = re.compile(r"[?？]|是什么意思|what\s+(?:does|is)\b", re.IGNORECASE)


def _opening(line: str) -> str:
    s = line.strip()
    s = re.sub(r"^(?:#{1,6}\s+|>\s+)", "", s)
    s = re.sub(r"^(\*\*|__)+", "", s)
    s = re.sub(r"(\*\*|__)+$", "", s)
    return s.strip()


def _is_heading_line(line: str) -> bool:
    """The line opens with the delivery-list heading. A quoted mention does not."""
    return bool(_HEADING_RE.match(_opening(line)))


def _has_link(line: str) -> bool:
    return bool(_LINK_RE.search(line))


def _split_heading_line(line: str) -> tuple[str, str]:
    """Split a heading line into the claim and the same-line download clause.

    The link and the words that introduce it stay visible. The claim is the
    closing block.
    """
    match = _LINK_RE.search(line)
    if not match:
        return line.strip(), ""
    left, right = line[: match.start()], line[match.start() :]
    label = _LABEL_TAIL_RE.search(left)
    if label:
        right = left[label.start() :] + right
        left = left[: label.start()]
    left = re.sub(r"[，,。；;：:\s]+$", "", left).strip()
    return left, right.strip()


def _block_continues(line: str) -> bool:
    """Following lines stay in the block until an independent answer."""
    if not line.strip() or _is_heading_line(line) or _has_link(line):
        return False
    opened = _opening(line)
    if _QUESTION_RE.search(opened):
        return False
    folded = opened.casefold()
    # The heading phrase quoted mid-line is a mention, not another list item.
    if ("本次交付清单" in opened or "delivery list" in folded) and not _HEADING_RE.match(opened):
        return False
    return True


def unknown_wrapup(lang: str = "zh") -> str:
    """Name finals whose wait ended without a placed image or an explicit error."""
    names = _final_names(_unknown_finals(_progress()), lang)
    if not names:
        return ""
    if lang == "en":
        return "Unknown result: " + ", ".join(names) + "."
    return "结果未知：" + "、".join(names) + "。"


def unplaced_wrapup(lang: str = "zh") -> str:
    """Name finals that have a file and are not on the canvas. Keeps the URL."""
    rows = _unplaced_finals(_progress())
    if not rows:
        return ""
    names = _QUOTE_NAME["en" if lang == "en" else "zh"]
    parts = [f"{names.get(slot) or slot} {url}" for slot, url in rows]
    if lang == "en":
        return "Generated, not on the canvas: " + "; ".join(parts) + "."
    return "已生成未落图：" + "、".join(parts) + "。"


def _settled_note(lang: str) -> str:
    return "\n".join(part for part in (
        failure_wrapup(lang), unplaced_wrapup(lang), unknown_wrapup(lang)) if part)


def still_generating_wrapup(lang: str = "zh") -> str:
    """Honest note for finals that are still in flight. Does not call them failures."""
    names = _final_names(_inflight_finals(_progress()), lang)
    if not names:
        return ""
    if lang == "en":
        return "Still generating: " + ", ".join(names) + "."
    return "仍在生成：" + "、".join(names) + "。"


def split_closing(text: str) -> tuple[str, str]:
    """Split one delivery-list block from the prose that must stay visible.

    The block starts at a line that opens with the heading (本次交付清单 /
    Delivery list). It keeps the following lines — list items, the boundary
    note, the next step — until a blank line, a line that carries a link, or a
    question / quoted mention. A download path on the heading line itself stays
    with the prose. A sentence that only quotes the heading is not a block.
    """
    kept: list[str] = []
    closing: list[str] = []
    lines = str(text or "").splitlines()
    i = 0
    in_block = False
    while i < len(lines):
        line = lines[i]
        if in_block:
            if _block_continues(line):
                closing.append(line)
                i += 1
                continue
            in_block = False
            if not line.strip():
                i += 1
                continue
        if _is_heading_line(line):
            claim, extra = _split_heading_line(line)
            if claim:
                closing.append(claim)
            if extra:
                kept.append(extra)
            in_block = True
            i += 1
            continue
        kept.append(line)
        i += 1
    prose = "\n".join(part for part in kept if part.strip()).strip()
    block = "\n".join(part for part in closing if part.strip()).strip()
    return prose, block


def accept_assistant_text(text: str) -> str:
    """Show progress, links, and other prose now. Hold only the delivery-list lines until the finals settle."""
    text = str(text or "").strip()
    if not text:
        return ""
    prose, closing = split_closing(text)
    if not closing:
        return text
    chat = _chat()
    if _turn().get("released") or _HELD_WRAPUP.get(chat):
        return prose
    if should_hold_wrapup():
        _HELD_WRAPUP[chat] = closing
        return prose
    # The finals are already placed, so this list is shown now. A later list in
    # the same turn keeps its prose and links and drops the list lines.
    _turn()["released"] = True
    return text


def release_wrapup(lang: str = "zh") -> str:
    """After a tool step: the held closing once every final has a shape, or a failure note once every attempt has settled."""
    progress = _progress()
    phase = str(progress.get("phase") or "")
    inflight = _inflight_finals(progress)
    missing = tuple(_explicit_failed_finals(progress))
    unknowns = tuple(_unknown_finals(progress))
    unplaced = tuple(_unplaced_finals(progress))
    if phase in {"finals", "done"} and (missing or unknowns or unplaced) and not inflight:
        signature = ("settled", missing, unknowns, unplaced)
        reported = progress.get("wrapup_reported")
        if reported == signature or (not unknowns and not unplaced and reported == missing):
            return ""
        _HELD_WRAPUP.pop(_chat(), None)
        _turn()["extra"] = []
        _turn()["released"] = True
        progress["wrapup_reported"] = signature
        return _settled_note(lang)
    if not finals_placed():
        return ""
    text = _HELD_WRAPUP.pop(_chat(), "")
    extras = [part for part in (_turn().get("extra") or []) if part]
    _turn()["extra"] = []
    parts = [part for part in [text, *extras] if part]
    if parts:
        _turn()["released"] = True
        progress["wrapup_reported"] = ()
    return "\n".join(parts)


def end_turn(lang: str = "zh") -> str:
    """Flush a terminal closing and drop deferred text so the next turn cannot replay it."""
    progress = _progress()
    phase = str(progress.get("phase") or "")
    text = ""
    if not _turn().get("released"):
        missing = tuple(_explicit_failed_finals(progress))
        unknowns = tuple(_unknown_finals(progress))
        unplaced = tuple(_unplaced_finals(progress))
        reported = progress.get("wrapup_reported")
        inflight = tuple(_inflight_finals(progress))
        settled = ("settled", missing, unknowns, unplaced)
        # Running stays open. A done row with a URL is generated-not-placed.
        # A done row with no URL is a missed place. Neither is still generating.
        if phase == "finals" and inflight:
            signature = ("running", missing, unknowns, unplaced, inflight)
            if signature != reported:
                parts = [failure_wrapup(lang), unplaced_wrapup(lang), unknown_wrapup(lang),
                         still_generating_wrapup(lang)]
                text = "\n".join(part for part in parts if part)
                progress["wrapup_reported"] = signature
            _HELD_WRAPUP.pop(_chat(), None)
        elif phase == "finals" and (missing or unknowns or unplaced) and reported not in {settled, missing}:
            text = _settled_note(lang)
            progress["wrapup_reported"] = settled
        elif not inflight:
            text = release_wrapup(lang)
    _HELD_WRAPUP.pop(_chat(), None)
    _TURN.pop(_chat(), None)
    return text


def ensure_run_budget(tracker, skill: str, preset: str) -> None:
    """The default path is 3 asks + 8 images + a quote per stage + the closing turn.

    The image cap is planned count + 2. Leaving planned at the page default of 4
    stops the run at 6 images, before the four deliverables finish.
    """
    if str(skill or "") != SKILL or is_template(preset):
        return
    current = int(getattr(tracker, "planned_images", 0) or 0)
    tracker.planned_images = max(current, BRAND_PLANNED_IMAGES)


_QUOTE_NAME = {
    "zh": {
        "moodboard": "情绪板",
        "logo_a": "Logo 方向 A",
        "logo_b": "Logo 方向 B",
        "logo_c": "Logo 方向 C",
        "spec": "规范卡",
        "cup": "外带杯与杯套",
        "bag": "纸袋",
        "storefront": "门店门头",
    },
    "en": {
        "moodboard": "Moodboard",
        "logo_a": "Logo direction A",
        "logo_b": "Logo direction B",
        "logo_c": "Logo direction C",
        "spec": "Guideline card",
        "cup": "Takeaway cup",
        "bag": "Paper bag",
        "storefront": "Storefront",
    },
}


def quote_line(slot_id: str, lang: str) -> str:
    """Quote-card row: material, exact pixels, ratio. No model name."""
    slot = _BY_ID.get(str(slot_id or ""))
    if not slot:
        return ""
    names = _QUOTE_NAME["en" if lang == "en" else "zh"]
    name = names.get(slot["id"]) or slot["id"]
    return f"{name} {slot['width']}×{slot['height']} {slot['ratio']}"


def _remaining_slot_ids(phase: str) -> list[str]:
    if phase == "moodboard":
        ids = ("moodboard",)
    elif phase == "logos":
        ids = LOGO_IDS
    elif phase == "finals":
        ids = FINAL_IDS
    else:
        return []
    progress = _progress()
    inflight = progress.get("inflight") or []
    shapes = progress.get("shapes") or {}
    return [slot for slot in ids if slot not in shapes and slot not in inflight]


def annotate_quote_steps(steps: list, paid_args: list | None = None, *,
                         current_skill: str = "", user_text: str | None = None,
                         current_preset: str = "") -> list:
    """Stamp brand slots onto a quote the model wrote itself.

    A quote_plan call often omits brand_slot. Without it the stage is not
    recognized, a sub-$0.50 stage can skip the card, and every row reads as
    the model name. Slots already on the generate calls win; otherwise the
    current stage supplies them. Other skills are left untouched.

    A quote with no submit this turn keeps that stamping. A turn that does
    submit stamps a slot only when the call will go through fill_default.
    The skill id and preset resolution are the same ones apply_generate uses.
    """
    phase = str(_progress().get("phase") or "")
    paid = [a for a in (paid_args or []) if isinstance(a, dict)]
    known = [str(a.get("brand_slot")) for a in paid if str(a.get("brand_slot") or "") in _BY_ID]
    brand_paid = any(a.get("skill") == SKILL or a.get("brand_slot") for a in paid)
    if phase not in {"moodboard", "logos", "finals"} and not known and not brand_paid:
        return list(steps or [])
    queue = known or _remaining_slot_ids(phase)
    cursor = 0
    out = []
    for step in steps or []:
        if not isinstance(step, dict):
            out.append(step)
            continue
        step = dict(step)
        if step.get("tool") != "generate_image":
            out.append(step)
            continue
        args = dict(step.get("arguments") or {})
        skill = str(args.get("skill") or "")
        if skill and skill != SKILL and not args.get("brand_slot"):
            out.append(step)
            continue
        # fill_default runs only when there is no preset. A preset call (with
        # or without skill) must keep the quote fingerprint empty so each
        # paid call above the confirm line asks on its own.
        if str(args.get("preset") or "").strip():
            out.append(step)
            continue
        if paid:
            from ..bot.skill_output import fills_brand_default
            # This turn submits. Do not invent a slot the submit will not have.
            if not fills_brand_default(args, current_skill, user_text, current_preset):
                out.append(step)
                continue
        if not args.get("brand_slot") and cursor < len(queue):
            slot = _BY_ID[queue[cursor]]
            cursor += 1
            args["brand_slot"] = slot["id"]
            args.setdefault("width", slot["width"])
            args.setdefault("height", slot["height"])
            args.setdefault("ratio", slot["ratio"])
            args["skill"] = SKILL
        step["arguments"] = args
        out.append(step)
    return out


def steps_are_brand_stage(steps: list) -> bool:
    slots = []
    for step in steps or []:
        if not isinstance(step, dict) or step.get("tool") != "generate_image":
            continue
        args = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
        if args.get("brand_slot"):
            slots.append(args["brand_slot"])
    return bool(slots) and same_stage(slots)


def other_stage_credits(stage: int) -> int:
    """Credits already confirmed on the other stages. This stage is excluded so a re-quote replaces it.

    Each stage is ceiled on its own, which is the amount that stage's card showed and the account
    was charged. Summing those integers matches the confirmed total. Ceil of the raw dollar sum
    can drop a stage that was already charged.
    """
    from ..bot.run_budget import ui_credits
    total = 0
    for key, rec in (_progress().get("quoted_stages") or {}).items():
        try:
            key_i = int(key)
        except (TypeError, ValueError):
            continue
        if int(stage or 0) and key_i == int(stage):
            continue
        total += ui_credits(_stage_amount(rec))
    return total


def _sum_stage_usd(progress: dict) -> float:
    total = 0.0
    for rec in (progress.get("quoted_stages") or {}).values():
        total += _stage_amount(rec)
    return round(total, 4)


def cumulative_line(total_usd: float, lang: str) -> str:
    from ..bot.run_budget import ui_credits
    stage = ui_credits(float(total_usd or 0))
    cum = other_stage_credits(0) + stage
    if lang == "zh":
        return f"本阶段 {stage} 积分，累计 {cum} 积分（含本阶段）。"
    return f"This stage is {stage} credits. Cumulative {cum} credits, including this stage."


def quoted_stage(steps: list) -> int:
    """The single brand stage in a quote, or 0 when the steps are not one stage."""
    stages = []
    for step in steps or []:
        if not isinstance(step, dict) or step.get("tool") != "generate_image":
            continue
        args = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
        stage = stage_of(args.get("brand_slot"))
        if stage:
            stages.append(stage)
    unique = set(stages)
    return stages[0] if len(unique) == 1 else 0


def stage_already_quoted(steps: list) -> bool:
    """True after this stage number was confirmed. A matching plan still needs stage_repeat."""
    stage = quoted_stage(steps)
    if not stage:
        return False
    return int(stage) in (_progress().get("quoted_stages") or {})


def _fp_int(value: object, default: int) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def brand_gate_row(args: dict) -> tuple | None:
    """One confirmed generate, ignoring prompt text: tool, model, size, count, slot."""
    rows = stage_fingerprint([{"tool": "generate_image", "arguments": args or {}}])
    return rows[0] if rows else None


def stage_fingerprint(steps: list) -> tuple:
    """Identity of one confirmed stage: tool, model, size, count, and prompt-slot id.

    A missing size or model uses the slot default, so a quote that names the slots
    matches the generate calls fill_default will actually submit. An explicit
    different model, size, count, or extra slot stays in the fingerprint.
    """
    rows = []
    progress = _progress()
    for step in steps or []:
        if not isinstance(step, dict) or step.get("tool") != "generate_image":
            continue
        args = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
        slot = _BY_ID.get(str(args.get("brand_slot") or ""))
        if slot is None:
            continue
        model = str(args.get("edit_model") or args.get("model") or step.get("model") or "")
        if not model:
            model = QWEN_EDIT if (args.get("refs") or args.get("base") or _refs_for(slot, progress)) else QWEN_T2I
        rows.append((
            "generate_image",
            model,
            _fp_int(args.get("width"), int(slot["width"])),
            _fp_int(args.get("height"), int(slot["height"])),
            _fp_int(args.get("count"), 1),
            str(slot["id"]),
        ))
    return tuple(sorted(rows))


def _stage_record(stage: int) -> dict | None:
    rec = (_progress().get("quoted_stages") or {}).get(int(stage or 0))
    if isinstance(rec, dict):
        return rec
    return None


def _stage_amount(rec: object) -> float:
    if isinstance(rec, dict):
        return float(rec.get("amount") or 0)
    if rec is None:
        return 0.0
    return float(rec)


def stage_repeat(steps: list) -> str:
    """How a later quote relates to the confirmed plan: new, continue, or done.

    new: no confirmed fingerprint, or this quote changed tools, model, size, count, or slots.
    continue: same fingerprint, and at least one confirmed slot has not been submitted.
    done: same fingerprint, and every confirmed slot has been submitted.
    """
    stage = quoted_stage(steps)
    fp = stage_fingerprint(steps)
    if not stage or not fp:
        return "new"
    rec = _stage_record(stage)
    if rec is None or not rec.get("fingerprint"):
        return "new"
    saved = tuple(tuple(row) for row in rec["fingerprint"])
    if saved != fp:
        return "new"
    confirmed = {str(row[-1]) for row in saved}
    submitted = {str(slot) for slot in (rec.get("submitted_slots") or [])}
    if confirmed and confirmed <= submitted:
        return "done"
    return "continue"


def submits_match_confirmed_plan(steps: list, submit_args: list | None) -> bool:
    """True when stage_repeat continue may skip a new confirm.

    Every generate submitted this turn must carry a brand_slot, and that slot
    must be one of the slots in the confirmed plan. A turn with no generate
    submits has nothing to reuse a confirm on.
    """
    stage = quoted_stage(steps)
    rec = _stage_record(stage) if stage else None
    saved = rec.get("fingerprint") if isinstance(rec, dict) else None
    plan = {str(row[-1]) for row in (saved or ()) if row}
    generates = [a for a in (submit_args or []) if isinstance(a, dict)]
    if not generates:
        return True
    if not plan:
        return False
    return all(str(a.get("brand_slot") or "") in plan for a in generates)


def _merge_fingerprint(old: object, new: tuple) -> tuple:
    by_slot = {}
    for row in old or ():
        if row:
            by_slot[str(row[-1])] = tuple(row)
    for row in new:
        by_slot[str(row[-1])] = tuple(row)
    return tuple(sorted(by_slot.values()))


def remember_stage_plan(steps: list, *, fresh: bool) -> None:
    """Store the plan the user just confirmed.

    A new confirm replaces the fingerprint of the slots on this card. Slots that
    were already submitted stay submitted and are not cleared.
    """
    stage = quoted_stage(steps)
    fp = stage_fingerprint(steps)
    if not stage or not fp:
        return
    progress = _progress()
    done = progress.setdefault("quoted_stages", {})
    rec = done.get(int(stage))
    if not isinstance(rec, dict):
        rec = {
            "amount": _stage_amount(rec) if rec is not None else 0.0,
            "fingerprint": None,
            "dispatched": False,
        }
        done[int(stage)] = rec
    if fresh or not rec.get("fingerprint"):
        prior = [str(slot) for slot in (rec.get("submitted_slots") or [])]
        if fresh and prior and rec.get("fingerprint"):
            rec["fingerprint"] = _merge_fingerprint(rec.get("fingerprint"), fp)
        else:
            rec["fingerprint"] = fp
        if fresh:
            if prior:
                rec["submitted_slots"] = prior
                confirmed = {str(row[-1]) for row in rec["fingerprint"] if row}
                rec["dispatched"] = bool(confirmed) and confirmed <= set(prior)
            else:
                rec["dispatched"] = False
                rec["submitted_slots"] = []
    _persist_grants()


def mark_stage_dispatched(steps: list) -> None:
    """Refresh the stage flag from the slots that were actually submitted.

    Submitting one image does not mark the other confirmed slots as submitted.
    """
    stage = quoted_stage(steps)
    rec = _stage_record(stage) if stage else None
    if rec is None:
        return
    confirmed = {str(row[-1]) for row in (rec.get("fingerprint") or ()) if row}
    submitted = {str(slot) for slot in (rec.get("submitted_slots") or [])}
    rec["dispatched"] = bool(confirmed) and confirmed <= submitted


def note_brand_submitted(args: dict) -> None:
    """One confirmed slot was submitted. The stage is done only after every confirmed slot is."""
    row = brand_gate_row(args)
    if row is None:
        return
    slot = str(row[-1])
    rec = _stage_record(stage_of(slot))
    if rec is None:
        return
    done = list(rec.get("submitted_slots") or [])
    if slot not in done:
        done.append(slot)
    prior_dispatching = [str(item) for item in (rec.get("dispatching_slots") or [])]
    rec["submitted_slots"] = done
    rec["dispatching_slots"] = [item for item in prior_dispatching if item != slot]
    confirmed = {str(item[-1]) for item in (rec.get("fingerprint") or ()) if item}
    if confirmed and confirmed <= set(done):
        rec["dispatched"] = True
    try:
        _persist_grants()
    except BrandGrantPersistError:
        rec["submitted_slots"] = [item for item in done if item != slot]
        rec["dispatching_slots"] = list(prior_dispatching)
        unknown = [str(item) for item in (rec.get("unknown_slots") or [])]
        if slot not in unknown:
            unknown.append(slot)
        rec["unknown_slots"] = unknown
        rec["dispatched"] = False
        try:
            _persist_grants()
        except BrandGrantPersistError:
            pass
        raise


def submitted_slots(stage: int) -> set[str]:
    rec = _stage_record(stage)
    if rec is None:
        return set()
    return {str(slot) for slot in (rec.get("submitted_slots") or [])}


def slot_already_submitted(args: dict) -> bool:
    """True when this confirmed brand slot was already submitted, including on an earlier turn."""
    row = brand_gate_row(args)
    if row is None:
        return False
    return str(row[-1]) in submitted_slots(stage_of(row[-1]))


_STAGE_DONE = {
    "zh": "这一阶段已经确认并提交过了，不要再生成。请进入下一阶段。",
    "en": "This stage was already confirmed and submitted. Do not generate it again. Continue to the next stage.",
}


def stage_done_text(lang: str) -> str:
    return _STAGE_DONE["zh" if lang == "zh" else "en"]


def spend_before(stage: int) -> float:
    """Spent total with this stage's previous confirmation removed, so a repeat card does not double it."""
    progress = _progress()
    spent = float(progress.get("spent") or 0)
    already = (progress.get("quoted_stages") or {}).get(int(stage or 0))
    if already is None:
        return spent
    return round(max(0.0, spent - _stage_amount(already)), 4)


def note_confirmed(total_usd: float, units: int = 0, stage: int = 0) -> None:
    """Record the stage price once. A second confirm of the same stage replaces it and does not add."""
    progress = _progress()
    done = progress.setdefault("quoted_stages", {})
    key = int(stage or 0)
    amount = float(total_usd or 0)
    first = not (key and key in done)
    if key and key in done:
        rec = done[key]
        if isinstance(rec, dict):
            rec["amount"] = amount
        else:
            done[key] = {"amount": amount, "fingerprint": None, "dispatched": False}
    elif key:
        done[key] = {"amount": amount, "fingerprint": None, "dispatched": False}
    if key:
        progress["spent"] = _sum_stage_usd(progress)
    else:
        progress["spent"] = round(float(progress.get("spent") or 0) + amount, 4)
    _persist_grants()
    if not first:
        return
    if units <= 0:
        return
    try:
        from . import paid_guard
        guard = paid_guard.TURNS.get(_chat())
    except Exception:
        guard = None
    if guard is None:
        return
    used = int(guard.used.get(guard.plan_item, 0) or 0)
    guard.cap = max(int(guard.cap or 0), used + int(units))


def brand_prompt(stage_credits: int, cum_credits: int, n: int, lang: str, *, under_gate: bool) -> str:
    """Card copy for one stage. Under the $0.50 gate we do not claim the threshold was crossed."""
    if lang == "zh":
        head = f"这个阶段共 {n} 张。"
        tail = f"本阶段 {stage_credits} 积分，累计 {cum_credits} 积分（含本阶段）。确定开始吗？"
        if not under_gate:
            return head + tail
        return head + tail
    head = f"This stage is {n} image{'s' if n != 1 else ''}. "
    tail = f"This stage is {stage_credits} credits. Cumulative {cum_credits} credits, including this stage. Start?"
    return head + tail


def flatten_opaque(data: bytes) -> bytes:
    """Save an opaque RGB PNG. Any alpha channel is flattened onto white."""
    if not data:
        return data
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as img:
            # Any alpha channel becomes opaque RGB on white, including an
            # all-255 alpha that would otherwise stay RGBA.
            if img.mode in ("RGB", "L", "1"):
                return data
            if img.mode == "P" and "transparency" not in img.info:
                return data
            rgba = img.convert("RGBA")
            base = Image.new("RGB", rgba.size, (255, 255, 255))
            base.paste(rgba, mask=rgba.getchannel("A"))
    except Exception:
        return data
    buf = io.BytesIO()
    base.save(buf, format="PNG")
    return buf.getvalue()


# Stable checklist names for the default path. The active item is the stage being quoted.
# These are the Plan UI labels and match the Chinese quote card: 情绪板, Logo 方向, 交付物.
PLAN_MOODBOARD = "情绪板"
PLAN_LOGOS = "Logo 方向"
PLAN_DELIVERABLES = "交付物"
PLAN_ITEMS = (PLAN_MOODBOARD, PLAN_LOGOS, PLAN_DELIVERABLES)


def default_hint() -> str:
    return (
        "When no industry template was selected, this is the brand-identity default path, "
        "not the 3+1 logo-system template. Three ask_user cards, then eight images, count=1 each. "
        "Card 1 before any image: one ask_user, questions bi_delivery (multi), bi_color, bi_mark, bi_source, "
        "pages 1-4, page_count 4, allow_skip true, allow_other true, no defaults and no recommended. "
        "Then exactly one moodboard, brand_slot=moodboard, 2048x1152 16:9, exactly 3 equal columns by 3 equal rows, "
        "nine cells in row order. Each cell has exactly one Chinese label and an image matching that label. "
        "One label per cell. Never join several labels with a separator. No empty cell. "
        "Every cell's content is full-bleed, filling its cell edge to edge, with no inner margin and no half-empty cell. "
        "The label is a small caption in the cell's bottom-left corner. "
        "Labels in order: 质感 色彩 符号 字标 版式 材料 外带杯 门头 数字. "
        "No English captions and no garbled Latin. "
        "Card 2 bi_moodboard confirms that board. Only answer A (or Skip) may continue. B or C returns to the moodboard. "
        "Then exactly three SEPARATE logo direction boards, brand_slot logo_a then logo_b then logo_c, "
        "each 2048x2048 1:1. logo_a is one open single-line bird on a branch. "
        "logo_b is a filled wood plaque plus a separate circular seal. "
        "logo_c is a cup-shaped badge, not a picture of a handled cup. The badge uses the accent color or the dark color from the confirmed color direction, and the bird is reversed out inside it as negative space, not drawn as a positive bird and not a bird standing on a branch outside it. "
        "Each logo board has four labelled zones: 主组合, 符号构造, 横版, 小尺寸. "
        "Each zone label appears exactly once. "
        "符号构造 shows the actual symbol construction. No empty placeholder box and no X box. "
        "小尺寸 includes the symbol, not the wordmark alone. "
        "The Chinese name and the English name appear together exactly once in each zone. No other small text. "
        "Do not print an English instruction label. "
        "On direction C the wordmark appears exactly once per zone. "
        "Pass the moodboard shape id in refs. "
        "Card 3 bi_direction: three options with image_url of those boards, exactly one recommended, nothing preselected. "
        "Then exactly four deliverables, brand_slot spec, cup, bag (each 1536x2048 3:4) and storefront (2048x1152 16:9). "
        "refs are the chosen logo shape and the moodboard. The spec card is exactly 7 panels. Each heading appears once, in this order: "
        "标识 / LOGO (the approved mark; 「最小使用尺寸」 is an annotation inside this panel, not a separate panel), "
        "色彩 / COLOR (a proportional color strip sampled from the moodboard 色彩 cell; "
        "each swatch has a Chinese color name, a role, and a percentage; "
        "any accent is at most about 5%; "
        "the names, roles, and ratios are sampled from that cell; "
        "do not hardcode a palette and do not invent hex values), "
        "变体 / VARIANTS (the approved variants, each with a short label), "
        "字体 / TYPE (this panel carries its full bilingual heading 字体 / TYPE, not clipped to 字; "
        "hierarchy and annotation density follow the gold; "
        "the Chinese brand name and the English brand name are copied character for character; "
        "Do not drop a character and do not substitute a character), "
        "版式 / LAYOUT (one filled layout diagram), "
        "使用禁忌 / MISUSE (uses only the brand colors, draws a red X, and keeps short captions of the same kind as the gold), "
        "影像与材质 / IMAGE (keeps short captions of the same kind as the gold). "
        "No heading is repeated. Do not add an eighth panel. Do not clip a heading. "
        "Where the gold shows an English counterpart, write the heading as Chinese and English side by side. "
        "Annotation density follows the gold. "
        "Allowed on-card text includes the bilingual headings, a Chinese color name plus a role plus a percentage on each swatch, "
        "the in-panel 「最小使用尺寸」 annotation, short captions on 使用禁忌 / MISUSE and 影像与材质 / IMAGE of the same kind as the gold, "
        "short labels on the approved variants, and the real Chinese brand name and the real English brand name from the brief, copied character for character. "
        "Do not write invented body copy. Do not invent English. "
        "Any text that does appear anywhere must be spelled correctly (one garbled character is not acceptable). "
        "Do not print an English instruction label. "
        "Paper ground, not black. "
        "The storefront is the full shopfront, front view, with the names once on the fascia and an A-frame standing sign. "
        "The takeaway cup must wear a cup sleeve (杯套). A bare cup is wrong. "
        "Cup and bag print both the Chinese name and the English name. "
        "Do not emit a separate palette image or a type specimen. "
        "Before any image, call update_plan with exactly these three items, in this order, "
        "and keep these names for the whole run: "
        f"\"{PLAN_MOODBOARD}\" for the one moodboard, \"{PLAN_LOGOS}\" for the three logo boards, "
        f"\"{PLAN_DELIVERABLES}\" for the four deliverables. "
        "Call update_plan again whenever the active stage changes: mark the stage you are about to quote as active, "
        "and mark that stage done after its images are placed. "
        "Do not rename an item, add an item, or drop an item. "
        "Quote each stage once, before it runs (moodboard, then the three logos, then the four deliverables). "
        "Do not send a second quote card for a stage that was already confirmed, and do not quote all eight on one card. "
        "The closing message has three parts: a delivery list, an honest-limits paragraph, and a next-step suggestion. "
        "Describe the palette in words consistent with the moodboard. Do not state hex values. "
        "Say the exact values are on the spec card and are screen estimates. "
        "The paragraph includes 矢量替换 and 色值为屏幕估算 (vector replacement and screen-estimated color). "
        "Send that closing only after wait_generation reports the four deliverables placed. "
        "Do not put it in the same message as those generate_image calls. "
        "Never say the work is ready to produce (可直接投产)."
    )


class BrandGrantPersistError(RuntimeError):
    """The brand confirmation was not saved. Callers must not dispatch."""


def session_default_stage_open() -> bool:
    """This chat is on moodboard, logos, or finals."""
    return str(_progress().get("phase") or "") in {"moodboard", "logos", "finals"}


def is_brand_stage_template_call(args: dict) -> bool:
    """skill + industry preset, no slot, while this chat is in a brand stage."""
    if not isinstance(args, dict) or args.get("brand_slot"):
        return False
    if str(args.get("skill") or "") != SKILL or not is_template(args.get("preset")):
        return False
    return session_default_stage_open()


def steps_include_brand_template(steps: list) -> bool:
    for step in steps or []:
        if not isinstance(step, dict) or step.get("tool") != "generate_image":
            continue
        args = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
        if is_brand_stage_template_call(args):
            return True
    return False


_TEMPLATE_STAGE = {
    "zh": {"moodboard": "情绪板", "logos": "Logo", "finals": "成稿"},
    "en": {"moodboard": "Moodboard", "logos": "Logo", "finals": "Finals"},
}
_TEMPLATE_NAME = {
    "zh": {
        "geometric": "几何", "handmade": "手作", "tech": "科技",
        "beauty": "美妆", "foodbev": "餐饮", "pet": "宠物",
    },
    "en": {
        "geometric": "Geometric", "handmade": "Handmade", "tech": "Tech",
        "beauty": "Beauty", "foodbev": "Food and beverage", "pet": "Pet",
    },
}
_TEMPLATE_EXTRA = {
    "zh": {
        "moodboard": "额外一张，不替换情绪板",
        "logos": "额外一张，不替换方向 A/B/C",
        "finals": "额外一张，不替换成稿物料",
    },
    "en": {
        "moodboard": "One extra image. It does not replace the moodboard.",
        "logos": "One extra image. It does not replace directions A/B/C.",
        "finals": "One extra image. It does not replace the final deliverables.",
    },
}


def template_quote_text(preset: str, lang: str, phase: str = "") -> str:
    """Card row for one extra template image during an open brand stage."""
    lang_key = "zh" if lang == "zh" else "en"
    phase_id = str(phase or _progress().get("phase") or "")
    stage = _TEMPLATE_STAGE[lang_key].get(phase_id) or phase_id
    name = _TEMPLATE_NAME[lang_key].get(str(preset or "")) or str(preset or "")
    extra = _TEMPLATE_EXTRA[lang_key].get(phase_id) or _TEMPLATE_EXTRA[lang_key]["logos"]
    if lang_key == "zh":
        title = f"{stage} 阶段 · {name}模板"
    else:
        title = f"{stage} stage · {name} template"
    return f"{title}\n{extra}"


def template_grant_key(args: dict) -> str:
    """Prompt, preset, and skill. Size filled after the quote is not part of the key."""
    import json
    raw = args if isinstance(args, dict) else {}
    return json.dumps({
        "skill": str(raw.get("skill") or ""),
        "preset": str(raw.get("preset") or ""),
        "prompt": str(raw.get("prompt") or ""),
    }, ensure_ascii=False, sort_keys=True)


def template_grants() -> dict:
    saved = _progress().get("template_grants")
    return dict(saved) if isinstance(saved, dict) else {}


def _grant_path() -> str:
    from ._common import app_path
    return app_path(_GRANT_FILE)


def _read_grant_file() -> dict:
    path = _grant_path()
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        return {"chats": {}}
    if not isinstance(raw, dict) or not isinstance(raw.get("chats"), dict):
        return {"chats": {}}
    return raw


def _write_grant_file(payload: dict) -> None:
    try:
        from .memory import atomic_write_json
        atomic_write_json(_grant_path(), payload)
    except BrandGrantPersistError:
        raise
    except Exception as exc:
        raise BrandGrantPersistError(str(exc) or "brand confirmation could not be saved") from exc


def _json_stages(stages: dict) -> dict:
    out = {}
    for key, rec in (stages or {}).items():
        if isinstance(rec, dict):
            out[str(int(key))] = _json_ready(rec)
    return out


def _persist_grants() -> None:
    disk = _read_grant_file()
    chats = dict(disk.get("chats") or {})
    for chat, row in _PROGRESS.items():
        stages = row.get("quoted_stages") or {}
        if stages:
            chats[str(chat)] = {"quoted_stages": _json_stages(stages)}
        else:
            chats.pop(str(chat), None)
    _write_grant_file({"chats": chats})


def _hydrate_grants(chat: str, row: dict) -> None:
    saved = (_read_grant_file().get("chats") or {}).get(str(chat)) or {}
    stages = saved.get("quoted_stages") if isinstance(saved, dict) else None
    if not isinstance(stages, dict) or not stages:
        return
    thawed = {}
    for key, rec in stages.items():
        try:
            stage = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(rec, dict):
            thawed[stage] = rec
    if thawed:
        row["quoted_stages"] = thawed
        row["spent"] = _sum_stage_usd(row)


def settle_restored_cards(chat_id: str, messages: list | None = None, *, now: float | None = None) -> list:
    """Close due brand cards before a restored session is rendered."""
    from . import bot_asks, chat_store
    clock = _clock() if now is None else float(now)
    for ask in list(bot_asks.PENDING.values()):
        if ask.chat_id == chat_id and confirm_expired(ask.spec, clock):
            bot_asks.resolve_ask(ask.id, "expired")
    if not messages:
        return messages or []
    for message in messages:
        blocks = message.get("blocks") if isinstance(message, dict) else None
        if not isinstance(blocks, list):
            continue
        changed = False
        for index, block in enumerate(blocks):
            if (isinstance(block, dict) and block.get("type") == "ask"
                    and block.get("status") == "pending" and confirm_expired(block, clock)):
                blocks[index] = {**block, "status": "expired"}
                changed = True
        if changed and message.get("id"):
            chat_store.update_message(chat_id, message["id"], blocks=blocks)
    return messages


def remember_template_grants(steps: list, *, identity: dict, amount: float, currency: str,
                             quote_id: str, created_at: float, expires_at: float) -> None:
    progress = _progress()
    bucket = progress.setdefault("template_grants", {})
    if not isinstance(bucket, dict):
        bucket = {}
        progress["template_grants"] = bucket
    written: list[str] = []
    previous = {key: bucket.get(key) for key in list(bucket)}
    try:
        for step in steps or []:
            if not isinstance(step, dict) or step.get("tool") != "generate_image":
                continue
            args = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
            if not is_brand_stage_template_call(args):
                continue
            key = template_grant_key(args)
            bucket[key] = {
                "type": "template",
                "key": key,
                "preset": str(args.get("preset") or ""),
                "prompt": str(args.get("prompt") or ""),
                "phase": str(progress.get("phase") or ""),
                "amount": round(float(amount or 0), 4),
                "currency": str(currency or BRAND_CURRENCY),
                "quote_id": str(quote_id or ""),
                "created_at": float(created_at),
                "expires_at": float(expires_at),
                "used": False,
                "user": str(identity.get("user") or ""),
                "project": str(identity.get("project") or ""),
                "chat": str(identity.get("chat") or ""),
            }
            written.append(key)
        if written:
            _persist_grants()
    except BrandGrantPersistError:
        for key in written:
            if key in previous:
                bucket[key] = previous[key]
            else:
                bucket.pop(key, None)
        raise


def template_submit_block(args: dict, turn: object = None, *, now: float | None = None) -> str | None:
    """Why this template grant must not pay, or None when this confirm still covers it."""
    if not is_brand_stage_template_call(args):
        return None
    grant = (_progress().get("template_grants") or {}).get(template_grant_key(args))
    if not isinstance(grant, dict) or grant.get("type") != "template":
        return "unconfirmed"
    if grant.get("used"):
        return "submitted"
    clock = _clock() if now is None else float(now)
    exp = grant.get("expires_at")
    if isinstance(exp, bool) or not isinstance(exp, (int, float)) or clock >= float(exp):
        return "expired"
    identity = turn_identity(turn)
    if (str(grant.get("user") or "") != identity["user"]
            or str(grant.get("project") or "") != identity["project"]
            or str(grant.get("chat") or "") != identity["chat"]):
        return "identity"
    if str(grant.get("prompt") or "") != str(args.get("prompt") or ""):
        return "mismatch"
    if str(grant.get("preset") or "") != str(args.get("preset") or ""):
        return "mismatch"
    return None


def mark_template_grant_used(args: dict) -> None:
    grant = (_progress().get("template_grants") or {}).get(template_grant_key(args))
    if not isinstance(grant, dict):
        return
    grant["used"] = True
    _persist_grants()


def missing_base_message(slot_id: str) -> str | None:
    """Why a stage 2/3 slot cannot be quoted, or None when its bases are present."""
    slot = _BY_ID.get(str(slot_id or ""))
    if slot is None or int(slot["stage"]) < 2:
        return None
    progress = _progress()
    shapes = progress.get("shapes") or {}
    missing: list[str] = []
    if not str(shapes.get("moodboard") or ""):
        missing.append("moodboard")
    if int(slot["stage"]) >= 3:
        chosen = str(progress.get("chosen") or "logo_a")
        if not str(shapes.get(chosen) or ""):
            missing.append(chosen)
    if not missing:
        return None
    zh_slot = _QUOTE_NAME["zh"].get(slot["id"], slot["id"])
    en_slot = _QUOTE_NAME["en"].get(slot["id"], slot["id"])
    zh_names = "、".join(_QUOTE_NAME["zh"].get(item, item) for item in missing)
    en_names = ", ".join(
        "moodboard" if item == "moodboard" else _QUOTE_NAME["en"].get(item, item) for item in missing)
    if card_lang() == "en":
        return (
            f"{en_slot} is missing its {en_names} base, so it can't be made right now. "
            "No quote was made and nothing was charged."
        )
    return _zh_gap([zh_slot, "缺少", zh_names, "底图，这一张暂时做不了。没有报价，也没有扣积分。"])


def _han(ch: str) -> bool:
    return "\u4e00" <= ch <= "\u9fff"


def _latin_or_digit(ch: str) -> bool:
    return ch.isascii() and (ch.isalpha() or ch.isdigit())


def _zh_gap(parts: list[str]) -> str:
    out = ""
    for part in parts:
        if not part:
            continue
        if out and ((_han(out[-1]) and _latin_or_digit(part[0]))
                     or (_latin_or_digit(out[-1]) and _han(part[0]))):
            out += " "
        out += part
    return out


def stage_base_block(steps: list) -> str | None:
    for step in steps or []:
        slot = _slot_id_of(step)
        stage = stage_of(slot)
        if slot and (slot in submitted_slots(stage) or slot in _held_slots(stage)):
            continue
        message = missing_base_message(slot)
        if message:
            return message
    return None


def release_preset_stamp(steps: list) -> list:
    """Drop a brand_slot that annotation stamped onto a preset quote row."""
    out = []
    for step in steps or []:
        if not isinstance(step, dict):
            out.append(step)
            continue
        step = dict(step)
        args = step.get("arguments")
        if (step.get("_slot_stamped") and step.get("tool") == "generate_image"
                and isinstance(args, dict) and str(args.get("preset") or "").strip()):
            args = dict(args)
            args.pop("brand_slot", None)
            step["arguments"] = args
            step.pop("_slot_stamped", None)
        out.append(step)
    return out


def unknown_slots(stage: int) -> set[str]:
    rec = _stage_record(stage)
    if rec is None:
        return set()
    return {str(slot) for slot in (rec.get("unknown_slots") or [])}


def unsubmitted_steps(steps: list) -> list:
    stage = quoted_stage(steps)
    done = submitted_slots(stage) if stage else set()
    held = _held_slots(stage) if stage else set()
    out = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        if step.get("tool") != "generate_image":
            out.append(step)
            continue
        slot = _slot_id_of(step)
        if slot and (slot in done or slot in held):
            continue
        out.append(step)
    return out


def only_reconcile_left(steps: list) -> bool:
    slots = [slot for slot in (_slot_id_of(step) for step in (steps or [])) if slot]
    if not slots:
        return False
    stage = quoted_stage(steps)
    done = submitted_slots(stage)
    held = _held_slots(stage)
    return all(slot in done or slot in held for slot in slots) and any(slot in held for slot in slots)


def all_slots_submitted(steps: list) -> bool:
    slots = [slot for slot in (_slot_id_of(step) for step in (steps or [])) if slot]
    if not slots:
        return False
    done = submitted_slots(quoted_stage(steps))
    return all(slot in done for slot in slots)


def invalidate_grant(stage: int) -> None:
    rec = _stage_record(stage)
    if not isinstance(rec, dict) or "grant" not in rec:
        return
    rec.pop("grant", None)
    rec.pop("expires_at", None)
    _persist_grants()


def supersede_brand_card(steps: list, spec: dict) -> list:
    opened = unsubmitted_steps(steps)
    stage = quoted_stage(steps) or quoted_stage(opened)
    digest = ""
    if isinstance(spec, dict):
        frozen = spec.get("frozen")
        if isinstance(frozen, dict):
            digest = str(frozen.get("digest") or "")
            stage = stage or int(frozen.get("stage") or 0)
    if not stage:
        return opened
    progress = _progress()
    done = progress.setdefault("quoted_stages", {})
    rec = done.get(int(stage))
    if not isinstance(rec, dict):
        rec = {"amount": 0.0, "fingerprint": None, "dispatched": False, "submitted_slots": []}
        done[int(stage)] = rec
    dead = [str(item) for item in (rec.get("superseded_digests") or [])]
    if digest and digest not in dead:
        dead.append(digest)
    rec["superseded_digests"] = dead
    if isinstance(rec.get("grant"), dict):
        invalidate_grant(int(stage))
    else:
        rec.pop("expires_at", None)
        _persist_grants()
    return opened


def grant_still_authorizes(steps: list, turn: object = None, *, now: float | None = None,
                           amount: float | None = None, currency: str | None = None,
                           quote_id: str | None = None) -> bool:
    stage = quoted_stage(steps)
    grant = _grant_of(stage)
    if grant is None:
        return False
    clock = _clock() if now is None else float(now)
    if confirm_expired({**grant, "brand_confirm": True}, clock):
        return False
    identity = turn_identity(turn)
    if (str(grant.get("user") or "") != identity["user"]
            or str(grant.get("project") or "") != identity["project"]
            or str(grant.get("chat") or "") != identity["chat"]):
        return False
    if amount is not None and round(float(amount or 0), 4) != round(float(grant.get("amount") or 0), 4):
        return False
    if currency is not None and str(currency or "") != str(grant.get("currency") or ""):
        return False
    if quote_id is not None and str(quote_id or "") != str(grant.get("quote_id") or ""):
        return False
    saved = {str(row.get("slot")): row for row in (grant.get("slots") or []) if isinstance(row, dict)}
    open_rows = _execution_rows(unsubmitted_steps(steps))
    if not open_rows:
        return False
    for row in open_rows:
        previous = saved.get(row["slot"])
        if previous is None:
            return False
        if _json_ready(previous) != _json_ready(row):
            return False
    return True


def bind_brand_generate(args: dict, quote_steps: list | None = None, claimed: set | None = None) -> dict:
    """Put a brand slot on this generate before it can be reserved."""
    args = dict(args or {})
    skill = str(args.get("skill") or "")
    if skill and skill != SKILL and not args.get("brand_slot"):
        return args
    if not args.get("brand_slot"):
        taken = claimed or set()
        for step in quote_steps or []:
            slot = str((step.get("arguments") or {}).get("brand_slot") or "") if isinstance(step, dict) else ""
            if slot and slot not in taken:
                args["brand_slot"] = slot
                args["skill"] = SKILL
                break
    if str(args.get("skill") or "") == SKILL or args.get("brand_slot"):
        return fill_default(args)
    return args


def expired_text(lang: str) -> str:
    return EXPIRED_TEXT["zh" if lang == "zh" else "en"]


def fixed_size_note(lang: str) -> str:
    return FIXED_SIZE_NOTE["zh" if lang == "zh" else "en"]


def confirm_expired(spec: object, now: float | None = None) -> bool:
    if not isinstance(spec, dict) or spec.get("brand_confirm") is not True:
        return False
    exp = spec.get("expires_at")
    if isinstance(exp, bool) or not isinstance(exp, (int, float)):
        return True
    clock = _clock() if now is None else float(now)
    return clock >= float(exp)


def turn_identity(turn: object = None, *, user: str = "", project: str = "", chat: str = "") -> dict:
    if turn is not None:
        user = user or str(getattr(turn, "owner_id", "") or "")
        project = project or str(getattr(turn, "project_id", "") or "")
        chat = chat or str(getattr(turn, "chat_id", "") or "")
    return {
        "user": user or "local",
        "project": project or "local",
        "chat": chat or _chat(),
    }


def _json_ready(value: object) -> object:
    import json
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))


def _step_args(step: object) -> dict:
    if not isinstance(step, dict) or step.get("tool") != "generate_image":
        return {}
    args = step.get("arguments")
    return dict(args) if isinstance(args, dict) else {}


def _slot_id_of(step: object) -> str:
    return str(_step_args(step).get("brand_slot") or "")


def normalize_slot_execution(args: dict) -> dict | None:
    """The execution this brand slot will actually submit.

    Invalid width, height, count, and model inputs fold to the slot lock before
    they are compared. Prompt, base, ordered references, and mask are the assembled
    request. A longer or different model-written prompt is a different execution.
    """
    raw = dict(args or {})
    slot = _BY_ID.get(str(raw.get("brand_slot") or ""))
    if slot is None:
        return None
    filled = fill_default(raw)
    if filled.get("_brand_block"):
        filled = {key: value for key, value in filled.items() if key != "_brand_block"}
        for key in ("model", "edit_model", "auto_model", "size_candidates"):
            filled.pop(key, None)
    params = {}
    for key in sorted(filled):
        if key in _EXEC_SKIP:
            continue
        value = filled[key]
        if isinstance(value, (str, int, float, bool)) or value is None:
            params[key] = value
        elif isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) or item is None for item in value):
            params[key] = list(value)
    try:
        width = int(filled["width"])
        height = int(filled["height"])
    except (KeyError, TypeError, ValueError):
        width, height = int(slot["width"]), int(slot["height"])
    refs = [str(item) for item in (filled.get("refs") or [])]
    return {
        "slot": str(slot["id"]),
        "stage": int(slot["stage"]),
        "model": str(filled.get("edit_model") or filled.get("model") or ""),
        "base": str(filled.get("base") or ""),
        "refs": refs,
        "mask": str(filled.get("mask") or ""),
        "width": width,
        "height": height,
        "count": int(filled.get("count") or 1),
        "prompt": str(filled.get("prompt") or ""),
        "params": params,
    }


def _execution_rows(steps: list) -> list[dict]:
    by_slot: dict[str, dict] = {}
    for step in steps or []:
        args = step.get("arguments") if isinstance(step, dict) else None
        row = normalize_slot_execution(args if isinstance(args, dict) else {})
        if row is not None:
            by_slot[row["slot"]] = row
    return [by_slot[key] for key in sorted(by_slot)]


def _assembled_quote_steps(steps: list) -> list:
    """Program assembly of each default-path slot before that request is frozen."""
    out = []
    for step in steps or []:
        if not isinstance(step, dict) or step.get("tool") != "generate_image":
            out.append(step)
            continue
        args = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
        if not args.get("brand_slot") or str(args.get("preset") or "").strip():
            out.append(step)
            continue
        step = dict(step)
        step["arguments"] = assemble_confirmed_request(args)
        out.append(step)
    return out


def build_grant(steps: list, *, identity: dict, amount: float, currency: str,
                quote_id: str, created_at: float, expires_at: float) -> dict:
    steps = _assembled_quote_steps(steps)
    body = {
        "user": str(identity.get("user") or ""),
        "project": str(identity.get("project") or ""),
        "chat": str(identity.get("chat") or ""),
        "stage": int(quoted_stage(steps) or 0),
        "amount": round(float(amount or 0), 4),
        "currency": str(currency or BRAND_CURRENCY),
        "quote_id": str(quote_id or ""),
        "created_at": float(created_at),
        "expires_at": float(expires_at),
        "slots": _execution_rows(steps),
    }
    encoded = __import__("json").dumps(body, ensure_ascii=False, sort_keys=True, default=str).encode()
    body["digest"] = hashlib.sha256(encoded).hexdigest()
    return _json_ready(body)


def _grant_of(stage: int) -> dict | None:
    rec = _stage_record(stage)
    grant = rec.get("grant") if isinstance(rec, dict) else None
    return grant if isinstance(grant, dict) else None


def grant_digest_superseded(stage: int, digest: str) -> bool:
    rec = _stage_record(stage)
    if not isinstance(rec, dict) or not digest:
        return False
    return str(digest) in {str(item) for item in (rec.get("superseded_digests") or [])}


def stamp_confirm_spec(spec: dict, steps: list, turn: object, *, amount: float, lang: str,
                       currency: str | None = None, quote_id: str | None = None) -> dict:
    """Freeze expiry and the quoted slots onto the card before it is shown."""
    card = dict(spec or {})
    created = _clock()
    lang_key = "zh" if lang == "zh" else "en"
    note = fixed_size_note(lang_key)
    prompt = str(card.get("prompt") or "")
    if note not in prompt:
        card["prompt"] = prompt.rstrip() + note
    card["brand_confirm"] = True
    card["size_locked"] = True
    card["created_at"] = created
    card["expires_at"] = created + BRAND_CONFIRM_TTL_S
    card["quote_id"] = str(quote_id or "") or uuid.uuid4().hex
    card["currency"] = str(currency or BRAND_CURRENCY)
    card["amount"] = round(float(amount or 0), 4)
    card["lang"] = lang_key
    if str(card.get("price_state") or "") in {"estimate", "unpriced"}:
        card["options"] = [
            {"id": "requote", "label": "重新取价" if lang_key == "zh" else "Request a new price"},
            {"id": "cancel", "label": "取消" if lang_key == "zh" else "Cancel"},
        ]
    frozen = build_grant(
        steps,
        identity=turn_identity(turn),
        amount=card["amount"],
        currency=card["currency"],
        quote_id=card["quote_id"],
        created_at=float(created),
        expires_at=float(card["expires_at"]),
    )
    card["frozen"] = frozen
    card["frozen_slots"] = list(frozen.get("slots") or [])
    card["brand_steps"] = _json_ready(list(steps or []))
    return card


def commit_confirmed_grant(steps: list, spec: dict, turn: object, *, amount: float) -> dict | None:
    """Store the snapshot the card already froze. Start does not rebuild it or move expires_at."""
    del steps, amount
    if not isinstance(spec, dict) or spec.get("brand_confirm") is not True:
        return None
    frozen = spec.get("frozen")
    if not isinstance(frozen, dict) or not frozen.get("digest"):
        return None
    created = frozen.get("created_at")
    expires = frozen.get("expires_at")
    if isinstance(created, bool) or not isinstance(created, (int, float)):
        return None
    if isinstance(expires, bool) or not isinstance(expires, (int, float)):
        return None
    stage = int(frozen.get("stage") or 0)
    if not stage:
        return None
    if grant_digest_superseded(stage, str(frozen.get("digest") or "")):
        return None
    identity = turn_identity(turn)
    if (str(frozen.get("user") or "") != identity["user"]
            or str(frozen.get("project") or "") != identity["project"]
            or str(frozen.get("chat") or "") != identity["chat"]):
        return None
    grant = _json_ready(frozen)
    progress = _progress()
    done = progress.setdefault("quoted_stages", {})
    rec = done.get(int(stage))
    if not isinstance(rec, dict):
        rec = {"amount": float(grant.get("amount") or 0), "fingerprint": None, "dispatched": False, "submitted_slots": []}
        done[int(stage)] = rec
    previous = rec.get("grant") if isinstance(rec.get("grant"), dict) else None
    previous_exp = rec.get("expires_at")
    rec["grant"] = grant
    rec["expires_at"] = grant["expires_at"]
    rec["amount"] = grant["amount"]
    try:
        _persist_grants()
    except BrandGrantPersistError:
        if previous is None:
            rec.pop("grant", None)
            rec.pop("expires_at", None)
        else:
            rec["grant"] = previous
            rec["expires_at"] = previous_exp
        raise
    return grant


def reserve_brand_dispatch(args: dict) -> None:
    if not isinstance(args, dict) or not args.get("brand_slot"):
        return
    slot = str(args.get("brand_slot") or "")
    stage = stage_of(slot)
    rec = _stage_record(stage)
    if rec is None:
        raise BrandGrantPersistError("brand slot has no confirmation to reserve")
    current = [str(item) for item in (rec.get("dispatching_slots") or [])]
    if slot in submitted_slots(stage) or slot in current:
        raise BrandGrantPersistError("brand slot is already reserved")
    current.append(slot)
    rec["dispatching_slots"] = current
    try:
        _persist_grants()
    except BrandGrantPersistError:
        rec["dispatching_slots"] = [item for item in current if item != slot]
        raise


def dispatching_slots(stage: int) -> set[str]:
    rec = _stage_record(stage)
    if rec is None:
        return set()
    return {str(slot) for slot in (rec.get("dispatching_slots") or [])}


def _held_slots(stage: int) -> set[str]:
    rec = _stage_record(stage)
    unknown = set()
    if isinstance(rec, dict):
        unknown = {str(slot) for slot in (rec.get("unknown_slots") or [])}
    return unknown | dispatching_slots(stage)


def assemble_confirmed_request(args: dict) -> dict:
    """The model-bound request for one default-path slot, before it is quoted.

    ``fill_default`` appends that slot's lock to the text already on the request.
    A missing base is not assembled here; ``stage_base_block`` reports it.
    Calling this again on the result does not add a second lock.
    """
    if not isinstance(args, dict) or not args.get("brand_slot"):
        return dict(args or {})
    if str(args.get("preset") or "").strip():
        return dict(args)
    filled = fill_default(args)
    if filled.get("_brand_block"):
        return dict(args)
    return filled


def submit_block_reason(args: dict, turn: object = None, *, now: float | None = None) -> str | None:
    """Why this brand generate must not run, or None when the frozen grant still allows the slot.

    The prompt must be the assembled snapshot the human confirmed. Replacing it
    or appending to it is a mismatch. Expiry, identity, a slot already submitted,
    and a reservation already held are mismatches of a different kind. A template
    call is ``template_submit_block``.
    """
    if not isinstance(args, dict) or not args.get("brand_slot"):
        return None
    slot = str(args.get("brand_slot") or "")
    if slot in _held_slots(stage_of(slot)):
        return "reconcile"
    if slot_already_submitted(args):
        return "submitted"
    stage = stage_of(args.get("brand_slot"))
    grant = _grant_of(stage)
    if grant is None:
        return "unconfirmed"
    clock = _clock() if now is None else float(now)
    if confirm_expired({**grant, "brand_confirm": True}, clock):
        return "expired"
    identity = turn_identity(turn)
    if (str(grant.get("user") or "") != identity["user"]
            or str(grant.get("project") or "") != identity["project"]
            or str(grant.get("chat") or "") != identity["chat"]):
        return "identity"
    row = normalize_slot_execution(args)
    saved = {str(item.get("slot")): item for item in (grant.get("slots") or []) if isinstance(item, dict)}
    frozen = saved.get(row["slot"]) if row is not None else None
    if row is None or frozen is None:
        return "mismatch"
    if _json_ready(frozen) != _json_ready(row):
        return "mismatch"
    return None


def submit_block_text(reason: str, lang: str) -> str:
    lang_key = "zh" if lang == "zh" else "en"
    if reason == "expired":
        return expired_text(lang_key)
    if reason == "reconcile":
        if lang_key == "zh":
            return "该槽位已生成但确认记录未能落盘，状态待核对，不会自动重发。"
        return ("This slot was generated but the confirmation record was not saved. "
                "It is pending review and will not be sent again.")
    if reason == "unconfirmed":
        if lang_key == "zh":
            return "确认没有保存成功，没有开始，也没有扣积分。请重新取价。"
        return "The confirmation was not saved. Nothing started and nothing was charged. Request a new price."
    if lang_key == "zh":
        return "参数已变化，上一张确认失效。请重新取价。已提交的槽位不会重跑。"
    return ("The parameters changed, so the previous confirmation is no longer valid. "
            "Request a new price. Submitted slots will not run again.")
