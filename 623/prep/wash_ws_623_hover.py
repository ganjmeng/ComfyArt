#!/usr/bin/env python3
"""#623 Batch A-video — WaveSpeed seedance-v1-pro-fast i2v hover muted loops for new6 skills.

Model: bytedance/seedance-v1-pro-fast/image-to-video
duration=3, resolution=480p, aspect_ratio=4:3
Never print API keys.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("/workspace/ComfyArt-review-assets/623")
PREP = ROOT / "prep"
OUT = ROOT / "wash" / "videos"
RAW = PREP / "raw"
FRAMES = PREP / "frames"
LEDGER = PREP / "ledger.jsonl"
LEDGER_SUMMARY = PREP / "seedance-fast-ledger.json"
MANIFEST = OUT / "manifest.json"
COVERS = Path("/workspace/594w/review-assets/494/covers-v4")
BASE = (os.environ.get("WAVESPEED_BASE_URL") or "https://api.wavespeed.ai").rstrip("/")
MODEL = "bytedance/seedance-v1-pro-fast/image-to-video"
DURATION = 3
RESOLUTION = "480p"
ASPECT = "4:3"
UNIT_QUOTE = 0.036

SKILLS = [
    "multi-angle",
    "logo-material",
    "meta-ads",
    "mobile-ui",
    "web-product",
    "marketing-campaign",
]

COMMON = (
    "Subtle product-video hover loop for a skill card. Soft camera and lighting drift only. "
    "KEEP composition, subjects, layout, colors, and any UI chrome / typography fully readable "
    "for every frame. No new logos, no watermarks, no Lovart glyphs, no author avatar. "
    "No dramatic morph, no scene rewrite, no Ken Burns fake pan of text, no empty freeze. "
    "Gentle continuous motion that loops cleanly at ~3 seconds."
)

PROMPTS = {
    "multi-angle": (
        f"{COMMON} Four-panel ceramic+wood pour-over dripper product grid on warm grey. "
        "Very gentle studio light drift and soft shadow breathing across all four panels; "
        "tiny micro-parallax on the wooden base grain. Panels stay locked in a 2x2 grid; "
        "product identity unchanged."
    ),
    "logo-material": (
        f"{COMMON} Dark charcoal 2x2 material board of embossed N logo tiles "
        "(brushed metal, glass, matte orange, woven fabric). Soft specular highlight drift "
        "and subtle refraction shimmer on glass; materials stay distinct; tiles stay locked "
        "in place; logo geometry readable."
    ),
    "meta-ads": (
        f"{COMMON} Dark Meta Ads portfolio board for AQUA PEAK sage bottle with three ad "
        "previews (1:1, 4:5, 9:16). Soft light drift across cards; tiny ambient motion "
        "inside lifestyle frames only; all titles, captions, and SHOP chip stay sharp and fixed."
    ),
    "mobile-ui": (
        f"{COMMON} Three Lumen Habit phones on mint desk with leaf and stylus. Soft screen "
        "glow pulse and gentle desk shadow drift; phones stay planted; all UI text, rings, "
        "charts, and buttons stay crisp and readable — no smearing."
    ),
    "web-product": (
        f"{COMMON} Northboard web product mock: landing hero + dashboard window on light grey. "
        "Soft ambient light drift and tiny UI shimmer on blue accents; browser chrome and "
        "all headlines/buttons/dashboard cards stay sharp and fixed."
    ),
    "marketing-campaign": (
        f"{COMMON} YORI LEAF TEA campaign mood board on wood table with matcha props. "
        "Soft natural light drift and tiny leaf/whisk micro-motion; board pins and all "
        "campaign typography stay sharp; hero cup identity preserved."
    ),
}


def load_key() -> str:
    key = (os.environ.get("WAVESPEED_API_KEY") or os.environ.get("WAVE_AI_API_KEY") or "").strip()
    if not key:
        raise SystemExit("WAVESPEED_API_KEY missing")
    return key


def api(method: str, path: str, body: dict | None = None) -> dict:
    key = load_key()
    data = None if body is None else json.dumps(body).encode()
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
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


def balance() -> float:
    r = api("GET", "/api/v3/balance")
    data = r.get("data") if isinstance(r, dict) else None
    if isinstance(data, dict) and "balance" in data:
        return float(data["balance"])
    raise SystemExit(f"balance failed: {str(r)[:300]}")


def ledger_write(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = {k: v for k, v in row.items() if "key" not in k.lower() and "token" not in k.lower()}
    with LEDGER.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def cover_path(skill: str) -> Path:
    png = COVERS / f"{skill}.png"
    webp = COVERS / f"{skill}.webp"
    if png.exists():
        return png
    if webp.exists():
        return webp
    raise FileNotFoundError(skill)


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
        raise RuntimeError(f"upload returned no URL: {str(r)[:400]}")
    return url


def create_i2v(skill: str, image_url: str) -> str:
    body = {
        "prompt": PROMPTS[skill],
        "image": image_url,
        "duration": DURATION,
        "resolution": RESOLUTION,
        "aspect_ratio": ASPECT,
        "camera_fixed": False,
    }
    r = api("POST", f"/api/v3/{MODEL}", body)
    task_id = ((r.get("data") or {}).get("id")) if isinstance(r, dict) else None
    if not task_id:
        ledger_write({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "event": "create_fail",
            "skill": skill,
            "model": MODEL,
            "response": str(r)[:500],
        })
        raise RuntimeError(f"create failed for {skill}: {str(r)[:500]}")
    ledger_write({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event": "create",
        "skill": skill,
        "model": MODEL,
        "taskId": task_id,
        "duration": DURATION,
        "resolution": RESOLUTION,
        "aspect_ratio": ASPECT,
        "unit_quote": UNIT_QUOTE,
        "prompt_chars": len(PROMPTS[skill]),
    })
    return task_id


def poll(task_id: str, timeout_s: int = 600) -> dict:
    t0 = time.time()
    delay = 2.0
    while time.time() - t0 < timeout_s:
        try:
            r = api("GET", f"/api/v3/predictions/{task_id}/result")
        except Exception as e:
            print(f"poll_error {task_id}: {e}", flush=True)
            time.sleep(delay)
            delay = min(delay * 1.4, 12)
            continue
        data = (r.get("data") or {}) if isinstance(r, dict) else {}
        status = data.get("status")
        print(f"poll {task_id} status={status}", flush=True)
        if status == "completed":
            return data
        if status in ("failed", "cancelled", "timeout", "deleted"):
            return data
        time.sleep(delay)
        delay = min(delay * 1.25, 10)
    raise TimeoutError(task_id)


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["curl", "-sS", "-L", "--connect-timeout", "20", "--max-time", "180", "-o", str(dest), url],
        capture_output=True,
        text=True,
    )
    if r.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
        return
    req = urllib.request.Request(url, headers={"User-Agent": "ComfyArt-623-hover/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as f:
        f.write(resp.read())


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_mid(path: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([
        "ffmpeg", "-y", "-ss", "1.5", "-i", str(path),
        "-frames:v", "1", "-q:v", "2", str(dest),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def probe(path: Path) -> dict:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,codec_name:format=duration",
        "-of", "json", str(path),
    ], text=True)
    return json.loads(out)


def run_one(skill: str) -> dict:
    src = cover_path(skill)
    print(f"upload {skill} from {src}", flush=True)
    image_url = upload_image(src)
    ledger_write({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event": "upload",
        "skill": skill,
        "source": str(src),
        "bytes": src.stat().st_size,
        # do not store long-lived secrets; download_url is temporary media
        "image_host": image_url.split("/")[2] if "://" in image_url else "",
    })
    task_id = create_i2v(skill, image_url)
    print(f"created {skill} taskId={task_id}", flush=True)
    data = poll(task_id)
    status = data.get("status")
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event": "complete",
        "skill": skill,
        "taskId": task_id,
        "status": status,
        "model": MODEL,
        "error": (data.get("error") or data.get("failure_reason") or "")[:300],
    }
    if status != "completed":
        ledger_write(row)
        raise RuntimeError(f"task failed {skill}: {row['error'] or status}")
    outputs = [o for o in (data.get("outputs") or []) if isinstance(o, str) and o.startswith("http")]
    if not outputs:
        ledger_write(row)
        raise RuntimeError(f"no outputs for {task_id}")
    raw = RAW / f"{skill}.mp4"
    download(outputs[0], raw)
    dest = OUT / f"{skill}.mp4"
    OUT.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw.read_bytes())
    digest = sha256_file(dest)
    mid = FRAMES / f"{skill}-mid.jpg"
    try:
        extract_mid(dest, mid)
    except Exception as e:
        print(f"frame_extract_warn {skill}: {e}", flush=True)
    info = probe(dest)
    row.update({
        "file": str(dest),
        "bytes": dest.stat().st_size,
        "sha256": digest,
        "resultUrl": outputs[0],
        "unit_quote": UNIT_QUOTE,
        "ffprobe": info,
        "mid_frame": str(mid) if mid.exists() else None,
    })
    ledger_write(row)
    print(f"saved {dest} bytes={dest.stat().st_size}", flush=True)
    return {
        "skill": skill,
        "prediction_id": task_id,
        "url": outputs[0],
        "bytes": dest.stat().st_size,
        "sha256": digest,
        "unit_quote": UNIT_QUOTE,
        "file": dest.name,
    }


def write_manifest(clips: list[dict], billed: float) -> None:
    videos = []
    for c in clips:
        videos.append({
            "skillId": c["skill"],
            "file": c["file"],
            "bytes": c["bytes"],
            "sha256": c["sha256"],
        })
    man = {
        "kind": "skill-list-cover-video",
        "source": "wavespeed-bytedance-seedance-v1-pro-fast-i2v",
        "model": MODEL,
        "note": (
            "Real WaveSpeed seedance-v1-pro-fast i2v clips for Phase1 new6 "
            f"(duration={DURATION}, {RESOLUTION}, {ASPECT}). See prep/seedance-fast-ledger.json."
        ),
        "duration": DURATION,
        "resolution": RESOLUTION,
        "aspect_ratio": ASPECT,
        "billed_usd": billed,
        "count": len(videos),
        "videos": videos,
    }
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["balance", "run", "manifest-only"])
    ap.add_argument("--skills", nargs="*", default=None)
    args = ap.parse_args()
    if args.cmd == "balance":
        print(json.dumps({"balance": balance()}))
        return
    which = args.skills or SKILLS
    for s in which:
        if s not in SKILLS:
            raise SystemExit(f"unknown skill {s}")
    if args.cmd == "manifest-only":
        clips = []
        for s in which:
            p = OUT / f"{s}.mp4"
            if not p.exists():
                raise SystemExit(f"missing {p}")
            clips.append({
                "skill": s,
                "file": p.name,
                "bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            })
        write_manifest(clips, billed=UNIT_QUOTE * len(clips))
        print(json.dumps({"manifest": str(MANIFEST), "count": len(clips)}))
        return

    before = balance()
    print(f"balance_before={before}", flush=True)
    ledger_write({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event": "batch_start",
        "skills": which,
        "model": MODEL,
        "balance_before": before,
        "unit_quote": UNIT_QUOTE,
    })
    clips = []
    failures = []
    for skill in which:
        try:
            clips.append(run_one(skill))
        except Exception as e:
            print(f"FAIL {skill}: {e}", flush=True)
            failures.append({"skill": skill, "error": str(e)[:400]})
            ledger_write({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "event": "fail",
                "skill": skill,
                "error": str(e)[:400],
            })
    after = balance()
    spend = round(before - after, 6)
    summary = {
        "model": MODEL,
        "duration": DURATION,
        "resolution": RESOLUTION,
        "aspect_ratio": ASPECT,
        "budget": round(UNIT_QUOTE * len(which), 3),
        "unit_quote": UNIT_QUOTE,
        "balance_before": before,
        "balance_after": after,
        "spend_actual": spend,
        "spend_est": round(UNIT_QUOTE * len(clips), 3),
        "n_ok": len(clips),
        "n_fail": len(failures),
        "clips": clips,
        "failures": failures,
        "spend_cap_ok": spend <= (UNIT_QUOTE * len(which) + 0.05),
    }
    LEDGER_SUMMARY.write_text(json.dumps(summary, indent=2) + "\n")
    if clips:
        write_manifest(clips, billed=spend if spend > 0 else UNIT_QUOTE * len(clips))
    ledger_write({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event": "batch_end",
        "balance_after": after,
        "spend_actual": spend,
        "n_ok": len(clips),
        "n_fail": len(failures),
    })
    print(json.dumps({
        "balance_before": before,
        "balance_after": after,
        "spend_actual": spend,
        "n_ok": len(clips),
        "n_fail": len(failures),
        "failures": failures,
    }, indent=2))
    if failures:
        sys.exit(2)


if __name__ == "__main__":
    main()
