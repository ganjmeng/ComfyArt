"""#825: GPT Image 2.6-flare is the Auto / feature default for text-to-image and image edit.

An explicit 2.5-flare id still routes to 2.5. This module does not pin quality.

GIF is text-to-image only (WaveSpeed docs, 2026-11-08): edit output_format is png/jpeg/webp.
A still image therefore becomes a reference plus a new text-to-image GIF. Frame count is not billed;
a GIF costs the same as a still of that quality and resolution. No live WaveSpeed submit in this module.
"""
from __future__ import annotations

import re

FLARE_T2I = "openai/gpt-image-2.6-flare/text-to-image"
SUNBURST_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
FLARE_EDIT = "openai/gpt-image-2.6-flare/edit"
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"
FLARE_25_T2I = "openai/gpt-image-2.5-flare/text-to-image"
GIF_T2I = (FLARE_T2I, SUNBURST_T2I)
GIF_EDIT = (FLARE_EDIT, SUNBURST_EDIT)

# (min, max, default). Docs: frame_count 2–16 default 9; frame_duration_ms 20–2000 default 200.
FRAME_COUNT = (2, 16, 9)
FRAME_MS = (20, 2000, 200)
COMPLEXITY = ("low", "medium", "high")

# Tech lock 2026-11-08. Medium 1k stills. GIF uses the same cell; frames are not a multiplier.
STILL_MEDIUM_1K = {
    FLARE_25_T2I: 0.024,
    FLARE_T2I: 0.05,
    SUNBURST_T2I: 0.05,
}

# Published 2.6 text-to-image table (quality, resolution) -> USD. Same for flare and sunburst.
# https://wavespeed.ai/models/openai/gpt-image-2.6-flare/text-to-image
TABLE_26 = {
    ("low", "1k"): 0.03, ("low", "2k"): 0.06, ("low", "4k"): 0.10,
    ("medium", "1k"): 0.05, ("medium", "2k"): 0.10, ("medium", "4k"): 0.18,
    ("high", "1k"): 0.06, ("high", "2k"): 0.12, ("high", "4k"): 0.21,
    ("xhigh", "1k"): 0.11, ("xhigh", "2k"): 0.21, ("xhigh", "4k"): 0.38,
    ("max", "1k"): 0.25, ("max", "2k"): 0.47, ("max", "4k"): 0.85,
}

# Fields sent to the price API. Frame timing is shown on the confirm line and then dropped so it cannot be billed.
UNBILLED = ("frame_count", "frame_duration_ms")

_GIF_RE = re.compile(r"(?<![A-Za-z])gifs?(?![A-Za-z])", re.I)
_VIDEO_FEATURES = {"text_to_video", "image_to_video", "reference_to_video", "motion_control", "lip_sync", "animate_image"}


def clamp_int(value, bounds: tuple[int, int, int]) -> int:
    lo, hi, default = bounds
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return min(hi, max(lo, n))


def gif_params(frame_count=None, frame_duration_ms=None) -> dict:
    return {
        "output_format": "gif",
        "frame_count": clamp_int(frame_count, FRAME_COUNT),
        "frame_duration_ms": clamp_int(frame_duration_ms, FRAME_MS),
    }


def prompt_wants_gif(text: str) -> bool:
    """User asked for a GIF / 动图. 'gift' does not count."""
    if any(w in text for w in ("动图", "动态图")):
        return True
    return _GIF_RE.search(text or "") is not None


def _fmt(inputs: dict) -> str:
    params = inputs.get("params") if isinstance(inputs.get("params"), dict) else {}
    return str(params.get("output_format") or inputs.get("output_format") or "").lower()


def wants_gif(inputs: dict) -> bool:
    return _fmt(inputs) == "gif"


def requests_gif(inputs: dict) -> bool:
    """Explicit gif, unless a different output_format was set. Otherwise the prompt."""
    fmt = _fmt(inputs)
    if fmt:
        return fmt == "gif"
    return prompt_wants_gif(str(inputs.get("prompt") or ""))


def ensure_args(args: dict) -> dict:
    """Fill GIF defaults on a generate_image call. Does not set quality or complexity."""
    if not isinstance(args, dict) or not requests_gif(args):
        return args
    out = dict(args)
    params = dict(out.get("params") or {}) if isinstance(out.get("params"), dict) else {}
    spec = gif_params(params.get("frame_count", out.get("frame_count")), params.get("frame_duration_ms", out.get("frame_duration_ms")))
    params.update(spec)
    out["params"] = params
    out["output_format"] = "gif"
    out["frame_count"] = spec["frame_count"]
    out["frame_duration_ms"] = spec["frame_duration_ms"]
    return out


def pick_t2i(model: str | None) -> str:
    """2.6-sunburst when the user named that family; otherwise 2.6-flare. Never 2.5."""
    m = str(model or "")
    if "2.6-sunburst" in m:
        return SUNBURST_T2I
    return FLARE_T2I


def _props(schema: dict | None) -> dict:
    if not isinstance(schema, dict):
        return {}
    props = schema.get("properties")
    return props if isinstance(props, dict) else {}


def has_gif(schema: dict | None) -> bool:
    return "gif" in [str(x).lower() for x in (_props(schema).get("output_format") or {}).get("enum") or []]


def note(route: str) -> dict:
    if route == "edit":
        return {
            "zh": "编辑模型已支持 gif，按编辑出循环 GIF。帧数不计费，价格与同档静图相同。",
            "en": "Edit supports gif, so this looping GIF is an edit. Frame count is not billed; the price matches the still.",
        }
    if route == "reference_t2i":
        # Official t2i request fields have no image/images/reference parameter
        # (https://wavespeed.ai/docs/docs-api/openai/openai-gpt-image-2.6-flare-text-to-image, read 2026-11-08).
        # The still URL is not posted. Do not switch this job to a video model.
        return {
            "zh": "GIF 只在文生图上可用。编辑模型没有 gif，不会改走视频。公开文生参数没有参考图字段，这张静图的地址不会送进请求；请在提示词里描述画面。帧数不计费，价格与同档静图相同。未点名模型时用 GPT Image 2.6 Flare。",
            "en": "GIF is text-to-image only. Edit has no gif, and this does not use a video model. The published text-to-image parameters have no reference-image field, so this still's URL is not sent; describe the picture in the prompt. Frame count is not billed; the price matches the still. An unnamed model uses GPT Image 2.6 Flare.",
        }
    return {
        "zh": "循环 GIF，用 GPT Image 2.6 文生。帧数不计费，价格与同档静图相同。未点名模型时文生和编辑用 GPT Image 2.6 Flare。",
        "en": "Looping GIF from GPT Image 2.6 text-to-image. Frame count is not billed; the price matches the still. An unnamed model uses GPT Image 2.6 Flare for images and edits.",
    }


def note_line(route: str) -> str:
    pair = note(route)
    return f"{pair['zh']} / {pair['en']}"


def choice(model: str, has_still: bool) -> dict:
    """Agent Auto row for a GIF. Does not return an edit_model or a video model."""
    picked = pick_t2i(model)
    named = bool(model) and model == picked
    route = "reference_t2i" if has_still else "text_to_image"
    reason = note(route)
    if model and model != picked:
        reason = {
            "zh": f"{model} 不能出 GIF，已改用 {picked}。{reason['zh']}",
            "en": f"{model} cannot emit a GIF, so {picked} is used. {reason['en']}",
        }
    return {"model": picked, "auto": not named, "category": "gif", "reason": reason, "gif_route": route}


def _refs(inputs: dict) -> list:
    refs = []
    for value in [inputs.get("image"), inputs.get("base"), *(inputs.get("images") if isinstance(inputs.get("images"), list) else [])]:
        if value and value not in refs:
            refs.append(value)
    return refs


def route_gif(inputs: dict, schemas: dict | None = None) -> dict:
    """Rewrite a GIF job onto a model that can emit gif. Never leaves it on a video feature.

    schemas: model id -> request schema (with a properties map). Missing schema means
    edit cannot emit gif (the checked docs), so a still uses reference + text-to-image.
    """
    if not requests_gif(inputs):
        return inputs
    schemas = schemas or {}
    out = dict(inputs)
    params = dict(out.get("params") or {}) if isinstance(out.get("params"), dict) else {}
    spec = gif_params(params.get("frame_count", out.get("frame_count")), params.get("frame_duration_ms", out.get("frame_duration_ms")))
    params.update(spec)
    out["params"] = params
    out["output_format"] = "gif"
    # Top-level copies stay equal to params so quote/confirm and the POST use one clamped count.
    out["frame_count"] = spec["frame_count"]
    out["frame_duration_ms"] = spec["frame_duration_ms"]
    feature = str(out.get("feature") or "text_to_image")
    video = feature in _VIDEO_FEATURES or "video" in feature
    refs = _refs(out)
    edit_model = None
    if refs and not video:
        named = str(out.get("model") or "")
        candidates = []
        if named.endswith("/edit"):
            candidates.append(named)
        candidates.extend([FLARE_EDIT, SUNBURST_EDIT])
        for cand in candidates:
            if has_gif(schemas.get(cand)):
                edit_model = cand
                break
    if edit_model:
        out["feature"] = "image_edit"
        out["model"] = edit_model
        out["gif_route"] = "edit"
    else:
        out["feature"] = "text_to_image"
        out["model"] = pick_t2i(None if video else out.get("model"))
        if refs:
            out["images"] = refs
            out["gif_route"] = "reference_t2i"
        else:
            out["gif_route"] = "text_to_image"
    out["gif_note"] = note_line(out["gif_route"])
    return out


def billable(priced: dict) -> dict:
    """Price-API body. Frame count and frame duration are not billed."""
    return {k: v for k, v in priced.items() if k not in UNBILLED}


def documented_usd(model: str, quality: str = "medium", resolution: str = "1k") -> float | None:
    """Published still price for the quote stub. None when this cell is not in the lock table.

    GIF uses the same number. Callers must not multiply by frame_count.
    """
    q = str(quality or "medium").lower()
    res = str(resolution or "1k").lower()
    if model == FLARE_25_T2I and q == "medium" and res == "1k":
        return STILL_MEDIUM_1K[FLARE_25_T2I]
    if model in GIF_T2I:
        return TABLE_26.get((q, res))
    return None


def gif_quote_label(frame_count, frame_duration_ms) -> str:
    spec = gif_params(frame_count, frame_duration_ms)
    return f"GIF {spec['frame_count']}×{spec['frame_duration_ms']}ms"
