"""#826 restricted SVG admission and local raster.

UTF-8 only. Dangerous constructs are rejected before a download is allowed.
A download of the original bytes exists only after the document parses, passes
the security walk, and the local raster then draws nothing.

This file does not open sockets or read paths out of the SVG.
Production rendering goes through svg_worker, which must enter a network
namespace and a Landlock filesystem sandbox before admit() runs. If either
setup fails, the child does not parse or draw. rlimit is only a resource cap.
"""
from __future__ import annotations

import base64
import io
import json
import math
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 512 * 1024
MAX_EDGE = 1024
MAX_PIXELS = 1024 * 1024
MAX_ELEMENTS = 2000
MAX_SECONDS = 0.25
# OS backstop around the child, including interpreter startup.
# The 0.25s budget still wraps the SVG work inside admit().
WORKER_AS = 768 * 1024 * 1024
WORKER_CPU = 3
WORKER_ALARM = 3
WORKER_FSIZE = 2 * 1024 * 1024

REJECTED = {
    "zh": "这个 SVG 不安全（含脚本、外部资源、本地文件、实体，或超出大小、像素或时长限制），已拒绝，不会提供下载。",
    "en": "This SVG is unsafe (script, external resource, local file, entity, or over the size, pixel, or time limit). It was rejected and is not available to download.",
}
PREVIEW_FAILED = {
    "zh": "预览失败，原 SVG 仍可下载。",
    "en": "Preview failed. The original SVG can still be downloaded.",
}
_READY = {"zh": "预览已生成。", "en": "Preview is ready."}
_CLEAR = {"zh": "预览已生成，背景是透明的。", "en": "Preview is ready. The background is transparent."}

_SCRIPT_TAGS = {"script", "foreignobject", "iframe", "object", "embed", "handler"}
_RESOURCE_TAGS = {"image", "audio", "video", "feimage"}
_ACTIVE_TAGS = {"animate", "animatetransform", "animatemotion", "set", "mpath"}
_DRAW_TAGS = {"rect", "circle", "ellipse", "polygon", "path"}
_NAMED = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "blue": (0, 0, 255),
    "green": (0, 128, 0), "transparent": None,
}
_NUM = re.compile(r"[+-]?(?:\d+\.\d+|\.\d+|\d+)(?:[eE][+-]?\d+)?")
_CMD = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]")
_PROLOG = re.compile(r"<\?xml(?:\s|\?)", re.I)
_PI = re.compile(r"<\?(?!xml(?:\s|\?))", re.I)
_DTD = re.compile(r"<!doctype|<!entity|<!element|<!attlist|<!notation|<!\[cdata\[", re.I)
_URL = re.compile(r"url\s*\(\s*['\"]?\s*([^)'\"]+)", re.I)
_IMPORT = re.compile(r"@import", re.I)
_ENC = re.compile(r"<\?xml[^?]*encoding\s*=\s*['\"]([^'\"]+)['\"]", re.I)


@dataclass(frozen=True)
class Limits:
    max_bytes: int = MAX_BYTES
    max_edge: int = MAX_EDGE
    max_pixels: int = MAX_PIXELS
    max_elements: int = MAX_ELEMENTS
    max_seconds: float = MAX_SECONDS

    def as_dict(self) -> dict:
        return {
            "max_bytes": self.max_bytes, "max_edge": self.max_edge, "max_pixels": self.max_pixels,
            "max_elements": self.max_elements, "max_seconds": self.max_seconds,
        }


LIMITS = Limits()


def raster_audit() -> dict:
    return {
        "limits": LIMITS.as_dict(),
        "inline_svg": False,
        "preview": "image/png from rect, circle, ellipse, polygon, and path; no browser and no network fetch",
        "encoding": "utf-8 only; UTF-16/32 and undecodable bytes are rejected before the security scan",
        "entities": "DOCTYPE, ENTITY, and CDATA are rejected on the decoded Unicode text before ElementTree",
        "stylesheet": "processing instructions other than the XML declaration, including xml-stylesheet, are rejected",
        "css": "@import and url() other than url(#id) are rejected",
        "script": "script, event handlers, javascript:, and foreignObject are rejected; nothing is evaluated",
        "local_file": "SVG path refs are rejected in the parser. The production child also applies Landlock with no allow rules and requires open(/etc/passwd) to fail before admit()",
        "network": "production child must enter a user and network namespace and observe an unreachable connect before parsing. A failed namespace does not render. rlimit is not network isolation",
        "process": "the child also sets RLIMIT_AS, RLIMIT_CPU, RLIMIT_FSIZE, and alarm. Those caps are not a network or filesystem sandbox",
        "worker": {"rlimit_as": WORKER_AS, "rlimit_cpu": WORKER_CPU, "rlimit_fsize": WORKER_FSIZE, "alarm_seconds": WORKER_ALARM},
        "monkeypatch_is_not_isolation": True,
        "dangerous_download": False,
        "safe_preview_failure_download": True,
        "invalid_xml_download": False,
    }


class Verdict:
    def __init__(self, status: str, reason: str, download: bytes | None, preview_png: bytes | None, pair: dict, kind: str = ""):
        self.status = status
        self.reason = reason
        self.download = download
        self.preview_png = preview_png
        self.kind = kind
        self.message_zh = pair["zh"]
        self.message_en = pair["en"]
        self.message = f"{pair['zh']} / {pair['en']}"
        self.inline_svg = False
        self.preview_type = "image/png" if preview_png else None
        self.limits = LIMITS.as_dict()
        self.runtime = {"mode": "inprocess"}

    @property
    def ok_download(self) -> bool:
        return self.status != "rejected" and self.download is not None


def _rejected(reason: str) -> Verdict:
    return Verdict("rejected", reason, None, None, REJECTED, "svgRejected")


def _line(pair: dict) -> str:
    return f"{pair['zh']} / {pair['en']}"


def read_limited(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read(LIMITS.max_bytes + 1)


def looks_like_svg(data: bytes = b"", content_type: str = "", url: str = "") -> bool:
    if "svg" in (content_type or "").lower():
        return True
    if str(url or "").split("?", 1)[0].lower().endswith(".svg"):
        return True
    head = bytes(data[:800]).lstrip().lower()
    return head.startswith((b"<svg", b"<?xml")) or b"<svg" in head


def _decode(data: bytes) -> tuple[str | None, str | None]:
    """Accept UTF-8 only. Do not search the raw bytes for ASCII markers."""
    if not data.strip():
        return None, "empty"
    if data.startswith((b"\xff\xfe", b"\xfe\xff", b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")) or b"\x00" in data:
        return None, "unsupported_encoding"
    raw = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, "unsupported_encoding"
    declared = _ENC.search(text[:200])
    if declared and declared.group(1).lower().replace("_", "-") not in ("utf-8", "utf8"):
        return None, "unsupported_encoding"
    return text, None


def _unicode_danger(text: str) -> str | None:
    """Fail closed on DTD, stylesheet PIs, and CSS loads. Comments are not a hiding place."""
    if _DTD.search(text):
        return "entity"
    if _PI.search(text):
        return "stylesheet"
    if _IMPORT.search(text):
        return "stylesheet"
    for match in _URL.finditer(text):
        target = match.group(1).strip()
        if not target.startswith("#"):
            return "external"
    stripped = re.sub(r"""xmlns(?::[a-z0-9]+)?\s*=\s*['"]https?://www\.w3\.org/[^'"]+['"]""", "", text, flags=re.I)
    if re.search(r"javascript:|vbscript:", stripped, re.I):
        return "script"
    if re.search(r"file:", stripped, re.I):
        return "local_file"
    if re.search(r"https?://|data:", stripped, re.I):
        return "external"
    return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower() if tag.startswith("{") else tag.lower()


def _num(value, default=None):
    if value is None:
        return default
    match = re.match(r"^\s*([+-]?(?:\d+\.\d+|\.\d+|\d+)(?:[eE][+-]?\d+)?)", str(value))
    if not match:
        return default
    return float(match.group(1))


def _url_kind(value: str) -> str | None:
    text = (value or "").strip()
    if not text or text.startswith("#"):
        return None
    low = text.lower()
    if low.startswith(("javascript:", "vbscript:")) or "javascript:" in low:
        return "script"
    if low.startswith("file:") or text.startswith(("/", "../", "./", "..\\")) or re.match(r"^[A-Za-z]:[\\/]", text):
        return "local_file"
    if re.search(r"(?i)(https?:|data:|php:|\\\\|//)", text):
        return "external"
    if re.match(r"(?i)^(?:[a-z0-9_./\\-]+\.)+(?:png|jpe?g|gif|svg|webp|css)$", text):
        return "local_file"
    return None


def _style_kind(style: str) -> str | None:
    if _IMPORT.search(style or "") or re.search(r"(?i)expression\s*\(|javascript:|-moz-binding|behavior\s*:", style or ""):
        return "stylesheet" if _IMPORT.search(style or "") else "script"
    for match in _URL.finditer(style or ""):
        target = match.group(1).strip()
        if target.startswith("#"):
            continue
        return _url_kind(target) or "external"
    return None


def _rgba(fill: str, fill_opacity, opacity):
    raw = (fill or "").strip()
    if raw.lower() in ("none", "transparent"):
        return None
    rgb = _NAMED.get(raw.lower())
    alpha = 1.0
    if raw.lower() in _NAMED and rgb is None:
        return None
    if rgb is None and raw.startswith("#"):
        hexes = raw[1:]
        if len(hexes) == 3:
            hexes = "".join(ch * 2 for ch in hexes)
        if len(hexes) not in (6, 8) or not re.fullmatch(r"[0-9a-fA-F]+", hexes):
            return None
        rgb = (int(hexes[0:2], 16), int(hexes[2:4], 16), int(hexes[4:6], 16))
        if len(hexes) == 8:
            alpha = int(hexes[6:8], 16) / 255
    if rgb is None:
        match = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9.]+)\s*)?\)", raw, re.I)
        if not match:
            return None
        rgb = tuple(int(match.group(i)) for i in (1, 2, 3))
        alpha = float(match.group(4)) if match.group(4) else 1.0
    for extra in (fill_opacity, opacity):
        number = _num(extra, None)
        if number is not None:
            alpha *= max(0.0, min(1.0, number))
    return (rgb[0], rgb[1], rgb[2], int(round(max(0.0, min(1.0, alpha)) * 255)))


def _attrs(el) -> dict:
    return {_local(key): value for key, value in el.attrib.items()}


def _paint(attrs: dict, prop: str = "fill"):
    style = attrs.get("style") or ""
    paint = attrs.get(prop)
    opacity = attrs.get("opacity")
    specific = attrs.get(f"{prop}-opacity")
    found = re.search(rf"(?i)(?:^|;)\s*{prop}\s*:\s*([^;]+)", style)
    if found:
        paint = found.group(1).strip()
    found = re.search(rf"(?i){prop}-opacity\s*:\s*([^;]+)", style)
    if found:
        specific = found.group(1).strip()
    if paint is None and prop == "fill":
        paint = "#000000"
    if paint is None:
        return None
    return _rgba(paint, specific, opacity)


def _canvas_size(attrs: dict, limits: Limits):
    box = (attrs.get("viewbox") or "").replace(",", " ").split()
    vx = vy = 0.0
    vw = vh = None
    if len(box) == 4:
        nums = [_num(part) for part in box]
        if all(number is not None for number in nums):
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
    if not isinstance(el.tag, str):
        return None
    name = _local(el.tag)
    attrs = _attrs(el)
    if name in _SCRIPT_TAGS or name in _ACTIVE_TAGS:
        return "script"
    if name in _RESOURCE_TAGS:
        return "external"
    if name == "style":
        kind = _style_kind("".join(el.itertext()) or "")
        if kind:
            return kind
    kind = _style_kind(attrs.get("style") or "")
    if kind:
        return kind
    for key, value in attrs.items():
        if key.startswith("on"):
            return "script"
        if key in ("href", "src", "xlink:href"):
            found = _url_kind(value)
            if found:
                return found
    if name == "use":
        href = attrs.get("href") or ""
        if href and not href.startswith("#"):
            return _url_kind(href) or "external"
    for child in list(el):
        found = _walk(child, limits, count)
        if found:
            return found
    return None


def _tokens(d: str) -> list[str]:
    return re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|[+-]?(?:\d+\.\d+|\.\d+|\d+)(?:[eE][+-]?\d+)?", d or "")


def _bezier(p0, p1, p2, p3, steps=12):
    pts = []
    for step in range(1, steps + 1):
        t = step / steps
        u = 1 - t
        pts.append((
            u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
            u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
        ))
    return pts


def _quad(p0, p1, p2, steps=8):
    return _bezier(p0, (p0[0] + 2 * p1[0] / 3, p0[1] + 2 * p1[1] / 3), (p2[0] + 2 * p1[0] / 3, p2[1] + 2 * p1[1] / 3), p2, steps)


def _arc(x1, y1, rx, ry, phi, large, sweep, x2, y2):
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    phi = math.radians(phi % 360)
    cos, sin = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p = cos * dx + sin * dy
    y1p = -sin * dx + cos * dy
    rx, ry = abs(rx), abs(ry)
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        scale = math.sqrt(lam)
        rx *= scale
        ry *= scale
    sign = -1 if large == sweep else 1
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = sign * math.sqrt(max(0.0, num / den)) if den else 0.0
    cxp = coef * (rx * y1p / ry if ry else 0)
    cyp = coef * (-ry * x1p / rx if rx else 0)
    cx = cos * cxp - sin * cyp + (x1 + x2) / 2
    cy = sin * cxp + cos * cyp + (y1 + y2) / 2

    def angle(ux, uy, vx, vy):
        dot = ux * vx + uy * vy
        norm = math.hypot(ux, uy) * math.hypot(vx, vy) or 1
        arc = math.acos(max(-1.0, min(1.0, dot / norm)))
        if ux * vy - uy * vx < 0:
            arc = -arc
        return arc

    theta = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    delta = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi
    steps = max(8, int(abs(delta) / (math.pi / 16)))
    pts = []
    for step in range(1, steps + 1):
        t = theta + delta * step / steps
        pts.append((
            cx + rx * math.cos(t) * cos - ry * math.sin(t) * sin,
            cy + rx * math.cos(t) * sin + ry * math.sin(t) * cos,
        ))
    return pts


def _subpaths(d: str) -> list[list[tuple[float, float]]]:
    tokens = _tokens(d)
    i = 0
    cmd = ""
    cx = cy = sx = sy = 0.0
    last_c = (0.0, 0.0)
    subs: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] | None = None

    def take(count: int) -> list[float] | None:
        nonlocal i
        if i + count > len(tokens):
            return None
        out = [float(tokens[i + n]) for n in range(count)]
        i += count
        return out

    while i < len(tokens):
        if _CMD.fullmatch(tokens[i]):
            cmd = tokens[i]
            i += 1
        elif not cmd:
            break
        relative = cmd.islower()
        op = cmd.upper()
        if op == "Z":
            if cur:
                cur.append((sx, sy))
                subs.append(cur)
            cur = None
            cx, cy = sx, sy
            continue
        if op == "M":
            pair = take(2)
            if not pair:
                break
            cx, cy = (cx + pair[0], cy + pair[1]) if relative else (pair[0], pair[1])
            sx, sy = cx, cy
            cur = [(cx, cy)]
            cmd = "l" if relative else "L"
            continue
        if op == "L":
            pair = take(2)
            if not pair:
                break
            cx, cy = (cx + pair[0], cy + pair[1]) if relative else (pair[0], pair[1])
            (cur or [(cx, cy)]).append((cx, cy))
            if cur is None:
                cur = [(cx, cy)]
            continue
        if op == "H":
            value = take(1)
            if not value:
                break
            cx = cx + value[0] if relative else value[0]
            if cur is None:
                cur = [(cx, cy)]
            cur.append((cx, cy))
            continue
        if op == "V":
            value = take(1)
            if not value:
                break
            cy = cy + value[0] if relative else value[0]
            if cur is None:
                cur = [(cx, cy)]
            cur.append((cx, cy))
            continue
        if op in ("C", "S", "Q", "T", "A"):
            need = {"C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}[op]
            nums = take(need)
            if not nums:
                break
            if relative and op != "A":
                nums = [nums[n] + (cx if n % 2 == 0 else cy) for n in range(len(nums))]
            start = (cx, cy)
            if op == "C":
                pts = _bezier(start, (nums[0], nums[1]), (nums[2], nums[3]), (nums[4], nums[5]))
                last_c = (nums[2], nums[3])
                cx, cy = nums[4], nums[5]
            elif op == "S":
                c1 = (2 * cx - last_c[0], 2 * cy - last_c[1]) if cmd.upper() in ("C", "S") else start
                pts = _bezier(start, c1, (nums[0], nums[1]), (nums[2], nums[3]))
                last_c = (nums[0], nums[1])
                cx, cy = nums[2], nums[3]
            elif op == "Q":
                pts = _quad(start, (nums[0], nums[1]), (nums[2], nums[3]))
                last_c = (nums[0], nums[1])
                cx, cy = nums[2], nums[3]
            elif op == "T":
                c1 = (2 * cx - last_c[0], 2 * cy - last_c[1]) if cmd.upper() in ("Q", "T") else start
                pts = _quad(start, c1, (nums[0], nums[1]))
                last_c = c1
                cx, cy = nums[0], nums[1]
            else:
                end = (nums[5], nums[6]) if not relative else (cx + nums[5], cy + nums[6])
                pts = _arc(cx, cy, nums[0], nums[1], nums[2], bool(nums[3]), bool(nums[4]), end[0], end[1])
                cx, cy = end
            if cur is None:
                cur = [start]
            cur.extend(pts)
            continue
        break
    if cur and len(cur) > 1:
        subs.append(cur)
    return subs


def _draw(el, draw, box):
    if not isinstance(el.tag, str):
        return
    name = _local(el.tag)
    attrs = _attrs(el)
    x0, y0, sx, sy = box
    if name in {"rect", "circle", "ellipse", "polygon"}:
        color = _paint(attrs)
        if color is not None:
            if name == "rect":
                x = x0 + _num(attrs.get("x"), 0) * sx
                y = y0 + _num(attrs.get("y"), 0) * sy
                w = _num(attrs.get("width"), 0) * sx
                h = _num(attrs.get("height"), 0) * sy
                draw.rectangle([x, y, x + max(w, 0), y + max(h, 0)], fill=color)
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
            else:
                pts = []
                nums = re.findall(r"[+-]?(?:\d+\.\d+|\.\d+|\d+)", attrs.get("points") or "")
                for index in range(0, len(nums) - 1, 2):
                    pts.append((x0 + float(nums[index]) * sx, y0 + float(nums[index + 1]) * sy))
                if len(pts) >= 3:
                    draw.polygon(pts, fill=color)
    elif name == "path":
        fill = _paint(attrs, "fill")
        stroke = _paint(attrs, "stroke")
        width = max(1, int(round(_num(attrs.get("stroke-width"), 1) * ((sx + sy) / 2))))
        for sub in _subpaths(attrs.get("d") or ""):
            pix = [(x0 + x * sx, y0 + y * sy) for x, y in sub]
            if fill and len(pix) >= 3:
                draw.polygon(pix, fill=fill)
            if stroke and len(pix) >= 2:
                draw.line(pix, fill=stroke, width=width)
    for child in list(el):
        _draw(child, draw, box)


def _png(im) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _failure_png() -> bytes:
    """A PNG record with no opaque pixels. The canvas draws its own placeholder.

    This bitmap is not a picture of the file. A gray field or a black block here
    would look like a finished image, so every pixel stays transparent.
    """
    from PIL import Image
    return _png(Image.new("RGBA", (8, 8), (0, 0, 0, 0)))


def _pixels(im) -> str:
    w, h = im.size
    px = im.load()
    if not any(px[x, y][3] > 0 for y in range(h) for x in range(w)):
        return "preview_failed"
    corners = (px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1])
    if all(c[3] == 0 for c in corners):
        return "transparent"
    return "normal"


def admit(data: bytes, *, limits: Limits | None = None, clock=None) -> Verdict:
    """In-process policy. Production callers use isolated_admit(), which runs this in a limited child."""
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
    text, encoding_error = _decode(data)
    if encoding_error:
        return _rejected(encoding_error)
    danger = _unicode_danger(text or "")
    if danger:
        return _rejected(danger)
    if slow():
        return _rejected("too_slow")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return _rejected("malformed")
    if not isinstance(root.tag, str) or _local(root.tag) != "svg":
        return _rejected("not_svg")
    walked = _walk(root, limits, [0])
    if walked:
        return _rejected(walked)
    if slow():
        return _rejected("too_slow")
    size = _canvas_size(_attrs(root), limits)
    if size == "too_many_pixels" or size is None:
        return _rejected("too_many_pixels" if size == "too_many_pixels" else "malformed")
    w, h, vx, vy, vw, vh = size
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    scale_x, scale_y = w / vw, h / vh
    _draw(root, ImageDraw.Draw(im, "RGBA"), (-vx * scale_x, -vy * scale_y, scale_x, scale_y))
    if slow():
        return _rejected("too_slow")
    state = _pixels(im)
    if state == "preview_failed":
        return Verdict("preview_failed", "undrawable", data, _failure_png(), PREVIEW_FAILED, "")
    pair = _READY if state == "normal" else _CLEAR
    return Verdict(state, state, data, _png(im), pair, "")


def isolated_admit(data: bytes) -> Verdict:
    """Production entry. The child renders only after network and filesystem isolation both succeed."""
    if not isinstance(data, (bytes, bytearray)):
        return _rejected("not_svg")
    data = bytes(data)
    if len(data) > LIMITS.max_bytes:
        return _rejected("too_large")
    worker = Path(__file__).with_name("svg_worker.py")
    try:
        proc = subprocess.run(
            [sys.executable, str(worker)],
            input=data,
            capture_output=True,
            timeout=WORKER_ALARM + 2,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _rejected("too_slow")
    if proc.returncode != 0 or not proc.stdout:
        verdict = _rejected("resource_limit")
        verdict.runtime = {"mode": "subprocess", "returncode": proc.returncode, "network_namespace": False}
        return verdict
    try:
        payload = json.loads(proc.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _rejected("resource_limit")
    download = base64.b64decode(payload["download"]) if payload.get("download") else None
    preview = base64.b64decode(payload["preview"]) if payload.get("preview") else None
    pair = {"zh": payload.get("message_zh") or REJECTED["zh"], "en": payload.get("message_en") or REJECTED["en"]}
    applied = payload.get("applied") or {}
    isolated = bool(payload.get("rendered") and applied.get("network_isolated") and applied.get("filesystem_isolated"))
    if not isolated:
        verdict = _rejected("isolation_unavailable")
        verdict.runtime = {"mode": "subprocess", "rendered": False, **applied}
        return verdict
    verdict = Verdict(payload.get("status") or "rejected", payload.get("reason") or "resource_limit", download, preview, pair, payload.get("kind") or "")
    verdict.runtime = {"mode": "subprocess", "rendered": True, **applied}
    if verdict.status == "rejected":
        verdict.download = None
        verdict.preview_png = None
        verdict.preview_type = None
    return verdict
