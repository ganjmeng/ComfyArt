"""#424: memory fallback — charge daily quota only after a real write; fallback stays default off.

Harness: tests/js/proactive_quota_424.ts. No network, no paid API."""
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
    out = tmp_path_factory.mktemp("q424") / "proactive_quota_424.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "proactive_quota_424.ts"},
    )
    run = subprocess.run(["node", str(out)], check=True, capture_output=True, text=True)
    return json.loads(run.stdout)


def test_fallback_default_off():
    """Issue: learnMemory 兜底保持默认关闭 (api/settings.py)."""
    src = (ROOT / "api/settings.py").read_text()
    m = re.search(r'"proactive-memory":\s*(True|False)', src)
    assert m and m.group(1) == "False"


def test_already_wrote_memory_does_not_charge(got):
    """验收：已写过记忆就不扣配额."""
    r = got["already_wrote_no_charge"]
    assert r["allowed"] is False
    assert r["charged"] is False
    assert r["runsAfter"] == 0


def test_fallback_write_charges_once(got):
    r = got["fallback_wrote_charges"]
    assert r["allowed"] is True
    assert r["charged"] is True
    assert r["runsAfter"] == 3  # was 2


def test_fallback_empty_learn_does_not_charge(got):
    r = got["fallback_empty_no_charge"]
    assert r["allowed"] is True
    assert r["charged"] is False
    assert r["runsAfter"] == 2


def test_disabled_or_at_limit_skips(got):
    assert got["disabled_no_run"] == {"allowed": False, "charged": False, "runsAfter": 0}
    assert got["at_limit_no_run"] == {"allowed": False, "charged": False, "runsAfter": 5}
    assert got["allowed_matrix"] == {"wrote": False, "ok": True, "off": False, "full": False}


def test_wiring_charges_after_learnMemory():
    """Source: no take('memory') before learn; charge only when n > 0 after learnMemory."""
    pro = (ROOT / "src/proactive.ts").read_text()
    assert "memoryFallbackAllowed(ex.wrote, s.runs.memory ?? 0, dailyLimit(), enabled('memory'))" in pro
    assert "const n = await learnMemory(ex, e.chat_id, e.message_id)" in pro
    assert "if (n > 0) await withState((s) => { take(s, 'memory') })" in pro
    # Must not take memory quota up-front anymore
    assert "const memory = take(s, 'memory')" not in pro
    assert "from './proactiveQuota'" in pro
