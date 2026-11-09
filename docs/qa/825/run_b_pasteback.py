#!/usr/bin/env python3
"""B1/B2 via production region pasteback. Cap $0.12. Never prints API key."""
from __future__ import annotations
import hashlib, io, json, os, sys, time
from pathlib import Path
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
LR = ROOT / "lr"
CALLS = ROOT / "calls.jsonl"
CAP = 0.12
BASE_URL = "https://api.wavespeed.ai/api/v3"
PROMPT = "Replace only the sky in the selection with a soft peach sunset, keep the building and window frames unchanged"
BASE_IMG = ROOT / "inputs" / "base-window-sky.png"
MASK_IMG = ROOT / "inputs" / "mask-sky-top.png"
TOUCH_PAD, TOUCH_MIN = 0.25, 384

def env_key():
    k = os.environ.get("WAVESPEED_API_KEY")
    if not k:
        for line in Path("/home/box/.secrets/comfyart-test.env").read_text().splitlines():
            if line.startswith("WAVESPEED_API_KEY="):
                k = line.split("=", 1)[1].strip().strip('"').strip("'")
                os.environ["WAVESPEED_API_KEY"] = k
                break
    if not k:
        raise SystemExit("missing key")
    return k

def headers():
    return {"Authorization": "Bearer " + env_key()}

def bal():
    r = requests.get(BASE_URL + "/balance", headers=headers(), timeout=20)
    r.raise_for_status()
    return float(r.json()["data"]["balance"])

def append(rec):
    with CALLS.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush(); os.fsync(f.fileno())

def crop_around(region, w, h):
    def grow(length, full):
        return min(full, max(length * (1 + TOUCH_PAD * 2), TOUCH_MIN))
    cw = min(w, round(grow(region["w"], w) / 8) * 8)
    ch = min(h, round(grow(region["h"], h) / 8) * 8)
    def clamp(v, size, full):
        return round(min(max(v, 0), full - size))
    return {"x": clamp(region["x"] + region["w"] / 2 - cw / 2, cw, w),
            "y": clamp(region["y"] + region["h"] / 2 - ch / 2, ch, h), "w": cw, "h": ch}

def mask_array_from_img(img: Image.Image, size=None):
    img = img.convert("RGBA")
    if size and img.size != size:
        img = img.resize(size, Image.NEAREST)
    return 1.0 - np.asarray(img.getchannel("A"), dtype=np.float32) / 255.0

def mask_png(m):
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

def upload(path: Path) -> str:
    r = requests.post(BASE_URL + "/media/upload/binary", headers=headers(),
                      files={"file": (path.name, path.read_bytes())}, timeout=120)
    r.raise_for_status()
    return r.json()["data"]["download_url"]

def poll(rid, timeout_s=600):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(4)
        g = requests.get(f"{BASE_URL}/predictions/{rid}/result", headers=headers(), timeout=30).json()["data"]
        if g.get("status") in ("completed", "failed"):
            return g
    return {"status": "timeout", "error": "poll timeout"}

def prepare_crop():
    OUT.mkdir(parents=True, exist_ok=True)
    base = Image.open(BASE_IMG).convert("RGB")
    mask = Image.open(MASK_IMG).convert("RGBA")
    W, H = base.size
    a = np.array(mask.getchannel("A"))
    ys, xs = (a == 0).nonzero()
    region = {"x": int(xs.min()), "y": int(ys.min()),
              "w": int(xs.max()) - int(xs.min()) + 1, "h": int(ys.max()) - int(ys.min()) + 1}
    box = crop_around(region, W, H)
    crop = base.crop((box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]))
    crop_path = OUT / "_b_paste_crop.png"
    crop.save(crop_path)
    # crop-local ComfyArt mask: α=0 where target (sky) intersects crop
    full_m = mask_array_from_img(mask, (W, H))  # 1 = target
    m = full_m[box["y"]:box["y"] + box["h"], box["x"]:box["x"] + box["w"]]
    mask_crop_bytes = mask_png(m)
    (OUT / "_b_paste_mask_crop.png").write_bytes(mask_crop_bytes)
    crop_hash = hashlib.sha256(crop_path.read_bytes()).hexdigest()
    return {
        "box": box, "region": region, "crop_path": crop_path, "crop_hash": crop_hash,
        "mask_crop_bytes": mask_crop_bytes, "orig_bytes": BASE_IMG.read_bytes(),
        "full_mask": mask, "W": W, "H": H,
    }

def one(job_id, model, prep, attempt, spent):
    b0 = bal()
    if b0 < 20:
        raise SystemExit(f"BALANCE<20 {b0}")
    if spent >= CAP:
        raise SystemExit(f"CAP {spent}")
    payload = {
        "prompt": PROMPT,
        "images": [upload(prep["crop_path"])],
        "resolution": "1k",
        "aspect_ratio": "3:4",
        "output_format": "png",
        # NO mask_image — production region path
    }
    t_submit = time.time()
    r = requests.post(f"{BASE_URL}/{model}", headers=headers(), json=payload, timeout=60)
    body = r.json()
    rid = (body.get("data") or {}).get("id") if body.get("code") == 200 else None
    submit_rec = {
        "event": "submit", "run": "B-pasteback", "id": job_id, "attempt": attempt, "model": model,
        "prediction_id": rid, "balance_before": b0, "http_status": r.status_code,
        "crop_sha256": prep["crop_hash"], "crop_box": prep["box"],
        "payload_keys": sorted(payload.keys()), "has_mask_image": "mask_image" in payload,
        "resolution": "1k", "aspect_ratio": "3:4", "prompt": PROMPT,
        "error": None if rid else body,
    }
    append(submit_rec)
    print(json.dumps({k: submit_rec[k] for k in ("event","id","attempt","model","prediction_id","balance_before","crop_sha256","has_mask_image")}, ensure_ascii=False), flush=True)
    if not rid:
        return {"ok": False, "cost": 0.0, "id": job_id, "attempt": attempt, "error": body, "balance_before": b0, "balance_after": bal()}

    g = poll(rid)
    t_done = time.time()
    time.sleep(2)
    b1 = bal()
    cost = round(b0 - b1, 6)
    ok = g.get("status") == "completed"
    raw_path = paste_path = None
    if ok and g.get("outputs"):
        raw = requests.get(g["outputs"][0], timeout=180).content
        raw_path = OUT / f"{job_id}-raw-crop.png"
        raw_path.write_bytes(raw)
        pasted = paste_result(prep["orig_bytes"], prep["mask_crop_bytes"], prep["box"], raw)
        paste_path = OUT / f"{job_id}-pasteback.png"
        paste_path.write_bytes(pasted)
        Image.open(io.BytesIO(pasted)).convert("RGB").save(OUT / f"{job_id}-pasteback.webp", "WEBP", quality=90)
    done = {
        "event": "done", "run": "B-pasteback", "id": job_id, "attempt": attempt, "model": model,
        "prediction_id": rid, "ok": ok, "status": g.get("status"),
        "balance_before": b0, "balance_after": b1, "cost": cost,
        "latency_s": round(t_done - t_submit, 3),
        "raw": str(raw_path) if raw_path else None,
        "pasteback": str(paste_path) if paste_path else None,
        "crop_sha256": prep["crop_hash"], "error": g.get("error") if not ok else None,
    }
    append(done)
    print(json.dumps({k: done[k] for k in ("event","id","ok","prediction_id","cost","latency_s","balance_after")}, ensure_ascii=False), flush=True)
    return done

def acceptance(prep, paste_path: Path):
    orig = np.asarray(Image.open(io.BytesIO(prep["orig_bytes"])).convert("RGB"))
    out = np.asarray(Image.open(paste_path).convert("RGB"))
    assert orig.shape == out.shape, (orig.shape, out.shape)
    full_m = mask_array_from_img(prep["full_mask"], (prep["W"], prep["H"]))  # 1=target
    outside = full_m < 0.5
    inside = full_m >= 0.5
    diff = np.abs(orig.astype(np.int16) - out.astype(np.int16))
    outside_diff = diff[outside]
    max_abs = int(outside_diff.max()) if outside_diff.size else 0
    n_diff = int((outside_diff.max(axis=-1) > 0).sum()) if outside_diff.size else 0
    # black band inside selection?
    inside_px = out[inside]
    near_black_frac = float((inside_px.max(axis=-1) < 20).mean()) if inside_px.size else 0.0
    inside_mean = inside_px.mean(axis=0).round(1).tolist() if inside_px.size else []
    return {
        "max_abs_diff_outside": max_abs,
        "n_diff_pixels_outside": n_diff,
        "outside_ok": max_abs == 0 and n_diff == 0,
        "inside_near_black_frac": round(near_black_frac, 4),
        "inside_mean_rgb": inside_mean,
        "black_band": near_black_frac > 0.5,
    }

def main():
    OUT.mkdir(exist_ok=True); LR.mkdir(exist_ok=True)
    prep = prepare_crop()
    append({"event": "b_pasteback_start", "balance": bal(), "cap": CAP,
            "crop_sha256": prep["crop_hash"], "crop_box": prep["box"], "region": prep["region"],
            "crop_bytes": prep["crop_path"].stat().st_size})
    print(f"START bal={bal()} crop_sha256={prep['crop_hash']} box={prep['box']}", flush=True)
    spent = 0.0
    results = []
    jobs = [
        ("B1p", "openai/gpt-image-2.5-sunburst/edit"),
        ("B2p", "openai/gpt-image-2.6-sunburst/edit"),
    ]
    for jid, model in jobs:
        if spent >= CAP:
            append({"event": "cap_stop", "spent": spent, "next": jid}); break
        ok = False; last = None
        for attempt in (1, 2):
            if spent >= CAP: break
            last = one(jid, model, prep, attempt, spent)
            results.append(last)
            spent = round(spent + float(last.get("cost") or 0), 6)
            append({"event": "spent_so_far", "run": "B-pasteback", "spent": spent})
            if last.get("ok"):
                ok = True; break
            print(f"FAIL {jid} attempt {attempt}", flush=True)
        if not ok:
            append({"event": "image_abandoned", "id": jid})
        if spent >= CAP:
            append({"event": "cap_stop_after", "spent": spent, "id": jid}); break

    # acceptance
    acc = {}
    for jid, _ in jobs:
        p = OUT / f"{jid}-pasteback.png"
        if p.exists():
            acc[jid] = acceptance(prep, p)
            append({"event": "acceptance", "id": jid, **acc[jid]})
            print(f"ACCEPT {jid} {acc[jid]}", flush=True)

    summary = {
        "event": "b_pasteback_end",
        "balance_end": bal(),
        "spent": spent,
        "crop_sha256": prep["crop_hash"],
        "results": [{k: r.get(k) for k in ("id","attempt","ok","prediction_id","cost","latency_s","balance_before","balance_after","model")} for r in results],
        "acceptance": acc,
    }
    append(summary)
    (ROOT / "B-pasteback-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({"event": "end", "spent": spent, "balance_end": summary["balance_end"]}, ensure_ascii=False), flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
