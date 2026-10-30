"""#462: description round-trip through the real saveSkill → loadSkills path. Harness: tests/js/skill_desc_462.ts (in-memory user files, no paid API)."""
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
    out = tmp_path_factory.mktemp("m462") / "skill_desc_462.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "skill_desc_462.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_description_with_colons_quotes_newlines_round_trips(got: dict) -> None:
    # newlines fold to spaces (frontmatter is one line); everything else identical
    assert got["tricky"] == got["trickyExpected"]
    assert got["direct"] == got["trickyExpected"]
    assert got["instructions"] == "Do: it"


def test_description_fully_quoted_keeps_its_quotes(got: dict) -> None:
    assert got["quoted"] == '"wrapped in quotes"'


def test_empty_description_writes_no_key(got: dict) -> None:
    assert got["emptyHasDescKey"] is False
    assert "description:" not in got["emptyMd"]
