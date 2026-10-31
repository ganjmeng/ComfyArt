"""#546 sidebar width = Lovart @1280 (expanded 240 / inner 216 px12, main px56, home column 928). Static, $0."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME_CSS = (ROOT / "src/styles/home.css").read_text()
BASE_CSS = (ROOT / "src/styles/base.css").read_text()


def _var(name: str) -> int:
    m = re.search(rf"{re.escape(name)}:\s*(\d+)px", BASE_CSS)
    assert m, name
    return int(m.group(1))


def test_tokens_match_lovart() -> None:
    assert _var("--ca-rail-w-expanded") == 240
    assert _var("--ca-rail-px-expanded") == 12
    assert _var("--ca-rail-w-expanded") - 2 * _var("--ca-rail-px-expanded") == 216
    assert _var("--ca-home-main-px") == 56
    assert _var("--ca-rail-w-collapsed") > 0


def test_home_column_math() -> None:
    w, px = _var("--ca-rail-w-expanded"), _var("--ca-home-main-px")
    assert 1280 - w - 2 * px == 928
    assert 1440 - w - 2 * px == 1088


def test_rules_use_tokens_in_place() -> None:
    assert "width: var(--ca-rail-w-collapsed)" in HOME_CSS
    assert "width: var(--ca-rail-w-expanded)" in HOME_CSS
    assert "padding: 96px var(--ca-home-main-px) 64px" in HOME_CSS
    assert "width: 160px" not in HOME_CSS
    assert not (ROOT / "src/home/Sidebar.tsx").exists()
