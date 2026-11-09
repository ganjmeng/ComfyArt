"""Replicate GPT Image 2.6 request body.

Field names come from the official model cards (2026-11-08):
https://replicate.com/openai/gpt-image-2.6-flare
https://replicate.com/openai/gpt-image-2.6-sunburst

The HTTP shape is the official model prediction create:
POST /v1/models/{owner}/{name}/predictions  body {"input": {...}}
https://replicate.com/docs/reference/http

Files are HTTP URLs or data URLs. Data URLs are for files up to 256 KiB.
This module does not invent fields, does not send openai_api_key, and does not
set a price.
"""
from __future__ import annotations

import base64
import os
from urllib.parse import urlparse

from . import gif_image
from ._common import view_path

DATA_URL_MAX = 256 * 1024
ASPECTS = {"1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "auto"}
STILL_FORMATS = {"png", "jpeg", "webp"}
QUALITIES = {"low", "medium", "high", "xhigh", "max", "auto"}
COMPLEXITIES = {"low", "medium", "high"}
FRAME_COUNT = (2, 16, 9)
FRAME_MS = (20, 2000, 200)


class PayloadError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.kind = "unsupported"


def prediction_url(model_id: str, base: str | None = None) -> str:
    owner, _, name = str(model_id).partition("/")
    if not owner or not name or "/" in name:
        raise PayloadError(f"replicate model id must be owner/name, got {model_id}")
    root = (base or os.environ.get("REPLICATE_API_BASE") or "https://api.replicate.com").rstrip("/")
    return f"{root}/v1/models/{owner}/{name}/predictions"


def _refs(inputs: dict) -> list[str]:
    found: list[str] = []
    images = inputs.get("images") if isinstance(inputs.get("images"), list) else []
    refs = inputs.get("refs") if isinstance(inputs.get("refs"), list) else []
    for value in [inputs.get("image"), inputs.get("base"), *images, *refs]:
        if isinstance(value, str) and value and value not in found:
            found.append(value)
    return found


def _as_image_ref(value: str) -> str:
    """Pass an HTTP(S) or data URL through. A local Comfy file becomes a data URL only under 256 KiB."""
    text = value.strip()
    if text.startswith(("https://", "http://")):
        return text
    if text.startswith("data:image/"):
        if len(text) > DATA_URL_MAX:
            raise PayloadError("参考图超过 Replicate 对 data URL 的 256 KiB 限制，已停止，未改成无图请求")
        return text
    path = _local_path(text)
    if not path:
        raise PayloadError("参考图不是 Replicate 接受的 URL，已停止，未丢弃参考图")
    try:
        size = os.path.getsize(path)
    except OSError as e:
        raise PayloadError("参考图读不出来，已停止，未丢弃参考图") from e
    if size > DATA_URL_MAX or size <= 0:
        raise PayloadError("参考图超过 256 KiB，本页没有已核对的 Replicate 上传接口，已停止，未丢弃参考图")
    with open(path, "rb") as handle:
        raw = handle.read()
    kind = "png" if raw.startswith(b"\x89PNG") else "jpeg" if raw.startswith(b"\xff\xd8") else "webp" if raw.startswith(b"RIFF") else ""
    if not kind:
        raise PayloadError("参考图不是 png、jpeg 或 webp，已停止")
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/{kind};base64,{encoded}"


def _local_path(value: str) -> str:
    if value.startswith("/api/view") or "filename=" in value:
        try:
            return view_path(value if value.startswith("/") else f"/api/view?{urlparse(value).query}")
        except (ValueError, OSError):
            return ""
    try:
        import folder_paths
        path = folder_paths.get_annotated_filepath(value)
    except Exception:
        return ""
    return path if path and os.path.isfile(path) else ""


def _nearest_aspect(ratio: float) -> str:
    """Map a width/height ratio onto the Replicate aspect_ratio enum (never WxH pixels)."""
    best = "1:1"
    best_d = float("inf")
    for item in ASPECTS:
        if ":" not in item:
            continue
        left, _, right = item.partition(":")
        try:
            value = float(left) / float(right)
        except ValueError:
            continue
        distance = abs(value - ratio)
        if distance < best_d:
            best_d, best = distance, item
    return best


def _aspect(inputs: dict) -> str:
    """Only emit values Replicate accepts (ASPECTS). Pixel sizes like 1024x1024 caused E006."""
    named = str(inputs.get("aspect_ratio") or inputs.get("ratio") or "").strip()
    if named in ASPECTS:
        return named
    # UI sometimes puts canvas pixels into aspect_ratio / ratio ("1024x1024").
    if "x" in named.lower() and ":" not in named:
        try:
            left, _, right = named.lower().partition("x")
            width, height = int(left), int(right)
            if width > 0 and height > 0:
                return _nearest_aspect(width / height)
        except ValueError:
            pass
    try:
        width, height = int(inputs.get("width")), int(inputs.get("height"))
    except (TypeError, ValueError):
        return ""
    if width > 0 and height > 0:
        return _nearest_aspect(width / height)
    return ""


def _optional_enum(inputs: dict, key: str, allowed: set[str]) -> str:
    params = inputs.get("params") if isinstance(inputs.get("params"), dict) else {}
    value = str(params.get(key) or inputs.get(key) or "").strip().lower()
    return value if value in allowed else ""


def build_input(capability: str, inputs: dict) -> dict:
    """The prediction ``input`` object. Raises PayloadError instead of dropping a reference."""
    prompt = str(inputs.get("prompt") or "").strip()
    if not prompt:
        raise PayloadError("缺少 prompt，未发送")
    refs = _refs(inputs)
    body: dict = {"prompt": prompt}
    gif = capability in ("text_to_gif", "reference_gif")
    if capability == "reference_gif":
        if not refs:
            raise PayloadError("参考图 GIF 缺少参考图，未改成无图文生")
        body["input_images"] = [_as_image_ref(item) for item in refs]
        body["output_format"] = "gif"
    elif capability == "text_to_gif":
        if refs:
            raise PayloadError("文生 GIF 带了参考图，未丢图，也未当成无图请求发送")
        body["output_format"] = "gif"
    elif capability == "image_edit":
        if not refs:
            raise PayloadError("图编辑缺少参考图，未改成文生图")
        body["input_images"] = [_as_image_ref(item) for item in refs]
        fmt = _optional_enum(inputs, "output_format", STILL_FORMATS)
        if fmt:
            body["output_format"] = fmt
        if _optional_enum(inputs, "output_format", {"gif"}):
            raise PayloadError("图编辑不发送 gif。参考图 GIF 是另一项能力")
    elif capability == "text_to_image":
        if refs:
            raise PayloadError("文生图带了参考图，未丢图")
        fmt = _optional_enum(inputs, "output_format", STILL_FORMATS)
        if fmt:
            body["output_format"] = fmt
    else:
        raise PayloadError(f"未实现的图像能力 {capability}")
    if gif:
        params = inputs.get("params") if isinstance(inputs.get("params"), dict) else {}
        spec = gif_image.gif_params(
            params.get("frame_count", inputs.get("frame_count")),
            params.get("frame_duration_ms", inputs.get("frame_duration_ms")),
        )
        body["frame_count"] = spec["frame_count"]
        body["frame_duration_ms"] = spec["frame_duration_ms"]
    aspect = _aspect(inputs)
    if aspect:
        body["aspect_ratio"] = aspect
    quality = _optional_enum(inputs, "quality", QUALITIES)
    if quality:
        body["quality"] = quality
    complexity = _optional_enum(inputs, "complexity", COMPLEXITIES)
    if complexity:
        body["complexity"] = complexity
    count = inputs.get("count", inputs.get("number_of_images"))
    if isinstance(count, int) and not isinstance(count, bool) and 1 <= count <= 10:
        body["number_of_images"] = count
    if "openai_api_key" in body or "svg_model" in body:
        raise PayloadError("请求包含不允许的字段")
    return body


def prediction_body(capability: str, inputs: dict) -> dict:
    return {"input": build_input(capability, inputs)}
