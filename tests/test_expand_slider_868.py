"""#868: expand scale slider must not jump the ModePanel while dragging (upstream 98786f6e).

After release, placement is handled by placeExpandPanel (see test_expand_panel_place_868.py).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "src/ui/ModePanel.tsx").read_text(encoding="utf-8")
CSS = (ROOT / "src/styles/canvas.css").read_text(encoding="utf-8")


def test_expand_slider_holds_panel_position_while_dragging():
    # Freeze left/top/width with pointer capture; expand uses expandBox (includes pads.l).
    assert "const [held, setHeld] = useState<{ left: number; top: number; width: number } | null>(null)" in SRC
    assert "if (held) ({ left, top, width: panelW } = held)" in SRC
    assert "e.target.setPointerCapture(e.pointerId)" in SRC
    assert "setHeld({ left, top, width: panelW })" in SRC
    assert "setHeld(null)" in SRC
    assert "onLostPointerCapture={() => {" in SRC
    assert "expandBox(" in SRC and "placeExpandPanel(" in SRC
    # Pointer-down (drag start) turns the move transition off; release turns it on.
    _, _, rest = SRC.partition("e.target.setPointerCapture(e.pointerId)")
    mid, _, up = rest.partition("onLostPointerCapture")
    assert "setMoving(false)" in mid
    assert "setHeld({ left, top, width: panelW })" in mid
    assert "setHeld(null)" in up
    assert "setMoving(true)" in up
    assert "data-move={moving || undefined}" in SRC
    assert "MOVE_MS" in SRC
    assert ".ca-panel[data-move] { transition: left 150ms ease, top 150ms ease; }" in CSS
