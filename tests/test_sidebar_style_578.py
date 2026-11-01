"""#578 sidebar style: 新建项目 bordered button, light-blue Beta tag after Arti, recent row pitch 38. Static, $0."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME_CSS = (ROOT / "src/styles/home.css").read_text()
SRC = ROOT / "src"


def _rule(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", HOME_CSS)
    assert m, selector
    return m.group(1)


def test_new_project_bordered_button_uses_tokens() -> None:
    rules = re.findall(r'\.ca-rail__btn\[data-testid="rail-new"\]\s*\{([^}]*)\}', HOME_CSS)
    body = " ".join(rules)
    assert "border: 1px solid var(--ca-border)" in body
    assert "background: var(--ca-float)" in body


def test_beta_badge_light_blue_tag() -> None:
    badge = re.search(r"\n\.ca-rail__badge\s*\{([^}]*)\}", HOME_CSS).group(1)
    assert "color: var(--ca-blue)" in badge
    assert "color-mix(in srgb, var(--ca-blue)" in badge
    assert "#fff" not in badge
    assert "flex: 0 1 auto" in _rule('.ca-rail[data-expanded] .ca-rail__btn[data-testid="rail-arti"] .ca-rail__label')


def test_recent_row_pitch_38() -> None:
    row = _rule(".ca-rail__recent-row")
    assert "min-height: 36px" in row
    assert "gap: 2px" in _rule(".ca-rail[data-expanded] .ca-rail__recent")


def test_no_brand_word_in_src() -> None:
    for p in SRC.rglob("*"):
        if p.is_file() and p.suffix in {".ts", ".tsx", ".css", ".json"}:
            assert "Lovart" not in p.read_text(errors="ignore"), p
