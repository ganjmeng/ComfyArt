"""#262: toolbar names-off hover tip restyle (dark chip above the button); icon and keycap rules unchanged."""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = (ROOT / "src/styles/base.css").read_text()
TB = (ROOT / "src/ui/ImageToolbar.tsx").read_text()


def rule(sel):
    m = re.search(r"(?m)^" + re.escape(sel) + r"\s*\{([^}]*)\}", BASE)
    assert m, sel
    return m.group(1)


def test_tip_chip():
    r = rule(".ca-tip")
    for s in ("background: #1a1a1a", "color: #fff", "12px/26px", "height: 26px", "padding: 0 8px",
              "border-radius: 6px", "border: none", "translate(-50%, -100%)", "0 2px 8px rgba(0,0,0,.16)"):
        assert s in r, s


def test_dark_border():
    assert "0 0 0 .5px rgba(255,255,255,.14)" in rule(':root[data-theme="dark"] .ca-tip')


def test_keycap_on_dark():
    k = rule(".ca-tip__key")
    assert "rgba(255,255,255,.16)" in k and "rgba(255,255,255,.72)" in k and "height: 18px" in k and "border-radius: 4px" in k


def test_tip_above_button():
    assert "top: r.top - 6" in TB and "r.bottom + 8" not in TB


def test_quick_icon_unchanged():
    line = [l for l in (ROOT / "src/ui/icons.tsx").read_text().splitlines() if l.lstrip().startswith("quick:")][0]
    assert hashlib.sha256((line + "\n").encode()).hexdigest() == "4ef4696c1d739fdcd315f5e14e7e66ba1a04f71fa35949b042454ca05104f1f1"
    assert "<Svg fill>" in line


def test_hints_unchanged_and_no_dot():
    chat = [l for l in TB.splitlines() if "id: 'chat'" in l][0]
    quick = [l for l in TB.splitlines() if "id: 'quick'" in l][0]
    assert "hint:" not in chat and "hint: 'Tab'" in quick
    assert "ca-dot" not in TB and "badge" not in TB.lower()


def test_dist_carries_it():
    css = "".join(p.read_text() for p in (ROOT / "dist").rglob("*.css"))
    assert "#1a1a1a" in css.lower() and "translate(-50%,-100%)" in css
