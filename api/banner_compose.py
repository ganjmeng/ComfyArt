"""youtube-channel-banner: 精确排版 final (reference run review-assets d7672d03).

The model draws a text-free 16:9 base. This module upscales it to exactly 2560×1440
and draws the three text lines with a bundled font, so the text is pixel-exact and
always inside YouTube's safe areas (reference contract, [left, top, right, bottom],
right/bottom exclusive):

- target box (P0 visible ink aim):      [820, 610, 1740, 818]  920×208, left-aligned
- shows-everywhere strict core:         [642, 551, 1918, 889]  every line's ink must be inside
- shows-everywhere hard boundary:       [482, 509, 2078, 931]  no line may cross it
- desktop visible band:                 [0, 509, 2560, 931]

Ink is measured on the rendered pixels (alpha of each line's own layer), not on font
metrics. There is no stroke or shadow, so the glyph alpha is all the visible ink.
Font size is fitted to the box width; a line that does not fit wraps or shrinks, and
nothing is ever clipped. If the text cannot be placed inside the strict core the call
fails instead of delivering clipped or out-of-area text.

This path is only for the youtube-channel-banner user-side final. It must not be used
by the gold / example wash pipelines (they keep the no-local-text rule): compose()
checks the skill, the purpose, and refuses when a wash script is on the call stack.
"""
from __future__ import annotations

import io
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SKILL = "youtube-channel-banner"
PURPOSE_USER_FINAL = "user_final"

CANVAS = (2560, 1440)
TARGET_BOX = (820, 610, 1740, 818)
STRICT_CORE = (642, 551, 1918, 889)
HARD_BOUNDARY = (482, 509, 2078, 931)
DESKTOP_BAND = (0, 509, 2560, 931)
TV_FULL = (0, 0, 2560, 1440)

FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_BOLD = FONT_DIR / "ComfyArtBannerSansSC-Bold.otf"
FONT_REGULAR = FONT_DIR / "ComfyArtBannerSansSC-Regular.otf"

# Base sizes at scale 1.0 (channel name is the largest, schedule the smallest).
CHANNEL_PX = 96
TAGLINE_PX = 46
SCHEDULE_PX = 32
GAP_AFTER_CHANNEL = 22
GAP_AROUND_ACCENT = 18
ACCENT_PX = 4
ACCENT_LEN = 200
MIN_SCALE = 0.18
# Vertical room when the text cannot fit the target box height: the strict core minus
# a small inner margin, still centred on the target box.
STRICT_MARGIN = 6
# Extra space between wrapped rows of the same line, as a share of its font size.
LINE_GAP = 0.22
# Below this scale a line wraps before it shrinks further (readability floor).
WRAP_FLOOR = 0.5

DEFAULT_BRAND = "#2F6BFF"
DEFAULT_TEXT = "#1F2430"
DEFAULT_SCHEDULE = "#4A5160"
DEFAULT_ACCENT = "#FF7A59"

MAX_FIELD_CHARS = 120

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")
# Closing punctuation never starts a wrapped line; opening punctuation never ends one.
_NO_LINE_START = set("，。、；：！？）》」』】〕〉,.;:!?)]}·—…%")
_NO_LINE_END = set("（《「『【〔〈([{")


class CompositorRefused(PermissionError):
    """The banner text compositor was called outside the youtube-channel-banner user final."""


class LayoutError(ValueError):
    """The text cannot be placed inside the strict core without clipping."""


def _color(value: object, fallback: str) -> tuple[int, int, int]:
    m = _HEX.match(str(value or "").strip())
    h = m.group(1) if m else fallback.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _wash_on_stack() -> str | None:
    """Filename of a wash-pipeline frame on the current call stack, if any."""
    f = sys._getframe(1)
    while f is not None:
        path = (f.f_code.co_filename or "").replace("\\", "/")
        name = os.path.basename(path).lower()
        if "wash" in name or "/scripts/" in path:
            return path
        f = f.f_back
    return None


def guard(skill: object, purpose: object) -> None:
    """Refuse every caller except the youtube-channel-banner user-side final."""
    if str(skill or "") != SKILL:
        raise CompositorRefused(f"banner text compositing is only for the {SKILL} skill (got {skill!r})")
    if purpose != PURPOSE_USER_FINAL:
        raise CompositorRefused("banner text compositing is only for the user-side final")
    wash = _wash_on_stack()
    if wash:
        raise CompositorRefused(f"banner text compositing cannot be called from a wash pipeline ({wash})")


def _font(path: Path, px: int):
    from PIL import ImageFont

    return ImageFont.truetype(str(path), max(6, int(round(px))))


def missing_glyphs(text: str) -> list[str]:
    """Characters the bundled font cannot draw (they would render as the .notdef box).

    Pillow only (runtime has no fontTools): a character whose bitmap equals the
    .notdef bitmap of a private-use code point is missing from the font.
    """
    out = set()
    for ch in set(text):
        if ch.isspace() or ch in _GLYPH_OK:
            continue
        if any(_glyph_sig(p, ch) == _glyph_sig(p, _NOTDEF_PROBE) for p in (FONT_BOLD, FONT_REGULAR)):
            out.add(ch)
        else:
            _GLYPH_OK.add(ch)
    return sorted(out)


_NOTDEF_PROBE = "\ue000"
_GLYPH_OK: set[str] = set()


def _glyph_sig(path: Path, ch: str) -> tuple:
    font = _font(path, 40)
    mask = font.getmask(ch)
    return mask.size, bytes(mask)


def _tokens(text: str) -> list[str]:
    """Wrap units: a Latin/number word (with its trailing spaces) or one CJK character."""
    out: list[str] = []
    for m in re.finditer(r"[A-Za-z0-9_@#&+\-'’./:]+\s*|\s+|.", text):
        out.append(m.group(0))
    return out


def _width(font, text: str) -> int:
    if not text:
        return 0
    l, _, r, _ = font.getbbox(text, anchor="ls")
    return r - l


def _break_word(font, word: str, width: int) -> list[str]:
    parts, cur = [], ""
    for ch in word:
        if cur and _width(font, cur + ch) > width:
            parts.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        parts.append(cur)
    return parts


def wrap(font, text: str, width: int) -> list[str]:
    """Greedy wrap for mixed CJK + Latin text; never returns a line wider than width."""
    text = " ".join(str(text or "").split())
    if not text:
        return []
    lines: list[str] = []
    cur = ""
    for tok in _tokens(text):
        if _width(font, (cur + tok).rstrip()) <= width:
            cur += tok
            continue
        if not cur.strip():
            # A single token wider than the box: break it by characters.
            pieces = _break_word(font, tok.strip(), width)
            lines.extend(pieces[:-1])
            cur = pieces[-1] if pieces else ""
            continue
        # Kinsoku: carry an opening bracket to the next line; pull a closing mark back.
        if tok[:1] in _NO_LINE_START and _width(font, (cur + tok).rstrip()) <= width * 1.04:
            cur += tok
            continue
        carry = ""
        if cur and cur.rstrip()[-1:] in _NO_LINE_END:
            carry = cur.rstrip()[-1]
            cur = cur.rstrip()[:-1]
        lines.append(cur.rstrip())
        nxt = (carry + tok).lstrip()
        if _width(font, nxt) > width:
            pieces = _break_word(font, nxt, width)
            lines.extend(pieces[:-1])
            nxt = pieces[-1] if pieces else ""
        cur = nxt
    if cur.strip():
        lines.append(cur.rstrip())
    return [ln for ln in lines if ln]


@dataclass
class Line:
    role: str
    text: str
    font_path: Path
    px: int
    color: tuple[int, int, int]
    x: int = 0
    baseline: int = 0
    ink: tuple[int, int, int, int] | None = None


@dataclass
class Layout:
    scale: float
    lines: list[Line] = field(default_factory=list)
    accent: tuple[int, int, int, int] | None = None
    accent_color: tuple[int, int, int] = (0, 0, 0)
    wrapped: bool = False


def _plan(channel: str, tagline: str, schedule: str, scale: float, allow_wrap: bool,
          colors: dict, box_w: int) -> tuple[list[tuple[str, list[str], Path, int, tuple]], int] | None:
    rows = []
    specs = (("channel", channel, FONT_BOLD, CHANNEL_PX, colors["brand"]),
             ("tagline", tagline, FONT_REGULAR, TAGLINE_PX, colors["text"]),
             ("schedule", schedule, FONT_REGULAR, SCHEDULE_PX, colors["schedule"]))
    for role, text, path, base, color in specs:
        text = " ".join(str(text or "").split())
        if not text:
            continue
        px = max(6, int(round(base * scale)))
        font = _font(path, px)
        if allow_wrap:
            parts = wrap(font, text, box_w)
        else:
            if _width(font, text) > box_w:
                return None
            parts = [text]
        rows.append((role, parts, path, px, color))
    return rows, 0


def _block(rows, scale: float):
    """Baselines relative to the block top, stacked on each line's real glyph box."""
    y = 0
    placed = []
    accent = None
    for i, (role, parts, path, px, color) in enumerate(rows):
        font = _font(path, px)
        for j, part in enumerate(parts):
            _, top, _, bottom = font.getbbox(part, anchor="ls")
            # Use at least a CJK em box so mixed rows keep an even rhythm.
            top = min(top, -int(round(px * 0.88)))
            bottom = max(bottom, int(round(px * 0.12)))
            if j:
                y += int(round(px * LINE_GAP))
            placed.append((role, part, path, px, color, y - top))
            y += bottom - top
        nxt = rows[i + 1][0] if i + 1 < len(rows) else None
        if role == "channel" and nxt:
            y += int(round(GAP_AFTER_CHANNEL * scale))
        if role == "tagline" and nxt == "schedule":
            g = int(round(GAP_AROUND_ACCENT * scale))
            t = max(2, int(round(ACCENT_PX * scale)))
            accent = (y + g, t)
            y += g + t + g
        elif role == "channel" and nxt == "schedule":
            y += int(round(GAP_AROUND_ACCENT * scale))
    return placed, accent, y


def _render_layer(line: Line):
    from PIL import Image, ImageDraw

    layer = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(layer).text((line.x, line.baseline), line.text, fill=255, font=_font(line.font_path, line.px), anchor="ls")
    return layer


def _inside(bbox, box) -> bool:
    return bbox[0] >= box[0] and bbox[1] >= box[1] and bbox[2] <= box[2] and bbox[3] <= box[3]


def layout(channel: str, tagline: str = "", schedule: str = "", *, colors: dict | None = None) -> Layout:
    """Fit the lines into the target box (wrap/shrink); ink-checked against the strict core."""
    colors = colors or {"brand": _color(None, DEFAULT_BRAND), "text": _color(None, DEFAULT_TEXT),
                        "schedule": _color(None, DEFAULT_SCHEDULE), "accent": _color(None, DEFAULT_ACCENT)}
    if not " ".join(str(channel or "").split()):
        raise LayoutError("channel name is required")
    tx0, ty0, tx1, ty1 = TARGET_BOX
    box_w = tx1 - tx0
    cy = (ty0 + ty1) / 2
    tall = (STRICT_CORE[3] - STRICT_MARGIN) - (STRICT_CORE[1] + STRICT_MARGIN)
    target_h = ty1 - ty0
    steps = [round(1.0 - 0.02 * i, 2) for i in range(int((1.0 - MIN_SCALE) / 0.02) + 1)]
    # In order: one row per line in the target box; wrapped rows in the target box;
    # wrapped rows in the strict-core height; then shrink below the readability floor.
    passes = ((False, target_h, WRAP_FLOOR), (True, target_h, WRAP_FLOOR),
              (True, tall, WRAP_FLOOR), (True, tall, MIN_SCALE))
    for allow_wrap, max_h, floor in passes:
        for scale in steps:
            if scale < floor:
                break
            planned = _plan(channel, tagline, schedule, scale, allow_wrap, colors, box_w)
            if planned is None:
                continue
            rows, _ = planned
            placed, accent, h = _block(rows, scale)
            if h > max_h:
                continue
            top = int(round(cy - h / 2))
            lo, hi = STRICT_CORE[1] + STRICT_MARGIN, STRICT_CORE[3] - STRICT_MARGIN - h
            top = max(lo, min(top, hi)) if hi >= lo else top
            lines = [Line(role, text, path, px, color, x=tx0, baseline=top + base)
                     for role, text, path, px, color, base in placed]
            ok = True
            for ln in lines:
                ln.ink = _render_layer(ln).getbbox()
                if ln.ink is None or not _inside(ln.ink, STRICT_CORE) or not _inside(ln.ink, HARD_BOUNDARY):
                    ok = False
                    break
            if not ok:
                continue
            acc = None
            if accent:
                ay, t = accent
                length = max(24, int(round(ACCENT_LEN * scale)))
                acc = (tx0 + 2, top + ay, tx0 + 2 + length, top + ay + t)
                if not _inside(acc, STRICT_CORE):
                    continue
            return Layout(scale=scale, lines=lines, accent=acc, accent_color=colors["accent"],
                          wrapped=any(len(r[1]) > 1 for r in rows))
    raise LayoutError("the banner text cannot fit inside the YouTube strict safe area without clipping")


def _to_canvas(base_bytes: bytes):
    """Center-crop to 16:9 when needed, then scale to exactly 2560×1440 (the reference run upscales the 2k base)."""
    from PIL import Image

    img = Image.open(io.BytesIO(base_bytes))
    img.load()
    img = img.convert("RGB")
    w, h = img.size
    target = CANVAS[0] / CANVAS[1]
    crop = None
    if abs(w / h - target) > 0.01:
        if w / h > target:
            nw = int(round(h * target))
            crop = ((w - nw) // 2, 0, (w - nw) // 2 + nw, h)
        else:
            nh = int(round(w / target))
            crop = (0, (h - nh) // 2, w, (h - nh) // 2 + nh)
        img = img.crop(crop)
    return img.resize(CANVAS, Image.LANCZOS), (w, h), crop


def graphic_mask(img):
    """Pixels that are part of a graphic (not light, calm background)."""
    import numpy as np

    a = np.asarray(img.convert("RGB"), dtype=np.int32)
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    lum = (a[..., 0] * 299 + a[..., 1] * 587 + a[..., 2] * 114) // 1000
    sat = (mx - mn)
    return (lum < 170) | (sat > 70)


def compose(base_bytes: bytes, *, channel: str, tagline: str = "", schedule: str = "",
            brand_color: object = None, text_color: object = None, accent_color: object = None,
            skill: object = None, purpose: object = None) -> tuple[bytes, dict]:
    """PNG bytes of the 2560×1440 final plus a report (ink boxes, checks, sizes)."""
    guard(skill, purpose)
    from PIL import Image, ImageDraw
    import numpy as np

    fields = {"channel": channel, "tagline": tagline, "schedule": schedule}
    for k, v in fields.items():
        if len(str(v or "")) > MAX_FIELD_CHARS:
            raise LayoutError(f"{k} is longer than {MAX_FIELD_CHARS} characters")
    missing = missing_glyphs("".join(str(v or "") for v in fields.values()))
    if missing:
        raise LayoutError("the bundled font cannot draw: " + "".join(missing))
    colors = {"brand": _color(brand_color, DEFAULT_BRAND), "text": _color(text_color, DEFAULT_TEXT),
              "schedule": _color(None, DEFAULT_SCHEDULE), "accent": _color(accent_color, DEFAULT_ACCENT)}
    plan = layout(channel, tagline, schedule, colors=colors)
    canvas, base_size, crop = _to_canvas(base_bytes)
    graphic = graphic_mask(canvas)
    out = canvas.copy()
    ink_union = np.zeros((CANVAS[1], CANVAS[0]), dtype=bool)
    report_lines = []
    for ln in plan.lines:
        layer = _render_layer(ln)
        solid = Image.new("RGB", CANVAS, ln.color)
        out.paste(solid, (0, 0), layer)
        ink = layer.getbbox()
        ink_union |= np.asarray(layer) > 0
        report_lines.append({
            "role": ln.role, "text": ln.text, "px": ln.px, "ink_bbox": list(ink),
            "inside_strict_core": _inside(ink, STRICT_CORE), "inside_hard_boundary": _inside(ink, HARD_BOUNDARY),
        })
    if plan.accent:
        ImageDraw.Draw(out).rectangle([plan.accent[0], plan.accent[1], plan.accent[2] - 1, plan.accent[3] - 1], fill=plan.accent_color)
        a = plan.accent
        ink_union[a[1]:a[3], a[0]:a[2]] = True
        report_lines.append({"role": "accent", "text": "", "px": a[3] - a[1], "ink_bbox": list(a),
                             "inside_strict_core": _inside(a, STRICT_CORE), "inside_hard_boundary": _inside(a, HARD_BOUNDARY)})
    ink_px = int(ink_union.sum())
    overlap = float((ink_union & graphic).sum() / ink_px) if ink_px else 0.0
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    report = {
        "width": CANVAS[0], "height": CANVAS[1], "base_size": list(base_size), "base_crop": list(crop) if crop else None,
        "scale": plan.scale, "wrapped": plan.wrapped, "lines": report_lines,
        "target_box": list(TARGET_BOX), "strict_core": list(STRICT_CORE), "hard_boundary": list(HARD_BOUNDARY),
        "all_inside_strict_core": all(r["inside_strict_core"] for r in report_lines),
        "all_inside_hard_boundary": all(r["inside_hard_boundary"] for r in report_lines),
        "graphic_overlap": round(overlap, 4),
        "text_area_clear": overlap <= 0.02,
        "font": FONT_BOLD.name.replace("-Bold.otf", ""),
    }
    return buf.getvalue(), report


# --- generate_image prompts for the three model steps (all GPT Image 2.6 Sunburst, 16:9 2k) ---

STAGES = ("board", "base", "direct")
STAGE_WIDTH, STAGE_HEIGHT, STAGE_RATIO = 2048, 1152, "16:9"

BOARD_CLAUSE = (
    "Direction board: ONE 16:9 image made of three stacked 16:3 horizontal YouTube channel banners "
    "(top, middle, bottom) separated by thin light gutters. The three directions differ in structure, "
    "not only in color: top = brand-led layout with generous white space and one simple graphic device; "
    "middle = full-frame illustrated scene spanning the whole banner; bottom = modular grid / node system "
    "with the text set inside the grid. All three share the same brand colors, the same Chinese sans-serif "
    "typeface and the same copy, exactly as quoted. No panel labels, no captions, no direction names, no "
    "fake UI, no buttons, no invented dates, accounts, handles or contact details, no prompt text."
)
BASE_CLAUSE = (
    "Text-free background plate for a 2560x1440 YouTube channel banner: absolutely NO text of any kind - "
    "no letters, words, numbers, logos, wordmarks, watermarks, signatures, captions, labels, signage, "
    "user-interface elements, buttons, icons, frames or fake UI anywhere in the image. Keep the chosen "
    "direction's main graphic and place it in the right part of the middle horizontal band (about 70%-81% "
    "across, 36%-64% down), fully inside that band. Leave the left and center of the middle band (about "
    "30%-68% across) as a light, calm, empty area for text that will be added later. Soft extension of the "
    "same light texture toward the top, bottom and edges."
)
DIRECT_CLAUSE = (
    "Final 16:9 YouTube channel banner with the text drawn by the image model. Render only the quoted text, "
    "spelled exactly, in a clean Chinese sans-serif, left-aligned inside the central safe band (about "
    "25%-75% across, 38%-62% down): the channel name largest in the brand color, the tagline smaller in a "
    "dark color, the schedule smallest. No other text, no fake UI, no invented dates, accounts or contact "
    "details, no prompt text."
)
_CLAUSES = {"board": BOARD_CLAUSE, "base": BASE_CLAUSE, "direct": DIRECT_CLAUSE}
_QUOTED = re.compile(r"[\"“”「」『』][^\"“”「」『』]{1,200}[\"“”「」『』]")


def stage_args(args: dict) -> dict:
    """generate_image args for one youtube-channel-banner model step.

    Forces one 16:9 image at 2k (2048×1152, the review-assets d7672d03 size) and appends the
    stage's fixed clause. The base stage also drops any quoted copy from the prompt so
    no exact text is ever requested on the text-free plate.
    """
    args = dict(args)
    stage = str(args.pop("banner_stage", "") or "").strip().lower()
    if str(args.get("skill") or "") != SKILL or not stage:
        return args
    if stage not in STAGES:
        raise ValueError(f"banner_stage must be one of {', '.join(STAGES)}")
    prompt = str(args.get("prompt") or "").strip()
    if stage == "base":
        prompt = _QUOTED.sub("", prompt)
        prompt = re.sub(r"(?:\s*[/／·、,，+＋]\s*){2,}", " ", prompt)
        prompt = re.sub(r"[ \t]{2,}", " ", prompt).strip(" ,，/")
    clause = _CLAUSES[stage]
    if clause not in prompt:
        prompt = f"{prompt}\n{clause}" if prompt else clause
    args["prompt"] = prompt
    args["ratio"] = STAGE_RATIO
    args["width"], args["height"] = STAGE_WIDTH, STAGE_HEIGHT
    args["count"] = 1
    for k in ("n", "base", "base_strength", "output_format", "frame_count", "frame_duration_ms"):
        args.pop(k, None)
    return args
