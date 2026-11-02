"""#607 soft — desktop rail default expanded; collapsed does not render 最近项目. Static, $0."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME_APP = (ROOT / "src/home/HomeApp.tsx").read_text(encoding="utf-8")
HOME_CSS = (ROOT / "src/styles/home.css").read_text(encoding="utf-8")
ZH = (ROOT / "src/locales/zh.json").read_text(encoding="utf-8")
EN = (ROOT / "src/locales/en.json").read_text(encoding="utf-8")


def test_desktop_default_expanded_only_one_persists_collapsed() -> None:
    # missing / '0' → expanded; only explicit '1' → collapsed
    assert "readLocal(RAIL_COLLAPSE_KEY) === '1'" in HOME_APP
    assert "readLocal(RAIL_COLLAPSE_KEY) !== '0'" not in HOME_APP
    assert "writeLocal(RAIL_COLLAPSE_KEY, next ? '1' : '0')" in HOME_APP


def test_collapsed_does_not_render_recent_block() -> None:
    # product lock A / lovart parity: recent only when expanded + non-empty
    assert "expanded && recent && recent.length > 0" in HOME_APP
    assert HOME_APP.count('data-testid="rail-recent"') == 1
    assert "else setRecent(null)" in HOME_APP


def test_copy_is_recent_projects_not_tasks() -> None:
    assert '"home.recentProjects": "最近项目"' in ZH
    assert "最近任务" not in ZH
    assert '"home.recentProjects": "Recent projects"' in EN or '"home.recentProjects": "Recent Projects"' in EN


def test_mobile_hides_recent_and_collapse_chrome() -> None:
    # keep bottom-nav sensible: recent/collapse chrome stay off on small screens
    assert ".ca-rail__logo, .ca-rail__spacer, .ca-rail__top, .ca-rail__recent, .ca-rail__label, .ca-rail__collapse { display: none; }" in HOME_CSS


def test_no_competitor_brand_in_touched_src() -> None:
    for rel in ("src/home/HomeApp.tsx", "src/styles/home.css", "src/locales/zh.json", "src/locales/en.json"):
        text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore").lower()
        assert "lovart" not in text, rel
