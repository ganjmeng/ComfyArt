"""#1002 (Refs #911) multi-angle stages, using the existing ask/continuation and canvas tools.

The setup ask block owns a durable, fail-closed submit ledger. It survives a new
agent turn/restart; a reserved/uncertain request is NEVER automatically resubmitted.
This is deliberately not a turn counter (cards commonly resume in another turn).
Only wait_generation's placed shapes unlock the composition card. Fixture pixels
are evidence, not defaults: final aspect comes from the answered setup card.
"""
from __future__ import annotations

import copy
import re

SKILL = "universal-multi-angle-grid"
SOURCE, ASPECT, COMPOSITIONS = "ma_source", "ma_aspect", "ma_compositions"
LEDGER = "multi_angle_state"
RATIOS = ("1:1", "3:4", "4:3", "16:9", "9:16", "4:5", "5:4", "3:2", "2:3")
VIEWS = {
    "1": ("正面全身", "front full subject"),
    "2": ("四分之三全身", "three-quarter full subject"),
    "3": ("90°侧面全身", "strict 90-degree side profile, full subject"),
    "4": ("正面中景", "front medium view"),
    "5": ("四分之三中景", "three-quarter medium view"),
    "6": ("背面全身", "rear full subject"),
    "7": ("俯视", "top view"),
    "8": ("细节特写", "detail close-up"),
    "9": ("低角度", "low-angle full subject"),
}
SIZE_KEYS = ("width", "height", "ratio", "resolution", "edit_resolution", "size_lock", "size_lock_mode", "size_candidates")


def _chat_id() -> str:
    from .mcp_tools._context import BOT_CHAT_ID
    return str(BOT_CHAT_ID.get() or "")


def _messages(chat_id: str) -> list[dict]:
    from . import chat_store
    from .skill_param_guard import _skill_from_block, _text_of, _SKILL_START_RE
    rows = chat_store.list_messages(chat_id) if chat_id else []
    start = 0
    for i, row in enumerate(rows):
        if row.get("role") != "user":
            continue
        if _SKILL_START_RE.search(str(row.get("content") or row.get("provider_text") or "")):
            start = i
        for block in row.get("blocks") or []:
            name = _skill_from_block(block)
            hit = _SKILL_START_RE.search(_text_of(block))
            name = name or (hit.group(2).strip() if hit else "")
            if name:
                start = i
    return rows[start:]


def _root(chat_id: str) -> tuple[dict | None, dict | None]:
    for row in reversed(_messages(chat_id)):
        for block in reversed(row.get("blocks") or []):
            if block.get("type") == "ask" and any(q.get("id") == SOURCE for q in block.get("questions") or []):
                return row, block
    return None, None


def applies(args: dict, chat_id: str = "") -> bool:
    from .skill_param_guard import context_from_chat, canonical_skill
    from ..bot.skill_output import resolve
    current = context_from_chat(chat_id or _chat_id()).skill
    current = resolve(current) or current
    named = resolve(args.get("skill")) or canonical_skill(str(args.get("skill") or ""))
    return named == SKILL or current == SKILL


def _question(qid: str, prompt: str, options: list[dict], *, multi: bool = False, page: int = 1) -> dict:
    return {"id": qid, "prompt": prompt, "options": options, "min_selections": 1,
            "max_selections": len(options) if multi else 1, "allow_other": multi,
            "placeholder": "输入编号 / Enter panel numbers" if multi else "",
            "page": page, "defaults": []}


def normalize_card(args: dict) -> dict:
    # Do not intercept approval cards or unrelated skills/cards.
    if args.get("kind") in ("run_approval", "plan_approval"):
        return args
    ids = {q.get("id") for q in args.get("questions") or [] if isinstance(q, dict)}
    if not applies({}, _chat_id()) and not ids.intersection({SOURCE, ASPECT, COMPOSITIONS}):
        return args
    from .bot_asks import card_lang
    zh = card_lang() == "zh"
    _, root = _root(_chat_id())
    if root is None or (root.get("status") in {"expired", "cancelled"} and not root.get(LEDGER)):
        source = [("single_front", "只上传1张正面主图", "One front reference image"),
                  ("multiple", "多张参考图", "Multiple reference images"),
                  ("description", "仅文字描述", "Description only")]
        questions = [
            _question(SOURCE, "参考图来源" if zh else "Reference source", [
                {"id": key, "label": z if zh else e} for key, z, e in source]),
            _question(ASPECT, "成品画幅" if zh else "Final image aspect", [
                {"id": ratio, "label": ratio + ("（推荐）" if zh else " (recommended)") if ratio == "1:1" else ratio}
                for ratio in RATIOS], page=2),
        ]
        return {"questions": questions, "page_count": 2, "allow_skip": False}
    if root.get("status") != "answered":
        raise ValueError("Answer the existing multi-angle source/aspect card; do not create another.")
    ledger = root.get(LEDGER) or {}
    if not ledger.get("preview", {}).get("delivered"):
        raise ValueError("Generate and wait for the numbered nine-panel lineart preview before composition selection.")
    # Reuse the persisted card on resume, rather than asking or charging twice.
    for row in _messages(_chat_id()):
        for block in row.get("blocks") or []:
            if (block.get("type") == "ask" and block.get("status") not in {"expired", "cancelled"}
                    and any(q.get("id") == COMPOSITIONS for q in block.get("questions") or [])):
                raise ValueError("Use the existing composition card/answer; do not create another.")
    q = _question(COMPOSITIONS, "选择想生成的构图（可多选，按图中编号）" if zh else
                  "Choose compositions (multiple panel numbers allowed)", [
                      {"id": key, "label": f"{key} {view[0 if zh else 1]}"} for key, view in VIEWS.items()], multi=True)
    return {"questions": [q], "allow_skip": False}


def _answer(block: dict, qid: str) -> dict:
    if block.get("status") != "answered":
        return {}
    return (block.get("answers") or {}).get(qid) or {}


def selection(chat_id: str) -> list[str]:
    for row in reversed(_messages(chat_id)):
        for block in reversed(row.get("blocks") or []):
            ans = _answer(block, COMPOSITIONS)
            if not ans:
                continue
            raw = [str(s) for s in ans.get("selected") or []]
            other = str(ans.get("other_text") or "").strip()
            if other:
                if not re.fullmatch(r"[1-9\s,，、;/]+", other):
                    raise ValueError("Composition custom text must contain panel numbers 1..9 only.")
                raw += re.findall(r"[1-9]", other)
            if any(s not in VIEWS for s in raw):
                raise ValueError("Unknown composition number; choose numbered panels 1..9.")
            return list(dict.fromkeys(raw))
    return []


def _save(chat_id: str, ledger: dict, expected_ledger: dict) -> None:
    from . import chat_store
    from .bot_turns import ACTIVE_TURNS
    row, block = _root(chat_id)
    if row is None:
        raise ValueError("Missing durable multi-angle setup card")
    if (block.get(LEDGER) or {}) != expected_ledger:
        raise ValueError("Multi-angle state changed concurrently; reconcile existing state before submitting")
    state = ACTIVE_TURNS.get(chat_id)
    live_blocks = state.blocks if state is not None and state.message_id == row["id"] else None
    blocks = copy.deepcopy(live_blocks if live_blocks is not None else row["blocks"])
    target = next(b for b in blocks if b.get("type") == "ask" and b.get("ask_id") == block.get("ask_id"))
    target[LEDGER] = copy.deepcopy(ledger)
    if not chat_store.compare_message_blocks(chat_id, row["id"], row["blocks"], blocks):
        raise ValueError("Cannot persist multi-angle state: concurrent write or missing message; nothing newly submitted")
    if live_blocks is not None:
        # Keep the existing live ask block in sync: later event flushes must not
        # erase the ledger. Do not mutate live state until the CAS succeeds.
        live_target = next(b for b in live_blocks if b.get("type") == "ask" and b.get("ask_id") == block.get("ask_id"))
        live_target[LEDGER] = copy.deepcopy(ledger)


def _blocked(message: str) -> dict:
    return {"status": "blocked", "submitted": False, "generation_succeeded": False,
            "kind": "multiAngleStage", "error": message}


def pixels(ratio: str) -> tuple[int, int]:
    w, h = map(int, ratio.split(":"))
    return (2048, round(2048 * h / w / 2) * 2) if w >= h else (round(2048 * w / h / 2) * 2, 2048)


def prepare(args: dict, chat_id: str = "") -> tuple[dict, dict | None]:
    """Pure stage/size/ref lock, also used by quotes. No paid reservation here."""
    chat_id = chat_id or _chat_id()
    if not applies(args, chat_id):
        return dict(args), None
    args = dict(args)
    _, root = _root(chat_id)
    if root is None or root.get("status") != "answered":
        return args, _blocked("Use ask_user for source/aspect and wait for its answer first.")
    source = (_answer(root, SOURCE).get("selected") or [""])[0]
    aspect = (_answer(root, ASPECT).get("selected") or [""])[0]
    if source not in {"single_front", "multiple", "description"} or aspect not in RATIOS:
        return args, _blocked("Source and final aspect must both be explicitly answered; no guessed defaults.")
    ledger = root.get(LEDGER) or {}
    if ledger and ((ledger.get("source") and ledger["source"] != source)
                   or (ledger.get("aspect") and ledger["aspect"] != aspect)):
        return args, _blocked("Source/aspect changed after submission; start a new explicit skill run, do not replay paid work.")
    preview = ledger.get("preview") or {}
    stage = str(args.get("multi_angle_stage") or ("final" if preview else "preview"))
    if stage not in {"preview", "final"}:
        return args, _blocked("multi_angle_stage must be preview or final")
    key = "preview"
    if stage == "final":
        if not preview.get("delivered"):
            return args, _blocked("Wait for the lineart preview to be delivered before final generation.")
        try:
            selected = selection(chat_id)
        except ValueError as e:
            return args, _blocked(str(e))
        if not selected:
            return args, _blocked("Answer the composition multi-select card before any final generation.")
        from . import paid_guard
        guard = paid_guard.TURNS.get(chat_id)
        if guard is not None and guard.user_count and len(selected) > guard.user_count:
            return args, _blocked("Selected final count exceeds the explicit user count; reconcile the composition answer first.")
        panel = str(args.get("composition_id") or "")
        if panel not in selected:
            return args, _blocked("Pass one composition_id from the answered card: " + ", ".join(selected))
        key = "final:" + panel
    old = ledger.get(key)
    if old:
        result = copy.deepcopy(old.get("result") or _blocked("Submission reserved/uncertain; reconcile existing task, never retry automatically."))
        result["multi_angle_replay"] = True
        return args, result
    from .skill_param_guard import context_from_chat, _text_of
    refs = ledger.get("refs") or context_from_chat(chat_id).uploads or list(args.get("refs") or [])
    if source != "description" and not refs:
        return args, _blocked("Attach the reference once; no paid call without the chosen reference source.")
    description = ledger.get("description")
    if description is None:
        description = "\n".join(_text_of(b) for row in _messages(chat_id) if row.get("role") == "user"
                                for b in row.get("blocks") or [] if b.get("type") == "text").strip()
        description = description or str(args.get("prompt") or "").strip()
    if not description:
        return args, _blocked("A subject description or reference brief is required.")
    # Preview layout is independent of final aspect. Default follows selected aspect;
    # an explicitly requested supported preview aspect is accepted, never fixture-locked.
    ratio = str(args.get("ratio") or aspect) if stage == "preview" else aspect
    if ratio not in RATIOS:
        return args, _blocked("Unsupported preview aspect")
    for name in SIZE_KEYS:
        args.pop(name, None)
    args.pop("base", None)
    args.pop("base_strength", None)
    args.pop("stage", None)
    args.update(skill=SKILL, ratio=ratio, count=1, n=1, size_lock=True)
    args["width"], args["height"] = pixels(ratio)
    args["refs"] = list(refs)
    args["ref_modes"] = ["content"] * len(refs)
    if stage == "final":
        # Bind the selected number to the preview actually delivered, not just a
        # fresh interpretation of its verbal label. Original subject stays first.
        for shape in preview.get("shapes") or []:
            if shape not in args["refs"]:
                args["refs"].append(shape)
                args["ref_modes"].append("composition")
    brief = f"User description (preserve):\n{description}\nReference source: {source}. Final aspect: {aspect}.\nPreserve subject identity, material, proportions, controls and background requirements.\n"
    if stage == "preview":
        brief += "Produce ONE lineart preview image: a numbered 3x3 nine-panel composition grid, labels 1..9. Not final photographs.\n"
        brief += "\n".join(f"{k}: {v[1]}" for k, v in VIEWS.items())
    else:
        brief += f"Produce ONE independent finished image, composition {panel}: {VIEWS[panel][1]}. No grid, panel numbers or collage."
    args["prompt"] = brief
    args["_multi_angle"] = {"key": key, "refs": list(refs), "description": description,
                            "source": source, "aspect": aspect}
    return args, None


def reserve(meta: dict, chat_id: str = "") -> dict | None:
    """Synchronous reservation immediately before dispatch (no await in between).

    Persist BEFORE submitting. Crash/timeout uncertainty intentionally blocks retries.
    Existing single-process canvas relay serializes this synchronous section.
    """
    chat_id = chat_id or _chat_id()
    _, root = _root(chat_id)
    ledger = copy.deepcopy((root or {}).get(LEDGER) or {})
    expected = copy.deepcopy(ledger)
    key = meta["key"]
    if key in ledger:
        return copy.deepcopy(ledger[key].get("result") or _blocked("Already reserved; inspect existing task, do not submit again."))
    for k in ("refs", "description", "source", "aspect"):
        ledger.setdefault(k, meta[k])
    ledger[key] = {"status": "reserved"}
    _save(chat_id, ledger, expected)
    return None


def submitted(meta: dict, result: dict, chat_id: str = "") -> None:
    chat_id = chat_id or _chat_id()
    _, root = _root(chat_id)
    ledger = copy.deepcopy((root or {}).get(LEDGER) or {})
    expected = copy.deepcopy(ledger)
    ledger[meta["key"]] = {"status": "submitted", "result": copy.deepcopy(result)}
    _save(chat_id, ledger, expected)


def record_wait(result: dict, chat_id: str = "") -> None:
    chat_id = chat_id or _chat_id()
    _, root = _root(chat_id)
    if root is None:
        return
    ledger = copy.deepcopy(root.get(LEDGER) or {})
    expected = copy.deepcopy(ledger)
    changed = False
    for entry in ledger.values():
        if not isinstance(entry, dict) or not entry.get("result", {}).get("ids"):
            continue
        ids = entry["result"]["ids"]
        shapes = [s for row in result.get("results") or [] if row.get("id") in ids
                  and not row.get("error") and row.get("status") == "done"
                  and row.get("placed") is True and row.get("generation_succeeded") is not False
                  and row.get("delivered", 1) == 1
                  for s in row.get("shapes") or []]
        if len(shapes) == 1:
            entry.update(delivered=True, shapes=shapes)
            changed = True
    if changed:
        _save(chat_id, ledger, expected)


def allow_selected_cap(args: dict, chat_id: str) -> None:
    """#1002: selected finals are a bounded plan, not the old flat 4-image cap.

    Called only on REAL MCP dispatch after prepare, never for quotes. Dollar /
    approval budgets remain unchanged. The preview is intermediate; a user count
    still bounds final images (prepare rejects more selections than that count).
    Remaining unreserved selected IDs, rather than the total, bound a resumed turn.
    """
    meta = args.get("_multi_angle") or {}
    if not str(meta.get("key") or "").startswith("final:"):
        return
    from . import paid_guard
    guard = paid_guard.TURNS.get(chat_id)
    if guard is None:
        return
    _, root = _root(chat_id)
    ledger = (root or {}).get(LEDGER) or {}
    remaining = sum("final:" + panel not in ledger for panel in selection(chat_id))
    guard.cap = max(guard.cap, guard.used.get(guard.plan_item, 0) + remaining)
