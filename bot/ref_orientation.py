"""#905: orientation of the comparison card inside a before-after reference image.

Decided on the server from pixels only; the chat model has no part in it. A reference is often a
card shown on a plain display background (cover.webp is a 1600x1200 landscape file holding a
portrait card), so the file's own width and height are not enough. Each row gets its own
background colour from its two ends, content is what differs from it, and the content box decides
the orientation. If no box is found, or it covers under 30% or over 95% of the image, the file's
pixel orientation is used instead.
"""
from __future__ import annotations

import base64
import io

SQUARE_TOLERANCE = 0.10  # width/height in [0.9, 1.1] counts as square
EDGE_PIXELS = 8  # per row, the mean of this many pixels at each end is that row's background
CONTENT_DIFF = 60  # a pixel differing from its row background by more than this is content
LINE_SHARE = 0.05  # a row or column is kept when more than this share of it is content
MIN_BOX_SHARE = 0.30  # below this the box is noise: fall back to pixel orientation
MAX_BOX_SHARE = 0.95  # above this there is no border (full bleed): fall back as well
ORIENTATION_RATIO = {"portrait": "4:5", "landscape": "16:9", "square": "1:1"}


def _orientation(w: int, h: int) -> str:
    r = w / h if h else 1.0
    if abs(r - 1.0) <= SQUARE_TOLERANCE + 1e-9:
        return "square"
    return "landscape" if r > 1 else "portrait"


def content_box(img) -> tuple[int, int, int, int] | None:
    """Box (x0, y0, x1, y1) of the content, or None when no usable box is found.

    Each row is compared against its own background, the mean of EDGE_PIXELS pixels at both ends of
    that row, so a backdrop with a vertical gradient (as in cover.webp) is still trimmed.
    """
    import numpy as np

    a = np.asarray(img.convert("RGB"), dtype=np.int16)
    h, w = a.shape[:2]
    if w < 4 * EDGE_PIXELS or h < 4 * EDGE_PIXELS:
        return None
    edges = np.concatenate([a[:, :EDGE_PIXELS], a[:, -EDGE_PIXELS:]], axis=1)
    bg = edges.mean(axis=1, keepdims=True)
    content = np.abs(a - bg).sum(axis=2) > CONTENT_DIFF
    rows = np.where(content.mean(axis=1) > LINE_SHARE)[0]
    cols = np.where(content.mean(axis=0) > LINE_SHARE)[0]
    if not len(rows) or not len(cols):
        return None
    box = (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)
    share = (box[2] - box[0]) * (box[3] - box[1]) / (w * h)
    if share < MIN_BOX_SHARE or share > MAX_BOX_SHARE:
        return None
    return box


def reference_orientation(data: bytes) -> str | None:
    """portrait / landscape / square for an image file's bytes; None when it cannot be decoded."""
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return None
    box = content_box(img)
    if box:
        return _orientation(box[2] - box[0], box[3] - box[1])
    return _orientation(*img.size)


def reference_ratio(data: bytes) -> str | None:
    o = reference_orientation(data)
    return ORIENTATION_RATIO.get(o) if o else None


def first_image_bytes(attachments) -> bytes | None:
    """Bytes of the first image attachment of a chat turn (base64 'data' as sent to the model)."""
    for a in attachments or []:
        if not isinstance(a, dict) or not a.get("data"):
            continue
        if not str(a.get("media_type") or "image/").startswith("image/"):
            continue
        try:
            return base64.b64decode(a["data"])
        except Exception:
            continue
    return None
