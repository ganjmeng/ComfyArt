"""Delivery checks on a finished image, shared by every skill that opts in.

A skill output row (bot/skill_output.OUTPUTS) that declares ``opaque: True``
marks its generate calls with ``opaque_output``. For those jobs the saved file
is an opaque RGB PNG (alpha flattened onto white), and a finished frame that is
full-frame random static is reported as a charged failure instead of placed.
"""
from __future__ import annotations

import io

# Native pixels, every 8th one. Shrinking to 48px averages real static into a mild texture.
# On the full paid sheets (stride 8): noise flat 0.30–0.31, corr 0.59–0.60, neighbor mean ~45.
# The other paid outputs and the Lovart gold stay at flat >= 0.82 and corr >= 0.82.
# 96px crops of those same files still separate: noise flat <= 0.39, reviewable flat >= 0.57.
_NOISE_STRIDE = 8
_NOISE_FLAT_MAX = 0.48
_NOISE_CORR_MAX = 0.75
_NOISE_MEAN_MIN = 32.0


def image_noise_metrics(data: bytes) -> dict | None:
    """Neighbor stats at native resolution. None when the bytes are not an image.

    Samples every ``_NOISE_STRIDE`` pixel and compares it with the next native
    pixel, not with a resized average.
    """
    if not data or len(data) < 32:
        return None
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return None
    w, h = img.size
    raw = img.tobytes()
    stride = _NOISE_STRIDE
    diffs: list[int] = []
    flat = 0
    lag_a: list[float] = []
    lag_b: list[float] = []
    for y in range(0, h, stride):
        row = y * w
        for x in range(0, w - 2, stride):
            i = (row + x) * 3
            r, g, b = raw[i], raw[i + 1], raw[i + 2]
            r2, g2, b2 = raw[i + 3], raw[i + 4], raw[i + 5]
            d = abs(r - r2) + abs(g - g2) + abs(b - b2)
            diffs.append(d)
            if d < 18:
                flat += 1
            r3, g3, b3 = raw[i + 6], raw[i + 7], raw[i + 8]
            lag_a.append((0.3 * r) + (0.59 * g) + (0.11 * b))
            lag_b.append((0.3 * r3) + (0.59 * g3) + (0.11 * b3))
    if len(diffs) < 16 or len(lag_a) < 16:
        return None
    mean = sum(diffs) / len(diffs)
    flat_ratio = flat / len(diffs)
    mean_a = sum(lag_a) / len(lag_a)
    mean_b = sum(lag_b) / len(lag_b)
    var_a = sum((v - mean_a) ** 2 for v in lag_a)
    var_b = sum((v - mean_b) ** 2 for v in lag_b)
    if var_a <= 1 or var_b <= 1:
        return {"mean": mean, "flat": flat_ratio, "corr": 1.0, "samples": len(diffs)}
    corr = sum((a - mean_a) * (b - mean_b) for a, b in zip(lag_a, lag_b)) / ((var_a * var_b) ** 0.5)
    return {"mean": mean, "flat": flat_ratio, "corr": corr, "samples": len(diffs)}


def image_is_full_frame_noise(data: bytes) -> bool:
    """True only for a frame that is essentially random static.

    A flat sheet, a panel layout, or any image with neighboring pixels that
    still agree with each other stays reviewable. Empty bytes are not noise;
    the caller treats those as an empty result.
    """
    stats = image_noise_metrics(data)
    if not stats:
        return False
    return (
        stats["flat"] <= _NOISE_FLAT_MAX
        and abs(stats["corr"]) <= _NOISE_CORR_MAX
        and stats["mean"] >= _NOISE_MEAN_MIN
    )



def flatten_opaque(data: bytes) -> bytes:
    """Save an opaque RGB PNG. Any alpha channel is flattened onto white."""
    if not data:
        return data
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as img:
            # Any alpha channel becomes opaque RGB on white, including an
            # all-255 alpha that would otherwise stay RGBA.
            if img.mode in ("RGB", "L", "1"):
                return data
            if img.mode == "P" and "transparency" not in img.info:
                return data
            rgba = img.convert("RGBA")
            base = Image.new("RGB", rgba.size, (255, 255, 255))
            base.paste(rgba, mask=rgba.getchannel("A"))
    except Exception:
        return data
    buf = io.BytesIO()
    base.save(buf, format="PNG")
    return buf.getvalue()

