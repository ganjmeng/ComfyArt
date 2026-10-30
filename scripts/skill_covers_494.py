"""#494-1 list covers: cover:true PNG per skill (review-assets 3c3edaa 494/covers) -> 462x346 webp in public/skills/<id>/cover.webp.

Pinned encoder: Pillow==13.0.0 (libwebp it bundles), fixed params below. Writes public/skills/covers.json with the source
PNG sha256 (checked against the source manifest) and the output webp sha256.
Usage: python3 scripts/skill_covers_494.py [/path/to/repo-with-review-assets-objects]
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import PIL
from PIL import Image

PILLOW = "13.0.0"
SRC_COMMIT = "3c3edaaf21991b0c9c0caf2366a4e47d6139efc1"
SRC_DIR = "494/covers"
SIZE = (462, 346)
PARAMS = {"format": "WEBP", "quality": 82, "method": 6, "exact": False}
OUT = Path(__file__).resolve().parents[1] / "public/skills"


def show(repo: str, path: str) -> bytes:
    return subprocess.run(["git", "-C", repo, "show", f"{SRC_COMMIT}:{path}"], check=True, capture_output=True).stdout


def main() -> None:
    assert PIL.__version__ == PILLOW, f"need Pillow=={PILLOW}, got {PIL.__version__}"
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    manifest = json.loads(show(repo, f"{SRC_DIR}/manifest.json"))
    covers = {}
    for item in manifest["images"]:
        if not item.get("cover"):
            continue
        sid = item["skill_id"]
        png = show(repo, f"{SRC_DIR}/{sid}/{item['n']}.png")
        src_sha = hashlib.sha256(png).hexdigest()
        assert src_sha == item["sha256"], f"{sid}: source sha mismatch"
        img = Image.open(io.BytesIO(png)).convert("RGB").resize(SIZE, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, **PARAMS)
        (OUT / sid).mkdir(parents=True, exist_ok=True)
        (OUT / sid / "cover.webp").write_bytes(buf.getvalue())
        covers[sid] = {"file": f"skills/{sid}/cover.webp", "source": f"{SRC_DIR}/{sid}/{item['n']}.png",
                       "source_sha256": src_sha, "sha256": hashlib.sha256(buf.getvalue()).hexdigest()}
    out = {"source_commit": SRC_COMMIT, "encoder": f"Pillow=={PILLOW}", "size": list(SIZE), "params": PARAMS, "covers": covers}
    (OUT / "covers.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"{len(covers)} covers")


if __name__ == "__main__":
    main()
