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


def test_el1_offline_write_fails_loudly_and_nothing_looks_saved(got):
    o = got["offline_write"]
    assert o["results"] == ["MemoryWriteError"] * 3
    assert o["atom"] == ["A"] and o["file"] == ["A"]  # not added, not deleted, not edited
    assert o["toast"] == "Save failed. Please retry." and o["kind"] == "error"


def test_el1_http_store_resends_once_with_same_op_id_then_fails(got):
    s = got["server_offline"]
    assert s["err"] == "MemoryWriteError" and s["attempts"] == 2 and s["sameOp"] is True
    assert s["retriedRev"] == 1  # a POST that committed before the network dropped is answered by the op_id replay


def test_el2_read_error_shows_error_state_never_local_or_deleted(got):
    r = got["read_error"]
    assert r["during"] == {"atom": 0, "error": True, "returned": 0}
    assert r["after"] == ["b"] and r["errorAfter"] is False  # deleted a never comes back


def test_el2_http_read_500_throws(got):
    assert got["server_read_500"] == "MemoryReadError"


def test_el3_conflict_reapplies_on_fresh_state_not_stale_snapshot(got):
    c = got["conflict_replay"]
    assert c["file"] == ["A-edit"] and c["atom"] == ["A-edit"]  # b stays deleted (the stale snapshot was not resent)
    assert c["distinctOps"] == 2  # the re-applied write is a new op


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
    # in-tab writes are queued: they never race (and 409) each other; cross-tab races are the rev check's job
    assert c == {"equal": True, "serial": 100, "concurrent": 100, "lost": 0, "selfConflicts": 0}


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


# ---- EL#1-3 against the REAL client store (serverMemoryStore → api()); red on 83393be ----
def test_el1_real_store_offline_write_fails_and_nothing_is_lost(got):
    r = got["real_offline"]
    assert r["res"] == "MemoryWriteError", r            # 83393be: mirror() → resolved
    assert r["atomDuring"] == ["A"] and r["toast"] in ("保存失败，请重试", "Save failed. Please retry."), r
    assert r["server"] == ["A"] and r["posts"] == 2, r   # one same-op_id resend, nothing silently 'saved'


def test_el2_real_store_read_error_no_mirror_no_resurrection_no_409_loop(got):
    r = got["real_read_error"]
    assert r["during"] == {"atom": [], "error": True}, r  # 83393be: mirror → ['deleted-elsewhere', 'B']
    assert r["after"] == ["B", "C"] and r["write"] == "ok" and r["server"] == ["B", "C"], r
    assert r["conflicts409"] == 0, r


def test_el3_real_store_conflict_rereads_and_never_resends_stale_body(got):
    r = got["real_conflict"]
    assert r["write"] == "ok" and r["server"] == ["A-edit"], r   # b stays deleted
    assert r["posts"] == 2 and r["distinctBodies"] == 2 and r["revs"] == [7, 8], r  # 83393be: 6 identical posts base_rev 0
    assert r["getsAfterConflict"] == 3, r  # load + attempt read + fresh re-read after the 409
