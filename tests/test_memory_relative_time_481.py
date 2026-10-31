"""#481 memory dialog header time is relative, per the redacted Lovart capture
(430/lovart-css/devtools_chat_rows_zh.png: 「更新于5分钟前」): 「更新于{N}小时前」, just updated = 「更新于刚刚」.
Import-from-file, the three tabs and the in-place modal (no navigation) stay."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLG = (ROOT / "src/ui/MemoryDialog.tsx").read_text()
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


def test_ago_buckets_are_relative() -> None:
    body = DLG[DLG.index("function ago("):DLG.index("function MemorySkeleton")]
    assert "Date.now() - time" in body
    for k in KEYS[1:]:
        assert f"t('memoryDialog.{k}'" in body
    assert "toLocaleString" not in body
    assert "t('memoryDialog.updatedAt', ago(latest))" in DLG


def test_existing_features_kept_481() -> None:
    assert "t('memoryDialog.importFromFile')" in DLG
    assert "setTab('log')" in DLG and "setTab('abilities')" in DLG
    assert "navigate(" not in DLG and "location.href" not in DLG
