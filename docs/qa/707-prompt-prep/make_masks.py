#!/usr/bin/env python3
"""$0 local feathered masks for #707 prompt prep. No API calls.

Mask convention: 8-bit L PNG, 255 = model edit (composite in), 0 = keep base pixels.
Person masks follow docs/design/643/WASH-SOP.md: ellipse + Gaussian feather,
vertical ramp to 0 at the collar line, scene box feathered inside the box.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[3]  # repo root
OUT = Path(__file__).resolve().parent / "masks"
PREV = Path(__file__).resolve().parent / "previews"
OUT.mkdir(exist_ok=True)
PREV.mkdir(exist_ok=True)

# Card crop of the typifying before-after cover (cream card on the 1600x1200 plate).
# Measured from connected bright component of docs/design/640/78/gold/before-after/cover.webp
BA_COVER = ROOT / "docs/design/640/78/gold/before-after/cover.webp"
BA_CARD_XYWH = (459, 145, 683, 910)  # x, y, w, h on the 1600x1200 cover
# Photo band and typography on the 683x910 card (luminance bands).
BA_PHOTO = dict(x0=8, y0=176, x1=675, y1=772, split=340)
BA_HEADLINE = dict(x0=24, y0=36, x1=659, y1=155)
BA_DISCLAIMER = dict(x0=180, y0=848, x1=503, y1=880)


def gauss_blur(arr: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0:
        return arr
    im = Image.fromarray(arr, mode="L")
    im = im.filter(ImageFilter.GaussianBlur(radius=radius))
    return np.array(im, dtype=np.uint8)


def ellipse_mask(w: int, h: int, box, blur: float) -> np.ndarray:
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse(tuple(box), fill=255)
    return gauss_blur(np.array(m, dtype=np.uint8), blur)


def collar_ramp(h: int, w: int, clip_y: int, ramp_px: int) -> np.ndarray:
    """1 above the collar, linear 1→0 over ramp_px ending at clip_y, 0 below."""
    ys = np.arange(h)[:, None]
    if ramp_px <= 0:
        gain = (ys < clip_y).astype(np.float32)
    else:
        start = clip_y - ramp_px
        gain = np.clip((clip_y - ys) / float(ramp_px), 0.0, 1.0)
        gain = np.where(ys < start, 1.0, gain)
        gain = np.where(ys >= clip_y, 0.0, gain)
    return np.repeat(gain, w, axis=1)


def box_mask(w: int, h: int, box, feather: float) -> np.ndarray:
    x0, y0, x1, y1 = box
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rectangle([x0, y0, x1, y1], fill=255)
    arr = np.array(m, dtype=np.uint8)
    # Keep feather inside the box: blur, then zero outside the original rect.
    blurred = gauss_blur(arr, feather)
    inside = np.zeros_like(arr)
    inside[y0:y1, x0:x1] = 255
    return np.where(inside == 255, blurred, 0).astype(np.uint8)


def save_L(arr: np.ndarray, path: Path) -> None:
    Image.fromarray(arr, mode="L").save(path, optimize=True)
    print("wrote", path, arr.shape, "nonzero", int((arr > 5).sum()), f"{100*(arr>5).mean():.2f}%")


def overlay(base: Image.Image, mask: np.ndarray, path: Path, color=(220, 40, 40)) -> None:
    rgb = base.convert("RGB")
    a = (mask.astype(np.float32) / 255.0)
    arr = np.array(rgb, dtype=np.float32)
    tint = np.zeros_like(arr)
    tint[..., 0], tint[..., 1], tint[..., 2] = color
    out = arr * (1 - 0.45 * a[..., None]) + tint * (0.45 * a[..., None])
    Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(path, quality=90)
    print("preview", path)


def before_after_masks() -> dict:
    cover = Image.open(BA_COVER).convert("RGB")
    W, H = cover.size
    assert (W, H) == (1600, 1200), (W, H)
    cx, cy, cw, ch = BA_CARD_XYWH
    # Face panels on the cover: the two photo rectangles, feathered inward,
    # no typography, no dark plate around the card.
    faces = np.zeros((H, W), dtype=np.uint8)
    photo_x0 = cx + BA_PHOTO["x0"]
    photo_x1 = cx + BA_PHOTO["x1"]
    photo_y0 = cy + BA_PHOTO["y0"]
    photo_y1 = cy + BA_PHOTO["y1"]
    split = cx + BA_PHOTO["split"]
    # slight inset so the 2px white gutter and card radius stay gold
    faces_box_l = (photo_x0 + 2, photo_y0 + 2, split - 2, photo_y1 - 2)
    faces_box_r = (split + 3, photo_y0 + 2, photo_x1 - 2, photo_y1 - 2)
    left = box_mask(W, H, faces_box_l, feather=10)
    right = box_mask(W, H, faces_box_r, feather=10)
    faces = np.maximum(left, right)

    copy = np.zeros((H, W), dtype=np.uint8)
    head = (
        cx + BA_HEADLINE["x0"],
        cy + BA_HEADLINE["y0"],
        cx + BA_HEADLINE["x1"],
        cy + BA_HEADLINE["y1"],
    )
    disc = (
        cx + BA_DISCLAIMER["x0"],
        cy + BA_DISCLAIMER["y0"],
        cx + BA_DISCLAIMER["x1"],
        cy + BA_DISCLAIMER["y1"],
    )
    copy = np.maximum(box_mask(W, H, head, 8), box_mask(W, H, disc, 6))
    both = np.maximum(faces, copy)

    save_L(faces, OUT / "before-after-cover-faces.png")
    save_L(both, OUT / "before-after-cover-faces-and-copy.png")
    overlay(cover, both, PREV / "before-after-cover-mask-overlay.jpg")
    return {
        "base": "docs/design/640/78/gold/before-after/cover.webp",
        "base_px": [W, H],
        "card_xywh": list(BA_CARD_XYWH),
        "photo_on_card": BA_PHOTO,
        "headline_on_card": BA_HEADLINE,
        "disclaimer_on_card": BA_DISCLAIMER,
        "face_boxes_on_cover": [list(faces_box_l), list(faces_box_r)],
        "files": {
            "faces_only": "docs/qa/707-prompt-prep/masks/before-after-cover-faces.png",
            "faces_and_copy": "docs/qa/707-prompt-prep/masks/before-after-cover-faces-and-copy.png",
        },
        "note": "Use faces_and_copy when the same Seedream edit also replaces the headline and disclaimer in-model; composite those regions back. BEFORE/AFTER labels stay gold (mask=0).",
    }


def pose_mask(path: Path, spec: dict, out_name: str, prev_name: str) -> dict:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    assert (w, h) == (1529, 2048), (path, w, h)
    face_box = spec["face_ellipse"]  # [x0,y0,x1,y1]
    blur = spec.get("face_blur", spec.get("blur", 28))
    face = ellipse_mask(w, h, face_box, blur)
    if "collar_clip_y" in spec:
        gain = collar_ramp(h, w, spec["collar_clip_y"], spec.get("collar_ramp_px", 40))
        face = (face.astype(np.float32) * gain).clip(0, 255).astype(np.uint8)
    scene = np.zeros((h, w), dtype=np.uint8)
    if "scene_box" in spec:
        scene = box_mask(w, h, spec["scene_box"], spec.get("box_feather", 14))
    elif "scene_rect" in spec:
        scene = box_mask(w, h, spec["scene_rect"], spec.get("box_feather", spec.get("blur", 34)))
    both = np.maximum(face, scene)
    save_L(both, OUT / out_name)
    overlay(im, both, PREV / prev_name)
    return {
        "base": str(path.relative_to(ROOT)),
        "base_px": [w, h],
        "spec": spec,
        "file": f"docs/qa/707-prompt-prep/masks/{out_name}",
    }


def main() -> None:
    meta = {"before-after": before_after_masks(), "pose-fission": []}
    # Coords copied from docs/design/643/wash-manifest.pose-fission.json (gold px 1529x2048).
    # Applied to the committed 643/wash examples, which already carry the #670 new face.
    specs = {
        1: {
            "face_ellipse": [640, 140, 960, 560],
            "face_blur": 28,
            "collar_clip_y": 430,
            "collar_ramp_px": 40,
            "scene_box": [0, 1480, 480, 1800],
            "box_feather": 14,
            "scene": "optional: drain area only if a face re-wash is requested",
        },
        2: {
            "face_ellipse": [690, 60, 980, 390],
            "face_blur": 24,
            "collar_clip_y": 345,
            "collar_ramp_px": 40,
            "scene_box": [60, 1320, 600, 1545],
            "box_feather": 14,
            "scene": "optional drain grate box",
        },
        3: {
            "face_ellipse": [500, 95, 775, 420],
            "face_blur": 24,
            "collar_clip_y": 360,
            "collar_ramp_px": 40,
            "scene_box": [0, 1385, 316, 1535],
            "box_feather": 10,
            "scene": "optional lower-left sidewalk box",
        },
        4: {
            "face_ellipse": [600, 45, 1110, 560],
            "face_blur": 34,
            "collar_clip_y": 620,  # keep the camel lapel and left sleeve out of the face mask
            "collar_ramp_px": 50,
            # Historical manifest scene_rect [0,0,500,1450] painted the left sleeve.
            # Tightened to the upper-left wall/window only; does not touch clothing.
            "scene_rect": [0, 40, 190, 720],
            "box_feather": 24,
            "scene": "optional upper-left wall/window only (tightened vs #670 rect)",
        },
    }
    for i, spec in specs.items():
        src = ROOT / f"643/wash/pose-fission/examples/0{i}.webp"
        meta["pose-fission"].append(
            pose_mask(
                src,
                spec,
                f"pose-fission-ex0{i}-face-scene.png",
                f"pose-fission-ex0{i}-mask-overlay.jpg",
            )
        )
    (Path(__file__).parent / "masks.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
    )
    print("wrote masks.json")


if __name__ == "__main__":
    main()
