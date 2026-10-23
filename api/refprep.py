"""Reference-image preprocessing for structure / color control (#80).

Upstream 5231d59 ran ComfyUI preprocessor nodes (Canny, LineArt, HED, ColorPreprocessor, ...)
before ControlNet. ComfyArt no longer loads local models, so the model-free preprocessors are
plain image filters here (Pillow only); the ones that need a model (depth, pose) are extracted by
the WaveSpeed control model itself (wavespeed-ai/z-image-turbo/controlnet)."""
from __future__ import annotations

import io
import random

from PIL import Image, ImageChops, ImageFilter, ImageOps

# structure modes WaveSpeed extracts itself (z-image-turbo/controlnet `mode`)
EXTRACTED = {"depth": "depth", "pose": "pose"}
# structure modes turned into a control image here and sent to flux-controlnet-union-pro-2.0
FILTERED = {"canny", "lineart", "mlsd", "scribble", "softedge", "tile"}
# color modes: the processed image replaces the reference for image_edit (as upstream fed qwen edit)
COLOR = {"recolor", "color", "shuffle", "brightness"}
# structure modes with no WaveSpeed model that accepts their map (capability gap, see #80)
NO_MODEL = {"normal", "seg"}


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
        e = _threshold(_edges(img, 1.5), 96)
        h = e.filter(ImageFilter.Kernel((5, 5), [0] * 10 + [1] * 5 + [0] * 10, 5))
        v = e.filter(ImageFilter.Kernel((5, 5), [0, 0, 1, 0, 0] * 5, 5))
        out = _threshold(ImageChops.lighter(h, v), 200)
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


def fit(img: Image.Image, width: int, height: int, resize: str = "crop") -> Image.Image:
    """Match the generation size like upstream ImageScale (crop=center / stretch)."""
    if resize == "stretch":
        return img.resize((width, height), Image.LANCZOS)
    return ImageOps.fit(img, (width, height), Image.LANCZOS)


def process_bytes(data: bytes, mode: str, res: int = 1024, size: tuple[int, int] | None = None, resize: str = "crop") -> bytes:
    out = process(Image.open(io.BytesIO(data)), mode, res)
    if size:
        out = fit(out, *size, resize)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()
