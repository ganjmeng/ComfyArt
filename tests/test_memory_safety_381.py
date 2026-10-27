"""#381 P0 memory data safety — behavior tests of src/memory.ts (real calls on stubbed userdata/localStorage).

Harness: tests/js/memory_safety.ts. No network, no paid API."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
                                reason="needs node + npm install")


def _defaults() -> dict:
    """Read the real server defaults for the two /arti capabilities from api/settings.py."""
    src = (ROOT / "api/settings.py").read_text()
    return {k: re.search(rf'"{k}":\s*(True|False)', src).group(1) == "True" for k in ("proactive-memory", "proactive-skills")}


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m381") / "memory_safety.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "memory_safety.ts"})
    run = subprocess.run(["node", str(out)], check=True, capture_output=True, text=True,
                         env={**os.environ, "SETTINGS": json.dumps(_defaults())})
    return json.loads(run.stdout)


def test_1_empty_open_writes_nothing(got):
    assert got["empty_open"] == {"atom": 0, "file": 0}


def test_1_delete_all_then_refresh_three_times_stays_zero(got):
    assert got["delete_all_refresh3"] == [[0, 0, 0]] * 3


def test_1_last_delete_is_not_resurrected_from_local_storage(got):
    assert got["no_local_resurrection"] == {"atom": 0, "file": 0}


def test_2_demo_cleanup_exact_only_verbatim_and_run_once(got):
    m = got["migration"]
    assert m["kept"] == ["s6", "u1", "u2", "u3"]  # 5 exact seeds gone; one-char-edited seed is the user's
    assert m["verbatim"] is True  # every original field kept as-is
    assert m["stamped"] is True  # plus owner_id / workspace_id local defaults
    assert m["editedKept"] is True
    assert m["logAfterFirst"] == 1 and m["logAfterRestarts"] == 1
    assert "5" in m["logText"]
    assert m["userSeedSurvives"] is True  # cleanup never reruns over the user's own later entries


def test_3_delete_by_id_removes_only_that(got):
    assert got["delete_by_id"] == ["b", "c"]


def test_3_text_match_is_exact_not_substring(got):
    assert got["substring_not_matched"] == ["a"]


def test_3_multi_match_writes_nothing_and_returns_candidates(got):
    m = got["multi_match"]
    assert m["unchanged"] is True
    assert m["forgetCandidates"] == ["a", "b"] and m["correctCandidates"] == ["a", "b"]
    assert m["chooser"] == 2


def test_3_correct_with_empty_old_is_rejected(got):
    assert got["correct_empty_old"] == {"unchanged": True, "changed": 0, "rejected": True}


def test_4_concurrent_proactive_and_ui_writes_equal_serial(got):
    c = got["concurrency"]
    assert c == {"equal": True, "serial": 100, "concurrent": 100, "lost": 0}


def test_4_stale_write_from_another_writer_is_retried_not_lost(got):
    # another tab / the agent writes between our read and our write: the store rejects (rev), the step re-runs
    assert got["external_writer"] == ["from-agent", "from-tab2", "from-ui"]


def test_5_deleted_memory_absent_from_next_prompt(got):
    assert got["prompt_after_delete"] == {"before": True, "after": False, "keeps": True}


def test_arti_switches_mirror_api_settings(got):
    d = _defaults()
    assert got["arti_caps"]["memory"] is (d["proactive-memory"] is True) is False
    assert got["arti_caps"]["skills"] is (d["proactive-skills"] is True) is False
    assert got["arti_caps"]["memOn"] is True
