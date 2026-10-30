"""#384 P0-4 canvas snapshot per turn + shared #382 budget — behavior tests (mock only).

Harness: tests/js/canvas_snapshot_384.ts. No network, no paid API."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m384") / "canvas_snapshot_384.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "canvas_snapshot_384.ts"},
    )
    run = subprocess.run(["node", str(out)], check=True, capture_output=True, text=True)
    return json.loads(run.stdout)


def test_constants_match_policy(got):
    policy = json.loads((ROOT / "api/memory_policy.json").read_text())
    c = got["constants"]
    assert c["MAX_SNAPSHOT_NODES"] == policy["max_snapshot_nodes"] == 40
    assert c["MAX_SNAPSHOT_TOKENS"] == policy["max_snapshot_tokens"] == 1500
    assert c["EMPTY_SNAPSHOT_TEXT"] == "空画布"


def test_ac1_five_nodes_selection_models(got):
    o = got["ac1_five_nodes"]
    assert o["included"] == 5
    assert o["omitted"] == 0
    assert o["typeCounts"] == {"image": 3, "text": 1, "frame": 1}
    assert o["hasModels"] is True
    assert o["hasTypes"] is True
    assert o["selectionExact"] is True
    assert o["selection"] == ["img:1", "frm:1"] or set(o["selection"]) == {"img:1", "frm:1"}


def test_mut_ac1_selection_all_nodes_red(got):
    """Mutation: selection = all node ids → AC1 red."""
    m = got["ac1_five_nodes"]["mutSelectionAll"]
    assert m["red"] is True
    assert m["selLen"] == 5


def test_ac2_every_turn_fresh(got):
    o = got["ac2_every_turn"]
    assert o["everyTurnAttached"] is True
    assert o["counts"] == [5, 4, 4]
    assert o["turn3Has4"] is True


def test_mut_ac2_first_turn_only_red(got):
    """Mutation: attach only on first turn → AC2 red."""
    m = got["ac2_every_turn"]["mutFirstOnly"]
    assert m["red"] is True
    assert m["attached"] == [True, False, False]


def test_ac3_truncates_large_canvas(got):
    o = got["ac3_trunc"]
    assert o["underCap"] is True
    assert o["included"] <= got["constants"]["MAX_SNAPSHOT_NODES"]
    assert o["omitted"] == 300 - o["included"]
    assert o["hasMore"] is True
    assert o["tokensOk"] is True
    assert o["tokens"] <= got["constants"]["MAX_SNAPSHOT_TOKENS"]


def test_mut_ac3_no_cap_red(got):
    """Mutation: drop node/token caps → AC3 red."""
    m = got["ac3_trunc"]["mutNoCap"]
    assert m["red"] is True


def test_ac4_snapshot_in_shared_budget(got):
    o = got["ac4_budget"]
    assert o["snapshotCounted"] is True
    assert o["withSnap"]["snapshot"] > 0
    assert o["packed"]["fits"] is True
    assert o["packed"]["orderOk"] is True
    assert o["packed"]["snapshotKeptOrTrimmedLast"] is True
    # history should be trimmed before memory/snapshot when over budget
    trimmed = o["packed"]["trimmed"]
    assert "history" in trimmed or o["withSnap"]["fits"]


def test_mut_ac4_snapshot_not_counted_red(got):
    """Mutation: budget ignores snapshot → AC4 red (undercount)."""
    m = got["ac4_budget"]["mutNotCounted"]
    assert m["red"] is True
    assert m["undercount"] is True


def test_ac5_empty_canvas(got):
    o = got["ac5_empty"]
    assert o["ok"] is True
    assert o["text"] == "空画布"
    assert o["empty"] is True
