"""#389: a shape both selected and @-mentioned shows one chip. Harness: tests/js/ref_dedupe_389.ts (pure, no paid API)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = (ROOT / "src/ui/Composer.tsx").read_text()

pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m389") / "ref_dedupe_389.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "ref_dedupe_389.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_ac1_ac2_selected_and_mentioned_once(got: dict) -> None:
    assert got["ac1"] == ["A"] and got["ac2"] == ["A"] and got["ac2b"] == ["A"]


def test_ac3_order_stable(got: dict) -> None:
    assert got["ac3"] == ["A", "B"]


def test_ac4_remove_clears_both_sources(got: dict) -> None:
    assert got["ac4"] == []


def test_ac5_dedupe_by_id_not_name(got: dict) -> None:
    assert got["ac5"] == ["shape:1", "shape:2"]


def test_composer_uses_helpers() -> None:
    assert "mergeRefIds(" in COMPOSER and "removeRefId(" in COMPOSER
