"""Reference-image preprocessing for structure / color control (#80).

Upstream 5231d59 ran ComfyUI preprocessor nodes (Canny, LineArt, HED, ColorPreprocessor, ...)
before ControlNet. ComfyArt no longer loads local models, so the model-free preprocessors are
plain image filters here (Pillow only); the ones that need a model (depth, pose) are extracted by
the WaveSpeed control model itself (wavespeed-ai/z-image-turbo/controlnet)."""
from __future__ import annotations

import io
import random

from PIL import Image, ImageChops, ImageFilter, ImageOps

# structure modes WaveSpeed extracts itself (z-image-turbo/controlnet `mode`): no cloud pose estimator exists
EXTRACTED = {"pose": "pose"}
POSE_FALLBACK = "softedge"  # pose ref on flux (custom window / multi-ref): soft-edge map of the reference
# structure modes turned into a control image here and sent to flux-controlnet-union-pro-2.0
FILTERED = {"canny", "lineart", "mlsd", "scribble", "softedge", "tile"}
# structure modes whose map comes from a cloud estimator first (feature, params), then flux-controlnet-union-pro-2.0
CLOUD_MAP = {
    "depth": ("depth_estimation", {"colormap": "grayscale", "output_format": "png"}),
    "normal": ("depth_estimation", {"colormap": "grayscale", "output_format": "png"}),  # + normal_from_depth
    "seg": ("segment", {"apply_mask": False, "output_format": "png"}),
}
# color modes: the processed image replaces the reference for image_edit (as upstream fed qwen edit)
COLOR = {"recolor", "color", "shuffle", "brightness"}
# still approximate vs upstream (labelled 「近似效果」 in the UI)
APPROX = {"mlsd", "tile", "normal", "seg", "pose"}


def _edges(img: Image.Image, blur: float = 1.0) -> Image.Image:
    g = ImageOps.grayscale(img).filter(ImageFilter.GaussianBlur(blur))
    return ImageOps.autocontrast(g.filter(ImageFilter.FIND_EDGES))


def _threshold(img: Image.Image, level: int) -> Image.Image:
    return img.point(lambda v: 255 if v >= level else 0)


def process(img: Image.Image, mode: str, res: int = 1024, seed: int = 0) -> Image.Image:
    img = img.convert("RGB")
    scale = res / max(img.size)
    if abs(scale - 1) > 0.01:
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    if mode == "canny":
        out = _threshold(_edges(img, 1.0), 64)
    elif mode == "lineart":
        out = _threshold(_edges(img, 0.6), 40).filter(ImageFilter.MaxFilter(3))
    elif mode == "mlsd":
        # straight-line emphasis: keep only long horizontal/vertical-ish edge runs
        e = _threshold(_edges(img, 1.0), 48).filter(ImageFilter.MaxFilter(3))
        h = e.filter(ImageFilter.Kernel((5, 5), [0] * 10 + [1] * 5 + [0] * 10, 5))
        v = e.filter(ImageFilter.Kernel((5, 5), [0, 0, 1, 0, 0] * 5, 5))
        out = _threshold(ImageChops.lighter(h, v), 250)
    elif mode == "scribble":
        out = _threshold(_edges(img, 3.0), 80).filter(ImageFilter.MaxFilter(5))
    elif mode == "softedge":
        out = ImageOps.autocontrast(_edges(img, 2.0).filter(ImageFilter.GaussianBlur(1.5)))
    elif mode == "tile":
        small = img.resize((max(1, img.width // 8), max(1, img.height // 8)), Image.BILINEAR)
        return small.resize(img.size, Image.BICUBIC).filter(ImageFilter.GaussianBlur(1))
    elif mode in ("recolor", "brightness"):
        out = ImageOps.grayscale(img)
        if mode == "brightness":
            out = out.filter(ImageFilter.GaussianBlur(8))
    elif mode == "color":
        small = img.resize((max(1, img.width // 64), max(1, img.height // 64)), Image.BOX)
        return small.resize(img.size, Image.NEAREST)
    elif mode == "shuffle":
        rng = random.Random(seed)
        out = img.copy()
        cell = max(8, img.width // 16)
        boxes = [(x, y, min(x + cell, img.width), min(y + cell, img.height)) for y in range(0, img.height, cell) for x in range(0, img.width, cell)]
        tiles = [img.crop(b) for b in boxes]
        rng.shuffle(tiles)
        for b, t in zip(boxes, tiles):
            out.paste(t.resize((b[2] - b[0], b[3] - b[1])), b[:2])
        return out.filter(ImageFilter.GaussianBlur(2))
    else:
        return img
    return out.convert("RGB")


def normal_from_depth(depth: Image.Image, strength: float = 4.0) -> Image.Image:
    """Tangent-space normal map from a grayscale depth map (near = white), math only, no model.
    Same RGB convention as upstream BAE-NormalMapPreprocessor output (x right, y up, z towards viewer)."""
    g = ImageOps.grayscale(depth).filter(ImageFilter.GaussianBlur(1))
    w, h = g.size
    px = g.load()
    out = Image.new("RGB", (w, h))
    o = out.load()
    for y in range(h):
        for x in range(w):
            dx = (px[min(x + 1, w - 1), y] - px[max(x - 1, 0), y]) / 255 * strength
            dy = (px[x, min(y + 1, h - 1)] - px[x, max(y - 1, 0)]) / 255 * strength
            nx, ny, nz = -dx, dy, 1.0
            n = (nx * nx + ny * ny + nz * nz) ** 0.5
            o[x, y] = (round((nx / n + 1) * 127.5), round((ny / n + 1) * 127.5), round((nz / n + 1) * 127.5))
    return out


def composite(maps: list[tuple[Image.Image, float]], size: tuple[int, int]) -> Image.Image:
    """Several structure refs into one control image (upstream chained one ControlNetApplyAdvanced per
    ref; the cloud control model takes one control_image). Each map is weighted by its strength
    relative to the strongest and merged with a per-pixel max, so every ref shapes the result."""
    top = max(s for _, s in maps) or 1.0
    out = Image.new("RGB", size)
    for img, s in maps:
        m = img.convert("RGB").resize(size, Image.LANCZOS)
        k = s / top
        if k < 1:
            m = m.point(lambda v, k=k: round(v * k))
        out = ImageChops.lighter(out, m)
    return out


def fit(img: Image.Image, width: int, height: int, resize: str = "crop") -> Image.Image:
    """Match the generation size like upstream ImageScale (crop=center / stretch)."""
    if resize == "stretch":
        return img.resize((width, height), Image.LANCZOS)
    return ImageOps.fit(img, (width, height), Image.LANCZOS)


def process_bytes(data: bytes, mode: str, res: int = 1024, size: tuple[int, int] | None = None, resize: str = "crop") -> bytes:
    out = to_png(process_image(data, mode, res, size, resize))
    return out


def process_image(data: bytes, mode: str, res: int = 1024, size: tuple[int, int] | None = None, resize: str = "crop") -> Image.Image:
    """`data` is the raw ref for filtered modes, or the cloud map (depth / sam3 mask) for CLOUD_MAP modes."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    if mode in CLOUD_MAP:
        scale = min(1.0, res / max(img.size))
        if scale < 1:
            img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
        out = normal_from_depth(img) if mode == "normal" else img
    else:
        out = process(img, mode, res)
    if size:
        out = fit(out, *size, resize)
    return out


def scale_fit(data: bytes, res: int = 1024, size: tuple[int, int] | None = None, resize: str = "crop") -> Image.Image:
    """Raw ref downscaled to `res` on its long side, then fit to the generation size (no map extraction)."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    scale = min(1.0, res / max(img.size))
    if scale < 1:
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    return fit(img, *size, resize) if size else img


def to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
