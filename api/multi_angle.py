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
from fractions import Fraction

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
            "max_selections": len(options) if multi else 1, "allow_other": True,
            "placeholder": ("输入编号 / Enter panel numbers" if multi else
                            "其他情况 / Other scenario" if qid == SOURCE else
                            "自定义比例或像素，例如 5:4 / 1200x960 px"),
            "page": page, "defaults": []}


def normalize_card(args: dict) -> dict:
    # Do not intercept approval cards or unrelated skills/cards.
    if args.get("kind") in ("run_approval", "plan_approval", "plan_quote"):
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
                raw += [token for token in re.split(r"[\s,，、;/]+", other) if token]
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


# This is a request-size fallback, NOT a measured universal Lovart delivery.
DEFAULT_SIZE_POLICY = "requested-aspect / 2k-long-edge fallback (square 2048); explicit user pixels win"
_DIMENSIONS = re.compile(r"(?<![\d.])(-?\d+(?:\.\d+)?)\s*[x×*]\s*(-?\d+(?:\.\d+)?)(?![\d.])", re.I)
_NAMED_DIMS = re.compile(r"(?:width|宽(?:度)?)\s*[:=：]?\s*(-?\d+(?:\.\d+)?)\s*(?:px|像素)?[\s,，;；]*(?:height|高(?:度)?)\s*[:=：]?\s*(-?\d+(?:\.\d+)?)", re.I)
_RATIOS = re.compile(r"(?<![\d.])(-?\d+(?:\.\d+)?)\s*[:：]\s*(-?\d+(?:\.\d+)?)(?![\d.])")


def _ratio(a: str, b: str) -> str:
    x, y = Fraction(a), Fraction(b)
    if x <= 0 or y <= 0 or not Fraction(1, 16) <= x / y <= 16:
        raise ValueError("比例必须为正数且在 1:16..16:1 内 / Use a positive aspect between 1:16 and 16:1.")
    q = x / y
    return f"{q.numerator}:{q.denominator}"


def _parse_spec(text: str) -> dict:
    sizes, ratios = set(), set()
    for m in list(_DIMENSIONS.finditer(text)) + list(_NAMED_DIMS.finditer(text)):
        w, h = map(Fraction, m.groups())
        if w.denominator != 1 or h.denominator != 1 or not (0 < w <= 32768 and 0 < h <= 32768):
            raise ValueError("像素须为 1..32768 内的正整数；请澄清宽高 / Pixel dimensions must be positive integers within 1..32768; clarify width/height.")
        sizes.add((int(w), int(h)))
    for m in _RATIOS.finditer(text):
        ratios.add(_ratio(*m.groups()))
    if len(sizes) > 1 or len(ratios) > 1:
        raise ValueError("存在多个冲突尺寸/比例，请明确唯一规格 / Conflicting sizes/aspects; specify one unambiguous specification.")
    out = {}
    if sizes:
        out["width"], out["height"] = next(iter(sizes))
        out["exact_pixels"] = True
    if ratios:
        out["ratio"] = next(iter(ratios))
    return out


def _merge_specs(*specs: dict) -> dict:
    out = {}
    for spec in specs:
        for key, value in spec.items():
            if key in out and out[key] != value:
                raise ValueError("描述与问询答案的规格冲突，请统一后再生成 / Description/card specifications conflict; clarify before generation.")
            out[key] = value
    if out.get("width"):
        actual = _ratio(str(out["width"]), str(out["height"]))
        if out.get("ratio") and out["ratio"] != actual:
            raise ValueError("像素宽高与所选比例冲突，请修改答案或明确像素 / Requested pixels conflict with selected aspect; correct the answer or pixel request.")
        out["ratio"] = actual
    return out


def _user_specs(chat_id: str) -> tuple[str, dict, dict]:
    from .skill_param_guard import _text_of
    from ..bot.skill_output import _INJECTED_RE, TEMPLATE_BLOCK_RE
    description = "\n".join(_text_of(b) for row in _messages(chat_id) if row.get("role") == "user"
                             for b in row.get("blocks") or [] if b.get("type") == "text").strip()
    # Only user-owned text supplies specifications; never parse model tool args.
    user_text = _INJECTED_RE.sub(" ", TEMPLATE_BLOCK_RE.sub(" ", description))
    final, preview = {}, {}
    for clause in re.split(r"[\n;；]|[,，](?=\s*(?:preview|final|lineart|预览|线稿|成品))", user_text, flags=re.I):
        spec = _parse_spec(clause)
        if re.search(r"\b(?:preview|lineart)\b|预览|线稿", clause, re.I):
            preview = _merge_specs(preview, spec)
        else:
            final = _merge_specs(final, spec)
    return description, final, preview


def pixels(ratio: str) -> tuple[int, int]:
    """Documented fallback only; share existing ratio sizing, never override user pixels."""
    from ..bot.skill_output import pixels_for_ratio
    wh = pixels_for_ratio(ratio)
    if wh is None:
        raise ValueError("无法推导默认尺寸，请输入明确像素 / Cannot derive fallback size; enter explicit pixel dimensions.")
    return (2048, 2048) if wh == (1024, 1024) else wh


def _complete_spec(spec: dict) -> dict:
    spec = dict(spec)
    if not spec.get("ratio"):
        raise ValueError("请明确成品比例或像素 / Specify final aspect or pixel dimensions.")
    if not spec.get("exact_pixels"):
        spec["width"], spec["height"] = pixels(spec["ratio"])
        spec["exact_pixels"] = False
        spec["default_policy"] = DEFAULT_SIZE_POLICY
    return spec


def validate_provider_size(args: dict, meta: dict, model: str, catalog: dict | None = None) -> dict | None:
    """No network: reuse adapter schema/exact-size helpers and fail before dispatch."""
    from . import wavespeed
    from .skill_size import accepts_exact_pixels
    spec = meta["stage_spec"]
    if (args.get("width"), args.get("height"), args.get("ratio")) != (spec["width"], spec["height"], spec["ratio"]):
        return _blocked("后续路由改写了规格，未提交 / Routing changed the requested specification; nothing submitted.")
    schema = wavespeed._schema((catalog if catalog is not None else wavespeed.cached_models()).get(model))
    if not schema:
        return (_blocked("模型像素能力未知，请先刷新模型目录或选择支持明确像素的模型；未提交 / Exact-pixel capability unknown; refresh the model catalogue or choose a pixel-capable model; nothing submitted.")
                if spec["exact_pixels"] else None)
    try:
        wavespeed.validate_user_ratio(schema, {**args, "user_ratio": spec["ratio"]}, model)
    except wavespeed.WaveSpeedError as e:
        return _blocked(str(e))
    w, h = spec["width"], spec["height"]
    props = schema.get("properties") or {}
    for name, values in (("size", (w, h)), ("width", (w,)), ("height", (h,))):
        field = props.get(name) or {}
        for value in values:
            if ((field.get("minimum") is not None and value < field["minimum"])
                    or (field.get("maximum") is not None and value > field["maximum"])
                    or (field.get("multipleOf") and value % field["multipleOf"])):
                return _blocked(f"{model} 不支持 {w}x{h}（{name} 范围/步长）；请选择支持的像素或模型，未提交 / Unsupported pixel range/step; choose supported pixels/model, nothing submitted.")
    if spec["exact_pixels"] and not accepts_exact_pixels(schema, w, h, model):
        return _blocked(f"{model} 无法保证明确像素 {w}x{h}；请选择支持该像素的模型，未提交且未换模型 / Model cannot preserve exact pixels; choose a capable model, no submission or model substitution.")
    return None


def prepare(args: dict, chat_id: str = "") -> tuple[dict, dict | None]:
    """Pure stage/size/ref lock, also used by quotes. No paid reservation here."""
    chat_id = chat_id or _chat_id()
    if not applies(args, chat_id):
        return dict(args), None
    args = dict(args)
    _, root = _root(chat_id)
    if root is None or root.get("status") != "answered":
        return args, _blocked("Use ask_user for source/aspect and wait for its answer first.")
    source_answer, aspect_answer = _answer(root, SOURCE), _answer(root, ASPECT)
    source_other = str(source_answer.get("other_text") or "").strip()
    source = (source_answer.get("selected") or ["other" if source_other else ""])[0]
    aspect_selected = (aspect_answer.get("selected") or [""])[0]
    aspect_other = str(aspect_answer.get("other_text") or "").strip()
    if source not in {"single_front", "multiple", "description", "other"} or (source == "other" and not source_other):
        return args, _blocked("请回答来源或填写其他情况 / Answer source or describe the other scenario.")
    ledger = root.get(LEDGER) or {}
    try:
        original_description, user_final, user_preview = _user_specs(chat_id)
        card_spec = _parse_spec(aspect_other)
        if aspect_selected:
            card_spec = _merge_specs(card_spec, {"ratio": _ratio(*str(aspect_selected).split(":"))})
        if not card_spec:
            raise ValueError("请选择比例或在其他栏输入比例/像素 / Select an aspect or enter aspect/pixels in Other.")
        final_spec = _complete_spec(_merge_specs(user_final, card_spec))
        # A preview may differ only when the USER requested its layout, never
        # because the model guessed width/height/ratio on the tool call.
        preview_spec = _complete_spec(user_preview) if user_preview else dict(final_spec)
        setup_snapshot = {"source": copy.deepcopy(source_answer), "aspect": copy.deepcopy(aspect_answer),
                          "final": final_spec, "preview": preview_spec}
        if ledger and ledger.get("setup_snapshot") != setup_snapshot:
            raise ValueError("Source/aspect changed after submission; 规格/来源已变更或旧记录缺少规格快照，请先核对原任务并显式开启新一轮，禁止付费重放 / Specification/source changed or legacy snapshot missing; reconcile existing work and start an explicit new skill run, do not replay paid work.")
    except (ValueError, ZeroDivisionError) as e:
        return args, _blocked(str(e))
    aspect = final_spec["ratio"]
    preview = ledger.get("preview") or {}
    stage = str(args.get("multi_angle_stage") or ("final" if preview.get("delivered") else "preview"))
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
    uploads = context_from_chat(chat_id).uploads
    refs = (list(ledger["refs"]) if "refs" in ledger else
            uploads or ([] if source == "description" else list(args.get("refs") or [])))
    if source not in {"description", "other"} and not refs:
        return args, _blocked("Attach the reference once; no paid call without the chosen reference source.")
    description = ledger["description"] if "description" in ledger else original_description or source_other
    if not description and not refs:
        return args, _blocked("请提供主体图片或描述 / Supply a subject image or description.")
    spec = preview_spec if stage == "preview" else final_spec
    for name in SIZE_KEYS:
        args.pop(name, None)  # replace guessed tool fields with the authoritative user spec below
    args.pop("base", None)
    args.pop("base_strength", None)
    args.pop("stage", None)
    args.update(skill=SKILL, ratio=spec["ratio"], width=spec["width"], height=spec["height"], count=1, n=1, size_lock=True)
    from ..bot.skill_output import STRICT_RATIO_994
    args[STRICT_RATIO_994] = spec["ratio"]  # existing page + adapter strict-ratio path
    args["refs"] = list(refs)
    args["ref_modes"] = ["content"] * len(refs)
    if stage == "final":
        # Bind the selected number to the preview actually delivered, not just a
        # fresh interpretation of its verbal label. Original subject stays first.
        for shape in preview.get("shapes") or []:
            if shape not in args["refs"]:
                args["refs"].append(shape)
                args["ref_modes"].append("composition")
    brief = f"User description (preserve; empty means image-only, use the attached subject without inventing a brief):\n{description}\nReference source: {source}; other scenario: {source_other}. Final specification: {final_spec['width']}x{final_spec['height']}, ratio {aspect}; exact user pixels={final_spec['exact_pixels']}. This stage: {spec['width']}x{spec['height']}, ratio {spec['ratio']}.\nPreserve subject identity, material, proportions, controls and background requirements.\n"
    if stage == "preview":
        brief += "Produce ONE lineart preview image: a numbered 3x3 nine-panel composition grid, labels 1..9. Not final photographs.\n"
        brief += "\n".join(f"{k}: {v[1]}" for k, v in VIEWS.items())
    else:
        brief += f"Produce ONE independent finished image, composition {panel}: {VIEWS[panel][1]}. No grid, panel numbers or collage."
    args["prompt"] = brief
    args["_multi_angle"] = {"key": key, "refs": list(refs), "description": description,
                            "source": source, "aspect": aspect, "setup_snapshot": setup_snapshot, "stage_spec": spec}
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
    for k in ("refs", "description", "source", "aspect", "setup_snapshot"):
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
