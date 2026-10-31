"""#552 sidebar finish — collapsed grey bg token, collapsed hides Beta, expanded recent list (reuse #535/#495). Static, $0."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME_APP = (ROOT / "src/home/HomeApp.tsx").read_text()
HOME_CSS = (ROOT / "src/styles/home.css").read_text()
BASE_CSS = (ROOT / "src/styles/base.css").read_text()


def _rule(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", HOME_CSS)
    assert m, selector
    return m.group(1)


def test_rail_bg_token_light_dark() -> None:
    light, dark = BASE_CSS.split(':root[data-theme="dark"]', 1)
    assert re.search(r"--ca-rail-bg:\s*#f5f5f5", light)
    assert re.search(r"--ca-rail-bg:\s*#1c1c1c", dark)
    # dark reuses the existing secondary surface value, no new token
    assert re.search(r"--ca-skillrun-side:\s*#1c1c1c", dark)


def test_collapsed_rail_uses_token() -> None:
    base = _rule(".ca-rail")
    assert "background: var(--ca-rail-bg)" in base
    assert "background: var(--ca-rail-bg)" in _rule(".ca-rail[data-expanded]")


def test_collapsed_hides_beta_badge() -> None:
    assert "badge={expanded ? t('home.artiBeta') : undefined}" in HOME_APP
    assert 'data-testid="rail-arti-beta"' in HOME_APP


def test_recent_list_single_data_driven() -> None:
    assert HOME_APP.count('data-testid="rail-recent"') == 1
    assert "expanded && recent && recent.length > 0" in HOME_APP
    assert "listProjects()" in HOME_APP
    assert "function RecentRow" in HOME_APP or "const RecentRow" in HOME_APP


def test_no_competitor_name_in_src() -> None:
    for p in (ROOT / "src").rglob("*"):
        if p.is_file() and p.suffix in {".ts", ".tsx", ".css", ".json", ".md", ".html"}:
            assert "lovart" not in p.read_text(errors="ignore").lower(), p
