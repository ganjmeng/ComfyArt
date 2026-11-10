#!/usr/bin/env python3
"""Paid one-set #825 keep-face compare. Serial only. Never prints API keys. No retries."""
from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]  # worktree root
PORTRAIT = REPO / "docs/qa/825/inputs/portrait-studio-01.webp"
OUT = ROOT / "out"
CALLS = ROOT / "calls.jsonl"
SPEND_JSON = ROOT / "spend.json"
CAP = 0.10
FLOOR = 20.0
BASE_URL = "https://api.wavespeed.ai/api/v3"
SECRETS = Path("/home/box/.secrets/comfyart-test.env")

PROMPT = "保留同一个人，脸、发型和坐姿都不变，只把衣服换成深色西装、背景换成办公室，去掉画面上所有文字"

JOBS = [
    {
        "id": "seedream",
        "model": "bytedance/seedream-v5.0-pro/edit",
        "label": "Seedream 5.0 Pro",
    },
    {
        "id": "banana",
        "model": "google/nano-banana-2.1/edit",
        "label": "Nano Banana 2.1",
    },
]

# Same relative box on every frame (fractions of width/height): hair + face + a little collar.
FACE_BOX = (0.28, 0.32, 0.80, 0.60)


def env_key() -> str:
    k = os.environ.get("WAVESPEED_API_KEY")
    if not k:
        for line in SECRETS.read_text().splitlines():
            if line.startswith("WAVESPEED_API_KEY="):
                k = line.split("=", 1)[1].strip().strip('"').strip("'")
                os.environ["WAVESPEED_API_KEY"] = k
                break
    if not k:
        raise SystemExit("WAVESPEED_API_KEY missing")
    return k


def headers() -> dict:
    return {"Authorization": "Bearer " + env_key()}


def bal() -> float:
    r = requests.get(BASE_URL + "/balance", headers=headers(), timeout=20)
    r.raise_for_status()
    return float(r.json()["data"]["balance"])


def quote(model: str) -> dict:
    body = {
        "model_id": model,
        "inputs": {"resolution": "1k", "aspect_ratio": "3:4", "output_format": "png"},
    }
    r = requests.post(BASE_URL + "/model/price", headers=headers(), json=body, timeout=20)
    r.raise_for_status()
    j = r.json()
    data = (j.get("data") or {}) if isinstance(j, dict) else {}
    list_price = data.get("price")
    disc = data.get("discounted_price", list_price)
    if not isinstance(disc, (int, float)):
        raise SystemExit(f"UNPRICED {model}")
    return {
        "model": model,
        "list_price": float(list_price) if isinstance(list_price, (int, float)) else float(disc),
        "discounted_price": float(disc),
    }


def append_call(rec: dict) -> None:
    with CALLS.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def safe_err(obj) -> object:
    """Drop anything that might echo a credential; keep short status text."""
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj[:400]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if any(s in lk for s in ("key", "token", "authorization", "secret", "password")):
                continue
            out[k] = safe_err(v) if isinstance(v, (dict, list)) else (str(v)[:400] if not isinstance(v, (int, float, bool, type(None))) else v)
        return out
    if isinstance(obj, list):
        return [safe_err(x) for x in obj[:8]]
    return str(obj)[:400]


def upload_file(path: Path) -> str:
    r = requests.post(
        BASE_URL + "/media/upload/binary",
        headers=headers(),
        files={"file": (path.name, path.read_bytes())},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["data"]["download_url"]


def poll(rid: str, timeout_s: int = 600) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(4)
        g = requests.get(f"{BASE_URL}/predictions/{rid}/result", headers=headers(), timeout=30).json()["data"]
        st = g.get("status")
        if st in ("completed", "failed"):
            return g
    return {"status": "timeout", "error": "poll timeout"}


def one_call(job: dict, image_url: str) -> dict:
    b0 = bal()
    if b0 < FLOOR:
        raise SystemExit(f"BALANCE<{FLOOR} stop before {job['id']}: {b0}")
    payload = {
        "prompt": PROMPT,
        "images": [image_url],
        "resolution": "1k",
        "aspect_ratio": "3:4",
        "output_format": "png",
    }
    model = job["model"]
    t_submit = time.time()
    r = requests.post(f"{BASE_URL}/{model}", headers=headers(), json=payload, timeout=60)
    try:
        body = r.json()
    except Exception:
        body = {"status_code": r.status_code, "text": r.text[:200]}
    rid = None
    if isinstance(body, dict) and body.get("code") == 200:
        rid = (body.get("data") or {}).get("id")
    submit_rec = {
        "event": "submit",
        "id": job["id"],
        "model": model,
        "prediction_id": rid,
        "balance_before": b0,
        "http_status": r.status_code,
        "error": None if rid else safe_err(body),
    }
    append_call(submit_rec)
    print(json.dumps({k: submit_rec[k] for k in ("event", "id", "model", "prediction_id", "balance_before")}, ensure_ascii=False), flush=True)
    if not rid:
        return {
            "id": job["id"],
            "model": model,
            "ok": False,
            "prediction_id": None,
            "balance_before": b0,
            "balance_after": bal(),
            "cost": 0.0,
            "latency_s": round(time.time() - t_submit, 3),
            "error": safe_err(body),
            "out": None,
        }
    g = poll(rid)
    t_done = time.time()
    time.sleep(2)
    b1 = bal()
    cost = round(b0 - b1, 6)
    ok = g.get("status") == "completed"
    out_path = None
    if ok and g.get("outputs"):
        OUT.mkdir(parents=True, exist_ok=True)
        data = requests.get(g["outputs"][0], timeout=180).content
        out_path = OUT / f"{job['id']}.png"
        out_path.write_bytes(data)
        try:
            Image.open(io.BytesIO(data)).convert("RGB").save(OUT / f"{job['id']}.webp", "WEBP", quality=90)
        except Exception as e:
            append_call({"event": "webp_fail", "id": job["id"], "error": str(e)})
    done = {
        "event": "done",
        "id": job["id"],
        "model": model,
        "prediction_id": rid,
        "ok": ok,
        "status": g.get("status"),
        "balance_before": b0,
        "balance_after": b1,
        "cost": cost,
        "latency_s": round(t_done - t_submit, 3),
        "out": str(out_path) if out_path else None,
        "error": safe_err(g.get("error")) if not ok else None,
    }
    append_call(done)
    print(json.dumps({k: done[k] for k in ("event", "id", "ok", "prediction_id", "cost", "latency_s", "balance_after")}, ensure_ascii=False), flush=True)
    return done


def font(size: int) -> ImageFont.FreeTypeFont:
    path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    return ImageFont.truetype(path, size, index=0)


def fit(im: Image.Image, height: int) -> Image.Image:
    im = im.convert("RGB")
    w, h = im.size
    nw = max(1, round(w * (height / h)))
    return im.resize((nw, height), Image.Resampling.LANCZOS)


def face_crop(im: Image.Image) -> Image.Image:
    im = im.convert("RGB")
    w, h = im.size
    l, t, r, b = FACE_BOX
    box = (int(w * l), int(h * t), int(w * r), int(h * b))
    return im.crop(box)


def labeled_row(images: list[tuple[str, Image.Image]], height: int, dest: Path) -> None:
    caps = []
    tiles = []
    f = font(28)
    for label, im in images:
        tile = fit(im, height)
        tiles.append(tile)
        caps.append(label)
    gap, cap_h, pad = 12, 48, 16
    widths = [t.size[0] for t in tiles]
    canvas_w = pad * 2 + sum(widths) + gap * (len(tiles) - 1)
    canvas_h = pad * 2 + cap_h + height
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    x = pad
    for label, tile, tw in zip(caps, tiles, widths):
        bbox = draw.textbbox((0, 0), label, font=f)
        lw = bbox[2] - bbox[0]
        draw.text((x + (tw - lw) // 2, pad + 8), label, fill=(30, 30, 30), font=f)
        canvas.paste(tile, (x, pad + cap_h))
        x += tw + gap
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest)
    canvas.save(dest.with_suffix(".webp"), "WEBP", quality=90)
    print(f"WROTE {dest} {canvas.size}", flush=True)


def make_triptychs() -> None:
    orig = Image.open(PORTRAIT)
    seed = Image.open(OUT / "seedream.png")
    banana = Image.open(OUT / "banana.png")
    labeled_row(
        [("原图", orig), ("Seedream 5.0 Pro", seed), ("Nano Banana 2.1", banana)],
        height=1024,
        dest=ROOT / "triptych.png",
    )
    labeled_row(
        [("原图 脸部", face_crop(orig)), ("Seedream 5.0 Pro", face_crop(seed)), ("Nano Banana 2.1", face_crop(banana))],
        height=640,
        dest=ROOT / "triptych-face.png",
    )


def main() -> int:
    if not PORTRAIT.is_file():
        raise SystemExit(f"missing reference {PORTRAIT}")
    quotes = [quote(j["model"]) for j in JOBS]
    catalog_sum = round(sum(q["discounted_price"] for q in quotes), 6)
    list_sum = round(sum(q["list_price"] for q in quotes), 6)
    print(json.dumps({"event": "catalog", "quotes": quotes, "discounted_sum": catalog_sum, "list_sum": list_sum, "cap": CAP}, ensure_ascii=False), flush=True)
    if catalog_sum > CAP or list_sum > CAP:
        print(f"STOP catalog sum over cap ${CAP}: discounted={catalog_sum} list={list_sum}", flush=True)
        return 2
    b_start = bal()
    print(f"RUN_START balance={b_start}", flush=True)
    if b_start < FLOOR:
        print(f"STOP balance < {FLOOR}", flush=True)
        return 3
    append_call({"event": "run_start", "balance": b_start, "cap": CAP, "quotes": quotes})
    print("uploading reference…", flush=True)
    image_url = upload_file(PORTRAIT)
    results = []
    for job in JOBS:
        rec = one_call(job, image_url)
        results.append(rec)
        if not rec["ok"]:
            print(f"STOP first failure on {job['id']}; no retry, no second model", flush=True)
            break
        if rec["balance_after"] < FLOOR:
            print(f"STOP balance dropped below {FLOOR} after {job['id']}: {rec['balance_after']}", flush=True)
            break
    b_end = bal()
    summary = {
        "event": "run_end",
        "balance_start": b_start,
        "balance_end": b_end,
        "spent_from_balance": round(b_start - b_end, 6),
        "quotes": quotes,
        "discounted_sum": catalog_sum,
        "list_sum": list_sum,
        "cap": CAP,
        "prompt": PROMPT,
        "reference": str(PORTRAIT.relative_to(REPO)),
        "results": results,
    }
    SPEND_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    append_call({"event": "run_end", "balance_start": b_start, "balance_end": b_end, "spent": round(b_start - b_end, 6)})
    print(json.dumps({"event": "run_end", "balance_start": b_start, "balance_end": b_end, "spent": round(b_start - b_end, 6)}, ensure_ascii=False), flush=True)
    if all(r.get("ok") and r.get("out") for r in results) and len(results) == 2:
        make_triptychs()
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
