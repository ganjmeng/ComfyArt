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

import io
import re

SKILL = "brand-identity-director"
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
        {"id": "C", "label": "杯形负空间", "description": "杯子外形，符号是杯中的负空间"},
    ],
}
_CARD3_EN = {
    "id": _CARD3,
    "prompt": "Which logo direction should be the final mark (logo_primary)?",
    "options": [
        {"id": "A", "label": "Single-line bird on a branch", "description": "One continuous line draws a bird perched on a branch"},
        {"id": "B", "label": "Wooden signboard and round seal", "description": "A solid wooden signboard plus a separate round seal"},
        {"id": "C", "label": "Cup-shaped negative space", "description": "A cup-shaped container; the symbol is the cup's negative space"},
    ],
}

_HEADS = {
    _Q_DELIVERY: ("要交付哪些物料", "which pieces should this basic brand"),
    _Q_COLOR: ("色彩方向选哪一种", "which color direction"),
    _Q_MARK: ("构成方向偏好", "which logo construction"),
    _Q_SOURCE: ("素材怎么处理", "how should the store and product"),
    _CARD2: ("视觉基准", "visual baseline"),
    _CARD3: ("logo_primary", "final mark"),
}


def card_lang(lang: str | None = None) -> str:
    if lang in ("zh", "en"):
        return lang
    from . import bot_asks
    got = bot_asks.card_lang()
    return got if got in ("zh", "en") else "zh"


def _cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _live_options(raw: object, fallback: list[dict], lang: str) -> list[dict]:
    """Keep the model's labels when the count matches and the language matches; else the measured fallback."""
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
    options = _live_options(raw.get("options"), locked["options"], lang)
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
    urls = _logo_urls()
    for opt, slot in zip(options, LOGO_IDS):
        url = urls.get(slot) or ""
        if not url:
            for raw_opt in raw_opts:
                if isinstance(raw_opt, dict) and str(raw_opt.get("id") or "").upper()[:1] == opt["id"]:
                    url = str(raw_opt.get("image_url") or "").strip()
        if url:
            opt["image_url"] = url
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


def reset_for_tests() -> None:
    _PROGRESS.clear()
    _HELD_WRAPUP.clear()
    _TURN.clear()


def _chat() -> str:
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
    return row


def _logo_urls() -> dict:
    return dict(_progress().get("urls") or {})


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


# Appended to the image prompt. The three logos must not share one bird-on-a-branch drawing.
_SLOT_LOCK = {
    "moodboard": (
        "LAYOUT LOCK: exactly 3 equal columns and 3 equal rows, nine filled cells, no blank cell, no merged cell. "
        "One short Chinese label per cell, in this order: 质感, 色彩, 符号, 字标, 版式, 材料, 外带杯, 门头, 数字. "
        "No English sentences, no lorem, no tiny Latin captions. Warm paper ground, not a black field."
    ),
    "logo_a": (
        "STRUCTURE LOCK A: the mark is one open single-line drawing of a bird perched on a branch. "
        "No filled plaque, no circular seal, no cup silhouette. "
        "The sheet still shows the mark, a construction grid, a horizontal lockup, small sizes, and one reversed dark block. "
        "The lockup prints BOTH the Chinese brand name and the English brand name from the brief. "
        "No other English words and no garbled captions. No bottom caption."
    ),
    "logo_b": (
        "STRUCTURE LOCK B: two separate parts, a solid filled wood plaque AND a circular seal. "
        "Not a line-drawing bird standing on a branch. "
        "The lockup prints BOTH the Chinese brand name and the English brand name. "
        "No garbled English captions. No bottom caption."
    ),
    "logo_c": (
        "STRUCTURE LOCK C: the mark is a cup-shaped container and the symbol is the cup's negative space. "
        "Not a bird standing on a branch, not a circular seal, not a wood plaque. "
        "The lockup prints BOTH the Chinese brand name and the English brand name. "
        "No garbled English captions. No bottom caption."
    ),
    "spec": (
        "GUIDELINE LOCK: one board with exactly these seven Chinese headings: "
        "最小尺寸, 变体, 色彩比例, 字体层级, 版式, 使用禁忌, 影像材质. "
        "Short Chinese words only, plus the brand's own Chinese and English names. "
        "No invented English such as fake size labels. Paper ground, not black."
    ),
    "cup": (
        "APPLICATION LOCK: takeaway cup wearing a sleeve (杯套). The print is a complete bilingual lockup: "
        "the Chinese brand name AND the English brand name, both readable. Do not print the English name alone. "
        "No extra English captions. A real cup on a light ground, not a black void."
    ),
    "bag": (
        "APPLICATION LOCK: paper bag. Complete bilingual lockup, Chinese name and English name both readable. "
        "Not English only. No garbled captions. Real paper, not a black void."
    ),
    "storefront": (
        "APPLICATION LOCK: storefront sign with both the Chinese brand name and the English brand name. "
        "No garbled small type. The sign is on a real facade, not a black field."
    ),
}


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
    lock = _SLOT_LOCK.get(str(slot["id"]))
    if lock and lock not in str(args.get("prompt") or ""):
        args["prompt"] = (str(args.get("prompt") or "").rstrip() + "\n" + lock).strip()
    refs = _refs_for(slot, progress)
    if refs:
        # The moodboard / chosen logo lead. A caller-supplied ref stays behind them.
        extra = [str(r) for r in (args.get("refs") or []) if str(r) not in refs]
        args["refs"] = refs + extra
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
        slot_id = progress["holders"].get(str(row.get("id") or ""))
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


def annotate_quote_steps(steps: list, paid_args: list | None = None) -> list:
    """Stamp brand slots onto a quote the model wrote itself.

    A quote_plan call often omits brand_slot. Without it the stage is not
    recognized, a sub-$0.50 stage can skip the card, and every row reads as
    the model name. Slots already on the generate calls win; otherwise the
    current stage supplies them. Other skills are left untouched.
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


def cumulative_line(total_usd: float, lang: str) -> str:
    from ..bot.run_budget import ui_credits
    prev = float(_progress().get("spent") or 0)
    stage = ui_credits(float(total_usd or 0))
    cum = ui_credits(prev + float(total_usd or 0))
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
    continue: same fingerprint, and its tools have not been dispatched yet.
    done: same fingerprint, and those tools were already dispatched or completed.
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
    return "done" if rec.get("dispatched") else "continue"


def remember_stage_plan(steps: list, *, fresh: bool) -> None:
    """Store the plan the user just confirmed. A new confirm clears the dispatched flag."""
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
        rec["fingerprint"] = fp
        if fresh:
            rec["dispatched"] = False


def mark_stage_dispatched(steps: list) -> None:
    """The confirmed plan's paid tools were submitted. A repeat must not submit them again."""
    stage = quoted_stage(steps)
    rec = _stage_record(stage) if stage else None
    if rec is not None:
        rec["dispatched"] = True


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
    if key and key in done:
        progress["spent"] = round(spend_before(key) + amount, 4)
        rec = done[key]
        if isinstance(rec, dict):
            rec["amount"] = amount
        else:
            done[key] = {"amount": amount, "fingerprint": None, "dispatched": False}
        return
    if key:
        done[key] = {"amount": amount, "fingerprint": None, "dispatched": False}
    progress["spent"] = round(float(progress.get("spent") or 0) + amount, 4)
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


def default_hint() -> str:
    return (
        "Output lock: no industry template was selected, so this is the brand-identity default path, "
        "NOT the 3+1 logo-system template. Three ask_user cards, then eight images, count=1 each. "
        "Card 1 before any image: one ask_user, questions bi_delivery (multi), bi_color, bi_mark, bi_source, "
        "pages 1-4, page_count 4, allow_skip true, allow_other true, no defaults and no recommended. "
        "Then exactly one moodboard, brand_slot=moodboard, 2048x1152 16:9, exactly 3 equal columns by 3 equal rows, "
        "no empty cell. Chinese labels only, in order: 质感 色彩 符号 字标 版式 材料 外带杯 门头 数字. "
        "No English captions and no garbled Latin. "
        "Card 2 bi_moodboard confirms that board. Only answer A (or Skip) may continue. B or C returns to the moodboard. "
        "Then exactly three SEPARATE logo direction boards, brand_slot logo_a then logo_b then logo_c, "
        "each 2048x2048 1:1. logo_a is one open single-line bird on a branch. "
        "logo_b is a filled wood plaque plus a separate circular seal. "
        "logo_c is a cup-shaped negative-space container, not a bird on a branch. "
        "Every lockup prints the Chinese brand name and the English brand name. "
        "Pass the moodboard shape id in refs. "
        "Card 3 bi_direction: three options with image_url of those boards, exactly one recommended, nothing preselected. "
        "Then exactly four deliverables, brand_slot spec, cup, bag (each 1536x2048 3:4) and storefront (2048x1152 16:9). "
        "refs are the chosen logo shape and the moodboard. The spec card has seven Chinese blocks: "
        "最小尺寸, 变体, 色彩比例, 字体层级, 版式, 使用禁忌, 影像材质. "
        "Cup and bag print both the Chinese name and the English name. "
        "Do not emit a separate palette image or a type specimen. "
        "Quote each stage once, before it runs (moodboard, then the three logos, then the four deliverables). "
        "Do not send a second quote card for a stage that was already confirmed, and do not quote all eight on one card. "
        "The closing message has three parts: a delivery list, an honest-limits paragraph that includes "
        "矢量替换 and 色值为屏幕估算 (vector replacement and screen-estimated color), and a next-step suggestion. "
        "Send that closing only after wait_generation reports the four deliverables placed. "
        "Do not put it in the same message as those generate_image calls. "
        "Never say the work is ready to produce (可直接投产)."
    )
