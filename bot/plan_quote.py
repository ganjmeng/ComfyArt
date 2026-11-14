"""#235: price a multi-step paid plan and decide whether to ask before it starts.

Pure helpers. The built-in agent calls these with an injected price table, so
tests never reach WaveSpeed. External agents do not use this module (#238).
"""
from __future__ import annotations

import inspect
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from .guide import PAID_TOOLS


def _gif():
    # Lazy: importing api at module load cycles through bot (api/__init__ -> bot -> plan_quote).
    from ..api import gif_image
    return gif_image


def _svg():
    from ..api import svg_image
    return svg_image

PriceAnswer = Optional[float] | tuple[Optional[float], str] | tuple[Optional[float], str, str]
Pricer = Callable[[str, dict], Awaitable[PriceAnswer]]
# #968: a pricer may answer a bare float (legacy exact price), `(price, source)` or
# `(price, source, reason)`; see `price_source` for the normalization.
ModelsFor = Callable[[str], Awaitable[list[tuple[str, Optional[float]]]]]
# #910: (tool, arguments) -> (routed model id, price inputs) or None. The built-in agent passes
# api.mcp_tools.canvas.quote_route, so an Auto step is named and priced as the model it will run on.
# #959: the third argument is the step's 0-based place in the quoted plan, so a per-image skill
# previews image 1..n instead of pricing every step as image 1.
Router = Callable[..., Optional[tuple[str, dict]]]

QUOTE_TOOL = "quote_plan"

# #968: the three-state price contract (api/wavespeed.py::quote_detail). `quote` is exact, `estimate`
# must be labelled 「约」 and `unpriced` shows no number and always asks.
SOURCE_QUOTE = "quote"
SOURCE_ESTIMATE = "estimate"
SOURCE_UNPRICED = "unpriced"
_SOURCES = (SOURCE_QUOTE, SOURCE_ESTIMATE, SOURCE_UNPRICED)

CANCEL_TEXT = {
    "zh": "已取消，没有扣费。",
    "en": "Cancelled. Nothing was charged.",
}
TOTAL_LABEL = {"zh": "总价", "en": "Total"}
ABOUT = {"zh": "约", "en": "about"}
# #968: the published table is the undiscounted list price. The charge is normally the price API's
# discounted price, so a fallback on it is an upper bound, not the quote. Name it on the card.
LIST_PRICE_NOTE = {"zh": "标价上限估算", "en": "list-price estimate"}
START_LABEL = {"zh": "开始", "en": "Start"}
CANCEL_LABEL = {"zh": "取消", "en": "Cancel"}
AUTO_LABEL = {"zh": "自动", "en": "Auto"}
_PROMPT = {
    # #397: credits only in the UI (1 credit = $0.01 via ui_credits); no $ sign.
    "zh": "这个任务共 {n} 步，预计约 {total} 积分，超过了你设置的 {threshold} 积分确认线。确定开始吗？",
    "en": "This task has {n} steps and will cost about {total} credits, above your {threshold} credits confirm limit. Start?",
}
# #418: a single generation at/over the confirm line gets the same card, worded for one step.
_PROMPT_ONE = {
    "zh": "这次生成预计约 {total} 积分，达到了你设置的 {threshold} 积分确认线。确定开始吗？",
    "en": "This generation will cost about {total} credits, at or above your {threshold} credits confirm limit. Start?",
}
_PRICE_KEYS = ("duration", "resolution", "aspect_ratio", "ratio", "size", "quality", "output_format", "frame_count", "frame_duration_ms")
_DROP_ARG = ("fallback", "fallback_model", "model")
_GENERIC = {"text-to-image", "image-to-image", "edit", "image-edit", "text-to-video", "image-to-video"}
_VIDEO_REF_KEYS = ("first_frame", "reference_images", "reference_videos", "motion_video", "speech_audio")

_features: Optional[dict] = None


def usd(n: float) -> str:
    """Same money text as src/usd.ts: at most 4 decimals, trailing zeros trimmed, at least 2 kept.
    Backend / logs only after #397 — the plan-quote UI uses credits_label."""
    v = float(n) if isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n) else 0.0
    text = f"{v:.4f}".rstrip("0")
    if "." not in text:
        text += "."
    whole, frac = text.split(".", 1)
    return f"{whole}.{frac.ljust(2, '0')}"


def threshold_text(n: float) -> str:
    """Legacy two-decimal USD (0.5 -> 0.50). Prefer credits_label for UI after #397."""
    v = float(n) if isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n) else 0.0
    return f"{v:.2f}"


def credits_text(n: int, lang: str, *, approx: bool = False) -> str:
    """#968: render an already-rounded credit count. Line credits are rounded once and the total is
    their sum, so the card's rows always add up to the total it shows."""
    n = int(n)
    lang = _lang(lang)
    if lang == "zh":
        body = f"积分 {n}" if n == 0 else f"{n} 积分"
        return f"约 {body}" if approx else body
    body = f"{n} credits"
    return f"about {body}" if approx else body


def credits_label(amount_usd: float, lang: str, *, approx: bool = False) -> str:
    """#397: line / total price as UI credits. Spend 0 → 「积分 0」 / "0 credits"; no $."""
    from .run_budget import ui_credits
    return credits_text(ui_credits(amount_usd), lang, approx=approx)


def price_source(answer: object) -> tuple[Optional[float], str, str]:
    """#968: normalize a pricer answer into `(amount, source, reason)`.

    A bare number is a legacy exact price. A tuple carries the three-state source and an optional
    reason. A source outside the contract (a token-billed provider's `unknown`, Replicate's
    `quote: "unknown"`) is never treated as exact: a known amount becomes an estimate and no amount
    is unpriced. An explicit unpriced answer never gets a stand-in number.
    """
    if isinstance(answer, (int, float)) and not isinstance(answer, bool):
        return float(answer), SOURCE_QUOTE, ""
    if not isinstance(answer, tuple) or len(answer) < 2:
        return None, SOURCE_UNPRICED, ""
    raw, source = answer[0], str(answer[1] or "")
    reason = str(answer[2] or "") if len(answer) > 2 else ""
    amount = (float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool)
              and math.isfinite(float(raw)) else None)
    if source not in _SOURCES:
        source = SOURCE_ESTIMATE if amount is not None else SOURCE_UNPRICED
    if source == SOURCE_UNPRICED or amount is None:
        return None, SOURCE_UNPRICED, reason
    return amount, source, reason


def _tool_features() -> dict:
    global _features
    if _features is None:
        path = Path(__file__).resolve().parent.parent / "api" / "wavespeed_models.json"
        with open(path, encoding="utf-8") as f:
            _features = json.load(f).get("tool_features") or {}
    return _features


def feature_of_step(tool: str, args: dict) -> str:
    """The feature whose price table prices this step. Generators follow the page, not the raw map."""
    if tool == "generate_image" and _gif().requests_gif(args):
        _gif().refuse_still_gif(args)  # #825: a still stops the quote; pure text GIF stays text-to-image
        return "text_to_image"
    if tool == "generate_image" and _svg().requests_svg(args):
        return "text_to_image"  # #826: SVG is t2i. Edit is refused before this is priced.
    if tool == "generate_image" and (args.get("refs") or args.get("base")):
        return "image_edit"
    if tool == "generate_video":
        if any(args.get(k) for k in _VIDEO_REF_KEYS):
            return "image_to_video"
        return "text_to_video"
    return _tool_features().get(tool, "")


def units_of(tool: str, args: dict) -> int:
    """generate_image count is N runs (the page clamps it to 1..4). Everything else is one run."""
    if tool != "generate_image":
        return 1
    if _svg().requests_svg(args):
        return 1  # #826: one SVG. A count other than 1 is refused, not billed as a batch.
    try:
        n = int(args.get("count") or 1)
    except (TypeError, ValueError):
        n = 1
    return min(4, max(1, n))


def price_inputs(args: dict) -> dict:
    """Fields that change a unit price. Count is applied outside, so num_images is not one of them."""
    out = {}
    for k in _PRICE_KEYS:
        v = args.get(k)
        if isinstance(v, (int, float, str)) and not isinstance(v, bool):
            out[k] = v
    return out


PLANNED_ANCHOR = "<planned-anchor>"  # #963: semantic slot for the packaging anchor a quote cannot name yet


def _planned_args(tool: str, args: dict, anchor: Optional[str] = None,
                  plan_position: Optional[int] = None) -> dict:
    """#963: compare a quoted step with its submit even when a ref is a future image.

    product-to-packaging images 2-4 take [product photo, anchor]. A quote made
    before image 1 exists can only name a placeholder for the anchor; the submit
    names the placed shape. This function compares that second slot semantically,
    but only for this skill and only with exactly two refs.

    `anchor=None` is the quote side (the anchor cannot exist yet): the slot is
    replaced with the plan sentinel when the step is an extension (`plan_position > 0`;
    image 1 is the anchor and stays strict, including a multi-product-ref anchor).
    A string `anchor` is the submit side: the slot is replaced **only when it is that
    placed anchor id**, so a wrong anchor, a wrong URL or a swapped order still fails
    the comparison. Ref count/order, the product photo and every other field stay strict.
    """
    if tool != "generate_image":
        return args
    from ..api.product_packaging import SKILL as packaging_skill
    if str(args.get("skill") or "") != packaging_skill:
        return args
    refs = args.get("refs")
    if not (isinstance(refs, list) and len(refs) == 2):
        return args
    if anchor is None:
        if plan_position is not None and plan_position <= 0:
            return args  # image 1 is the anchor: its refs are the product photo(s), compared strictly
    elif not anchor or str(refs[1]) != anchor:
        return args
    return {**args, "refs": [refs[0], PLANNED_ANCHOR]}


def canon_key(tool: str, args: dict, model: str = "", *, plan: bool = False,
              anchor: Optional[str] = None, plan_position: Optional[int] = None) -> tuple:
    """Identity of one authorized paid call: tool + selected model + arguments, without fallback fields.

    `plan=True` is the plan-gate comparison (#963): a packaging anchor slot that
    cannot exist yet is compared as a slot, the same on both sides. Dedupe
    (`paid_key`) keeps the strict default so two different anchors stay distinct.
    """
    clean = {}
    if isinstance(args, dict):
        for k, v in args.items():
            if k in _DROP_ARG:
                continue
            clean[k] = v
    if plan:
        clean = _planned_args(str(tool), clean, anchor, plan_position)
    picked = str(model or (args.get("model") if isinstance(args, dict) else "") or "")
    blob = json.dumps(clean, sort_keys=True, ensure_ascii=False, default=str)
    return (str(tool), picked, blob)


def model_label(model_id: str) -> str:
    if not model_id:
        return ""
    try:
        from ..api.wavespeed import display_of, short_label
        shown = display_of(model_id)
        if shown and shown.get("name"):
            return str(shown["name"])
        return short_label(model_id)
    except Exception:
        parts = [p for p in str(model_id).split("/") if p]
        while len(parts) > 1 and parts[-1] in _GENERIC:
            parts.pop()
        return " ".join(parts) or str(model_id)


def _lang(lang: str) -> str:
    return "zh" if lang == "zh" else "en"


@dataclass
class Line:
    text: str
    price: str
    amount: float
    approx: bool
    unpriced: bool
    key: tuple
    # #909: paid units this line authorizes (generate_image count, 1 otherwise).
    units: int = 1
    # #968: the three-state price source (`quote` | `estimate` | `unpriced`) survives from
    # api.wavespeed.quote_detail, so an estimate can never render as an exact price. `reason` names
    # the fallback (e.g. `list_price` = undiscounted published table, an upper bound), `credits` is the
    # rounded amount this line shows.
    source: str = SOURCE_QUOTE
    reason: str = ""
    credits: int = 0


@dataclass
class Quote:
    lines: list[Line]
    total: float
    n: int
    ask: bool
    lang: str
    prompt: str
    total_label: str
    total_text: str
    keys: list[tuple]
    cancel_text: str
    # #909: sum of the lines' paid units; the paid-guard cap follows this when
    # the user did not name a whole-group count.
    units: int = 0
    # #968: the total the card shows is the sum of the per-line rounded credits, so line and total
    # can never disagree. `total` above stays the exact USD sum used by the confirm threshold.
    total_credits: int = 0

    def ask_spec(self) -> dict:
        lang = _lang(self.lang)
        return {
            "prompt": self.prompt,
            "options": [
                {"id": "start", "label": START_LABEL[lang]},
                {"id": "cancel", "label": CANCEL_LABEL[lang]},
            ],
            "min_selections": 1,
            "max_selections": 1,
            "allow_other": False,
            "kind": "plan_quote",
            "lines": [{"text": ln.text, "price": ln.price, "source": ln.source} for ln in self.lines],
            "total_label": self.total_label,
            "total": self.total_text,
        }

    def started_result(self) -> str:
        """No prices: the card already showed them, and an under-threshold start shows none."""
        return json.dumps({"ok": True, "start": True}, ensure_ascii=False)


def normalize_steps(raw: object) -> list[dict]:
    """Paid steps only. A fallback step is dropped; a fallback model is not priced."""
    if not isinstance(raw, list):
        return []
    out = []
    for step in raw:
        if not isinstance(step, dict) or step.get("fallback") is True:
            continue
        tool = str(step.get("tool") or "")
        if tool not in PAID_TOOLS:
            continue
        args = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
        args = {k: v for k, v in args.items() if k not in ("fallback", "fallback_model")}
        model = str(step.get("model") or args.get("model") or "")
        blob = f"{args.get('prompt') or ''} {step.get('text') or ''}"
        merged = {**args, "prompt": blob}
        if tool == "generate_image" and _svg().requests_svg(merged):
            blocked = _svg().block_reason(merged)
            if blocked:
                out.append({
                    "text": str(step.get("text") or "").strip(),
                    "tool": tool,
                    "model": "",
                    "arguments": args,
                    "svg_blocked": blocked,
                })
                continue
            if not merged.get("prompt"):
                merged["prompt"] = str(step.get("text") or "")
            args = _svg().ensure_args(merged)
            model = _svg().pick_t2i(model)
            args["model"] = model
        elif tool == "generate_image" and _gif().requests_gif({**args, "prompt": blob}):
            base = dict(args)
            if not base.get("prompt"):
                base["prompt"] = str(step.get("text") or "")
            if not _gif().requests_gif(base):
                base["output_format"] = "gif"
            _gif().refuse_still_gif(base)  # before ensure/price: no quote for a still GIF
            args = _gif().ensure_args(base)
            model = _gif().pick_t2i(model)
            args["model"] = model
        out.append({
            "text": str(step.get("text") or "").strip(),
            "tool": tool,
            "model": model,
            "arguments": args,
        })
    return out


def _quote_choice(step: dict, router: Optional[Router]) -> Optional[dict]:
    """#953: model_choice for quote-card copy (skill / Auto / user-named). Display only."""
    args = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
    tool = str(step.get("tool") or "")
    if not tool:
        return None
    try:
        from ..api.mcp_tools.canvas import select_model
        return select_model(tool, dict(args))
    except Exception:
        return None


async def _max_model(feature: str, models_for: ModelsFor) -> tuple[str, Optional[float]]:
    rows = await models_for(feature) if feature else []
    best_id, best = "", None
    for mid, price in rows:
        if not isinstance(price, (int, float)) or isinstance(price, bool):
            continue
        if best is None or float(price) > best:
            best_id, best = str(mid), float(price)
    return best_id, best


def _route(router: Router, tool: str, args: dict, position: int):
    """Call a router with the step's plan position; older routers take (tool, args) only."""
    try:
        takes = "position" in inspect.signature(router).parameters
    except (TypeError, ValueError):
        takes = False
    return router(tool, args, position=position) if takes else router(tool, args)


def _plan_positions(steps: list[dict]) -> list[int]:
    """0-based place of each step among the earlier steps of the same tool + skill (#959).

    A per-image skill (product-to-packaging) puts all its images in one plan; the quote must
    walk that sequence (image 1, then 2..n) instead of previewing every step as image 1.
    This is computed per quote build and never executes anything, so repeating the quote
    starts again from the turn's real next place.
    """
    seen: dict[tuple[str, str], int] = {}
    out: list[int] = []
    for step in steps:
        args = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
        key = (str(step.get("tool") or ""), str(args.get("skill") or ""))
        at = seen.get(key, 0)
        out.append(at)
        seen[key] = at + 1
    return out


@dataclass
class _StepPrice:
    """#968: one priced step; `source`/`reason` are the price contract from the pricer."""
    amount: Optional[float]
    approx: bool
    show: str
    choice: Optional[dict]
    blocked: Optional[dict]
    units: int
    source: str = SOURCE_QUOTE
    reason: str = ""


async def _price_step(step: dict, pricer: Pricer, models_for: ModelsFor,
                      router: Optional[Router] = None, position: int = 0) -> _StepPrice:
    """(line amount, approx, model id to show, optional model_choice for the quote copy,
    optional param-block, paid units, source, reason). Unknown prices use the dearest model of that type.
    #910: with a router, the step is shown and priced as the model it is routed to (Auto included), with its
    reference images counted, so the card's model and price are the ones that will run.
    #959: `position` is the step's place in the quoted plan (see _plan_positions).
    #968: the pricer's source is carried through; an `estimate` line is marked 约 and an explicit
    `unpriced` answer never borrows another model's number."""
    tool, args, model = step["tool"], step["arguments"], step["model"]
    inputs = price_inputs(args)
    units = units_of(tool, args)
    feature = feature_of_step(tool, args)
    routed = _route(router, tool, args, position) if router is not None and not step.get("svg_blocked") else None
    choice = None
    if routed and isinstance(routed, tuple) and (routed[1] or {}).get("param_blocked"):
        # #956 / #957: do not price a silent text-to-image fallback when required params are missing.
        return _StepPrice(None, True, "", None, routed[1]["param_blocked"], 0, SOURCE_UNPRICED, "param_blocked")
    if routed and routed[0]:
        model = routed[0]
        payload = dict(routed[1] or {})
        # #953: the routed choice carries the quote-card source (skill / Auto / user-named).
        maybe = payload.pop("_model_choice", None)
        if isinstance(maybe, dict):
            choice = maybe
        inputs = {**inputs, **{k: v for k, v in payload.items() if k in _PRICE_KEYS or k in ("images", "width", "height")}}
        # #956 / #957: units follow the validated args (e.g. packaging/portrait lock count to 1).
        if "count" in payload or "n" in payload:
            units = units_of(tool, {**args, **{k: payload[k] for k in ("count", "n") if k in payload}})
    approx = False
    show = model
    source, reason = SOURCE_QUOTE, ""
    amount: Optional[float] = None
    if model:
        answer = await pricer(model, inputs)
        amount, source, reason = price_source(answer)
        if amount is None and answer is None:
            # #235 legacy: a pricer with no answer at all prices the dearest model of that type, labelled 约.
            # #968: an explicit `(None, "unpriced")` answer is honored — no stand-in number for a known tier.
            approx = True
            _fb, fb_price = await _max_model(feature, models_for)
            amount = fb_price
            source = SOURCE_ESTIMATE if fb_price is not None else SOURCE_UNPRICED
            reason = "dearest_model"
    else:
        approx = True
        show, amount = await _max_model(feature, models_for)
        source = SOURCE_ESTIMATE if amount is not None else SOURCE_UNPRICED
        reason = "dearest_model"
    if amount is None:
        return _StepPrice(None, True, show, choice, None, units, SOURCE_UNPRICED, reason)
    return _StepPrice(round(float(amount) * units, 6),
                      approx or source == SOURCE_ESTIMATE, show, choice, None, units, source, reason)


def _needs_ask(total: float, threshold: float, force: bool) -> bool:
    if force or threshold == 0:
        return True
    return round(total, 4) >= round(float(threshold), 4)


async def build_quote(steps: object, lang: str, *, threshold: float,
                      pricer: Pricer, models_for: ModelsFor, router: Optional[Router] = None) -> Optional[Quote]:
    """A quote for 2+ priced steps. #418: a single step gets a quote only when it needs asking
    (estimate >= threshold, threshold 0, or unpriced); otherwise None (no card, run as before)."""
    lang = _lang(lang)
    from .run_budget import ui_credits
    prepared = normalize_steps(steps)
    if not prepared:
        return None
    lines: list[Line] = []
    positions = _plan_positions(prepared)
    for step, position in zip(prepared, positions):
        if step.get("svg_blocked"):
            lines.append(Line(
                text=step["svg_blocked"]["message"], price=ABOUT[lang], amount=0.0, approx=True,
                unpriced=True, key=canon_key(step["tool"], step["arguments"], step["model"], plan=True, plan_position=position),
                units=0, source=SOURCE_UNPRICED, reason="svg_blocked",
            ))
            continue
        priced = await _price_step(step, pricer, models_for, router, position)
        show, routed_choice, blocked, units = priced.show, priced.choice, priced.blocked, priced.units
        if blocked:
            # #956 / #957: required params are missing; name the real refusal and price nothing.
            lines.append(Line(
                text=str(blocked.get("error") or blocked.get("user_message") or ""),
                price=ABOUT[lang], amount=0.0, approx=True, unpriced=True,
                key=canon_key(step["tool"], step["arguments"], "", plan=True, plan_position=position),
                units=0, source=SOURCE_UNPRICED, reason="param_blocked",
            ))
            continue
        amount, approx, source, reason = priced.amount, priced.approx, priced.source, priced.reason
        unpriced = amount is None
        name = step["text"] or step["tool"]
        label = model_label(show) if show else AUTO_LABEL[lang]
        choice = routed_choice or _quote_choice(step, router)
        routed_id = str((choice or {}).get("edit_model") or (choice or {}).get("model") or "")
        if choice and (not show or routed_id == str(show)):
            from ..api.auto_models import quote_model_copy
            copied = quote_model_copy(choice, show or "", lang)
            if copied:
                label = copied
        text = f"{name} · {label}" if label else name
        if step["tool"] == "generate_image" and _gif().requests_gif(step["arguments"]):
            text = f"{text} · {_gif().gif_quote_label(step['arguments'].get('frame_count'), step['arguments'].get('frame_duration_ms'))}"
        if step["tool"] == "generate_image" and _svg().requests_svg(step["arguments"]):
            text = f"{text} · SVG · n=1"
        # #968: an undiscounted list-price fallback is an upper bound, not this run's price.
        if source == SOURCE_ESTIMATE and reason == "list_price":
            text = f"{text} · {LIST_PRICE_NOTE[lang]}"
        if unpriced:
            price = ABOUT[lang]
            amount_n = 0.0
            credits = 0
        else:
            # #968: round once per line; the total below is the sum of these, never a re-rounding of USD.
            credits = ui_credits(amount)
            price = credits_text(credits, lang, approx=approx)
            amount_n = float(amount or 0)
        lines.append(Line(
            text=text, price=price, amount=amount_n, approx=approx or unpriced,
            unpriced=unpriced, key=canon_key(step["tool"], step["arguments"], step["model"], plan=True, plan_position=position),
            units=units, source=source, reason=reason, credits=credits,
        ))
    total = round(sum(ln.amount for ln in lines), 4)
    ask = _needs_ask(total, threshold, any(ln.unpriced for ln in lines))
    if len(lines) == 1 and not ask:
        return None
    # One estimated line makes the sum an estimate too: 「约 64 积分」 / "about 64 credits".
    # #968: the displayed total is the sum of the line credits (not ui_credits(sum of USD)), so the rows
    # and the total can never disagree: 4 x 0.115 is 12+12+12+12 = 48, not ceil(0.46) = 46/47.
    total_credits = sum(ln.credits for ln in lines)
    total_text = credits_text(total_credits, lang, approx=any(ln.approx for ln in lines))
    return Quote(
        lines=lines, total=total, n=len(lines), ask=ask, lang=lang,
        prompt=(_PROMPT_ONE if len(lines) == 1 else _PROMPT)[lang].format(
            n=len(lines), total=total_credits, threshold=ui_credits(threshold),
        ),
        total_label=TOTAL_LABEL[lang], total_text=total_text,
        keys=[ln.key for ln in lines], cancel_text=CANCEL_TEXT[lang],
        units=sum(ln.units for ln in lines), total_credits=total_credits,
    )
