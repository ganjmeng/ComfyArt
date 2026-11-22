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
        {"id": "A", "label": "方向 A"},
        {"id": "B", "label": "方向 B"},
        {"id": "C", "label": "方向 C"},
    ],
}
_CARD3_EN = {
    "id": _CARD3,
    "prompt": "Which logo direction should be the final mark (logo_primary)?",
    "options": [
        {"id": "A", "label": "Direction A"},
        {"id": "B", "label": "Direction B"},
        {"id": "C", "label": "Direction C"},
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
        if isinstance(shapes, list) and shapes and str(shapes[0]).strip():
            placed = str(shapes[0]).strip()
        failed = progress.setdefault("failed", [])
        status = str(row.get("status") or "").lower()
        if placed:
            progress["shapes"][slot_id] = placed
            if slot_id in failed:
                failed.remove(slot_id)
            if isinstance(urls, list) and urls:
                progress["urls"][slot_id] = str(urls[0])
            if slot_id in progress["inflight"]:
                progress["inflight"].remove(slot_id)
        elif status in {"running", "pending", "queued"}:
            # A timeout poll that is still running is not a failed final.
            if slot_id not in progress["inflight"]:
                progress["inflight"].append(slot_id)
        elif status in {"error", "failed", "cancelled", "declined"} or (
            row.get("error") and status not in {"running", "pending", "queued"}
        ):
            if slot_id not in progress["shapes"] and slot_id not in failed:
                failed.append(slot_id)
            if slot_id in progress["inflight"]:
                progress["inflight"].remove(slot_id)
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


_URL_RE = __import__("re").compile(r"https?://\S+")


def _closing_line(line: str) -> bool:
    """The delivery-list heading, not a sentence that merely mentions the words."""
    folded = line.casefold()
    return "本次交付清单" in line or "delivery list" in folded


def still_generating_wrapup(lang: str = "zh") -> str:
    """Honest note for finals that are still in flight. Does not call them failures."""
    names = _final_names(_inflight_finals(_progress()), lang)
    if not names:
        return ""
    if lang == "en":
        return "Still generating: " + ", ".join(names) + "."
    return "仍在生成：" + "、".join(names) + "。"


def split_closing(text: str) -> tuple[str, str]:
    """Separate the delivery-list lines from prose and links.

    A download URL on the same line as the list stays with the prose.
    """
    kept: list[str] = []
    closing: list[str] = []
    for line in str(text or "").splitlines():
        if not _closing_line(line):
            kept.append(line)
            continue
        urls = _URL_RE.findall(line)
        body = _URL_RE.sub("", line).strip()
        if body:
            closing.append(body)
        if urls:
            kept.append(" ".join(urls))
    return "\n".join(part for part in kept if part.strip()).strip(), "\n".join(closing).strip()


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
    missing = _explicit_failed_finals(progress)
    if phase in {"finals", "done"} and missing and not inflight:
        if tuple(missing) == tuple(progress.get("wrapup_reported") or ()):
            return ""
        _HELD_WRAPUP.pop(_chat(), None)
        _turn()["extra"] = []
        _turn()["released"] = True
        progress["wrapup_reported"] = tuple(missing)
        return failure_wrapup(lang)
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
        reported = progress.get("wrapup_reported")
        inflight = tuple(_inflight_finals(progress))
        # A still-running final is not a failure. Say it is still generating,
        # and do not publish the held success list.
        if phase == "finals" and inflight:
            signature = ("running", missing, inflight)
            if signature != reported:
                parts = [failure_wrapup(lang), still_generating_wrapup(lang)]
                text = "\n".join(part for part in parts if part)
                progress["wrapup_reported"] = signature
            _HELD_WRAPUP.pop(_chat(), None)
        elif phase == "finals" and missing and missing != reported:
            text = failure_wrapup(lang)
            progress["wrapup_reported"] = missing
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


def note_confirmed(total_usd: float, units: int = 0) -> None:
    """Record the stage price and let this stage run on top of images already made."""
    progress = _progress()
    progress["spent"] = round(float(progress.get("spent") or 0) + float(total_usd or 0), 4)
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
        "Then exactly one moodboard, brand_slot=moodboard, 2048x1152 16:9, a 3x3 nine-grid "
        "(tone, color, perch symbol, bilingual wordmark, layout margins, handmade material, takeaway cup, "
        "storefront, social extension). "
        "Card 2 bi_moodboard confirms that board. Only answer A (or Skip) may continue. B or C returns to the moodboard. "
        "Then exactly three SEPARATE logo direction boards, brand_slot logo_a then logo_b then logo_c, "
        "each 2048x2048 1:1, each a direction sheet (primary mark, construction grid, horizontal lockup, small and reversed). "
        "Pass the moodboard shape id in refs. Different shape language on each board. "
        "Card 3 bi_direction: three options with image_url of those boards, exactly one recommended, nothing preselected. "
        "Then exactly four deliverables, brand_slot spec, cup, bag (each 1536x2048 3:4) and storefront (2048x1152 16:9). "
        "refs are the chosen logo shape and the moodboard. Palette and type live only on the spec card. "
        "Do not emit a separate palette image or a type specimen. "
        "Quote each stage on its own before it runs (moodboard, then the three logos, then the four deliverables); "
        "do not quote all eight on one card. "
        "The closing message has three parts: a delivery list, an honest-limits paragraph that includes "
        "矢量替换 and 色值为屏幕估算 (vector replacement and screen-estimated color), and a next-step suggestion. "
        "Send that closing only after wait_generation reports the four deliverables placed. "
        "Do not put it in the same message as those generate_image calls. "
        "Never say the work is ready to produce (可直接投产)."
    )
