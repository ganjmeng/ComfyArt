"""#481 memory dialog header time is relative, per the redacted Lovart capture
(430/lovart-css/devtools_chat_rows_zh.png: 「更新于5分钟前」): 「更新于{N}小时前」, just updated = 「更新于刚刚」.
Import-from-file, the three tabs and the in-place modal (no navigation) stay.

Also: behavioral ago() harness (tests/js/ago_481.ts) covering zh/en boundaries so mutations that
hardcode 「刚刚」, break hour buckets, or change en copy go red.
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
DLG = (ROOT / "src/ui/MemoryDialog.tsx").read_text()
AGO_SRC = (ROOT / "src/memoryRelativeTime.ts").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())
KEYS = ("updatedAt", "justNow", "minutesAgo", "hoursAgo", "daysAgo")


def _fmt(tpl: str, *a: object) -> str:
    return re.sub(r"\{(\d+)\}", lambda m: str(a[int(m.group(1))]), tpl)


def test_zh_copy_matches_lovart() -> None:
    z = lambda k: ZH[f"memoryDialog.{k}"]
    assert _fmt(z("updatedAt"), _fmt(z("hoursAgo"), 14)) == "更新于14小时前"
    assert _fmt(z("updatedAt"), _fmt(z("minutesAgo"), 5)) == "更新于5分钟前"
    assert _fmt(z("updatedAt"), z("justNow")) == "更新于刚刚"
    assert "此刻" not in z("justNow")


def test_keys_in_both_locales() -> None:
    for k in KEYS:
        assert ZH.get(f"memoryDialog.{k}") and EN.get(f"memoryDialog.{k}")


def test_en_copy_locked() -> None:
    """Lock shipping en strings (Lovart en not verified yet; keep main wording)."""
    assert EN["memoryDialog.updatedAt"] == "Updated {0}"
    assert EN["memoryDialog.justNow"] == "just now"
    assert EN["memoryDialog.minutesAgo"] == "{0} minutes ago"
    assert EN["memoryDialog.hoursAgo"] == "{0} h ago"
    assert EN["memoryDialog.daysAgo"] == "{0} d ago"
    assert EN["memoryDialog.justNow"] != "now"
    assert "此刻" not in EN["memoryDialog.justNow"]


def test_ago_buckets_are_relative() -> None:
    body = AGO_SRC
    assert "export function ago(" in body
    assert "(now - time) / 60000" in body or "(Date.now() - time) / 60000" in body
    for k in KEYS[1:]:
        assert f"t('memoryDialog.{k}'" in body
    assert "toLocaleString" not in body
    assert "from '../memoryRelativeTime'" in DLG
    assert "t('memoryDialog.updatedAt', ago(latest))" in DLG
    # invalid / missing time: span is gated on truthy latest
    assert "latest && !loading" in DLG


def test_existing_features_kept_481() -> None:
    assert "t('memoryDialog.importFromFile')" in DLG
    assert "setTab('log')" in DLG and "setTab('abilities')" in DLG
    assert "navigate(" not in DLG and "location.href" not in DLG


@pytest.fixture(scope="module")
def ago_got(tmp_path_factory) -> dict:
    if not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"):
        pytest.skip("needs node + npm install")
    out = tmp_path_factory.mktemp("ago481") / "ago_481.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "ago_481.ts"},
    )
    run = subprocess.run(["node", str(out)], check=True, capture_output=True, text=True)
    return json.loads(run.stdout)


def test_ago_behavior_zh_boundaries(ago_got: dict) -> None:
    z = ago_got["zh"]
    assert z["justNow0"] == "刚刚"
    assert z["justNow30s"] == "刚刚"
    assert z["justNowFuture"] == "刚刚"
    assert z["m59"] == "59分钟前"
    assert z["h1"] == "1小时前"
    assert z["h23_59"] == "23小时前"
    assert z["d1"] == "1天前"
    assert z["d2"] == "2天前"
    assert z["m5"] == "5分钟前"
    assert z["h14"] == "14小时前"
    assert ago_got["composed"]["zhJust"] == "更新于刚刚"
    assert ago_got["composed"]["zh14h"] == "更新于14小时前"
    assert ago_got["composed"]["zh5m"] == "更新于5分钟前"
    assert "此刻" not in z["justNow0"]


def test_ago_behavior_en_boundaries(ago_got: dict) -> None:
    e = ago_got["en"]
    assert e["justNow0"] == "just now"
    assert e["justNow30s"] == "just now"
    assert e["justNowFuture"] == "just now"
    assert e["m59"] == "59 minutes ago"
    assert e["h1"] == "1 h ago"
    assert e["h23_59"] == "23 h ago"
    assert e["d1"] == "1 d ago"
    assert e["d2"] == "2 d ago"
    assert e["m5"] == "5 minutes ago"
    assert e["h14"] == "14 h ago"
    assert ago_got["composed"]["enJust"] == "Updated just now"
    assert ago_got["composed"]["en14h"] == "Updated 14 h ago"
    assert ago_got["composed"]["en5m"] == "Updated 5 minutes ago"
    # lock en keys as returned by t()
    assert ago_got["enKeys"]["justNow"] == "just now"
    assert ago_got["enKeys"]["hoursAgo"] == "{0} h ago"
    assert ago_got["enKeys"]["justNow"] != "now"


def test_ago_mutations_would_fail(ago_got: dict) -> None:
    """The three HOLD mutations must be distinguishable from the real buckets."""
    m = ago_got["mutationWouldCatch"]
    assert m["zhAllJustNow"] is True
    assert m["enAllJustNow"] is True
    assert m["zhHourBoundaryDistinct"] is True
    assert m["enHourBoundaryDistinct"] is True
