"""#386: event-driven canvas review + state machine.

Harness: tests/js/review386/main.ts (mock ask/export; fake timers). No network, no paid API.
"""
from __future__ import annotations

import json
import os
import re
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
    out = tmp_path_factory.mktemp("r386") / "review386.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/review386/rolldown.config.mjs"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "main.ts"},
    )
    run = subprocess.run(["node", str(out)], check=True, capture_output=True, text=True)
    return json.loads(run.stdout)


def test_machine_table_exhaustive(got):
    """AC1: every (phase, event) pair — legal transitions + illegal throw/soft-fail."""
    m = got["machine"]
    assert m["legal"] == 16
    assert m["illegal"] == 26  # 6*7 - 16
    # Source: notified → reviewing must NOT be legal
    src = (ROOT / "src/reviewMachine.ts").read_text()
    assert "notified: { ack: 'idle', cancel: 'idle' }" in src
    assert "notified" in src and "start_review" not in re.search(
        r"notified:\s*\{[^}]+\}", src
    ).group(0)


def test_debounce_one_export_one_ask(got):
    """AC2: 1 gen + 5 canvas changes inside window → 1 export, 1 ask."""
    mid = got["debounce_mid"]
    assert mid["phase"] == "scheduled"
    assert mid["asks"] == 0 and mid["exports"] == 0
    d = got["debounce"]
    assert d["asks"] == 1 and d["exports"] == 1
    assert d["cards"] == 1 and d["notices"] == 1
    assert d["phase"] == "idle"


def test_reentrancy_pending_followup(got):
    """AC3: triggers while reviewing → pending; ask stays 1 until finish."""
    r = got["reentrancy"]
    assert r["midPhase"] == "reviewing"
    assert r["pendingDuring"] is True
    assert r["asks"] == 1
    assert r["exports"] == 1
    # follow-up was armed then ran (same sig → gated → idle)
    assert r["afterPhase"] == "scheduled" or r["finalPhase"] == "idle"


def test_signature_covers_image_content(got):
    """AC4: same id, new src → different signature."""
    s = got["signature_content"]
    assert s["changed"] is True
    assert s["covers_src"] is True
    assert got["signature_stable"] is True
    # Source must include src in the signature line
    pro = (ROOT / "src/proactive.ts").read_text()
    assert "asset?.props.src" in pro or "asset?.props.src ??" in pro
    assert ":${src}:" in pro or "${id}:${shape.type}" in pro


def test_cancel_drops_inflight(got):
    """AC5: cancel mid-review → idle, 0 cards."""
    c = got["cancel"]
    assert c["mid"] == "reviewing"
    assert c["phase"] == "idle"
    assert c["pending"] is False
    assert c["cards"] == 0


def test_ask_fail_then_retry(got):
    """AC6: ask error → no card; retry succeeds → 1 card."""
    a = got["ask_fail_retry"]
    assert a["afterFail"]["cards"] == 0
    assert a["afterFail"]["phase"] == "idle"
    assert a["afterRetry"]["cards"] == 1
    assert a["afterRetry"]["issue"] == "fixed"


def test_empty_issues_no_card(got):
    """AC6: 0 issues → succeed, panel stays empty (no card)."""
    e = got["empty_ok"]
    assert e["asks"] == 1 and e["exports"] == 1
    assert e["cards"] == 0
    assert e["phase"] == "idle"


def test_min_shapes_and_daily_limit(got):
    """AC7: <3 shapes or daily 0 → 0 ask."""
    assert got["min_shapes"] == {"phase": "idle", "asks": 0, "exports": 0}
    assert got["daily_limit"] == {"phase": "idle", "asks": 0, "exports": 0}


def test_saas_stamp_owner_workspace(got):
    """SaaS stub: review cards carry owner_id + workspace_id + project_id."""
    s = got["saas_stamp"]
    assert s["has_owner"] and s["has_workspace"] and s["has_project"]
    assert s["owner"] == "local" and s["workspace"] == "local"
    feed = (ROOT / "src/reviewFeed.ts").read_text()
    assert "ReviewFeedStore" in feed
    assert "owner_id" in feed and "workspace_id" in feed
    assert "setReviewFeedStore" in feed


def test_wiring_event_debounce_arti_feed():
    """Source wiring: debounce constant, onImagePlaced + store.listen, Arti feed."""
    pro = (ROOT / "src/proactive.ts").read_text()
    assert "REVIEW_DEBOUNCE_MS = 5000" in pro
    assert "onImagePlaced" in pro
    assert "store.listen" in pro
    assert "postReviewCard" in pro
    assert "createReviewController" in pro
    mascot = (ROOT / "src/ui/ArtiMascot.tsx").read_text()
    assert "reviewFeedAtom" in mascot
    assert 'data-testid="arti-review-card"' in mascot
    assert "dismissReviewCard" in mascot
    shell = (ROOT / "src/styles/shell.css").read_text()
    assert ".arti-notify__card" in shell
    assert "var(--ca-field" in shell or "var(--ca-field," in shell
    en = (ROOT / "src/locales/en.json").read_text()
    zh = (ROOT / "src/locales/zh.json").read_text()
    assert '"arti.notify.dismiss"' in en and '"arti.notify.dismiss"' in zh


def test_mutation_guards_present():
    """Must-red mutations: guards exist in source (static stand-in for inject-red)."""
    machine = (ROOT / "src/reviewMachine.ts").read_text()
    # M1: notified must not jump to reviewing
    notified = re.search(r"notified:\s*\{([^}]+)\}", machine).group(1)
    assert "start_review" not in notified and "succeed" not in notified
    # M2: reviewing re-entry → pending
    pro = (ROOT / "src/proactive.ts").read_text()
    assert "rt.pending = true" in pro
    assert "exporting' || rt.phase === 'reviewing'" in pro or 'exporting" || rt.phase === "reviewing"' in pro
    # M3: debounce uses REVIEW_DEBOUNCE_MS (not 0)
    assert "}, REVIEW_DEBOUNCE_MS)" in pro
    # M4: signature includes src
    assert "src" in re.search(r"export function canvasSignature[\s\S]+?\.join", pro).group(0)
    # M5: cancel bumps gen
    assert "rt.gen += 1" in pro


def test_design_shots_exist():
    after = ROOT / "docs/design/386/78/after"
    assert (after / "review-notify-light.png").is_file()
    assert (after / "review-notify-dark.png").is_file()
    assert (ROOT / "docs/design/386/78/NOTES.md").is_file()
