"""#826: GPT Image 2.6 text-to-image SVG. One image. Edit is not supported.

The quote is the existing still cell plus SVG_ADDON_USD ($0.02).
Medium 1k is 0.05 + 0.02 = 0.07. That sum is the published still table, not a new vendor price.
This module never opens a socket, reads a local path from the SVG, or calls WaveSpeed.

Preview is a PNG from a restricted draw of rect / circle / ellipse / polygon.
Raw SVG is never returned as the preview. Dangerous files have no download.
A safe file whose preview cannot be drawn still keeps the original bytes.
"""
from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass

from .gif_image import FLARE_T2I, SUNBURST_T2I, documented_usd

FLARE = FLARE_T2I
SUNBURST = SUNBURST_T2I
SVG_ADDON_USD = 0.02

# Caps the rasterizer actually enforces. Over any one of these is a rejection, not a download.
MAX_BYTES = 512 * 1024
MAX_EDGE = 1024
MAX_PIXELS = 1024 * 1024
MAX_ELEMENTS = 2000
MAX_SECONDS = 0.25

_SVG_RE = re.compile(r"(?<![A-Za-z0-9])svgs?(?![A-Za-z0-9])", re.I)
_VIDEO = {"text_to_video", "image_to_video", "reference_to_video", "motion_control", "lip_sync", "animate_image"}
_SCRIPT_TAGS = {"script", "foreignobject", "iframe", "object", "embed", "handler"}
_RESOURCE_TAGS = {"image", "audio", "video", "feimage"}
_ACTIVE_TAGS = {"animate", "animatetransform", "animatemotion", "set", "mpath"}
_DRAW_TAGS = {"rect", "circle", "ellipse", "polygon"}
_NAMED = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "blue": (0, 0, 255),
    "green": (0, 128, 0), "transparent": None,
}
_URL_BAD = re.compile(r"(?i)(javascript:|vbscript:|data:|https?:|file:|php:|\\\\|//)")
_ENTITY = (b"<!doctype", b"<!entity", b"<!element", b"<!attlist", b"<!notation", b"<![cdata[")


@dataclass(frozen=True)
class Limits:
    max_bytes: int = MAX_BYTES
    max_edge: int = MAX_EDGE
    max_pixels: int = MAX_PIXELS
    max_elements: int = MAX_ELEMENTS
    max_seconds: float = MAX_SECONDS

    def as_dict(self) -> dict:
        return {
            "max_bytes": self.max_bytes,
            "max_edge": self.max_edge,
            "max_pixels": self.max_pixels,
            "max_elements": self.max_elements,
            "max_seconds": self.max_seconds,
        }


LIMITS = Limits()

# Readable copy. No vendor name (#712). Kept in lockstep with src/locales wsErr.svg*.
USER = {
    "rejected": {
        "zh": "这个 SVG 不安全（含脚本、外部资源、本地文件、实体，或超出大小、像素或时长限制），已拒绝，不会提供下载。",
        "en": "This SVG is unsafe (script, external resource, local file, entity, or over the size, pixel, or time limit). It was rejected and is not available to download.",
    },
    "edit": {
        "zh": "SVG 只支持文生图，一次一张，不能从编辑或参考图生成。",
        "en": "SVG is text-to-image only, one image at a time. Edit and reference images are not supported.",
    },
    "count": {
        "zh": "SVG 一次只能生成 1 张。",
        "en": "SVG can only generate 1 image at a time.",
    },
    "preview_failed": {
        "zh": "预览失败，原 SVG 仍可下载。",
        "en": "Preview failed. The original SVG can still be downloaded.",
    },
}
NOTE = {
    "zh": "矢量 SVG，用 GPT Image 2.6 文生，一次一张。默认模型仍是 GPT Image 2.5 Flare。价格是同档静图再加 $0.02（沿用既有静图价，不是新核价）。",
    "en": "Vector SVG from GPT Image 2.6 text-to-image, one image. The default model stays GPT Image 2.5 Flare. Price is the still price plus $0.02 (existing still table, not a new price check).",
}


def _line(pair: dict) -> str:
    return f"{pair['zh']} / {pair['en']}"


class Verdict:
    def __init__(self, status: str, reason: str, download: bytes | None, preview_png: bytes | None, pair: dict, kind: str = ""):
        self.status = status
        self.reason = reason
        self.download = download
        self.preview_png = preview_png
        self.kind = kind
        self.message_zh = pair["zh"]
        self.message_en = pair["en"]
        self.message = _line(pair)
        self.inline_svg = False
        self.preview_type = "image/png" if preview_png else None
        self.limits = LIMITS.as_dict()

    @property
    def ok_download(self) -> bool:
        return self.status != "rejected" and self.download is not None


def audit() -> dict:
    """What the rasterizer refuses, and the thresholds it uses. No network is opened to produce this."""
    return {
        "limits": LIMITS.as_dict(),
        "inline_svg": False,
        "preview": "image/png from rect, circle, ellipse, polygon only",
        "network": "this module has no socket or HTTP client; http(s), protocol-relative, and data: URLs are rejected",
        "local_file": "file:, absolute paths, and relative file refs are rejected; ElementTree is given no custom opener",
        "entities": "DOCTYPE, ENTITY, and CDATA are rejected on the raw bytes before ElementTree",
        "script": "script, event handlers, javascript:, and foreignObject are rejected; nothing is evaluated",
        "resource": "byte size, edge, pixel area, element count, and elapsed seconds are capped",
        "dangerous_download": False,
        "safe_preview_failure_download": True,
        "addon_usd": SVG_ADDON_USD,
        "medium_1k_usd": 0.07,
        "price_basis": "existing still cell + 0.02; medium 1k 0.07 is that sum, not a new vendor price",
    }


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


def _count_ok(inputs: dict) -> bool:
    params = inputs.get("params") if isinstance(inputs.get("params"), dict) else {}
    for key in ("count", "n", "num_images"):
        value = inputs.get(key, params.get(key))
        if value in (None, ""):
            continue
        try:
            if int(value) != 1:
                return False
        except (TypeError, ValueError):
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
    """2.6-sunburst text-to-image only when that family was named. Never an edit id. Never 2.5."""
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


def read_limited(path: str) -> bytes:
    """Read at most one byte past the size cap so an oversized file is rejected without loading the rest."""
    with open(path, "rb") as handle:
        return handle.read(LIMITS.max_bytes + 1)


def looks_like_svg(data: bytes = b"", content_type: str = "", url: str = "") -> bool:
    if "svg" in (content_type or "").lower():
        return True
    if str(url or "").split("?", 1)[0].lower().endswith(".svg"):
        return True
    head = bytes(data[:800]).lstrip().lower()
    return head.startswith(b"<svg") or head.startswith(b"<?xml") or b"<svg" in head


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower() if tag.startswith("{") else tag.lower()


def _num(value, default=None):
    if value is None:
        return default
    match = re.match(r"^\s*([+-]?\d+(?:\.\d+)?)", str(value))
    if not match:
        return default
    return float(match.group(1))


def _url_kind(value: str) -> str | None:
    text = (value or "").strip()
    if not text or text.startswith("#"):
        return None
    low = text.lower()
    if low.startswith("javascript:") or low.startswith("vbscript:") or "javascript:" in low:
        return "script"
    if low.startswith("file:") or text.startswith("/") or text.startswith("../") or text.startswith("./") or text.startswith("..\\") or re.match(r"^[A-Za-z]:[\\/]", text):
        return "local_file"
    if _URL_BAD.search(text):
        return "external"
    if re.match(r"(?i)^(?:[a-z0-9_./\\-]+\.)+(?:png|jpe?g|gif|svg|webp)$", text):
        return "local_file"
    return None


def _style_kind(style: str) -> str | None:
    if re.search(r"(?i)expression\s*\(|javascript:|@import|-moz-binding|behavior\s*:", style or ""):
        return "script"
    for match in re.finditer(r"(?i)url\s*\(\s*['\"]?([^)'\"]+)", style or ""):
        target = match.group(1).strip()
        if target.startswith("#"):
            continue
        return _url_kind(target) or "external"
    return None


def _entity(data: bytes) -> bool:
    low = data.lower()
    return any(tok in low for tok in _ENTITY)


def _token_reason(text: str) -> str | None:
    """Used only when the document does not parse. The SVG namespace URL is not a resource load."""
    low = text.lower()
    if any(tok.decode() in low for tok in _ENTITY):
        return "entity"
    if "<script" in low or "javascript:" in low or re.search(r"\son[a-z]+\s*=", low):
        return "script"
    if "file:" in low:
        return "local_file"
    stripped = re.sub(r"""xmlns(?::[a-z0-9]+)?\s*=\s*['"]https?://www\.w3\.org/[^'"]+['"]""", "", low)
    if "http://" in stripped or "https://" in stripped or "data:" in stripped:
        return "external"
    return None


def _rgba(fill: str, fill_opacity, opacity):
    raw = (fill or "").strip()
    if raw.lower() in ("none", "transparent"):
        return None
    rgb = _NAMED.get(raw.lower())
    if raw.lower() in _NAMED and rgb is None:
        return None
    if rgb is None and raw.startswith("#"):
        hexes = raw[1:]
        if len(hexes) == 3:
            hexes = "".join(c * 2 for c in hexes)
        if len(hexes) in (6, 8) and re.fullmatch(r"[0-9a-fA-F]+", hexes):
            rgb = (int(hexes[0:2], 16), int(hexes[2:4], 16), int(hexes[4:6], 16))
            alpha = int(hexes[6:8], 16) / 255 if len(hexes) == 8 else 1.0
        else:
            return None
    else:
        alpha = 1.0
    if rgb is None:
        match = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9.]+)\s*)?\)", raw, re.I)
        if not match:
            return None
        rgb = tuple(int(match.group(i)) for i in (1, 2, 3))
        alpha = float(match.group(4)) if match.group(4) else 1.0
    for extra in (fill_opacity, opacity):
        n = _num(extra, None)
        if n is not None:
            alpha *= max(0.0, min(1.0, n))
    return (rgb[0], rgb[1], rgb[2], int(round(max(0.0, min(1.0, alpha)) * 255)))


def _attrs(el) -> dict:
    return {_local(k): v for k, v in el.attrib.items()}


def _paint(attrs: dict):
    style = attrs.get("style") or ""
    fill = attrs.get("fill")
    fill_opacity = attrs.get("fill-opacity")
    opacity = attrs.get("opacity")
    found = re.search(r"(?i)(?:^|;)\s*fill\s*:\s*([^;]+)", style)
    if found:
        fill = found.group(1).strip()
    found = re.search(r"(?i)fill-opacity\s*:\s*([^;]+)", style)
    if found:
        fill_opacity = found.group(1).strip()
    if fill is None:
        fill = "#000000"
    return _rgba(fill, fill_opacity, opacity)


def _canvas_size(attrs: dict, limits: Limits):
    vb = (attrs.get("viewbox") or "").replace(",", " ").split()
    vx = vy = 0.0
    vw = vh = None
    if len(vb) == 4:
        nums = [_num(p) for p in vb]
        if all(n is not None for n in nums):
            vx, vy, vw, vh = nums
    width = _num(attrs.get("width"), vw if vw else 64.0)
    height = _num(attrs.get("height"), vh if vh else 64.0)
    if vw is None or vh is None or vw <= 0 or vh <= 0:
        vx, vy, vw, vh = 0.0, 0.0, width, height
    if width <= 0 or height <= 0 or vw <= 0 or vh <= 0:
        return None
    if width > limits.max_edge or height > limits.max_edge or width * height > limits.max_pixels:
        return "too_many_pixels"
    return int(round(width)), int(round(height)), vx, vy, vw, vh


def _walk(el, limits: Limits, count: list):
    count[0] += 1
    if count[0] > limits.max_elements:
        return "too_many_elements"
    name = _local(el.tag) if isinstance(el.tag, str) else ""
    attrs = _attrs(el) if isinstance(el.tag, str) else {}
    if name in _SCRIPT_TAGS or name in _ACTIVE_TAGS:
        return "script"
    if name in _RESOURCE_TAGS:
        return "external"
    if name == "style":
        return _style_kind("".join(el.itertext()) or "") or _walk_children(el, limits, count)
    styled = _style_kind(attrs.get("style") or "")
    if styled:
        return styled
    for key, value in attrs.items():
        if key.startswith("on"):
            return "script"
        if key in ("href", "src", "xlink:href"):
            kind = _url_kind(value)
            if kind:
                return kind
    if name == "use":
        href = attrs.get("href") or ""
        if href and not href.startswith("#"):
            return _url_kind(href) or "external"
    return _walk_children(el, limits, count)


def _walk_children(el, limits, count):
    for child in list(el):
        kind = _walk(child, limits, count)
        if kind:
            return kind
    return None


def _draw(el, draw, box, limits, count):
    """Draw the safe subset. The caller has already rejected dangerous nodes."""
    name = _local(el.tag) if isinstance(el.tag, str) else ""
    attrs = _attrs(el) if isinstance(el.tag, str) else {}
    x0, y0, sx, sy = box
    if name in _DRAW_TAGS:
        color = _paint(attrs)
        if color is not None:
            if name == "rect":
                x = x0 + _num(attrs.get("x"), 0) * sx
                y = y0 + _num(attrs.get("y"), 0) * sy
                w = _num(attrs.get("width"), 0) * sx
                h = _num(attrs.get("height"), 0) * sy
                draw.rectangle([x, y, x + w, y + h], fill=color)
            elif name == "circle":
                cx = x0 + _num(attrs.get("cx"), 0) * sx
                cy = y0 + _num(attrs.get("cy"), 0) * sy
                r = _num(attrs.get("r"), 0) * ((sx + sy) / 2)
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
            elif name == "ellipse":
                cx = x0 + _num(attrs.get("cx"), 0) * sx
                cy = y0 + _num(attrs.get("cy"), 0) * sy
                rx = _num(attrs.get("rx"), 0) * sx
                ry = _num(attrs.get("ry"), 0) * sy
                draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=color)
            elif name == "polygon":
                pts = []
                nums = re.findall(r"[+-]?\d+(?:\.\d+)?", attrs.get("points") or "")
                for i in range(0, len(nums) - 1, 2):
                    pts.append((x0 + float(nums[i]) * sx, y0 + float(nums[i + 1]) * sy))
                if len(pts) >= 3:
                    draw.polygon(pts, fill=color)
    for child in list(el):
        _draw(child, draw, box, limits, count)


def _failure_png() -> bytes:
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (32, 32), (128, 128, 128, 255))
    ImageDraw.Draw(im).rectangle([0, 0, 3, 3], fill=(0, 0, 0, 255))
    return _png(im)


def _png(im) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _pixels(im) -> str:
    w, h = im.size
    px = im.load()
    drawn = any(px[x, y][3] > 0 for y in range(h) for x in range(w))
    if not drawn:
        return "preview_failed"
    corners = (px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1])
    if all(c[3] == 0 for c in corners):
        return "transparent"
    return "normal"


def _rejected(reason: str) -> Verdict:
    return Verdict("rejected", reason, None, None, USER["rejected"], "svgRejected")


def _failed(data: bytes, reason: str) -> Verdict:
    return Verdict("preview_failed", reason, bytes(data), _failure_png(), USER["preview_failed"], "")


def admit(data: bytes, *, limits: Limits | None = None, clock=None) -> Verdict:
    """Classify and rasterize. Rejected files return no bytes. Preview bytes are PNG or absent.

    limits defaults to LIMITS. clock defaults to time.monotonic. Tests inject both; production does not.
    """
    limits = limits or LIMITS
    clock = clock or time.monotonic
    start = clock()

    def slow() -> bool:
        return (clock() - start) > limits.max_seconds

    if not isinstance(data, (bytes, bytearray)):
        return _rejected("not_svg")
    data = bytes(data)
    if len(data) > limits.max_bytes:
        return _rejected("too_large")
    if _entity(data):
        return _rejected("entity")
    if slow():
        return _rejected("too_slow")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", "replace")
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        kind = _token_reason(text)
        if kind:
            return _rejected(kind)
        return _failed(data, "malformed")
    if not isinstance(root.tag, str) or _local(root.tag) != "svg":
        return _rejected("not_svg")
    danger = _walk(root, limits, [0])
    if danger == "too_many_elements" or danger:
        return _rejected(danger or "script")
    if slow():
        return _rejected("too_slow")
    size = _canvas_size(_attrs(root), limits)
    if size == "too_many_pixels" or size is None:
        return _rejected("too_many_pixels" if size == "too_many_pixels" else "malformed")
    w, h, vx, vy, vw, vh = size
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    sx, sy = w / vw, h / vh
    _draw(root, ImageDraw.Draw(im, "RGBA"), (-vx * sx, -vy * sy, sx, sy), limits, [0])
    if slow():
        return _rejected("too_slow")
    state = _pixels(im)
    if state == "preview_failed":
        return _failed(data, "undrawable")
    pair = {"zh": "预览已生成。", "en": "Preview is ready."} if state == "normal" else {
        "zh": "预览已生成，背景是透明的。", "en": "Preview is ready. The background is transparent.",
    }
    return Verdict(state, state, data, _png(im), pair, "")
