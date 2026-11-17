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
PANEL_IDS = tuple(str(i) for i in range(1, 10))


def validate_plan(value: object) -> dict:
    """A subject-aware plan is supplied by the agent after inspecting input, never a fixed view list."""
    if not isinstance(value, dict):
        raise ValueError("Provide composition_plan with subject, purpose, subject_geometry, appearance and nine panels with separate geometry/appearance before preview submission.")
    out = {}
    for key in ("subject", "purpose", "subject_geometry"):
        text = value.get(key)
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError(f"composition_plan.{key} is required: provide structured geometry separately from appearance; replan before submission.")
        out[key] = text.strip()
    appearance = value.get("appearance")
    if not isinstance(appearance, str) or len(appearance) > 2000:
        raise ValueError("composition_plan.appearance must be a separate string (empty if unspecified); replan before submission.")
    out["appearance"] = appearance.strip()
    panels = value.get("panels")
    if not isinstance(panels, list) or len(panels) != 9:
        raise ValueError("composition_plan requires exactly nine panels, IDs 1..9.")
    clean = []
    for panel in panels:
        if not isinstance(panel, dict) or str(panel.get("id")) not in PANEL_IDS:
            raise ValueError("Each composition plan panel needs one ID 1..9.")
        item = {"id": str(panel["id"])}
        for key in ("name", "description", "geometry"):
            text = panel.get(key)
            if not isinstance(text, str) or not text.strip() or len(text) > 2000:
                raise ValueError(f"Each panel requires a non-empty {key} (max 2000 characters).")
            item[key] = text.strip()
        appearance = panel.get("appearance")
        if not isinstance(appearance, str) or len(appearance) > 2000:
            raise ValueError("Each panel requires separate appearance text (empty if unspecified); geometry is camera/framing/structures only.")
        item["appearance"] = appearance.strip()
        clean.append(item)
    if {p["id"] for p in clean} != set(PANEL_IDS):
        raise ValueError("Composition plan IDs must be unique and cover 1..9.")
    for key in ("name", "description", "geometry"):
        if len({p[key].casefold() for p in clean}) != 9:
            raise ValueError(f"Composition plan {key}s must distinguish all nine panels.")
    out["panels"] = sorted(clean, key=lambda p: int(p["id"]))
    return out


def preview_plan_view(plan: dict) -> dict:
    """Use explicit geometry fields only, never infer/scrub legacy mixed prose.

    Original names, purpose, descriptions and appearance remain frozen for the
    selection card/finals. Semantic correctness of geometry still needs visual QA.
    """
    return {"subject_geometry": plan["subject_geometry"], "panels": [
        {"id": panel["id"], "geometry": panel["geometry"]} for panel in plan["panels"]]}


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
            ids = {q.get("id") for q in block.get("questions") or []}
            if block.get("type") == "ask" and ids.intersection({SOURCE, ASPECT}):
                return row, block
    return None, None


def applies(args: dict, chat_id: str = "") -> bool:
    from .skill_param_guard import context_from_chat, canonical_skill
    from ..bot.skill_output import resolve
    current = context_from_chat(chat_id or _chat_id()).skill
    current = resolve(current) or current
    named = resolve(args.get("skill")) or canonical_skill(str(args.get("skill") or ""))
    return named == SKILL or current == SKILL


# Setup-card copy: zh is Lovart verbatim (product-locked). English is a faithful
# translation of that meaning, not a claimed official Lovart English original.
SOURCE_OPTIONS = (
    ("multiple", "上传多角度产品图", "Upload multi-angle product photos"),
    ("single_front", "只上传 1 张正面主图", "Upload only 1 front hero image"),
    ("no_photo", "暂无实拍图，先做产品示意", "No real product photos yet, start with a product concept"),
)
# D is the allow_other field, not a fourth selectable id.
ASPECT_OPTIONS = (
    ("1:1", "1:1 方图（推荐）", "1:1 square (recommended)"),
    ("3:4", "3:4 竖图", "3:4 portrait"),
    ("4:3", "4:3 横图", "4:3 landscape"),
)
CARD_ASPECTS = tuple(key for key, _z, _e in ASPECT_OPTIONS)
SOURCE_IDS = {"single_front", "multiple", "no_photo", "description", "other"}
TEXT_ONLY_SOURCES = {"no_photo", "description", "other"}
QUOTE_KINDS = {"plan_quote", "run_approval", "plan_approval"}
QUOTE_CONFIRM_IDS = {"start", "run", "always"}


def _question(qid: str, prompt: str, options: list[dict], *, multi: bool = False, page: int = 1,
              allow_other: bool = True, placeholder: str = "") -> dict:
    return {"id": qid, "prompt": prompt, "options": options, "min_selections": 1,
            "max_selections": len(options) if multi else 1, "allow_other": allow_other,
            "placeholder": placeholder, "page": page, "defaults": []}


def _attached_refs(chat_id: str = "") -> list[str]:
    from .skill_param_guard import context_from_chat
    return list(context_from_chat(chat_id or _chat_id()).uploads)


def _infer_source(refs: list[str]) -> str:
    return "multiple" if len(refs) > 1 else "single_front"


def _selected_ids(block: dict) -> set[str]:
    ids = {str(s) for s in (block.get("selected") or [])}
    for answer in (block.get("answers") or {}).values():
        if isinstance(answer, dict):
            ids.update(str(s) for s in (answer.get("selected") or []))
    return ids


def quote_confirmed(chat_id: str = "") -> bool:
    """True when a plan_quote / run_approval card was confirmed after the setup card."""
    chat_id = chat_id or _chat_id()
    setup_row, _root_block = _root(chat_id)
    seen_setup = setup_row is None
    for row in _messages(chat_id):
        if setup_row is not None and row.get("id") == setup_row.get("id"):
            seen_setup = True
        if not seen_setup:
            continue
        for block in row.get("blocks") or []:
            if (block.get("type") == "ask" and block.get("kind") in QUOTE_KINDS
                    and block.get("status") == "answered"
                    and _selected_ids(block) & QUOTE_CONFIRM_IDS):
                return True
    return False


def require_confirmed_quote(meta: dict, chat_id: str = "") -> dict | None:
    """Block a new paid dispatch until the quote/approval card is confirmed.

    Quotes (prepare / quote_route) and ledger replays of an already reserved
    submission do not need a new confirmation.
    """
    chat_id = chat_id or _chat_id()
    _, root = _root(chat_id)
    ledger = (root or {}).get(LEDGER) or {}
    if meta.get("key") in ledger:
        return None
    if quote_confirmed(chat_id):
        return None
    return _blocked("Confirm the quote/approval card before any paid generate_image; nothing submitted. / 出图前请先确认报价，未提交。")


def normalize_card(args: dict) -> dict:
    # Do not intercept approval cards or unrelated skills/cards.
    if args.get("kind") in ("run_approval", "plan_approval", "plan_quote"):
        return args
    ids = {q.get("id") for q in args.get("questions") or [] if isinstance(q, dict)}
    if not applies({}, _chat_id()) and not ids.intersection({SOURCE, ASPECT, COMPOSITIONS}):
        return args
    from .bot_asks import card_lang
    zh = card_lang() == "zh"
    chat_id = _chat_id()
    _, root = _root(chat_id)
    if root is None or (root.get("status") in {"expired", "cancelled"} and not root.get(LEDGER)):
        refs = _attached_refs(chat_id)
        aspect = _question(ASPECT, "详情页主画幅用哪个？" if zh else "Which aspect should the detail-page hero use?", [
            {"id": key, "label": z if zh else e} for key, z, e in ASPECT_OPTIONS],
            allow_other=False)
        questions = [aspect]
        if not refs:
            questions.insert(0, _question(
                SOURCE, "产品参考图怎么提供？" if zh else "How should product reference images be provided?",
                [{"id": key, "label": z if zh else e} for key, z, e in SOURCE_OPTIONS],
                placeholder="直接说明" if zh else "Describe the other situation"))
        return {"questions": questions, "page_count": 1, "allow_skip": True}
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
    plan = validate_plan(ledger.get("composition_plan"))
    q = _question(COMPOSITIONS, "选择想生成的构图（可多选，按图中编号）" if zh else
                  "Choose compositions (multiple panel numbers allowed)", [
                      {"id": panel["id"], "label": f"{panel['id']} {panel['name']}",
                       "description": panel["description"]} for panel in plan["panels"]],
                  multi=True, placeholder="输入编号 / Enter panel numbers")
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
            if any(s not in PANEL_IDS for s in raw):
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


def apply_audit_mode(args: dict, meta: dict) -> None:
    """User pixels require exact delivery; aspect fallback uses the existing ratio/min-side audit.

    Skill pins may drop width, height, or size_lock. Restore only the fields that are
    actually missing. A present but conflicting width or height is left intact so
    validate_provider_size can refuse it. Never assign both edges just because one is missing.
    """
    spec = meta["stage_spec"]
    if args.get("width") is None:
        args["width"] = spec["width"]
    if args.get("height") is None:
        args["height"] = spec["height"]
    if not args.get("ratio"):
        args["ratio"] = spec["ratio"]
    if (args.get("width"), args.get("height")) == (spec["width"], spec["height"]):
        args["size_lock"] = True
    if spec["exact_pixels"]:
        args.pop("size_lock_mode", None)
    else:
        from .skill_size import RATIO_MODE
        args["size_lock_mode"] = RATIO_MODE


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
    if source not in SOURCE_IDS or (source == "other" and not source_other):
        refs = _attached_refs(chat_id) or list(args.get("refs") or [])
        if refs and source not in SOURCE_IDS:
            source = _infer_source(refs)
        else:
            return args, _blocked("请回答来源或填写其他情况 / Answer source or describe the other scenario.")
    ledger = root.get(LEDGER) or {}
    if ledger.get("preview"):
        try:
            validate_plan(ledger.get("composition_plan"))
        except ValueError:
            blocked = _blocked("Legacy submitted composition_plan is archive/query only. Do not convert its frozen mapping, submit finals, or automatically pay again; 尚有旧计划提交记录，只能查询结果或归档，不能迁移后重付费。")
            blocked["legacy_plan_archive_only"] = True
            blocked["existing_task_ids"] = [task for entry in ledger.values() if isinstance(entry, dict)
                                            for task in (entry.get("result") or {}).get("ids", [])]
            return args, blocked
    try:
        original_description, user_final, user_preview = _user_specs(chat_id)
        card_spec = _parse_spec(aspect_other)
        if aspect_selected:
            card_spec = _merge_specs(card_spec, {"ratio": _ratio(*str(aspect_selected).split(":"))})
        if not card_spec:
            raise ValueError("请选择比例或在其他栏输入比例/像素 / Select an aspect or enter aspect/pixels in Other.")
        final_spec = _complete_spec(_merge_specs(user_final, card_spec))
        # The setup aspect controls FINALS. An explicit user preview request wins;
        # otherwise the model may choose the nine-grid layout ratio before dispatch.
        # Freeze that resolved choice on reservation, not on a pure price quote.
        frozen_preview = (ledger.get("setup_snapshot") or {}).get("preview")
        # Preview honors the answered final aspect. Agent-supplied ratio/size
        # must not override it (the 12:01 default path used 1:1 after 3:4).
        # Only an explicit user preview specification is independent.
        if user_preview:
            preview_spec = _complete_spec(user_preview)
        elif frozen_preview:
            preview_spec = copy.deepcopy(frozen_preview)
        else:
            preview_spec = _complete_spec({"ratio": final_spec["ratio"]})
        setup_snapshot = {"source": copy.deepcopy(source_answer), "aspect": copy.deepcopy(aspect_answer),
                          "final": final_spec, "preview": preview_spec,
                          "preview_request": copy.deepcopy(user_preview)}
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
    try:
        # Once dispatched, model-supplied replacements cannot renumber/reinterpret
        # the visible preview or its composition card on continuation.
        plan = validate_plan(ledger.get("composition_plan") if ledger.get("preview") else args.get("composition_plan"))
        if stage == "final" and not ledger.get("composition_plan"):
            raise ValueError("Missing persisted composition plan; reconcile the preview, do not submit paid finals.")
    except ValueError as e:
        return args, _blocked(str(e))
    old = ledger.get(key)
    if old:
        result = copy.deepcopy(old.get("result") or _blocked("Submission reserved/uncertain; reconcile existing task, never retry automatically."))
        result["multi_angle_replay"] = True
        return args, result
    from .skill_param_guard import context_from_chat, _text_of
    uploads = context_from_chat(chat_id).uploads
    refs = (list(ledger["refs"]) if "refs" in ledger else
            uploads or ([] if source in TEXT_ONLY_SOURCES else list(args.get("refs") or [])))
    if source not in TEXT_ONLY_SOURCES and not refs:
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
    apply_audit_mode(args, {"stage_spec": spec})
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
    if stage == "preview":
        view = preview_plan_view(plan)
        brief = f"Subject geometry: {view['subject_geometry']}\nThis stage: {spec['width']}x{spec['height']}, ratio {spec['ratio']}.\nPreserve reference identity, geometry and proportions. For each panel, draw only the structures visible from that panel's frozen camera; occlude surfaces that camera cannot see. The source image supplies subject identity, not a front-facing camera for every panel.\n"
    else:
        brief = f"User description (preserve; empty means image-only, use the attached subject without inventing a brief):\n{description}\nReference source: {source}; other scenario: {source_other}. Final specification: {final_spec['width']}x{final_spec['height']}, ratio {aspect}; exact user pixels={final_spec['exact_pixels']}. This stage: {spec['width']}x{spec['height']}, ratio {spec['ratio']}.\nPreserve subject identity, geometry, proportions, controls and the user's background requirements.\n"
        brief += f"Frozen composition planning context: subject={plan['subject']}; purpose={plan['purpose']}. Subject appearance: {plan['appearance']}.\n"
    if stage == "preview":
        brief += (
            "Produce ONE lineart preview image (LINEART ONLY planning sheet): a numbered 3x3 nine-panel composition grid, labels 1..9. "
            "Use thin black contour/structural lines on a plain white background; keep the interior paper-white. "
            "No color, gray fills, shading, gradients, shadows, lighting, material texture, realistic photography, "
            "clay render or 3D product rendering. The attached reference supplies identity/geometry ONLY at this stage, "
            "not its photographic finish. User material/finish requirements are deferred to finished images.\n"
            "For each panel, execute its frozen camera position, viewing direction, framing and visible surfaces/occlusions. Change the camera, not the subject pose, unless that panel explicitly requests a pose change. Keep each panel's instructions local to that panel; a close-up of an interior in one panel does not make that interior visible from another camera. "
            "An overhead plan must show the actual top-facing geometry rather than reuse the front silhouette; "
            "similarly distinguish side/rear views. Do not invent nonexistent parts to distinguish panels.\n"
            "Only structured subject geometry and numbered panel geometry are executable here. "
            "Names, purpose, original user wording and appearance are reserved for finished images, not injected into this preview. "
            "仅执行结构化主体几何与各格机位/构图，名称、用途、用户原话与外观描述保留给成品阶段。\n")
        brief += "\n".join(f"{p['id']}: {p['geometry']}" for p in view["panels"])
        brief += "\nUse exactly this panel numbering and composition plan; do not substitute generic views."
    else:
        chosen = next(p for p in plan["panels"] if p["id"] == panel)
        brief += "Restore the original subject's material, color and finish from the original reference/brief; use the lineart only for composition.\n"
        brief += (
            f"Produce ONE independent finished image, composition {panel}: {chosen['name']} — {chosen['description']}. Frozen geometry: {chosen['geometry']}. Panel appearance: {chosen['appearance']}. "
            "Match that exact numbered panel in the delivered preview. "
            "Preserve that selected panel's screen-left/right orientation, camera direction and handedness; "
            "do not mirror, horizontally flip, or reverse the composition. "
            "Infer orientation only from the selected frozen panel and its delivered preview cell; do not invent a preferred facing. "
            "No grid, panel numbers or collage.")
    args["prompt"] = brief
    args["_multi_angle"] = {"key": key, "refs": list(refs), "description": description,
                            "source": source, "aspect": aspect, "setup_snapshot": setup_snapshot, "stage_spec": spec,
                            "composition_plan": plan}
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
    try:
        plan = validate_plan(meta.get("composition_plan"))
        if ledger.get("preview") and ledger.get("composition_plan") != plan:
            raise ValueError("Composition plan changed concurrently; reconcile the frozen preview plan.")
        if key.startswith("final:") and not ledger.get("composition_plan"):
            raise ValueError("No persisted preview plan; no paid final submission allowed.")
    except ValueError as e:
        return _blocked(str(e))
    if key in ledger:
        return copy.deepcopy(ledger[key].get("result") or _blocked("Already reserved; inspect existing task, do not submit again."))
    if not ledger.get("preview"):
        ledger["composition_plan"] = plan  # unsubmitted plans may be replanned, never submitted ones
    for k in ("refs", "description", "source", "aspect", "setup_snapshot", "composition_plan"):
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
