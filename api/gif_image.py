"""#825: GPT Image 2.6-flare is the Auto / feature default for text-to-image and image edit.

An explicit 2.5-flare id still routes to 2.5. This module does not pin quality.

A pure text-to-image GIF stays on 2.6 text-to-image. A GIF that also carries a still
(image, images, refs, or base) is refused before any quote or provider POST.
That refusal is not a still-to-GIF implementation: the published text-to-image schema
has no reference field (docs read 2026-11-08). Frame count is not billed.
No live WaveSpeed submit in this module.
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


def asked_int(value) -> int | None:
    """A whole number the caller actually sent. Missing or non-integers are not an original value."""
    if isinstance(value, bool) or not isinstance(value, int):
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            return int(value.strip())
        return None
    return value


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


class StillGifUnsupported(Exception):
    """GIF plus a still. Raised before any price call or generation POST.

    This is a refusal. It does not implement still-to-GIF.
    """


# Readable in both languages. Quoting and generation do not start.
REFUSAL_ZH = "静图转 GIF 不支持参考图，估价和生成都不会开始。请去掉参考图、底图或图片列表后再做纯文生 GIF，或在提示词里描述画面。"
REFUSAL_EN = "Still-to-GIF does not support a reference image, so quoting and generation do not start. Remove the reference, base image, or image list and use a text-only GIF, or describe the picture in the prompt."

# Tech named base in addition to refs and images. Scalars and lists are both stills.
_STILL_SCALARS = ("image", "base", "reference_image", "last_image", "markup_image", "mask_image")
_STILL_LISTS = ("images", "refs", "reference_images")


def refusal_text() -> str:
    return f"{REFUSAL_ZH} / {REFUSAL_EN}"


def _filled(value) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return any(_filled(item) for item in value)
    if isinstance(value, dict):
        return any(_filled(item) for item in value.values())
    return bool(value)


def still_fields(inputs: dict) -> list[str]:
    """Names of attached stills: image, images, refs, base, and the same keys under params."""
    if not isinstance(inputs, dict):
        return []
    bags = [inputs]
    params = inputs.get("params")
    if isinstance(params, dict):
        bags.append(params)
    found: list[str] = []
    for bag in bags:
        for key in (*_STILL_SCALARS, *_STILL_LISTS):
            if key in bag and _filled(bag.get(key)) and key not in found:
                found.append(key)
    return found


def has_still(inputs: dict) -> bool:
    return bool(still_fields(inputs))


def refuse_still_gif(inputs: dict) -> None:
    """Stop a GIF that carries a still. Pure text-to-image GIF is left alone."""
    if isinstance(inputs, dict) and requests_gif(inputs) and has_still(inputs):
        raise StillGifUnsupported(refusal_text())


def still_block(inputs: dict) -> dict | None:
    """Agent-facing refusal. None when the call may continue. No quote and no submit."""
    if not isinstance(inputs, dict) or not requests_gif(inputs) or not has_still(inputs):
        return None
    text = refusal_text()
    return {
        "status": "failed",
        "generation_succeeded": False,
        "submitted": False,
        "error": text,
        "kind": "gifStillUnsupported",
        "user_message": text,
    }


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
        # Kept only so an old caller cannot describe a drop-and-continue path.
        # route_gif raises StillGifUnsupported instead of posting a text-only GIF.
        return {"zh": REFUSAL_ZH, "en": REFUSAL_EN}
    return {
        "zh": "循环 GIF，用 GPT Image 2.6 文生。帧数不计费，价格与同档静图相同。未点名模型时文生和编辑用 GPT Image 2.6 Flare。",
        "en": "Looping GIF from GPT Image 2.6 text-to-image. Frame count is not billed; the price matches the still. An unnamed model uses GPT Image 2.6 Flare for images and edits.",
    }


def note_line(route: str) -> str:
    pair = note(route)
    return f"{pair['zh']} / {pair['en']}"


def choice(model: str, has_still_image: bool) -> dict:
    """Agent Auto row for a GIF. A still is a refusal, not a text-to-image rewrite."""
    if has_still_image:
        return {
            "model": "",
            "auto": True,
            "category": "gif_still_unsupported",
            "blocked": True,
            "reason": {"zh": REFUSAL_ZH, "en": REFUSAL_EN},
        }
    picked = pick_t2i(model)
    named = bool(model) and model == picked
    route = "text_to_image"
    reason = note(route)
    if model and model != picked:
        reason = {
            "zh": f"{model} 不能出 GIF，已改用 {picked}。{reason['zh']}",
            "en": f"{model} cannot emit a GIF, so {picked} is used. {reason['en']}",
        }
    return {"model": picked, "auto": not named, "category": "gif", "reason": reason, "gif_route": route}


def route_gif(inputs: dict, schemas: dict | None = None) -> dict:
    """Rewrite a pure text GIF onto 2.6 text-to-image. Never leaves it on a video feature.

    A still (image, images, refs, or base) raises StillGifUnsupported before any rewrite.
    schemas is unused for that refusal: edit-with-gif is not a still-to-GIF path.
    """
    if not requests_gif(inputs):
        return inputs
    refuse_still_gif(inputs)
    if schemas is not None and not isinstance(schemas, dict):
        raise StillGifUnsupported(refusal_text())
    out = dict(inputs)
    params = dict(out.get("params") or {}) if isinstance(out.get("params"), dict) else {}
    raw_count = params.get("frame_count", out.get("frame_count"))
    raw_ms = params.get("frame_duration_ms", out.get("frame_duration_ms"))
    spec = gif_params(raw_count, raw_ms)
    params.update(spec)
    out["params"] = params
    out["output_format"] = "gif"
    # Top-level copies stay equal to params so quote/confirm and the POST use one clamped count.
    out["frame_count"] = spec["frame_count"]
    out["frame_duration_ms"] = spec["frame_duration_ms"]
    asked_count = asked_int(raw_count)
    asked_ms = asked_int(raw_ms)
    if asked_count is not None and asked_count != spec["frame_count"]:
        out["gif_asked_frame_count"] = asked_count
    if asked_ms is not None and asked_ms != spec["frame_duration_ms"]:
        out["gif_asked_frame_duration_ms"] = asked_ms
    feature = str(out.get("feature") or "text_to_image")
    video = feature in _VIDEO_FEATURES or "video" in feature
    out["feature"] = "text_to_image"
    out["model"] = pick_t2i(None if video else out.get("model"))
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
