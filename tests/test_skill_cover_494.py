"""#494-1: cover fallback (cover → own images[0] → grey + icon) and data-driven chips through the real src/skills.ts.
Harness: tests/js/skill_cover_494.ts (stubs from tests/js/rolldown.config.mjs, no network, $0)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m494") / "skill_cover_494.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "skill_cover_494.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_no_image_falls_back_to_icon(got):
    assert got["noImage"] is None and got["custom"] is None  # null → grey background + Lucide icon


def test_own_image_used(got):
    assert got["ownImage"] == {"src": "input/r.png", "own": "userdata"}


def test_builtin_covers(got):
    covers = got["builtinCovers"]
    assert covers.pop("custom-workflow") is None
    tip = "48362260e70c8d60a1a755a1b31d0f4ae5c0ab67"
    assert covers == {
        k: f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{tip}/494/wash/covers/{k}.webp"
        for k in covers
    } and len(covers) == 10


def test_chips_from_data(got):
    assert got["chips"] == ["forYou", "ecommerce", "branding", "social", "ads"]  # 网站 empty → hidden
    by = got["byChip"]
    assert len(by["forYou"]) == 11
    assert by == {"forYou": by["forYou"], "ecommerce": ["packaging", "product"], "branding": ["brand"],
                  "social": ["social", "thumbnail"], "ads": ["poster", "banner", "motion"]}
    for sid in ("character", "interior", "custom-workflow"):
        assert all(sid not in v for k, v in by.items() if k != "forYou")
