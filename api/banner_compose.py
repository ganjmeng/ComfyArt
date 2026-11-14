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
Font size is fitted to the box width. A line that does not fit wraps first; the
tagline (subtitle) and third line (schedule / update line, e.g. 「每周二 / 周五更新」)
never shrink below a measured glyph height of 36px on the 2560×1440 canvas (or 0.3×
the title ink height when that is larger and still smaller than the title). The
tagline font size is always at least the update-line font size. Lines wrap at
· 、 ， / and spaces first, without splitting English words; character breaks are a
last resort and must not leave a single character or a short word (e.g. Edition)
alone. If the text still cannot be placed inside the strict core at that floor, the
call raises instead of clipping or going below the floor.

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
SCHEDULE_PX = 40
# Tagline (subtitle) and schedule (update line) measured ink height floor on the 2560×1440 canvas.
LINE_MIN_INK = 36
SCHEDULE_MIN_INK = LINE_MIN_INK  # alias
SCHEDULE_TITLE_RATIO = 0.3
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
    """The text cannot be placed inside the strict core at the size floors and title > tagline hierarchy."""


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


def _glyph_ink_height(path: Path, px: int, text: str) -> int:
    """Measured ink height of `text` at `px`, same method as the compositor's layers."""
    from PIL import Image, ImageDraw

    text = " ".join(str(text or "").split())
    if not text:
        return 0
    px = max(6, int(round(px)))
    w = max(64, px * (len(text) + 4) + 16)
    h = max(64, px * 4)
    layer = Image.new("L", (w, h), 0)
    ImageDraw.Draw(layer).text((px, px * 2), text, fill=255, font=_font(path, px), anchor="ls")
    box = layer.getbbox()
    return 0 if box is None else box[3] - box[1]


def _px_for_min_ink(path: Path, text: str, min_ink: int) -> int:
    """Smallest font size whose measured ink height is at least `min_ink`."""
    text = " ".join(str(text or "").split())
    if not text:
        return 6
    lo, hi = 6, 240
    while lo < hi:
        mid = (lo + hi) // 2
        if _glyph_ink_height(path, mid, text) >= min_ink:
            hi = mid
        else:
            lo = mid + 1
    return lo


def _schedule_min_ink(title_ink: int) -> int:
    """Primary floor is 36px. Use 0.3× title ink when that is larger and still below the title."""
    ratio = int(round(SCHEDULE_TITLE_RATIO * title_ink)) if title_ink else 0
    if ratio > SCHEDULE_MIN_INK and ratio < title_ink:
        return ratio
    return SCHEDULE_MIN_INK


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


def _width(font, text: str) -> int:
    if not text:
        return 0
    l, _, r, _ = font.getbbox(text, anchor="ls")
    return r - l


# Preferred wrap points (no jieba): middle dot, enumeration/comma, slash, and spaces.
_WRAP_BREAKS = set("·、，/")
_SHORT_LATIN = 8  # "Edition" is 8; a lone shorter Latin word on a line is an orphan
_LATIN_ATOM = re.compile(r"[A-Za-z]+")


def _segments(text: str) -> list[str]:
    """Split on preferred breaks, keeping the break character on the preceding segment."""
    segs, buf = [], ""
    for ch in text:
        buf += ch
        if ch in _WRAP_BREAKS or ch.isspace():
            segs.append(buf)
            buf = ""
    if buf:
        segs.append(buf)
    return segs


def _latin_words(text: str) -> list[str]:
    return _LATIN_ATOM.findall(text or "")


def _is_short_latin_line(text: str) -> bool:
    s = text.strip()
    return bool(re.fullmatch(r"[A-Za-z]+", s)) and len(s) <= _SHORT_LATIN


def _short_source_words(text: str) -> set[str]:
    """Space-delimited short Latin words in the source (e.g. Edition). Punctuation-only splits do not count."""
    out: set[str] = set()
    for tok in (text or "").split():
        core = tok.strip("".join(_WRAP_BREAKS))
        if re.fullmatch(r"[A-Za-z]+", core) and len(core) <= _SHORT_LATIN:
            out.add(core)
    return out


def _is_orphan_short_word(line: str, source: str) -> bool:
    s = line.strip()
    return _is_short_latin_line(s) and s in _short_source_words(source)


def _is_single_char_line(text: str) -> bool:
    return len(text.strip()) == 1


def _join_segs(a: str, b: str) -> str:
    if not a:
        return b.lstrip() if b[:1].isspace() else b
    if a[-1:].isspace() or a[-1:] in _WRAP_BREAKS or b[:1].isspace() or b[:1] in _WRAP_BREAKS:
        return a + b
    return a + b


def _break_chars(font, text: str, width: int) -> list[str] | None:
    """Character wrap as a last resort. No 1-character piece. None if it cannot be done."""
    text = text.strip()
    if not text:
        return []
    if _width(font, text) <= width:
        return [text]
    if len(text) < 2 or _width(font, text[:2]) > width:
        return None
    lines, cur = [], ""
    for ch in text:
        trial = cur + ch
        if cur and _width(font, trial) > width:
            if len(cur) < 2:
                return None
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        if len(cur) == 1 and lines:
            prev = lines[-1]
            if len(prev) < 3 or _width(font, cur) > width:
                return None
            # Don't leave a single char alone: move one character down.
            lines[-1] = prev[:-1]
            cur = prev[-1] + cur
            if _width(font, lines[-1]) > width or _width(font, cur) > width or len(lines[-1]) < 2:
                return None
        if len(cur.strip()) < 2:
            return None
        lines.append(cur)
    if any(len(ln.strip()) < 2 for ln in lines):
        return None
    return lines


def wrap(font, text: str, width: int) -> list[str] | None:
    """Wrap mixed CJK + Latin text.

    Break first at · 、 ， / and spaces, and never split an English word. Only when a
    segment has no break point and is wider than the box, break by character — and
    then never leave a single character at a line end or alone, or a short word
    (e.g. Edition) alone on a line. Returns None when the text cannot be wrapped
    legally at this width (the caller should shrink other lines or raise).
    """
    text = " ".join(str(text or "").split())
    if not text:
        return []
    if _width(font, text) <= width:
        return [text]
    lines: list[str] = []
    cur = ""
    for seg in _segments(text):
        trial = _join_segs(cur, seg)
        if _width(font, trial.rstrip()) <= width:
            cur = trial
            continue
        if not cur.strip():
            # A single segment wider than the box: no preferred break remains; character-break.
            parts = _break_chars(font, seg, width)
            if parts is None:
                return None
            lines.extend(parts[:-1])
            cur = parts[-1]
            continue
        lines.append(cur.rstrip())
        body = seg.lstrip()
        if _width(font, body.rstrip()) <= width:
            cur = body
        else:
            parts = _break_chars(font, body, width)
            if parts is None:
                return None
            lines.extend(parts[:-1])
            cur = parts[-1]
    if cur.strip():
        lines.append(cur.rstrip())
    lines = [ln for ln in lines if ln.strip()]

    def _glue(a: str, b: str) -> str:
        b = b.strip()
        if not a:
            return b
        if a[-1:].isspace() or a[-1:] in _WRAP_BREAKS or b[:1] in _WRAP_BREAKS:
            return (a.rstrip() if a[-1:].isspace() and b[:1] in _WRAP_BREAKS else a) + (b if a[-1:].isspace() or b[:1] in _WRAP_BREAKS or a[-1:] in _WRAP_BREAKS else " " + b)
        return a + " " + b

    def _split_last_unit(text: str) -> tuple[str, str] | None:
        segs = [s for s in _segments(text) if s.strip()]
        if len(segs) < 2:
            return None
        head = "".join(segs[:-1]).rstrip()
        tail = segs[-1].strip()
        if not head or not tail:
            return None
        return head, tail

    # Pull a short orphan word (or lone character) up onto the previous line.
    # If that overflows, move the previous line's last unit down with the orphan.
    # If neither fits, this width is illegal (do not leave the orphan).
    changed = True
    while changed:
        changed = False
        for i, ln in enumerate(lines):
            orphan = _is_orphan_short_word(ln, text) or _is_single_char_line(ln)
            if not orphan or len(lines) == 1:
                continue
            if i > 0:
                merged = _glue(lines[i - 1], ln)
                if _width(font, merged.rstrip()) <= width:
                    lines[i - 1] = merged.rstrip()
                    lines.pop(i)
                    changed = True
                    break
                moved = _split_last_unit(lines[i - 1])
                if moved:
                    head, tail = moved
                    nxt = _glue(tail, ln)
                    if (_width(font, head) <= width and _width(font, nxt) <= width
                            and not _is_single_char_line(head)
                            and not (len(lines) > 2 and _is_short_latin_line(head))):
                        lines[i - 1] = head
                        lines[i] = nxt
                        changed = True
                        break
            return None
    if any(_is_single_char_line(ln) for ln in lines):
        return None
    if len(lines) > 1 and any(_is_orphan_short_word(ln, text) for ln in lines):
        return None
    # English words stay intact when packing at preferred breaks. Character-break
    # of a segment wider than the box may cut a letter-run that had no break point.
    if any(_width(font, ln) > width for ln in lines):
        return None
    return lines


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
          colors: dict, box_w: int, schedule_px: int | None = None,
          tagline_px: int | None = None, channel_px: int | None = None,
          ) -> tuple[list[tuple[str, list[str], Path, int, tuple]], int] | None:
    rows = []
    specs = (("channel", channel, FONT_BOLD, CHANNEL_PX, colors["brand"]),
             ("tagline", tagline, FONT_REGULAR, TAGLINE_PX, colors["text"]),
             ("schedule", schedule, FONT_REGULAR, SCHEDULE_PX, colors["schedule"]))
    forced = {"channel": channel_px, "tagline": tagline_px, "schedule": schedule_px}
    for role, text, path, base, color in specs:
        text = " ".join(str(text or "").split())
        if not text:
            continue
        if forced[role] is not None:
            px = max(6, int(forced[role]))
        else:
            px = max(6, int(round(base * scale)))
        font = _font(path, px)
        if allow_wrap:
            parts = wrap(font, text, box_w)
            if parts is None:
                return None
        else:
            if _width(font, text) > box_w:
                return None
            parts = [text]
        rows.append((role, parts, path, px, color))
    return rows, 0


def _line_px_for(text: str, scale: float, base_px: int, title_ink: int, parts: list[str] | None = None,
                 path: Path = FONT_REGULAR, min_ink: int | None = None) -> int:
    """Font size: scaled size, never below the ink floor for this copy (each wrapped row)."""
    need = LINE_MIN_INK if min_ink is None else min_ink
    if min_ink is None and path == FONT_REGULAR:
        need = _schedule_min_ink(title_ink)
    texts = [p for p in (parts or []) if p] or [" ".join(str(text or "").split())]
    texts = [t for t in texts if t]
    if not texts:
        return 6
    floor = max(_px_for_min_ink(path, t, need) for t in texts)
    return max(floor, int(round(base_px * scale)))


def _schedule_px_for(schedule: str, scale: float, title_ink: int, parts: list[str] | None = None) -> int:
    return _line_px_for(schedule, scale, SCHEDULE_PX, title_ink, parts)


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
    """Fit the lines into the target box (wrap first, then shrink other lines); ink-checked against the strict core.

    Every title, tagline and schedule row never shrinks below LINE_MIN_INK (36px). Tagline/schedule may
    use 0.3× the title ink height when that is larger and still smaller than the title. Shrink order
    keeps title font size strictly greater than tagline, and tagline at least the update-line size.
    If the text still cannot fit after wrapping while holding that hierarchy, this raises.
    """
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
    # One row per line in the target box; wrap first in the target box; then wrap in
    # the strict-core height. Tagline and schedule may shrink toward their ink floors;
    # title stays strictly larger than the tagline, and every title row stays >= 36px ink.
    passes = ((False, target_h, WRAP_FLOOR), (True, target_h, WRAP_FLOOR),
              (True, tall, MIN_SCALE))
    for allow_wrap, max_h, floor in passes:
        for scale in steps:
            if scale < floor:
                break
            ch_px = max(6, int(round(CHANNEL_PX * scale)))
            sched_px = max(6, int(round(SCHEDULE_PX * scale))) if schedule else None
            tag_px = max(6, int(round(TAGLINE_PX * scale))) if tagline else None
            planned = _plan(channel, tagline, schedule, scale, allow_wrap, colors, box_w,
                            channel_px=ch_px, schedule_px=sched_px, tagline_px=tag_px)
            if planned is None:
                continue
            rows, _ = planned
            # After wrapping, bump every role to its ink floor and keep title > tagline >= schedule.
            stable = False
            for _ in range(6):
                by = {row[0]: row for row in rows}
                ch_parts = by["channel"][1] if "channel" in by else []
                title_ink = max((_glyph_ink_height(FONT_BOLD, ch_px, p) for p in ch_parts), default=LINE_MIN_INK)
                need = _schedule_min_ink(title_ink)
                new_ch = _line_px_for(channel, scale, CHANNEL_PX, title_ink, parts=ch_parts,
                                      path=FONT_BOLD, min_ink=LINE_MIN_INK) if ch_parts else ch_px
                new_sch = (_line_px_for(schedule, scale, SCHEDULE_PX, title_ink,
                                        parts=by["schedule"][1], min_ink=need)
                           if "schedule" in by else sched_px)
                new_tag = (_line_px_for(tagline, scale, TAGLINE_PX, title_ink,
                                        parts=by["tagline"][1], min_ink=need)
                           if "tagline" in by else tag_px)
                if new_tag is not None and new_sch is not None:
                    new_tag = max(new_tag, new_sch)
                if new_tag is not None and new_ch <= new_tag:
                    new_ch = new_tag + 1
                # Title ink must stay the largest: at least 36px, and above the tallest tagline row.
                if ch_parts and "tagline" in by and new_tag is not None:
                    tag_inks = [_glyph_ink_height(FONT_REGULAR, new_tag, p) for p in by["tagline"][1]]
                    if tag_inks:
                        new_ch = max(new_ch, _line_px_for(channel, scale, CHANNEL_PX, title_ink,
                                                          parts=ch_parts, path=FONT_BOLD,
                                                          min_ink=max(LINE_MIN_INK, max(tag_inks) + 1)))
                if (new_ch, new_tag, new_sch) == (ch_px, tag_px, sched_px):
                    stable = True
                    break
                nxt = _plan(channel, tagline, schedule, scale, allow_wrap, colors, box_w,
                            channel_px=new_ch, schedule_px=new_sch, tagline_px=new_tag)
                if nxt is None:
                    planned = None
                    break
                ch_px, tag_px, sched_px = new_ch, new_tag, new_sch
                rows, _ = nxt
                planned = nxt
            if planned is None or not stable:
                continue
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
            floored = [ln for ln in lines if ln.role in ("channel", "tagline", "schedule") and ln.ink]
            if any((ln.ink[3] - ln.ink[1]) < LINE_MIN_INK for ln in floored):
                continue
            ch_pxs = [ln.px for ln in lines if ln.role == "channel"]
            tag_pxs = [ln.px for ln in lines if ln.role == "tagline"]
            sch_pxs = [ln.px for ln in lines if ln.role == "schedule"]
            if tag_pxs and sch_pxs and min(tag_pxs) < max(sch_pxs):
                continue
            if tag_pxs and ch_pxs and min(ch_pxs) <= max(tag_pxs):
                continue
            ch_inks = [ln.ink[3] - ln.ink[1] for ln in lines if ln.role == "channel" and ln.ink]
            tag_inks = [ln.ink[3] - ln.ink[1] for ln in lines if ln.role == "tagline" and ln.ink]
            if ch_inks and tag_inks and min(ch_inks) <= max(tag_inks):
                continue
            acc = None
            if accent:
                ay, t = accent
                length = max(24, int(round(ACCENT_LEN * max(scale, 0.5))))
                acc = (tx0 + 2, top + ay, tx0 + 2 + length, top + ay + t)
                if not _inside(acc, STRICT_CORE):
                    continue
            return Layout(scale=scale, lines=lines, accent=acc, accent_color=colors["accent"],
                          wrapped=any(len(r[1]) > 1 for r in rows))
    raise LayoutError("三行文字换行后仍排不进横幅安全区（标题须大于副标题且各行需保持至少 36px），请缩短后再继续。")


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


SHORTEN_COPY_ID = "yt_shorten_copy"
SHORTEN_COPY = {
    "zh": {
        "prompt": "横幅上的文字排在安全区内有点长，请缩短后再继续。",
        "placeholder": "请输入更短的频道名 / 标语 / 更新行",
    },
    "en": {
        "prompt": "The banner text is a bit long for the safe area. Please shorten it to continue.",
        "placeholder": "Shorter name / tagline / update line",
    },
}
# Backward-compatible aliases (zh).
SHORTEN_COPY_PROMPT = SHORTEN_COPY["zh"]["prompt"]
SHORTEN_COPY_PLACEHOLDER = SHORTEN_COPY["zh"]["placeholder"]


def shorten_copy_lang() -> str:
    """Same ask-card language rule as the other cards (`bot_asks.card_lang`)."""
    from . import bot_asks
    lang = bot_asks.card_lang()
    return lang if lang in SHORTEN_COPY else "zh"


def shorten_copy_card(lang: str | None = None) -> dict:
    """Ask-user card: shorten the banner copy. Neutral wording, follows the UI/ask-card language."""
    from . import bot_asks

    copy = SHORTEN_COPY[lang if lang in SHORTEN_COPY else shorten_copy_lang()]
    return bot_asks.validate_spec({
        "questions": [{
            "id": SHORTEN_COPY_ID,
            "prompt": copy["prompt"],
            "allow_other": True,
            "placeholder": copy["placeholder"],
            "page": 1,
        }],
        "page_count": 1,
        "allow_skip": False,
        "allow_other": True,
        "prompt": copy["prompt"],
    })


def shorten_copy_result(lang: str | None = None) -> dict:
    lang = lang if lang in SHORTEN_COPY else shorten_copy_lang()
    card = shorten_copy_card(lang)
    copy = SHORTEN_COPY[lang]
    return {
        "status": "needs_input",
        "submitted": False,
        "generation_succeeded": False,
        "charged": False,
        "kind": "bannerTextShorten",
        "lang": lang,
        "prompt": card["prompt"],
        "questions": card["questions"],
        "page_count": card.get("page_count", 1),
        "allow_skip": False,
        "allow_other": True,
        "placeholder": copy["placeholder"],
        "ask": card,
    }


def preflight_base_text(args: dict) -> dict | None:
    """Dry-run the 2560×1440 layout for a youtube-channel-banner base generate, before any model call.

    Returns a shorten-copy card when the chosen copy will not fit at the line-3 floor.
    Returns None when this is not a base-stage call, or when the copy fits.
    """
    if str(args.get("skill") or "") != SKILL:
        return None
    try:
        stage = resolve_banner_stage(args)
    except ValueError:
        return None
    if stage != "base":
        return None
    channel = str(args.get("channel_name") or "")
    tagline = str(args.get("tagline") or "")
    schedule = str(args.get("schedule") or "")
    for value in (channel, tagline, schedule):
        if len(value) > MAX_FIELD_CHARS:
            return shorten_copy_result()
    try:
        layout(channel, tagline, schedule)
    except LayoutError:
        return shorten_copy_result()
    return None


_TEXT_MODE_STAGE = {"A": "base", "B": "direct"}
_DELIVERY_STAGE = {"A": "board", "B": "base", "C": "direct"}
_MISSING_STAGE_ERROR = (
    "banner_stage is required after card 2 (yt_direction / yt_text_mode) has been answered; "
    "pass banner_stage explicitly as 'base' (精确排版) or 'direct' (图像模型直出). "
    "The server will not generate another direction board."
)
_MISSING_DELIVERY_ERROR = (
    "banner_stage is required after card 1 (yt_delivery) has been answered with a value that cannot be mapped; "
    "pass banner_stage explicitly as 'board' (先出三方向选择板), 'base' (精确排版) or 'direct' (图像模型直出). "
    "The server will not generate a paid image."
)
_NOTURN_PREFIX = "__noturn__"


def _banner_chat_id() -> str:
    """The live Agent chat, when generate_image is running inside one."""
    from .mcp_tools._context import BOT_CHAT_ID, GUARD_CHAT_ID
    for raw in (BOT_CHAT_ID.get(), GUARD_CHAT_ID.get()):
        chat = str(raw or "").strip()
        if chat and not chat.startswith(_NOTURN_PREFIX):
            return chat
    return ""


def _ask_blocks(chat_id: str) -> list[dict]:
    """Ask-card blocks for this chat: persisted messages, then the live turn (freshest)."""
    if not chat_id:
        return []
    blocks: list[dict] = []
    seen: set[str] = set()

    def _add(block: object) -> None:
        if not isinstance(block, dict) or block.get("type") != "ask":
            return
        key = str(block.get("ask_id") or "")
        if key:
            if key in seen:
                # A later copy (live turn) replaces the earlier persisted one.
                blocks[:] = [b for b in blocks if str(b.get("ask_id") or "") != key]
            seen.add(key)
        blocks.append(block)

    try:
        from . import chat_store
        for msg in chat_store.list_messages(chat_id) or []:
            for block in msg.get("blocks") or []:
                _add(block)
    except Exception:
        pass
    try:
        from .bot_turns import ACTIVE_TURNS
        state = ACTIVE_TURNS.get(chat_id)
        if state is not None:
            for block in getattr(state, "blocks", None) or []:
                _add(block)
    except Exception:
        pass
    return blocks


def _block_questions(block: dict) -> list[dict]:
    questions = [q for q in (block.get("questions") or []) if isinstance(q, dict)]
    if block.get("id") or block.get("prompt"):
        questions = questions + [{"id": block.get("id"), "prompt": block.get("prompt")}]
    return questions


def _is_card_block(block: dict, locked_card: tuple) -> bool:
    from . import bot_asks
    return any(bot_asks._yt_match(q, locked) for q in _block_questions(block) for locked in locked_card)


def _is_card1_block(block: dict) -> bool:
    from . import bot_asks
    return _is_card_block(block, bot_asks.YT_CARD_1)


def _is_card2_block(block: dict) -> bool:
    from . import bot_asks
    return _is_card_block(block, bot_asks.YT_CARD_2)


def _latest_answered_card2(chat_id: str) -> dict | None:
    """Latest answered card 2 in block order (kept for tests and the order-aware lookup)."""
    found = None
    for block in _ask_blocks(chat_id):
        if block.get("status") == "answered" and _is_card2_block(block):
            found = block
    return found


def _latest_answered_card_positions(chat_id: str) -> tuple[int | None, int | None, dict | None, dict | None]:
    """Indices of the latest answered card 1 and card 2 in `_ask_blocks` order, plus both blocks."""
    card1_i: int | None = None
    card2_i: int | None = None
    card1_block: dict | None = None
    card2_block: dict | None = None
    for i, block in enumerate(_ask_blocks(chat_id)):
        if block.get("status") != "answered":
            continue
        if _is_card1_block(block):
            card1_i = i
            card1_block = block
        if _is_card2_block(block):
            card2_i = i
            card2_block = block
    return card1_i, card2_i, card1_block, card2_block


def _question_answer(block: dict, locked: dict) -> dict:
    from . import bot_asks
    answers = block.get("answers")
    if isinstance(answers, dict):
        raw = answers.get(locked["id"])
        if isinstance(raw, dict):
            return raw
        for key, value in answers.items():
            if isinstance(value, dict) and bot_asks._yt_match({"id": key, "prompt": ""}, locked):
                return value
    questions = [q for q in (block.get("questions") or []) if isinstance(q, dict)]
    if not questions:
        questions = [{"id": block.get("id"), "prompt": block.get("prompt")}]
    if len(questions) <= 1 and bot_asks._yt_match(questions[0], locked):
        return {"selected": block.get("selected") or [], "other_text": block.get("other_text") or ""}
    return {}


def _map_text_mode(selected: object, other_text: object, options: object) -> str | None:
    """Map a yt_text_mode answer to base / direct. Return None when it cannot be determined."""
    labels = {}
    if isinstance(options, list):
        for opt in options:
            if isinstance(opt, dict) and opt.get("id") is not None:
                labels[str(opt.get("id"))] = str(opt.get("label") or "")
    picked = [str(s).strip() for s in (selected or []) if str(s).strip()]
    for item in picked:
        key = item.upper()
        if key in _TEXT_MODE_STAGE:
            return _TEXT_MODE_STAGE[key]
        for oid, label in labels.items():
            if item == label or item == oid:
                return _TEXT_MODE_STAGE.get(str(oid).upper())
    text = str(other_text or "").strip()
    if not text:
        return None
    # Only exact, unambiguous wording — free text otherwise stays undetermined.
    if text in labels.values():
        for oid, label in labels.items():
            if text == label:
                return _TEXT_MODE_STAGE.get(str(oid).upper())
    compact = text
    for mark in ("（推荐）", "(推荐)", "(Recommended)", "(recommended)"):
        compact = compact.replace(mark, "")
    compact = compact.strip()
    exact = {
        "精确排版": "base",
        "精确排版（推荐）": "base",
        "exact layout": "base",
        "exact layout (recommended)": "base",
        "base": "base",
        "图像模型直出": "direct",
        "image model renders the text": "direct",
        "direct": "direct",
    }
    return exact.get(text) or exact.get(compact) or exact.get(text.lower())


def stage_from_card2(block: dict) -> str | None:
    """Infer banner_stage from an answered card-2 block, or None if it cannot be determined."""
    from . import bot_asks
    answer = _question_answer(block, bot_asks.YT_TEXT_MODE)

    def _is_text_mode(raw: object) -> bool:
        return any(bot_asks._yt_match(raw, locked) for locked in bot_asks.YT_TEXT_MODES)

    options = None
    for q in block.get("questions") or []:
        if isinstance(q, dict) and _is_text_mode(q):
            options = q.get("options")
            break
    if options is None and _is_text_mode({"id": block.get("id"), "prompt": block.get("prompt")}):
        options = block.get("options")
    return _map_text_mode(answer.get("selected"), answer.get("other_text"), options)


def _map_delivery(selected: object, other_text: object, options: object) -> str | None:
    """Map a yt_delivery answer to board / base / direct.

    A or a skipped empty answer → board; B → base; C → direct. Return None
    when free text or a selected value cannot be mapped — the caller refuses
    instead of generating a paid fallback.
    """
    labels = {}
    if isinstance(options, list):
        for opt in options:
            if isinstance(opt, dict) and opt.get("id") is not None:
                labels[str(opt.get("id"))] = str(opt.get("label") or "")
    picked = [str(s).strip() for s in (selected or []) if str(s).strip()]
    text = str(other_text or "").strip()
    if not picked and not text:
        return "board"
    for item in picked:
        key = item.upper()
        if key in _DELIVERY_STAGE:
            return _DELIVERY_STAGE[key]
        for oid, label in labels.items():
            if item == label or item == oid:
                return _DELIVERY_STAGE.get(str(oid).upper())
    if not text:
        return None
    if text in labels.values():
        for oid, label in labels.items():
            if text == label:
                return _DELIVERY_STAGE.get(str(oid).upper())
    exact = {
        "先出三方向选择板，再做终稿": "board",
        "board": "board",
        "直接出一张终稿，文字用精确排版渲染": "base",
        "base": "base",
        "直接出一张终稿，文字由图像模型生成": "direct",
        "direct": "direct",
    }
    return exact.get(text) or exact.get(text.lower())


def stage_from_card1(block: dict) -> str | None:
    """Infer banner_stage from an answered card-1 yt_delivery, or None if unmapped."""
    from . import bot_asks
    answer = _question_answer(block, bot_asks.YT_DELIVERY)
    options = None
    for q in block.get("questions") or []:
        if isinstance(q, dict) and bot_asks._yt_match(q, bot_asks.YT_DELIVERY):
            options = q.get("options")
            break
    if options is None and bot_asks._yt_match({"id": block.get("id"), "prompt": block.get("prompt")}, bot_asks.YT_DELIVERY):
        options = block.get("options")
    return _map_delivery(answer.get("selected"), answer.get("other_text"), options)


def infer_omitted_stage() -> str:
    """When banner_stage is omitted: card-order, then yt_delivery or yt_text_mode.

    Reads this chat's ask blocks (chat_store messages and the live ACTIVE_TURNS
    turn) in message/block order. If the latest answered card 2 is newer than
    the latest answered card 1, take base/direct from yt_text_mode; if that
    cannot be mapped, raise ValueError so the call is refused and no paid
    image is generated (card-2 skip stays a refusal).

    Otherwise use the latest card 1 yt_delivery: A or skipped → board, B →
    base, C → direct. Unmapped free text is refused (no paid fallback). A
    second banner in the same chat starts with a new card 1, so that card
    decides. No chat, or no answered card 1, still defaults to board.
    """
    chat_id = _banner_chat_id()
    if not chat_id:
        return "board"
    card1_i, card2_i, card1_block, card2_block = _latest_answered_card_positions(chat_id)
    if card2_i is not None and (card1_i is None or card2_i > card1_i):
        stage = stage_from_card2(card2_block)
        if stage in ("base", "direct"):
            return stage
        raise ValueError(_MISSING_STAGE_ERROR)
    if card1_block is None:
        return "board"
    stage = stage_from_card1(card1_block)
    if stage in ("board", "base", "direct"):
        return stage
    raise ValueError(_MISSING_DELIVERY_ERROR)


def resolve_banner_stage(args: dict) -> str | None:
    """Effective banner_stage for this generate_image call, or None for other skills."""
    if str(args.get("skill") or "") != SKILL:
        return None
    stage = str(args.get("banner_stage") or "").strip().lower()
    if stage:
        if stage not in STAGES:
            raise ValueError(f"banner_stage must be one of {', '.join(STAGES)}")
        return stage
    return infer_omitted_stage()


def stage_args(args: dict) -> dict:
    """generate_image args for one youtube-channel-banner model step.

    Forces one 16:9 image at 2k (2048×1152, the review-assets d7672d03 size) and appends the
    stage's fixed clause. The base stage also drops any quoted copy from the prompt so
    no exact text is ever requested on the text-free plate.

    #948: a missing banner_stage is decided by the latest answered card 1 and
    card 2 in this chat. When the latest card 2 is newer, the server takes
    base/direct from the yt_text_mode answer; if that cannot be determined,
    the call is refused (card-2 skip stays a refusal). Otherwise it uses
    card 1 yt_delivery: A or skipped → board (BOARD_CLAUSE plus 2048×1152),
    B → base, C → direct. Unmapped free text is refused — no paid fallback.
    A second banner in the same chat uses the new card 1. Agent-passed
    width/height/ratio are overwritten by the stage size. Other skills are
    unchanged.
    """
    args = dict(args)
    stage = resolve_banner_stage(args)
    args.pop("banner_stage", None)
    if stage is None:
        return args
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
    for k in ("n", "base", "base_strength", "output_format", "frame_count", "frame_duration_ms",
              "channel_name", "tagline", "schedule"):
        args.pop(k, None)
    return args
