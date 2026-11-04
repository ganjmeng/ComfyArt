"""#705 P0 — skill read with an empty id: explicit non-retryable error (real src/skills.ts via a node harness),
and the agent loop guards (non-retryable stop, P1 same-tool >3 stop). No LLM, no WaveSpeed."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

from ComfyArt.bot.run_budget import SUB_REASONS, ProgressTracker, StepObservation, StopReason

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(not (ROOT / "node_modules/.bin/rolldown").exists() or not shutil.which("node"),
                                reason="needs node + npm install")


@lru_cache(maxsize=1)
def report() -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"skillid705-{os.getpid()}.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/skillid705/rolldown.config.mjs"], cwd=ROOT,
                   check=True, capture_output=True, env={**os.environ, "OUT": str(out)})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True, timeout=60).stdout)


@needs_node
@pytest.mark.parametrize("lang", ["en", "zh"])
def test_skill_empty_id_is_explicit_and_non_retryable(lang) -> None:
    r = report()
    assert r["marker"] == "[non-retryable]"
    for case in ("empty", "emptyId", "blankName"):
        err = r[lang][case]["error"]
        assert err.startswith("[non-retryable] skill read needs a non-empty id or name"), err
        assert "unknown skill undefined" not in err


@needs_node
@pytest.mark.parametrize("lang", ["en", "zh"])
def test_skill_linkedin_banner_registered_and_every_builtin_reads_by_id_and_name(lang) -> None:
    r = report()[lang]
    assert r["inList"] is True
    assert r["badReads"] == {}
    # (b) the registry error lists every skill, linkedin-banner included (it sits near the end, ~char 1800)
    assert "(linkedin-banner)" in r["unknownName"]["error"]
    assert "[non-retryable]" not in r["unknownName"]["error"]  # a wrong name is still retryable (call list)


def test_same_sub_reasons_are_registered() -> None:
    assert {"same_tool", "non_retryable"} <= SUB_REASONS[StopReason.STUCK]


def _obs(tool, i, result=None):
    return [StepObservation(tool=tool, args_key=f"{tool}{i}", result=result if result is not None else f"text {i}")]


def test_tracker_same_tool_more_than_3_in_a_row() -> None:
    t = ProgressTracker()
    assert [t.observe(i, _obs("skill", i)) for i in range(1, 5)] == [None, None, None, "same_tool"]


def test_tracker_same_tool_reset_by_artifacts_other_tool_or_parallel_batch() -> None:
    t = ProgressTracker()
    for i in range(1, 9):  # each step lands a new shape: real progress, never same_tool
        assert t.observe(i, _obs("add_text", i, json.dumps({"id": f"shape:{i}"}))) is None
    t = ProgressTracker()
    out = [t.observe(i, _obs(n, i)) for i, n in enumerate(["skill"] * 3 + ["add_text"] + ["skill"] * 3, 1)]
    assert out == [None] * 7
    t = ProgressTracker()  # one step with 4 parallel generate_image calls counts once
    batch = [StepObservation("generate_image", f"g{k}", json.dumps({"id": f"job:{k}"})) for k in range(4)]
    assert t.observe(1, batch) is None
