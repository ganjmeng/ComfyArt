"""#826: GPT Image 2.6 text-to-image SVG. One image. Edit is not supported.

The quote is the existing still cell plus SVG_ADDON_USD ($0.02).
Medium 1k is 0.05 + 0.02 = 0.07. That sum is the published still table, not a new vendor price.
This module never opens a socket, reads a local path from the SVG, or calls WaveSpeed.

Preview is a local PNG (rect, circle, ellipse, polygon, path). Raw SVG is never the preview.
Empty, non-SVG, and invalid XML are rejected. Only a document that passes the
security checks and then cannot be drawn keeps its original bytes.
"""
from __future__ import annotations

import re

from .gif_image import FLARE_T2I, SUNBURST_T2I, documented_usd
from .svg_raster import (
    LIMITS, PREVIEW_FAILED, REJECTED, admit, isolated_admit, looks_like_svg, raster_audit, read_limited,
)

FLARE = FLARE_T2I
SUNBURST = SUNBURST_T2I
SVG_ADDON_USD = 0.02

_SVG_RE = re.compile(r"(?<![A-Za-z0-9])svgs?(?![A-Za-z0-9])", re.I)
_VIDEO = {"text_to_video", "image_to_video", "reference_to_video", "motion_control", "lip_sync", "animate_image"}
# Readable copy. No vendor name (#712). Kept in lockstep with src/locales wsErr.svg*.
USER = {
    "rejected": REJECTED,
    "edit": {
        "zh": "SVG 只支持文生图，一次一张，不能从编辑或参考图生成。",
        "en": "SVG is text-to-image only, one image at a time. Edit and reference images are not supported.",
    },
    "count": {
        "zh": "SVG 一次只能生成 1 张。",
        "en": "SVG can only generate 1 image at a time.",
    },
    "preview_failed": PREVIEW_FAILED,
}
NOTE = {
    "zh": "矢量 SVG，显式使用 GPT Image 2.6 文生，一次一张。不改全局默认模型。价格是同档静图再加 $0.02（沿用既有静图价，不是新核价）。",
    "en": "Vector SVG explicitly uses GPT Image 2.6 text-to-image, one image. This does not change the global default model. Price is the still price plus $0.02 (existing still table, not a new price check).",
}


def _line(pair: dict) -> str:
    return f"{pair['zh']} / {pair['en']}"


def audit() -> dict:
    """Raster controls plus the local price note. Network namespace may be unavailable; that is recorded, not implied."""
    info = raster_audit()
    info["addon_usd"] = SVG_ADDON_USD
    info["medium_1k_usd"] = 0.07
    info["price_basis"] = "existing still cell + 0.02; medium 1k 0.07 is that sum, not a new vendor price"
    return info


def _fmt(inputs: dict) -> str:
    params = inputs.get("params") if isinstance(inputs.get("params"), dict) else {}
    return str(params.get("output_format") or inputs.get("output_format") or "").lower()


def prompt_wants_svg(text: str) -> bool:
    if any(w in (text or "") for w in ("矢量", "可编辑路径", "可編輯路徑")):
        return True
    return _SVG_RE.search(text or "") is not None


def requests_svg(inputs: dict) -> bool:
    """Explicit svg wins. Otherwise the prompt, unless a GIF format or GIF wording already owns it."""
    if not isinstance(inputs, dict):
        return False
    fmt = _fmt(inputs)
    if fmt:
        return fmt == "svg"
    from .gif_image import requests_gif
    if requests_gif(inputs):
        return False
    return prompt_wants_svg(str(inputs.get("prompt") or ""))


def _exact_one(value) -> bool:
    """True only for an exact integer 1. Floats such as 1.5 and 1.0 are rejected, not truncated."""
    if value is None or value == "":
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip() == "1"
    return False


def _count_ok(inputs: dict) -> bool:
    params = inputs.get("params") if isinstance(inputs.get("params"), dict) else {}
    for source in (inputs, params):
        if not isinstance(source, dict):
            continue
        for key in ("count", "n", "num_images"):
            if key in source and not _exact_one(source[key]):
                return False
    return True


def _block(code: str) -> dict:
    pair = USER[code]
    kind = {"edit": "svgEdit", "count": "svgCount"}[code]
    return {"code": code, "kind": kind, "reason": pair, "message": _line(pair)}


def block_reason(inputs: dict) -> dict | None:
    """Edit, references, video, and n≠1 never become a text-to-image SVG job."""
    if not requests_svg(inputs):
        return None
    feature = str(inputs.get("feature") or "")
    model = str(inputs.get("model") or "")
    refs = inputs.get("refs") or inputs.get("images") or inputs.get("image") or inputs.get("base") or inputs.get("mask")
    if feature in _VIDEO or "video" in feature or feature == "image_edit" or model.endswith("/edit") or refs:
        return _block("edit")
    if not _count_ok(inputs):
        return _block("count")
    return None


def pick_t2i(model: str | None) -> str:
    """2.6-sunburst text-to-image only when that family was named. Otherwise 2.6-flare text-to-image. Never an edit id."""
    m = str(model or "")
    if "2.6-sunburst" in m and not m.endswith("/edit"):
        return SUNBURST
    return FLARE


def ensure_args(args: dict) -> dict:
    """Fill output_format=svg and n=1. Does not set quality or complexity. No-op when blocked."""
    if not isinstance(args, dict) or not requests_svg(args) or block_reason(args):
        return args
    out = dict(args)
    params = dict(out.get("params") or {}) if isinstance(out.get("params"), dict) else {}
    params["output_format"] = "svg"
    params.pop("frame_count", None)
    params.pop("frame_duration_ms", None)
    out["params"] = params
    out["output_format"] = "svg"
    out["count"] = 1
    out["n"] = 1
    return out


def route(inputs: dict) -> dict:
    """Text-to-image on 2.6, output_format=svg, n=1. A blocked job returns svg_error and is not rewritten."""
    if not isinstance(inputs, dict) or not requests_svg(inputs):
        return inputs
    blocked = block_reason(inputs)
    if blocked:
        return {**inputs, "svg_error": blocked}
    out = dict(inputs)
    out["feature"] = "text_to_image"
    out["model"] = pick_t2i(out.get("model"))
    params = dict(out.get("params") or {}) if isinstance(out.get("params"), dict) else {}
    params["output_format"] = "svg"
    params.pop("frame_count", None)
    params.pop("frame_duration_ms", None)
    out["params"] = params
    out["output_format"] = "svg"
    out["count"] = 1
    out["n"] = 1
    out["svg_route"] = "text_to_image"
    out["svg_note"] = _line(NOTE)
    return out


def choice(model: str | None) -> dict:
    picked = pick_t2i(model)
    named = bool(model) and str(model) == picked
    reason = dict(NOTE)
    if model and str(model) != picked:
        reason = {
            "zh": f"{model} 不能出 SVG，已改用 {picked}。{NOTE['zh']}",
            "en": f"{model} cannot emit SVG, so {picked} is used. {NOTE['en']}",
        }
    return {"model": picked, "auto": not named, "category": "svg", "reason": reason, "svg_route": "text_to_image", "n": 1}


def local_usd(model: str, quality: str = "medium", resolution: str = "1k") -> float | None:
    """Still cell + $0.02. None when that cell is not in the existing table. No network."""
    still = documented_usd(model, quality, resolution)
    if still is None:
        return None
    return round(float(still) + SVG_ADDON_USD, 4)


def has_svg(schema: dict | None) -> bool:
    props = schema.get("properties") if isinstance(schema, dict) else None
    enum = ((props or {}).get("output_format") or {}).get("enum") or []
    return "svg" in [str(x).lower() for x in enum]
