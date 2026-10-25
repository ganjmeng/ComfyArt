"""#243: key dialog restyle is scoped to .ca-rename--key; shared .ca-rename / Modal stay as on main."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OV = (ROOT / "src/styles/overlays.css").read_text()


def rule(sel):
    m = re.search(re.escape(sel) + r"\s*\{([^}]*)\}", OV)
    assert m, sel
    return m.group(1)


def test_key_card_style():
    r = rule(".ca-modal__card.ca-rename--key")
    assert "border-radius: 20px" in r
    assert "inset 0 0 0 var(--ca-border-w) var(--ca-border)" in r and "var(--ca-shadow-float)" in r


def test_key_head_and_body():
    h = rule(".ca-rename--key > .ca-side__head")
    assert "height: 56px" in h and "padding: 0 16px 0 24px" in h
    assert "padding: 0 24px 24px" in rule(".ca-rename--key > .ca-rename__body")


def test_shared_rules_untouched():
    assert "border-radius: 16px" in rule(".ca-modal__card") and "0 12px 40px rgba(0,0,0,.18)" in rule(".ca-modal__card")
    assert "padding: 0 20px 20px" in rule(".ca-rename__body")
    assert "height: 48px" in (ROOT / "src/styles/shell.css").read_text().split(".ca-side__head {")[1].split("}")[0]
    base = (ROOT / "src/styles/base.css").read_text()
    assert base.count("--ca-shadow-float: var(--ca-shadow)") == 2 and "--ca-backdrop: rgba(0,0,0,.4)" in base


def test_modifier_only_on_key_dialog():
    assert "ca-rename--key" in (ROOT / "src/ui/KeySettings.tsx").read_text()
    for f in (ROOT / "src").rglob("*.tsx"):
        if f.name != "KeySettings.tsx":
            assert "ca-rename--key" not in f.read_text(), f.name
    assert "ca-panel__input" not in "".join(l for l in OV.splitlines() if "ca-rename--key" in l)


def test_dist_carries_it():
    css = "".join(p.read_text() for p in (ROOT / "dist").rglob("*.css"))
    assert ".ca-rename--key" in css and "--ca-shadow-float" in css
