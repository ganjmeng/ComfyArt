"""Chat panel topbar (400px .ca-agent) must not overflow: title shrinks instead of pushing the collapse icon past the divider."""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "src/styles/shell.css"


def _rule(sel):
    m = re.search(r"^" + re.escape(sel) + r" \{([^}]*)\}", CSS.read_text(), re.M)
    assert m, sel
    return m.group(1)


def test_title_can_shrink():
    r = _rule(".ca-head__name")
    assert "flex: none" not in r
    assert re.search(r"flex: 0 1 ", r)
    assert "min-width: 0" in r and "max-width: 182px" in r


def test_agent_panel_width_unchanged():
    assert "width: 400px" in _rule(".ca-agent")


def test_568_spacing():
    assert "padding: 0 12px;" in _rule(".ca-head")
    assert "padding: 0 12px 0 10px" in _rule(".ca-top")


def test_568_no_saved_label():
    src = (CSS.parents[1] / "ui/ProjectHeader.tsx").read_text()
    assert "projectHeader.saved'" not in src and "projectHeader.saving" not in src
    assert "projectHeader.saveFailed" in src  # failed save + retry still shown
