#!/usr/bin/env python3
"""#873 masked Flare trial — production crop-and-pasteback path.

Forces openai/gpt-image-2.6-flare/edit through the same region crop flow as
api/wavespeed.py region_inputs / _submit_paste (crop only, no mask_image,
resolution 1k, nearest-tier aspect ratio, then local pasteback).

  --dry-run   print request plan + catalog estimate; NO network / NO key use
  --live      one paid call ($0.1 cap); abort if balance < $20; stop after one failure

Never prints the API key. Reads /home/box/.secrets/comfyart-test.env in --live only.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
OUT = ROOT / "out"
LR = ROOT / "lr"
CALLS = ROOT / "calls.jsonl"
CAP = 0.10
MIN_BALANCE = 20.0
BASE_URL = "https://api.wavespeed.ai/api/v3"
MODEL = "openai/gpt-image-2.6-flare/edit"
RESOLUTION = "1k"
PROMPT = (
    "Change only the selected can to a matte sage-green aluminum finish; "
    "keep shape, logo layout, and background unchanged; keep the KOIRA wordmark, "
    '"AMBER ROAST OOLONG" text, sun and koi line art, silver rim, highlights and floor shadow unchanged.'
)
BASE_IMG = ROOT / "base.png"
MASK_IMG = ROOT / "mask.png"
TOUCH_PAD, TOUCH_MIN = 0.25, 384
ASPECTS = [
    "1:1", "1:2", "2:1", "1:3", "3:1", "2:3", "3:2", "3:4", "4:3",
    "4:5", "5:4", "9:16", "16:9", "9:21", "21:9",
]


def nearest_aspect(w: int, h: int) -> str:
    """Mirror api/wavespeed.py _nearest from crop width/height."""
    aspect = w / h

    def ratio(s: str) -> float:
        a, b = s.split(":")
        return float(a) / float(b)

    return min(ASPECTS, key=lambda o: abs(math.log(ratio(o) / aspect)))


def catalog_base_price(model: str) -> float | None:
    """Estimate from the repo fixture catalog (no live price call in dry-run)."""
    path = REPO / "tests/fixtures/wavespeed_catalog_subset.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    row = data.get(model) or {}
    v = row.get("base_price")
    return float(v) if v is not None else None


def env_key() -> str:
    k = os.environ.get("WAVESPEED_API_KEY")
    if not k:
        for line in Path("/home/box/.secrets/comfyart-test.env").read_text().splitlines():
            if line.startswith("WAVESPEED_API_KEY="):
                k = line.split("=", 1)[1].strip().strip('"').strip("'")
                os.environ["WAVESPEED_API_KEY"] = k
                break
    if not k:
        raise SystemExit("missing WAVESPEED_API_KEY")
    return k


def headers() -> dict:
    return {"Authorization": "Bearer " + env_key()}


def bal() -> float:
    r = requests.get(BASE_URL + "/balance", headers=headers(), timeout=20)
    r.raise_for_status()
    return float(r.json()["data"]["balance"])


def append(rec: dict) -> None:
    with CALLS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def crop_around(region: dict, w: int, h: int) -> dict:
    def grow(length, full):
        return min(full, max(length * (1 + TOUCH_PAD * 2), TOUCH_MIN))

    cw = min(w, round(grow(region["w"], w) / 8) * 8)
    ch = min(h, round(grow(region["h"], h) / 8) * 8)

    def clamp(v, size, full):
        return round(min(max(v, 0), full - size))

    return {
        "x": clamp(region["x"] + region["w"] / 2 - cw / 2, cw, w),
        "y": clamp(region["y"] + region["h"] / 2 - ch / 2, ch, h),
        "w": cw,
        "h": ch,
    }


def mask_array_from_img(img: Image.Image, size=None) -> np.ndarray:
    """ComfyArt mask: α=0 is edit target → return 1.0 where edit."""
    img = img.convert("RGBA")
    if size and img.size != size:
        img = img.resize(size, Image.NEAREST)
    return 1.0 - np.asarray(img.getchannel("A"), dtype=np.float32) / 255.0


def mask_png(m: np.ndarray) -> bytes:
    a = np.clip(np.round((1.0 - m) * 255.0), 0, 255).astype(np.uint8)
    rgba = np.dstack([np.full_like(a, 255)] * 3 + [a])
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
    return buf.getvalue()


def composite(dest, src, x, y, m):
    out = dest.copy()
    H, W = dest.shape[:2]
    h, w = src.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return out
    s = src[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32)
    mm = m[y0 - y:y1 - y, x0 - x:x1 - x][..., None]
    d = dest[y0:y1, x0:x1].astype(np.float32)
    mixed = np.clip(np.round(d * (1.0 - mm) + s * mm), 0, 255).astype(np.uint8)
    out[y0:y1, x0:x1] = np.where(mm > 0, mixed, dest[y0:y1, x0:x1])
    return out


def rgb_bytes(data, size=None):
    img = Image.open(io.BytesIO(data)).convert("RGB")
    if size and img.size != size:
        img = img.resize(size, Image.BICUBIC)
    return np.asarray(img).copy()


def png_bytes(arr):
    buf = io.BytesIO()
    Image.fromarray(arr, "RGB").save(buf, format="PNG")
    return buf.getvalue()


def paste_result(orig: bytes, mask_crop: bytes, box: dict, result: bytes) -> bytes:
    dest = rgb_bytes(orig)
    src = rgb_bytes(result, (box["w"], box["h"]))
    m = mask_array_from_img(Image.open(io.BytesIO(mask_crop)), (box["w"], box["h"]))
    return png_bytes(composite(dest, src, box["x"], box["y"], m))


def prepare_crop() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    base = Image.open(BASE_IMG).convert("RGB")
    mask = Image.open(MASK_IMG).convert("RGBA")
    W, H = base.size
    full_m = mask_array_from_img(mask, (W, H))
    ys, xs = np.where(full_m >= 0.5)
    if xs.size == 0:
        raise SystemExit("mask has no edit region")
    region = {
        "x": int(xs.min()),
        "y": int(ys.min()),
        "w": int(xs.max()) - int(xs.min()) + 1,
        "h": int(ys.max()) - int(ys.min()) + 1,
    }
    box = crop_around(region, W, H)
    crop = base.crop((box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]))
    crop_path = OUT / "_crop.png"
    crop.save(crop_path)
    m = full_m[box["y"]:box["y"] + box["h"], box["x"]:box["x"] + box["w"]]
    mask_crop_bytes = mask_png(m)
    (OUT / "_mask_crop.png").write_bytes(mask_crop_bytes)
    return {
        "box": box,
        "region": region,
        "crop_path": crop_path,
        "crop_hash": hashlib.sha256(crop_path.read_bytes()).hexdigest(),
        "mask_crop_bytes": mask_crop_bytes,
        "orig_bytes": BASE_IMG.read_bytes(),
        "full_mask": mask,
        "W": W,
        "H": H,
        "aspect_ratio": nearest_aspect(box["w"], box["h"]),
    }


def make_collages(prep: dict, result_path: Path) -> dict:
    LR.mkdir(parents=True, exist_ok=True)
    base = Image.open(BASE_IMG).convert("RGB")
    result = Image.open(result_path).convert("RGB")
    if result.size != base.size:
        result = result.resize(base.size, Image.BICUBIC)
    gap = 12
    lr = Image.new("RGB", (base.width * 2 + gap, base.height), (255, 255, 255))
    lr.paste(base, (0, 0))
    lr.paste(result, (base.width + gap, 0))
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    d = ImageDraw.Draw(lr)
    d.text((8, 8), "base", fill=(20, 20, 20), font=font)
    d.text((base.width + gap + 8, 8), "Flare edit pasteback", fill=(20, 20, 20), font=font)
    lr_path = LR / "LR-base-vs-flare.png"
    lr.save(lr_path)

    # 200% crop of the mask edge (box expanded a bit)
    box = prep["box"]
    pad = 40
    x0 = max(0, box["x"] - pad)
    y0 = max(0, box["y"] - pad)
    x1 = min(base.width, box["x"] + box["w"] + pad)
    y1 = min(base.height, box["y"] + box["h"] + pad)
    edge = Image.new("RGB", ((x1 - x0) * 2 + gap, (y1 - y0) * 2), (255, 255, 255))
    left = base.crop((x0, y0, x1, y1)).resize(((x1 - x0) * 2, (y1 - y0) * 2), Image.NEAREST)
    right = result.crop((x0, y0, x1, y1)).resize(((x1 - x0) * 2, (y1 - y0) * 2), Image.NEAREST)
    # side-by-side at 200% of the edge window
    duo = Image.new("RGB", (left.width * 2 + gap, left.height), (255, 255, 255))
    duo.paste(left, (0, 0))
    duo.paste(right, (left.width + gap, 0))
    edge_path = LR / "edge-200pct.png"
    duo.save(edge_path)
    return {"lr": str(lr_path), "edge_200pct": str(edge_path)}


def upload(path: Path) -> str:
    r = requests.post(
        BASE_URL + "/media/upload/binary",
        headers=headers(),
        files={"file": (path.name, path.read_bytes())},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["data"]["download_url"]


def poll(rid: str, timeout_s: float = 600) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(4)
        g = requests.get(
            f"{BASE_URL}/predictions/{rid}/result", headers=headers(), timeout=30
        ).json()["data"]
        if g.get("status") in ("completed", "failed"):
            return g
    return {"status": "timeout", "error": "poll timeout"}


def dry_run(prep: dict) -> int:
    price = catalog_base_price(MODEL)
    plan = {
        "mode": "dry-run",
        "model": MODEL,
        "prompt": PROMPT,
        "base": str(BASE_IMG.relative_to(REPO)),
        "mask": str(MASK_IMG.relative_to(REPO)),
        "base_size": [prep["W"], prep["H"]],
        "mask_region": prep["region"],
        "crop_box": prep["box"],
        "crop_sha256": prep["crop_hash"],
        "aspect_ratio": prep["aspect_ratio"],
        "resolution": RESOLUTION,
        "num_images": 1,
        "cap_usd": CAP,
        "min_balance_usd": MIN_BALANCE,
        "estimated_cost_usd": price,
        "estimated_cost_source": "tests/fixtures/wavespeed_catalog_subset.json base_price",
        "payload_shape": {
            "prompt": PROMPT,
            "images": ["<uploaded crop only — production pasteback, NO mask_image>"],
            "resolution": RESOLUTION,
            "aspect_ratio": prep["aspect_ratio"],
            "output_format": "png",
        },
        "notes": [
            "Mirrors api/wavespeed.py region_inputs/_submit_paste: crop submitted, mask used only locally for pasteback.",
            "Live mode: one submit, stop after one failure, no retries.",
            "$0.1 spend cap; abort if WaveSpeed balance < $20.",
        ],
    }
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    (ROOT / "dry-run.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    return 0


def live(prep: dict) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    LR.mkdir(parents=True, exist_ok=True)
    b0 = bal()
    if b0 < MIN_BALANCE:
        raise SystemExit(f"BALANCE<{MIN_BALANCE} ({b0}); abort")
    if CAP < 0.01:
        raise SystemExit("CAP too low")
    append({
        "event": "start",
        "model": MODEL,
        "balance_before": b0,
        "cap": CAP,
        "crop_box": prep["box"],
        "region": prep["region"],
        "crop_sha256": prep["crop_hash"],
        "aspect_ratio": prep["aspect_ratio"],
        "resolution": RESOLUTION,
        "prompt": PROMPT,
    })
    payload = {
        "prompt": PROMPT,
        "images": [upload(prep["crop_path"])],
        "resolution": RESOLUTION,
        "aspect_ratio": prep["aspect_ratio"],
        "output_format": "png",
        # NO mask_image — production region path
    }
    t_submit = time.time()
    r = requests.post(f"{BASE_URL}/{MODEL}", headers=headers(), json=payload, timeout=60)
    body = r.json()
    rid = (body.get("data") or {}).get("id") if body.get("code") == 200 else None
    append({
        "event": "submit",
        "model": MODEL,
        "prediction_id": rid,
        "balance_before": b0,
        "http_status": r.status_code,
        "crop_sha256": prep["crop_hash"],
        "crop_box": prep["box"],
        "aspect_ratio": prep["aspect_ratio"],
        "resolution": RESOLUTION,
        "has_mask_image": "mask_image" in payload,
        "error": None if rid else body,
    })
    print(json.dumps({
        "event": "submit", "model": MODEL, "prediction_id": rid,
        "balance_before": b0, "aspect_ratio": prep["aspect_ratio"],
    }, ensure_ascii=False), flush=True)
    if not rid:
        append({"event": "failed_no_id", "stop": "no retries"})
        print("FAIL: no prediction id; stopping (no retries)", flush=True)
        return 1

    g = poll(rid)
    time.sleep(2)
    b1 = bal()
    cost = round(b0 - b1, 6)
    ok = g.get("status") == "completed"
    result_path = None
    if ok and g.get("outputs"):
        raw = requests.get(g["outputs"][0], timeout=180).content
        (OUT / "raw-crop.png").write_bytes(raw)
        pasted = paste_result(prep["orig_bytes"], prep["mask_crop_bytes"], prep["box"], raw)
        result_path = OUT / "pasteback.png"
        result_path.write_bytes(pasted)
        collages = make_collages(prep, result_path)
    else:
        collages = {}
        append({"event": "failed", "prediction_id": rid, "status": g.get("status"),
                "error": g.get("error"), "stop": "no retries"})
        print(f"FAIL: status={g.get('status')}; stopping (no retries)", flush=True)

    done = {
        "event": "done",
        "model": MODEL,
        "prediction_id": rid,
        "ok": ok,
        "status": g.get("status"),
        "balance_before": b0,
        "balance_after": b1,
        "cost": cost,
        "latency_s": round(time.time() - t_submit, 3),
        "pasteback": str(result_path) if result_path else None,
        "collages": collages,
        "cap": CAP,
        "under_cap": cost <= CAP,
    }
    append(done)
    print(json.dumps({k: done[k] for k in (
        "event", "ok", "prediction_id", "cost", "balance_after", "under_cap"
    )}, ensure_ascii=False), flush=True)
    if cost > CAP:
        print(f"WARNING: cost {cost} exceeded cap {CAP}", flush=True)
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--live", action="store_true")
    args = ap.parse_args()
    if not BASE_IMG.exists() or not MASK_IMG.exists():
        raise SystemExit(f"missing {BASE_IMG} or {MASK_IMG}")
    prep = prepare_crop()
    if args.dry_run:
        return dry_run(prep)
    return live(prep)


if __name__ == "__main__":
    sys.exit(main())
