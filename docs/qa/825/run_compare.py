#!/usr/bin/env python3
"""Paid 10-image #825 comparison. Serial only. Never prints API keys."""
from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
LR = ROOT / "lr"
CALLS = ROOT / "calls.jsonl"
CAP = 0.65
BASE_URL = "https://api.wavespeed.ai/api/v3"

PROMPT_A = (
    "Furniture retail poster, light-blue velvet sofa hero on a warm wood floor.\n"
    "Brand line: 「ARDEN雅登家居丨双11狂欢购」.\n"
    "Small date line: 「10.24 20:00 - 11.11 23:59」.\n"
    "Headline (exact): 「换个心情 / 过冬！」.\n"
    "Offer lines: 「先领3000元暖家补贴」; 「11月1日0点开抢」; 「低至6折！」; 「沙发卧室客厅同场」.\n"
    "Footer price chips in our words: 「预估到手 ¥2199」 and 「叠加会员券再减」.\n"
    "White bold italic Chinese type with dark outline, readable small text, clean e-commerce layout, no watermark."
)
PROMPT_B = "Replace only the sky in the selection with a soft peach sunset, keep the building and window frames unchanged"
PROMPT_C = (
    "Keep the same person and face identity from the reference. Turn her to a 3/4 profile with a natural smile. "
    "Move her to a bright living room by the window with natural light. Outfit unchanged. "
    "Real skin texture, no AI face, no watermark."
)
PROMPT_D = (
    "Photoreal portrait of an attractive young East Asian woman, beauty-campaign grade, natural makeup, "
    "real skin texture with fine pores, soft daylight, 35mm photography look, 非网红脸, no logo, no watermark."
)

BASE_IMG = ROOT / "inputs" / "base-window-sky.png"
MASK_IMG = ROOT / "inputs" / "mask-sky-top.png"
PORTRAIT = ROOT / "inputs" / "portrait-studio-01.webp"


def env_key() -> str:
    k = os.environ.get("WAVESPEED_API_KEY")
    if not k:
        # load from secrets without printing
        p = Path("/home/box/.secrets/comfyart-test.env")
        for line in p.read_text().splitlines():
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


def mask_to_white(path: Path) -> bytes:
    img = Image.open(path).convert("RGBA")
    alpha = img.getchannel("A")
    out = alpha.point(lambda a: 255 - a).convert("L")
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def crop_masked_region(base: Path, mask: Path, dest: Path) -> Path:
    b = Image.open(base).convert("RGB")
    a = Image.open(mask).convert("RGBA").getchannel("A")
    import numpy as np

    aa = np.array(a)
    ys, xs = (aa == 0).nonzero()
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    b.crop(box).save(dest)
    return dest


def upload_bytes(name: str, data: bytes) -> str:
    r = requests.post(
        BASE_URL + "/media/upload/binary",
        headers=headers(),
        files={"file": (name, data)},
        timeout=120,
    )
    r.raise_for_status()
    j = r.json()
    return j["data"]["download_url"]


def upload_file(path: Path) -> str:
    return upload_bytes(path.name, path.read_bytes())


def append_call(rec: dict) -> None:
    with CALLS.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def poll(rid: str, timeout_s: int = 600) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(4)
        g = requests.get(f"{BASE_URL}/predictions/{rid}/result", headers=headers(), timeout=30).json()["data"]
        st = g.get("status")
        if st == "completed":
            return g
        if st == "failed":
            return g
    return {"status": "timeout", "error": "poll timeout"}


def one_call(job: dict, attempt: int) -> dict:
    """Submit one prediction. Writes prediction id to calls.jsonl at submit time."""
    b0 = bal()
    if b0 < 20:
        raise SystemExit(f"BALANCE<20 stop before {job['id']}: {b0}")
    spent = job.get("_spent", 0.0)
    # caller tracks spent; we just check bal

    payload = dict(job["payload"])
    # upload media if needed
    if "images_paths" in job:
        payload["images"] = [upload_file(Path(p)) for p in job["images_paths"]]
    if "mask_path" in job:
        mb = mask_to_white(Path(job["mask_path"]))
        payload["mask_image"] = upload_bytes("mask-ws.png", mb)

    model = job["model"]
    t_submit = time.time()
    r = requests.post(f"{BASE_URL}/{model}", headers=headers(), json=payload, timeout=60)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:500], "status_code": r.status_code}

    rid = None
    if isinstance(body, dict) and body.get("code") == 200:
        rid = (body.get("data") or {}).get("id")

    submit_rec = {
        "event": "submit",
        "id": job["id"],
        "attempt": attempt,
        "model": model,
        "prediction_id": rid,
        "balance_before": b0,
        "http_status": r.status_code,
        "submit_ts": t_submit,
        "error": None if rid else body,
    }
    append_call(submit_rec)
    print(json.dumps({k: submit_rec[k] for k in ("event", "id", "attempt", "model", "prediction_id", "balance_before")}, ensure_ascii=False), flush=True)

    if not rid:
        return {
            "id": job["id"],
            "attempt": attempt,
            "ok": False,
            "prediction_id": None,
            "balance_before": b0,
            "balance_after": bal(),
            "cost": 0.0,
            "latency_s": round(time.time() - t_submit, 3),
            "error": body,
            "out": None,
        }

    g = poll(rid)
    t_done = time.time()
    time.sleep(2)  # allow billing to settle a bit
    b1 = bal()
    cost = round(b0 - b1, 6)
    ok = g.get("status") == "completed"
    out_path = None
    if ok and g.get("outputs"):
        out_path = OUT / f"{job['id']}.png"
        data = requests.get(g["outputs"][0], timeout=180).content
        out_path.write_bytes(data)
        # also a reasonable webp
        try:
            im = Image.open(io.BytesIO(data)).convert("RGB")
            im.save(OUT / f"{job['id']}.webp", "WEBP", quality=90)
        except Exception as e:
            append_call({"event": "webp_fail", "id": job["id"], "error": str(e)})

    done = {
        "event": "done",
        "id": job["id"],
        "attempt": attempt,
        "model": model,
        "prediction_id": rid,
        "ok": ok,
        "status": g.get("status"),
        "balance_before": b0,
        "balance_after": b1,
        "cost": cost,
        "latency_s": round(t_done - t_submit, 3),
        "out": str(out_path) if out_path else None,
        "error": g.get("error") if not ok else None,
    }
    append_call(done)
    print(json.dumps({k: done[k] for k in ("event", "id", "attempt", "ok", "prediction_id", "cost", "latency_s", "balance_after")}, ensure_ascii=False), flush=True)
    return done


def jobs() -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    crop = OUT / "_b_sky_crop.png"
    crop_masked_region(BASE_IMG, MASK_IMG, crop)
    return [
        {
            "id": "A1",
            "model": "openai/gpt-image-2.6-flare/text-to-image",
            "payload": {
                "prompt": PROMPT_A,
                "resolution": "2k",
                "aspect_ratio": "3:4",
                "output_format": "png",
            },
            "catalog": 0.10,
            "short": "2.6-flare t2i",
            "size": "2K 3:4",
        },
        {
            "id": "A2",
            "model": "openai/gpt-image-2.6-sunburst/text-to-image",
            "payload": {
                "prompt": PROMPT_A,
                "resolution": "2k",
                "aspect_ratio": "3:4",
                "output_format": "png",
            },
            "catalog": 0.10,
            "short": "2.6-sunburst t2i",
            "size": "2K 3:4",
        },
        {
            "id": "B1",
            "model": "openai/gpt-image-2.5-sunburst/edit",
            "payload": {
                "prompt": PROMPT_B,
                "resolution": "1k",
                "aspect_ratio": "3:4",
                "output_format": "png",
            },
            "images_paths": [str(crop)],
            "catalog": 0.039,
            "short": "2.5-sunburst edit",
            "size": "1K",
        },
        {
            "id": "B2",
            "model": "openai/gpt-image-2.6-sunburst/edit",
            "payload": {
                "prompt": PROMPT_B,
                "resolution": "1k",
                "aspect_ratio": "3:4",
                "output_format": "png",
            },
            "images_paths": [str(BASE_IMG)],
            "mask_path": str(MASK_IMG),
            "catalog": 0.065,
            "short": "2.6-sunburst edit",
            "size": "1K",
        },
        {
            "id": "C1",
            "model": "google/nano-banana-2.1/edit",
            "payload": {
                "prompt": PROMPT_C,
                "resolution": "1k",
                "aspect_ratio": "3:4",
                "output_format": "png",
            },
            "images_paths": [str(PORTRAIT)],
            "catalog": 0.04,
            "short": "nano-banana-2.1 edit",
            "size": "1K",
        },
        {
            "id": "C2",
            "model": "bytedance/seedream-v5.0-pro/edit",
            "payload": {
                "prompt": PROMPT_C,
                "resolution": "1k",
                "aspect_ratio": "3:4",
                "output_format": "png",
            },
            "images_paths": [str(PORTRAIT)],
            "catalog": 0.045,
            "short": "seedream-v5.0-pro edit",
            "size": "1K",
        },
        {
            "id": "C3",
            "model": "openai/gpt-image-2.6-sunburst/edit",
            "payload": {
                "prompt": PROMPT_C,
                "resolution": "1k",
                "aspect_ratio": "3:4",
                "output_format": "png",
            },
            "images_paths": [str(PORTRAIT)],
            "catalog": 0.065,
            "short": "2.6-sunburst edit",
            "size": "1K",
        },
        {
            "id": "D1",
            "model": "google/nano-banana-2.1/text-to-image",
            "payload": {
                "prompt": PROMPT_D,
                "resolution": "1k",
                "aspect_ratio": "3:4",
                "output_format": "png",
            },
            "catalog": 0.04,
            "short": "nano-banana-2.1 t2i",
            "size": "1K",
        },
        {
            "id": "D2",
            "model": "bytedance/seedream-v5.0-pro",
            "payload": {
                "prompt": PROMPT_D,
                "resolution": "1k",
                "aspect_ratio": "3:4",
                "output_format": "png",
            },
            "catalog": 0.045,
            "short": "seedream-v5.0-pro t2i",
            "size": "1K",
        },
        {
            "id": "D3",
            "model": "openai/gpt-image-2.6-sunburst/text-to-image",
            "payload": {
                "prompt": PROMPT_D,
                "resolution": "1k",
                "aspect_ratio": "3:4",
                "output_format": "png",
            },
            "catalog": 0.05,
            "short": "2.6-sunburst t2i",
            "size": "1K",
        },
    ]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    LR.mkdir(parents=True, exist_ok=True)
    # fresh log for this run (keep prior if exists by renaming)
    if CALLS.exists():
        CALLS.rename(CALLS.with_suffix(".jsonl.bak"))
    CALLS.write_text("")

    b_start = bal()
    append_call({"event": "run_start", "balance": b_start, "cap": CAP})
    print(f"RUN_START balance={b_start}", flush=True)
    if b_start < 20:
        print("STOP balance < 20")
        return 2

    spent = 0.0
    results = []
    meta = {j["id"]: j for j in jobs()}

    for job in jobs():
        if spent >= CAP:
            print(f"CAP reached {spent} >= {CAP}; stop before {job['id']}", flush=True)
            append_call({"event": "cap_stop", "spent": spent, "next": job["id"]})
            break
        # skip if already have successful out (resume)
        if (OUT / f"{job['id']}.png").exists():
            print(f"SKIP existing {job['id']}", flush=True)
            continue

        ok = False
        last = None
        for attempt in (1, 2):
            if spent >= CAP:
                break
            last = one_call(job, attempt)
            results.append(last)
            if last.get("cost"):
                spent = round(spent + float(last["cost"]), 6)
            append_call({"event": "spent_so_far", "spent": spent})
            if last.get("ok"):
                ok = True
                break
            print(f"FAIL {job['id']} attempt {attempt}", flush=True)
            if attempt == 2:
                append_call({"event": "image_abandoned", "id": job["id"]})
        if spent >= CAP:
            print(f"CAP after {job['id']}: {spent}", flush=True)
            append_call({"event": "cap_stop_after", "spent": spent, "id": job["id"]})
            break

    b_end = bal()
    summary = {
        "event": "run_end",
        "balance_start": b_start,
        "balance_end": b_end,
        "spent_from_balance": round(b_start - b_end, 6),
        "spent_sum_deltas": spent,
        "results": [
            {k: r.get(k) for k in ("id", "attempt", "ok", "prediction_id", "cost", "latency_s", "balance_before", "balance_after", "out")}
            for r in results
        ],
    }
    append_call(summary)
    (ROOT / "run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({"event": "run_end", "balance_start": b_start, "balance_end": b_end, "spent": round(b_start - b_end, 6)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
