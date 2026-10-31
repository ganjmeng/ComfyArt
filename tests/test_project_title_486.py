"""#486: project top-bar title matches Lovart — fixed ~182px input, single-line ellipsis, select-on-focus, Escape cancels."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = (ROOT / "src/ui/ProjectHeader.tsx").read_text()
SHELL = (ROOT / "src/styles/shell.css").read_text()


def _name_rule() -> str:
    m = re.search(r"\.ca-head__name \{[^}]+\}", SHELL)
    assert m, ".ca-head__name rule missing"
    return m.group(0)


def test_title_input_fixed_width_with_ellipsis():
    rule = _name_rule()
    assert "width: 182px" in rule
    assert "max-width: 182px" in rule
    assert "overflow: hidden" in rule
    assert "text-overflow: ellipsis" in rule
    assert "white-space: nowrap" in rule
    assert "min-width: 0" in rule
    # must not flex-grow into a tiny leftover slot
    assert "flex: none" in rule or "flex: 0" in rule


def test_title_input_no_hover_tooltip():
    # Lovart: hover shows no tooltip with the full title
    block = HEADER[HEADER.index("className=\"ca-head__name\"") : HEADER.index("<SaveStatus")]
    assert "title=" not in block


def test_title_select_on_focus_and_escape_cancels():
    assert "data-testid=\"project-title\"" in HEADER
    assert "titleBaseline" in HEADER
    assert "e.currentTarget.select()" in HEADER
    assert "e.key === 'Escape'" in HEADER
    assert "editor.updateDocumentSettings({ name: titleBaseline.current })" in HEADER


def test_title_still_enter_to_blur():
    assert "if (isEnter(e)) e.currentTarget.blur()" in HEADER
