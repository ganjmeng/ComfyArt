#!/usr/bin/env python3
"""#636/#653 soft wash C deferred5 — WaveSpeed gpt-image-2.5-sunburst/edit on c5-nearmiss stills.
Product remap (Examples-only; L = lovart.ai nearMiss):
  logo-abstract      → 2ns5q6jxbyf4 carousel hardMax 11
  photo-split-poster → 2pg3z0ftueww still 1
  ppt-visual         → 2n7npu8pocu8 still 1
  promo-ecommerce    → 2q1txsahwp34 carousel 4
  naive-illustration → 2qapfgd34fsw carousel 4 (NOT doodle/matte)
Out: 636/wash/<skill>/{cover.webp,examples/NN.webp,featured/NN.webp}
Never print API keys. No Lovart string in product paths.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import mimetypes
import os
import subprocess
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

BC = Path("/workspace/ComfyArt-review-assets/phase2/bc-refs/c5-nearmiss")
OUT = Path("/workspace/636-c/review-assets/636/wash")
PREP = Path("/workspace/636-c/prep")
LEDGER = PREP / "ledger.jsonl"
BASE = (os.environ.get("WAVESPEED_BASE_URL") or "https://api.wavespeed.ai").rstrip("/")
MODEL = "openai/gpt-image-2.5-sunburst/edit"

PROMPT = (
    "Subtle copyright-dodge edit of this reference still for a production skill card. "
    "KEEP composition, subjects, palette, lighting, crop, and density almost 1:1. "
    "Remove watermarks, platform logos, author avatars, HUD brand marks, and any third-party "
    "product UI chrome that names a competitor. Soften or replace unreadable microcopy with "
    "clean short neutral chips if needed. Do not invent a new sparse redesign. "
    "No new logos, no watermarks, no author names."
)

# skill_id -> nearMiss folder + layout
SKILLS = {
    "logo-abstract": {
        "near": "2ns5q6jxbyf4",
        "layout": "examples-carousel",
        "ex_max": 11,
        "ar_cover": "4:3",
    },
    "photo-split-poster": {
        "near": "2pg3z0ftueww",
        "layout": "examples-single-still",
        "ex_max": 1,
        "ar_cover": "4:3",
    },
    "ppt-visual": {
        "near": "2n7npu8pocu8",
        "layout": "examples-single-still",
        "ex_max": 1,
        "ar_cover": "4:3",
    },
    "promo-ecommerce": {
        "near": "2q1txsahwp34",
        "layout": "examples-carousel",
        "ex_max": 4,
        "ar_cover": "4:3",
    },
    "naive-illustration": {
        "near": "2qapfgd34fsw",
        "layout": "examples-carousel",
        "ex_max": 4,
        "ar_cover": "4:3",
    },
}


def load_key() -> str:
    key = (os.environ.get("WAVESPEED_API_KEY") or os.environ.get("WAVE_AI_API_KEY") or "").strip()
    if not key:
        raise SystemExit("WAVESPEED_API_KEY missing")
    return key


def api(method: str, path: str, body: dict | None = None) -> dict:
    key = load_key()
    data = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw_txt = e.read().decode() if e.fp else str(e)
        try:
            return json.loads(raw_txt)
        except Exception:
            return {"code": e.code, "msg": raw_txt, "data": None}


def ledger(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = {k: v for k, v in row.items() if "key" not in k.lower() and "token" not in k.lower()}
    with LEDGER.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def balance() -> float:
    r = api("GET", "/api/v3/balance")
    data = r.get("data") or {}
    return float(data.get("balance", 0))


def upload_image(path: Path) -> str:
    key = load_key()
    boundary = f"----ws{uuid.uuid4().hex}"
    filename = path.name
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    file_bytes = path.read_bytes()
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {ctype}\r\n\r\n".encode(),
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        BASE + "/api/v3/media/upload/binary",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        r = json.loads(resp.read().decode())
    url = ((r.get("data") or {}).get("download_url"))
    if not url:
        raise RuntimeError(f"upload failed: {str(r)[:400]}")
    return url


def create_edit(image_url: str, ar: str) -> str:
    body = {
        "prompt": PROMPT,
        "images": [image_url],
        "aspect_ratio": ar,
        "resolution": "1k",
        "output_format": "png",
    }
    r = api("POST", f"/api/v3/{MODEL}", body)
    task_id = ((r.get("data") or {}).get("id")) if isinstance(r, dict) else None
    if not task_id:
        raise RuntimeError(f"create failed: {str(r)[:500]}")
    return task_id


def poll(task_id: str, timeout_s: int = 420) -> dict:
    t0 = time.time()
    delay = 2.0
    while time.time() - t0 < timeout_s:
        r = api("GET", f"/api/v3/predictions/{task_id}/result")
        data = (r.get("data") or {}) if isinstance(r, dict) else {}
        status = data.get("status")
        print(f"poll {task_id[:8]} status={status}", flush=True)
        if status == "completed":
            return data
        if status in ("failed", "cancelled", "timeout", "deleted"):
            return data
        time.sleep(delay)
        delay = min(delay * 1.25, 10)
    raise TimeoutError(task_id)


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["curl", "-sS", "-L", "--connect-timeout", "20", "--max-time", "180", "-o", str(dest), url],
        check=True,
    )


def pick_ar(w: int, h: int) -> str:
    r = w / h
    cands = {
        "1:1": 1.0,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "3:2": 1.5,
        "2:3": 2 / 3,
    }
    return min(cands.items(), key=lambda kv: abs(kv[1] - r))[0]


def to_webp(src: Path, dest: Path, max_edge: int = 1400, quality: int = 86) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGB")
    w, h = im.size
    scale = min(1.0, max_edge / max(w, h))
    if scale < 1.0:
        im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    im.save(dest, "WEBP", quality=quality, method=6)
    return dest


def cover_webp(src: Path, dest: Path) -> Path:
    """List cover plate 462x346 (2x = 924x692)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGB")
    tw, th = 924, 692
    w, h = im.size
    target_ar = tw / th
    cur_ar = w / h
    if cur_ar > target_ar:
        nw = int(h * target_ar)
        left = (w - nw) // 2
        im = im.crop((left, 0, left + nw, h))
    else:
        nh = int(w / target_ar)
        top = (h - nh) // 2
        im = im.crop((0, top, w, top + nh))
    im = im.resize((tw, th), Image.Resampling.LANCZOS)
    im.save(dest, "WEBP", quality=86, method=6)
    return dest


def jobs() -> list[dict]:
    out = []
    for skill, meta in SKILLS.items():
        root = BC / meta["near"]
        cover = root / "cover.png"
        if not cover.exists():
            raise SystemExit(f"missing cover {cover}")
        out.append({"skill": skill, "kind": "cover", "src": cover, "ar": meta["ar_cover"]})
        ex_dir = root / "examples"
        stills = sorted(ex_dir.glob("*.png")) + sorted(ex_dir.glob("*.jpg"))
        if len(stills) < meta["ex_max"]:
            raise SystemExit(f"{skill}: need {meta['ex_max']} examples, have {len(stills)}")
        for i, p in enumerate(stills[: meta["ex_max"]], 1):
            im = Image.open(p)
            out.append({"skill": skill, "kind": "example", "n": i, "src": p, "ar": pick_ar(*im.size)})
    return out


def wash_one(job: dict) -> dict:
    skill, kind, src = job["skill"], job["kind"], Path(job["src"])
    tag = f"{skill}/{kind}" + (f"/{job.get('n'):02d}" if kind == "example" else "")
    raw_png = PREP / "raw" / f"{tag.replace('/', '__')}.png"
    if kind == "cover":
        dest = OUT / skill / "cover.webp"
    else:
        dest = OUT / skill / "examples" / f"{job['n']:02d}.webp"
    if dest.exists() and dest.stat().st_size > 1000:
        return {"tag": tag, "ok": True, "skipped": True, "dest": str(dest)}
    print(f"upload {tag} {src}", flush=True)
    url = upload_image(src)
    task_id = create_edit(url, job["ar"])
    ledger({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": "create", "tag": tag, "taskId": task_id, "ar": job["ar"]})
    data = poll(task_id)
    outs = data.get("outputs") or data.get("output") or []
    if isinstance(outs, str):
        outs = [outs]
    if isinstance(outs, dict):
        outs = list(outs.values())
    if not outs:
        for k in ("url", "urls", "images"):
            if data.get(k):
                outs = data[k] if isinstance(data[k], list) else [data[k]]
                break
    if data.get("status") != "completed" or not outs:
        ledger({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": "fail", "tag": tag, "data": str(data)[:500]})
        return {"tag": tag, "ok": False, "error": str(data)[:400]}
    out_url = outs[0] if isinstance(outs[0], str) else (outs[0].get("url") if isinstance(outs[0], dict) else None)
    if not out_url:
        return {"tag": tag, "ok": False, "error": f"no url in {outs!r}"[:400]}
    download(out_url, raw_png)
    if kind == "cover":
        cover_webp(raw_png, dest)
    else:
        to_webp(raw_png, dest)
    ledger({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": "complete", "tag": tag, "dest": str(dest), "bytes": dest.stat().st_size})
    print(f"ok {tag} -> {dest}", flush=True)
    return {"tag": tag, "ok": True, "dest": str(dest)}


def pack_featured() -> None:
    """featured 3–5: cover + examples (cycle if short). Matches #637 pack."""
    for skill, meta in SKILLS.items():
        sdir = OUT / skill
        ex = sorted((sdir / "examples").glob("*.webp"))
        cover = sdir / "cover.webp"
        feat_dir = sdir / "featured"
        feat_dir.mkdir(parents=True, exist_ok=True)
        pool = ([cover] if cover.exists() else []) + ex
        if not pool:
            continue
        # Prefer 5 when pool >=5; else max(3, len) with cycle to ≥3
        if len(pool) >= 5:
            n = 5
        else:
            n = max(3, len(pool))
        for i in range(1, n + 1):
            src = pool[(i - 1) % len(pool)]
            dest = feat_dir / f"{i:02d}.webp"
            if not dest.exists():
                Image.open(src).convert("RGB").save(dest, "WEBP", quality=86, method=6)


def main() -> None:
    PREP.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (PREP / "raw").mkdir(parents=True, exist_ok=True)
    js = jobs()
    print(f"jobs={len(js)} balance_before={balance()}", flush=True)
    ok = fail = 0
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(wash_one, j) for j in js]
        for fut in cf.as_completed(futs):
            r = fut.result()
            if r.get("ok"):
                ok += 1
            else:
                fail += 1
                print("FAIL", r, flush=True)
    pack_featured()
    bal = balance()
    manifest = {
        "issue": 636,
        "pr": 653,
        "model": MODEL,
        "remap": {s: m["near"] for s, m in SKILLS.items()},
        "skills": {s: {k: v for k, v in m.items() if k != "near"} | {"near": m["near"]} for s, m in SKILLS.items()},
        "ok": ok,
        "fail": fail,
        "balance_after": bal,
        "outs": {
            s: {
                "cover": (OUT / s / "cover.webp").exists(),
                "examples": sorted(p.name for p in (OUT / s / "examples").glob("*.webp")),
                "featured": sorted(p.name for p in (OUT / s / "featured").glob("*.webp")),
                "ex_max": SKILLS[s]["ex_max"],
            }
            for s in SKILLS
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2), flush=True)
    if fail:
        raise SystemExit(f"wash fail={fail}")


if __name__ == "__main__":
    main()
