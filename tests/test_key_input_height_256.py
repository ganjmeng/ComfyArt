"""#256: inputs inside a vertical .ca-rename__field must keep their 36px height (no flex shrink)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_rename_field_input_not_flexed():
    css = (ROOT / "src/styles/overlays.css").read_text()
    assert re.search(r"\.ca-rename__field--key\s*>\s*\.ca-panel__input\s*\{[^}]*flex:\s*none", css)


def test_panel_input_height_36():
    css = (ROOT / "src/styles/canvas.css").read_text()
    block = re.search(r"\.ca-panel__input\s*\{([^}]*)\}", css).group(1)
    assert "height: 36px" in block


def test_dist_carries_fix():
    css = "".join(p.read_text() for p in (ROOT / "dist").rglob("*.css"))
    assert re.search(r"\.ca-rename__field--key>\.ca-panel__input\{flex:none\}", css)


def test_scoped_to_key_dialog_only():
    css = (ROOT / "src/styles/overlays.css").read_text()
    assert not re.search(r"\.ca-rename__field\s*>\s*\.ca-panel__input", css)
    assert (ROOT / "src/ui/KeySettings.tsx").read_text().count("ca-rename__field--key") == 2
    for f in (ROOT / "src/ui").glob("*.tsx"):
        if f.name != "KeySettings.tsx":
            assert "ca-rename__field--key" not in f.read_text(), f.name
