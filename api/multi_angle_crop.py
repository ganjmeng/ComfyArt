"""#1003 (Refs #911) multi-angle finals: crop the selected cell out of the delivered preview.

Product 23:0x ruling: a final's composition reference is ONLY the selected cell of the
delivered nine-grid preview, never the whole grid. Grid cells are not equal thirds (the
5cf1 preview has dividers near x=500/958, y=861/1702 on 1440x2560), so the dividers are
detected from pixels. Detection fails closed: when it is not confident the caller blocks
the paid final instead of guessing equal thirds.

The crop is inset past the detected divider stroke (and the outer frame) so no grid line
remains, and the small isolated panel-number glyph near the cell's top-left corner is
whitened. Only that small label box is changed; the drawing itself is never altered.
Pure numpy + PIL, no network.
"""
from __future__ import annotations

import hashlib
import io
import os

DARK = 128            # luminance below this is ink
TOL = 0.006           # horizontal/vertical tolerance window (share of the dimension) for slanted strokes
MIN_COVER = 0.90      # a divider must have ink within the window on >= 90% of the scan lines
RIVAL_GAP = 0.04      # a second qualifying line farther than this (share of dimension) = ambiguous
MAX_SLOPE = 0.02      # dividers are near-axis-aligned (<= 2% drift)
MAX_RESID = 0.004     # fitted line residual bound (share of dimension)
SEARCH = ((0.20, 0.46), (0.54, 0.80))  # first / second divider search bands
EDGE_BAND = 0.03      # outer frame search band at each image edge
PAD = 0.004           # extra inset beyond the stroke (share of the dimension, min 4 px)
LABEL_ZONE = (0.22, 0.14)   # top-left zone (share of cell w, h) where the number label is searched
LABEL_MAX = (0.12, 0.09)    # a label is smaller than this (share of cell w, h)
LABEL_MOAT = 0.02           # white gap required around the label (share of cell width, min 4 px)
SUBFOLDER = "comfyart/multi_angle"


class CropError(ValueError):
    """Detection is not confident; the caller must block, not guess."""


def _ink(img):
    import numpy as np
    return np.asarray(img.convert("L"), dtype=np.uint8) < DARK


def _dilate(mask, radius: int):
    """Boolean dilation along axis 1 (columns) by +-radius."""
    import numpy as np
    out = mask.copy()
    for s in range(1, radius + 1):
        out[:, s:] |= mask[:, :-s]
        out[:, :-s] |= mask[:, s:]
    return out


def _axis_lines(ink, axis_len: int):
    """Detect the two interior dividers + outer frame extents on one axis.

    `ink` is oriented so that the divider runs along axis 0 (i.e. we look for columns).
    Returns dict with fitted lines and per-divider stroke half-widths.
    """
    import numpy as np
    h, w = ink.shape
    radius = max(3, int(round(TOL * w)))
    cover = _dilate(ink, radius).mean(axis=0)
    lines = []
    for lo, hi in SEARCH:
        a, b = int(lo * w), int(hi * w)
        band = cover[a:b]
        peak = a + int(np.argmax(band))
        if cover[peak] < MIN_COVER:
            raise CropError(f"no confident grid divider in {lo:.2f}..{hi:.2f} (best coverage {cover[peak]:.2f} at {peak})")
        strong = a + np.where(band >= MIN_COVER)[0]
        if len(strong) and (strong.max() - strong.min()) > max(3 * radius, RIVAL_GAP * w):
            raise CropError(f"ambiguous grid dividers in {lo:.2f}..{hi:.2f} ({int(strong.min())}..{int(strong.max())})")
        # Fit the (possibly slightly slanted) stroke: per block of scan lines, the ink centroid in the window.
        win = slice(max(0, peak - 2 * radius), min(w, peak + 2 * radius + 1))
        ys, xs, widths = [], [], []
        step = max(8, h // 64)
        for y0 in range(0, h - step + 1, step):
            sub = ink[y0:y0 + step, win]
            cols = np.where(sub.any(axis=0))[0]
            rows_hit = sub.any(axis=1).mean()
            if rows_hit < 0.9 or not len(cols):
                continue  # blocks where the drawing crosses / the stroke is broken are not used for the fit
            per_row = [np.where(r)[0] for r in sub if r.any()]
            centers = [float(np.median(c)) for c in per_row]
            ys.append(y0 + step / 2)
            xs.append(win.start + float(np.median(centers)))
            widths.append(float(np.median([len(c) for c in per_row])))
        if len(ys) < 16:
            raise CropError(f"divider near {peak} is not continuous enough to fit")
        ys, xs = np.array(ys), np.array(xs)
        slope, icept = np.polyfit(ys, xs, 1)
        resid = np.abs(xs - (slope * ys + icept))
        # robust: refit without the worst 10% (drawing touching the line)
        keep = resid <= np.percentile(resid, 90)
        slope, icept = np.polyfit(ys[keep], xs[keep], 1)
        resid = np.abs(xs[keep] - (slope * ys[keep] + icept))
        if abs(slope) > MAX_SLOPE or resid.max() > max(3.0, MAX_RESID * w):
            raise CropError(f"divider near {peak} is not a straight grid line (slope {slope:.4f}, residual {resid.max():.1f}px)")
        half = float(np.median(widths)) / 2 + float(resid.max())
        lines.append({"peak": peak, "slope": float(slope), "intercept": float(icept), "half": half})
    pad = max(4, int(round(PAD * w)))
    # Outer frame: a qualifying line hugging each edge (optional).
    edge = int(EDGE_BAND * w)
    lead = np.where(cover[:edge] >= MIN_COVER)[0]
    tail = np.where(cover[w - edge:] >= MIN_COVER)[0]
    start = (int(lead.max()) + 1 + pad) if len(lead) else pad   # dilated extent already includes the radius
    end = (w - edge + int(tail.min()) - pad) if len(tail) else w - pad
    return {"lines": lines, "start": start, "end": end, "pad": pad, "radius": radius}


def _at(line: dict, t: float) -> float:
    return line["slope"] * t + line["intercept"]


def detect_grid(img) -> dict:
    """Detected dividers of a 3x3 grid. Raises CropError when not confident."""
    import numpy as np
    ink = _ink(img)
    h, w = ink.shape
    if w < 300 or h < 300:
        raise CropError(f"preview too small to detect a grid ({w}x{h})")
    v = _axis_lines(ink, w)            # vertical dividers: look for columns
    hz = _axis_lines(np.ascontiguousarray(ink.T), h)  # horizontal dividers: columns of the transpose
    xs = [round(_at(l, h / 2), 1) for l in v["lines"]]
    ys = [round(_at(l, w / 2), 1) for l in hz["lines"]]
    widths = [xs[0] - 0, xs[1] - xs[0], w - xs[1]]
    heights = [ys[0] - 0, ys[1] - ys[0], h - ys[1]]
    if min(widths) < 0.2 * w or min(heights) < 0.2 * h:
        raise CropError(f"implausible grid cells (x={xs}, y={ys})")
    return {"size": [w, h], "x": xs, "y": ys, "_v": v, "_h": hz}


def cell_box(grid: dict, cell: int) -> list[int]:
    """[x0, y0, x1, y1] of the cell interior, inset past the divider strokes and frame."""
    import numpy as np
    w, h = grid["size"]
    v, hz = grid["_v"], grid["_h"]
    r, c = divmod(int(cell) - 1, 3)
    # Bounds along the other axis first (needed to evaluate slanted lines over the cell span).
    def bounds(ax, idx, span):
        lo_t, hi_t = span
        if idx == 0:
            lo = ax["start"]
        else:
            line = ax["lines"][idx - 1]
            lo = max(_at(line, lo_t), _at(line, hi_t)) + line["half"] + ax["pad"]
        if idx == 2:
            hi = ax["end"]
        else:
            line = ax["lines"][idx]
            hi = min(_at(line, lo_t), _at(line, hi_t)) - line["half"] - ax["pad"]
        return int(np.ceil(lo)), int(np.floor(hi))
    rough_y = ([0] + grid["y"] + [h])[r:r + 2]
    x0, x1 = bounds(v, c, rough_y)
    y0, y1 = bounds(hz, r, (x0, x1))
    x0, x1 = bounds(v, c, (y0, y1))
    if x1 - x0 < 0.15 * w or y1 - y0 < 0.15 * h:
        raise CropError(f"cell {cell} interior too small after inset")
    return [x0, y0, x1, y1]


def _label_box(ink, cell_w: int, cell_h: int):
    """Small isolated glyph cluster nearest the top-left corner, or None. Never the drawing."""
    import numpy as np
    zw, zh = int(LABEL_ZONE[0] * cell_w), int(LABEL_ZONE[1] * cell_h)
    zone = ink[:zh, :zw]
    pts = np.argwhere(zone)
    if not len(pts):
        return None
    y, x = pts[np.argmin(pts[:, 0] + pts[:, 1])]
    moat = max(4, int(round(LABEL_MOAT * cell_w)))
    box = [int(x), int(y), int(x) + 1, int(y) + 1]
    for _ in range(200):
        x0, y0 = max(0, box[0] - moat), max(0, box[1] - moat)
        x1, y1 = min(cell_w, box[2] + moat), min(cell_h, box[3] + moat)
        sub = np.argwhere(ink[y0:y1, x0:x1])
        nb = [x0 + int(sub[:, 1].min()), y0 + int(sub[:, 0].min()),
              x0 + int(sub[:, 1].max()) + 1, y0 + int(sub[:, 0].max()) + 1]
        if nb == box:
            break
        box = nb
        if box[2] - box[0] > LABEL_MAX[0] * cell_w or box[3] - box[1] > LABEL_MAX[1] * cell_h:
            return None  # grew into the drawing: not an isolated label
    else:
        return None
    if box[2] - box[0] > LABEL_MAX[0] * cell_w or box[3] - box[1] > LABEL_MAX[1] * cell_h:
        return None
    if box[2] > zw or box[3] > zh:
        return None
    return box


def crop_cell(data: bytes, cell: int) -> tuple[bytes, dict]:
    """PNG bytes of the selected cell (lines/label removed) + audit info. Raises CropError."""
    from PIL import Image
    import numpy as np
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        raise CropError(f"delivered preview is not a readable image: {e}") from None
    img = img.convert("RGB")
    grid = detect_grid(img)
    box = cell_box(grid, cell)
    out = img.crop(tuple(box))
    arr = np.array(out)
    ink = np.asarray(out.convert("L"), dtype=np.uint8) < DARK
    label = _label_box(ink, out.width, out.height)
    if label is not None:
        # Whiten the label plus its moat; the moat is ink-free by construction (see _label_box), so
        # this only removes the glyph and its light antialias halo, never a drawing stroke.
        g = max(4, int(round(LABEL_MOAT * out.width)))
        lx0, ly0, lx1, ly1 = max(0, label[0] - g), max(0, label[1] - g), label[2] + g, label[3] + g
        arr[ly0:ly1, lx0:lx1] = 255
        label = [lx0, ly0, min(lx1, out.width), min(ly1, out.height)]
    buf = io.BytesIO()
    Image.fromarray(arr, "RGB").save(buf, format="PNG", optimize=False)
    png = buf.getvalue()
    info = {"cell": int(cell), "box": box, "size": grid["size"],
            "dividers": {"x": grid["x"], "y": grid["y"]},
            "label_removed": label is not None, "label_box": label,
            "sha256": hashlib.sha256(png).hexdigest()}
    return png, info


def read_source(ref: str) -> bytes:
    """Bytes of a delivered preview file reference (/api/view?... or 'name [output]')."""
    from .wavespeed import _local_path
    try:
        path = _local_path(str(ref or "").strip())
    except Exception:
        path = None
    if not path or not os.path.isfile(path):
        raise CropError(f"delivered preview file is not available locally: {ref}")
    with open(path, "rb") as f:
        return f.read()


def save_crop(png: bytes, info: dict) -> str:
    """Archive the crop under the output dir; returns its /api/view URL (content-addressed, idempotent)."""
    import folder_paths
    from urllib.parse import urlencode
    name = f"ma-cell{info['cell']}-{info['sha256'][:16]}.png"
    root = os.path.abspath(folder_paths.get_output_directory())
    path = os.path.join(root, SUBFOLDER, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.isfile(path):
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(png)
        os.replace(tmp, path)
    return "/api/view?" + urlencode({"filename": name, "subfolder": SUBFOLDER, "type": "output"})
