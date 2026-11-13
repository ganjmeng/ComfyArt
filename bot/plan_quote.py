"""#235: price a multi-step paid plan and decide whether to ask before it starts.

Pure helpers. The built-in agent calls these with an injected price table, so
tests never reach WaveSpeed. External agents do not use this module (#238).
"""
from __future__ import annotations

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

Pricer = Callable[[str, dict], Awaitable[Optional[float]]]
ModelsFor = Callable[[str], Awaitable[list[tuple[str, Optional[float]]]]]
# #910: (tool, arguments) -> (routed model id, price inputs) or None. The built-in agent passes
# api.mcp_tools.canvas.quote_route, so an Auto step is named and priced as the model it will run on.
Router = Callable[[str, dict], Optional[tuple[str, dict]]]

QUOTE_TOOL = "quote_plan"

CANCEL_TEXT = {
    "zh": "已取消，没有扣费。",
    "en": "Cancelled. Nothing was charged.",
}
TOTAL_LABEL = {"zh": "总价", "en": "Total"}
ABOUT = {"zh": "约", "en": "about"}
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


def credits_label(amount_usd: float, lang: str, *, approx: bool = False) -> str:
    """#397: line / total price as UI credits. Spend 0 → 「积分 0」 / "0 credits"; no $."""
    from .run_budget import ui_credits
    n = ui_credits(amount_usd)
    lang = _lang(lang)
    if lang == "zh":
        body = f"积分 {n}" if n == 0 else f"{n} 积分"
        return f"约 {body}" if approx else body
    body = f"{n} credits"
    return f"about {body}" if approx else body


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


def canon_key(tool: str, args: dict, model: str = "") -> tuple:
    """Identity of one authorized paid call: tool + selected model + arguments, without fallback fields."""
    clean = {}
    if isinstance(args, dict):
        for k, v in args.items():
            if k in _DROP_ARG:
                continue
            clean[k] = v
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
            "lines": [{"text": ln.text, "price": ln.price} for ln in self.lines],
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


async def _price_step(step: dict, pricer: Pricer, models_for: ModelsFor,
                      router: Optional[Router] = None) -> tuple[Optional[float], bool, str, Optional[dict]]:
    """(line amount, approx, model id to show, optional model_choice). Unknown prices use the dearest model of that type.
    #910: with a router, the step is shown and priced as the model it is routed to (Auto included), with its
    reference images counted, so the card's model and price are the ones that will run."""
    tool, args, model = step["tool"], step["arguments"], step["model"]
    inputs = price_inputs(args)
    units = units_of(tool, args)
    feature = feature_of_step(tool, args)
    routed = router(tool, args) if router is not None and not step.get("svg_blocked") else None
    choice = None
    if routed and routed[0]:
        model = routed[0]
        payload = dict(routed[1] or {})
        maybe = payload.pop("_model_choice", None)
        if isinstance(maybe, dict):
            choice = maybe
        inputs = {**inputs, **{k: v for k, v in payload.items() if k in _PRICE_KEYS or k in ("images", "width", "height")}}
    approx = False
    show = model
    unit: Optional[float] = None
    if model:
        unit = await pricer(model, inputs)
        if unit is None:
            approx = True
            _fb, fb_price = await _max_model(feature, models_for)
            unit = fb_price
    else:
        approx = True
        show, unit = await _max_model(feature, models_for)
    if unit is None:
        return None, True, show, choice
    return round(float(unit) * units, 6), approx, show, choice


def _needs_ask(total: float, threshold: float, force: bool) -> bool:
    if force or threshold == 0:
        return True
    return round(total, 4) >= round(float(threshold), 4)


async def build_quote(steps: object, lang: str, *, threshold: float,
                      pricer: Pricer, models_for: ModelsFor, router: Optional[Router] = None) -> Optional[Quote]:
    """A quote for 2+ priced steps. #418: a single step gets a quote only when it needs asking
    (estimate >= threshold, threshold 0, or unpriced); otherwise None (no card, run as before)."""
    lang = _lang(lang)
    prepared = normalize_steps(steps)
    if not prepared:
        return None
    lines: list[Line] = []
    for step in prepared:
        if step.get("svg_blocked"):
            lines.append(Line(
                text=step["svg_blocked"]["message"], price=ABOUT[lang], amount=0.0, approx=True,
                unpriced=True, key=canon_key(step["tool"], step["arguments"], step["model"]),
            ))
            continue
        amount, approx, show, routed_choice = await _price_step(step, pricer, models_for, router)
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
        if unpriced:
            price = ABOUT[lang]
            amount_n = 0.0
        else:
            price = credits_label(amount or 0, lang, approx=approx)
            amount_n = float(amount or 0)
        lines.append(Line(
            text=text, price=price, amount=amount_n, approx=approx or unpriced,
            unpriced=unpriced, key=canon_key(step["tool"], step["arguments"], step["model"]),
        ))
    total = round(sum(ln.amount for ln in lines), 4)
    ask = _needs_ask(total, threshold, any(ln.unpriced for ln in lines))
    if len(lines) == 1 and not ask:
        return None
    # One estimated line makes the sum an estimate too: 「约 64 积分」 / "about 64 credits".
    from .run_budget import ui_credits
    total_text = credits_label(total, lang, approx=any(ln.approx for ln in lines))
    return Quote(
        lines=lines, total=total, n=len(lines), ask=ask, lang=lang,
        prompt=(_PROMPT_ONE if len(lines) == 1 else _PROMPT)[lang].format(
            n=len(lines), total=ui_credits(total), threshold=ui_credits(threshold),
        ),
        total_label=TOTAL_LABEL[lang], total_text=total_text,
        keys=[ln.key for ln in lines], cancel_text=CANCEL_TEXT[lang],
    )
