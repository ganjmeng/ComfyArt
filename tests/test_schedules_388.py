"""#388: schedule unattended over-quote skip + cross-tab lock.

Harness: tests/js/schedules388/main.ts (mock send/ask; no paid calls).
"""
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
    out = tmp_path_factory.mktemp("s388") / "schedules388.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/schedules388/rolldown.config.mjs"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "main.ts"},
    )
    run = subprocess.run(["node", str(out)], check=True, capture_output=True, text=True, timeout=30)
    return json.loads(run.stdout)


def test_ac1_over_quote_skipped_no_charge(got):
    """AC1: plan_quote over → skipped; 0 paid; run_mode=unattended."""
    a = got["ac1_skip"]
    assert a["handled"] is True
    assert a["runMode"] == "unattended"
    assert a["paidCalls"] == 0
    assert a["pendingLeft"] == 0
    # Source: run() must pass unattended
    src = (ROOT / "src/schedules.ts").read_text()
    assert "runMode: 'unattended'" in src
    assert "registerSchedulePending" in src


def test_ac2_exactly_one_schedule_notice(got):
    """AC2: exactly 1 kind=schedule notice with 「已跳过」 + reason."""
    a = got["ac1_skip"]
    assert a["noticeCount"] == 1
    assert a["kind"] == "schedule"
    assert a["hasSkipped"] is True
    assert "已跳过" in a["title"]
    assert "未扣费" in (a["body"] or "") or "报价" in (a["body"] or "")
    assert a["owner"] == "local-owner"
    assert a["workspace"] == "local-workspace"
    # abort suppresses notice
    assert got["abort"]["handled"] is True
    assert got["abort"]["notices"] == 0


def test_ac3_last_run_advanced(got):
    """AC3: lastRun updated; repeat stays enabled; nextRun advances."""
    a = got["ac3_lastRun"]
    assert a["claimedId"] == "s1"
    assert a["lastRunIsNow"] is True
    assert a["enabled"] is True
    assert a["nextAfter"] is not None
    assert a["nextAfter"] > a["lastRun"]


def test_ac4_dual_tab_lock_main_red_branch_green(got):
    """AC4: locked claim once (branch green); unlocked double (main red)."""
    a = got["ac4_dual"]
    assert a["lockWinsOnce"] is True and a["lockedClaims"] == 1
    assert a["unlockedDouble"] is True and a["unlockedClaims"] == 2
    src = (ROOT / "src/schedules.ts").read_text()
    assert "comfyart-schedules" in src
    assert "scheduleLocks" in src
    assert "claimDueScheduleUnlocked" in src  # main-red seam


def test_ac5_under_threshold_started(got):
    """AC5: success path → started notice, not skip."""
    a = got["ac5_ok"]
    assert a["kind"] == "schedule"
    assert a["isStarted"] is True
    assert a["notSkip"] is True


def test_stop_helper_and_i18n(got):
    s = got["stop_helper"]
    assert s["budget"] is True and s["notApproved"] is True and s["other"] is False
    i = got["i18n"]
    assert "已跳过" in i["zhTitle"] and "未扣费" in i["zhReason"]
    assert "skipped" in i["enTitle"].lower() and "not charged" in i["enReason"].lower()


def test_mutation_no_lock_would_fail():
    """Must-red: removing lock → AC4 unlocked path is the red proof (already in got)."""
    src = (ROOT / "src/schedules.ts").read_text()
    assert "if (scheduleLocks?.request)" in src


def test_mutation_skip_requires_notice():
    """Must-red: skip without notify would fail AC2 — source always notify on skip."""
    src = (ROOT / "src/schedulePending.ts").read_text()
    assert "schedules.skippedOverQuote" in src
    assert "void notify(" in src


def test_arti_shows_schedule_cards():
    """ArtiMascot surfaces unread schedule notices as cards (#404/#474 lesson)."""
    src = (ROOT / "src/ui/ArtiMascot.tsx").read_text()
    assert "arti-schedule-card" in src
    assert "kind === 'schedule'" in src
    css = (ROOT / "src/styles/shell.css").read_text()
    assert "arti-notify__card-body" in css


def test_api_accepts_turn_run_mode():
    """Send endpoint accepts interactive|unattended (distinct from chat auto|ask)."""
    src = (ROOT / "api/bot.py").read_text()
    assert "interactive" in src and "unattended" in src
    assert 'run_mode must be \'interactive\' or \'unattended\'' in src or 'interactive", "unattended"' in src
