import math

import numpy as np
from PIL import Image, ImageFilter

EASE_OUT = (0, 0, 0.58, 1)
EASE_IN_OUT = (0.42, 0, 0.58, 1)
SPRING = (0.18, 0.89, 0.32, 1.28)
STILL = {"opacity": 1.0, "dx": 0.0, "dy": 0.0, "scale": 1.0, "blur": 0.0, "reveal": 1.0}
KEYFRAMES = {
    "fade": ([(0, {"opacity": 0}), (1, {"opacity": 1})], EASE_OUT),
    "spring-up": ([(0, {"opacity": 0, "dy": 28}), (1, {"opacity": 1, "dy": 0})], SPRING),
    "blur-in": ([(0, {"opacity": 0, "blur": 14, "scale": 1.06}), (1, {"opacity": 1, "blur": 0, "scale": 1})], EASE_OUT),
    "zoom-in": ([(0, {"opacity": 0, "scale": 1.12}), (1, {"opacity": 1, "scale": 1})], EASE_OUT),
    "slide-left": ([(0, {"opacity": 0, "dx": 64}), (1, {"opacity": 1, "dx": 0})], EASE_OUT),
    "slide-right": ([(0, {"opacity": 0, "dx": -64}), (1, {"opacity": 1, "dx": 0})], EASE_OUT),
    "wipe-in": ([(0, {"reveal": 0}), (1, {"reveal": 1})], EASE_IN_OUT),
    "pulse": ([(0, {"opacity": 0, "scale": 0.92}), (0.7, {"opacity": 1, "scale": 1.06}), (1, {"opacity": 1, "scale": 1})], SPRING),
    "wave": ([(0, {"dy": 0}), (0.5, {"dy": -8}), (1, {"dy": 0})], EASE_IN_OUT),
}


def bezier(curve: tuple, x: float) -> float:
    x1, y1, x2, y2 = curve

    def at(a, b, t):
        return 3 * a * t * (1 - t) ** 2 + 3 * b * t * t * (1 - t) + t ** 3

    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if at(x1, x2, mid) < x else (lo, mid)
    return at(y1, y2, (lo + hi) / 2)


def motion(kind: str, p: float) -> dict:
    if kind not in KEYFRAMES or p >= 1:
        return STILL
    frames, curve = KEYFRAMES[kind]
    p = max(0.0, p)
    i = next(j for j in range(1, len(frames)) if p <= frames[j][0]) - 1
    (a, start), (b, end) = frames[i], frames[i + 1]
    e = bezier(curve, (p - a) / (b - a))
    out = dict(STILL)
    for key in start:
        out[key] = start[key] + (end[key] - start[key]) * e
    out["opacity"] = min(1.0, max(0.0, out["opacity"]))
    return out


def paste(below: np.ndarray, img: np.ndarray, alpha, x: int, y: int) -> np.ndarray:
    height, width = below.shape[:2]
    h, w = img.shape[:2]
    if alpha is None and x <= 0 and y <= 0 and x + w >= width and y + h >= height:
        return np.ascontiguousarray(img[-y:height - y, -x:width - x])
    x0, y0, x1, y1 = max(0, x), max(0, y), min(width, x + w), min(height, y + h)
    out = below.copy()
    if x1 <= x0 or y1 <= y0:
        return out
    src = img[y0 - y:y1 - y, x0 - x:x1 - x]
    if alpha is None:
        out[y0:y1, x0:x1] = src
    else:
        a = alpha[y0 - y:y1 - y, x0 - x:x1 - x]
        out[y0:y1, x0:x1] = (out[y0:y1, x0:x1] * (1 - a) + src * a + 0.5).astype(np.uint8)
    return out


def disk(size: int) -> np.ndarray:
    r = size / 2
    yy, xx = np.mgrid[:size, :size] + 0.5
    return np.clip(r - np.hypot(xx - r, yy - r) + 0.5, 0, 1)[..., None].astype(np.float32)


class Overlay:
    def __init__(self, spec: dict, height: int, path: str):
        self.start = float(spec["start"])
        self.end = self.start + float(spec["duration"])
        self.x, self.y = int(spec.get("x", 0)), int(spec.get("y", 0))
        self.image = Image.open(path).convert("RGBA")
        arr = np.asarray(self.image).astype(np.float32) / 255
        self.rgb, self.alpha = arr[..., :3] * 255, arr[..., 3:]
        bx, by, bw, bh = spec.get("box") or (self.x, self.y, *self.image.size)
        self.box = (bx - self.x, by - self.y, bw, bh)
        self.animation = spec.get("animation") or {}
        self.unit = height / 1080

    def state(self, t: float) -> dict:
        duration = float(self.animation.get("duration") or 0)
        return motion(self.animation.get("type", "none"), (t - self.start) / duration) if duration > 0 else STILL

    def apply(self, frame: np.ndarray, t: float) -> np.ndarray:
        m = self.state(t)
        if m == STILL:
            return paste(frame, self.rgb, self.alpha, self.x, self.y)
        image = self.image
        bx, by, bw, bh = self.box
        if m["reveal"] < 1:
            keep = Image.new("L", image.size, 0)
            keep.paste(255, (round(bx), round(by), round(bx + bw * m["reveal"]), round(by + bh)))
            image = image.copy()
            image.putalpha(Image.fromarray(np.minimum(np.asarray(image.getchannel("A")), np.asarray(keep))))
        s = m["scale"]
        x = self.x + (bx + bw / 2) * (1 - s) + m["dx"] * self.unit
        y = self.y + (by + bh / 2) * (1 - s) + m["dy"] * self.unit
        if s != 1:
            image = image.resize((max(1, round(image.width * s)), max(1, round(image.height * s))), Image.BILINEAR)
        if m["blur"] > 0:
            sigma = m["blur"] * self.unit
            pad = math.ceil(3 * sigma)
            grown = Image.new("RGBa", (image.width + 2 * pad, image.height + 2 * pad))
            grown.paste(image.convert("RGBa"), (pad, pad))
            image = grown.filter(ImageFilter.GaussianBlur(sigma)).convert("RGBA")
            x, y = x - pad, y - pad
        arr = np.asarray(image).astype(np.float32) / 255
        return paste(frame, arr[..., :3] * 255, arr[..., 3:] * m["opacity"], round(x), round(y))
