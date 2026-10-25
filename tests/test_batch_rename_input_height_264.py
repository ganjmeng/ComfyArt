"""#264: batch rename dialog inputs must keep their 36px height (no flex shrink), scoped to BatchRename only."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_batch_field_input_not_flexed():
    css = (ROOT / "src/styles/overlays.css").read_text()
    assert re.search(r"\.ca-rename__field--batch\s*>\s*\.ca-panel__input\s*\{[^}]*flex:\s*none", css)


def test_dist_carries_fix():
    css = "".join(p.read_text() for p in (ROOT / "dist").rglob("*.css"))
    assert re.search(r"\.ca-rename__field--batch>\.ca-panel__input\{flex:none\}", css)


def test_scoped_to_batch_rename_only():
    css = (ROOT / "src/styles/overlays.css").read_text()
    assert not re.search(r"\.ca-rename__field\s*>\s*\.ca-panel__input", css)
    assert (ROOT / "src/ui/BatchRename.tsx").read_text().count("ca-rename__field--batch") == 2
    for f in (ROOT / "src/ui").glob("*.tsx"):
        if f.name != "BatchRename.tsx":
            assert "ca-rename__field--batch" not in f.read_text(), f.name
