"""#868: expand scale slider must not jump the ModePanel while dragging (upstream 98786f6e)."""
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "src/ui/ModePanel.tsx").read_text(encoding="utf-8")


def test_expand_slider_holds_panel_position_while_dragging():
    # Freeze left/top with pointer capture; left expand edge uses pads.l.
    assert "const [held, setHeld] = useState<{ left: number; top: number } | null>(null)" in SRC
    assert "if (held) ({ left, top } = held)" in SRC
    assert "e.target.setPointerCapture(e.pointerId)" in SRC
    assert "setHeld({ left, top })" in SRC
    assert "onLostPointerCapture={() => setHeld(null)}" in SRC
    assert "const leftEdge = rect.l - (mode === 'expand' ? pads.l * s : 0)" in SRC
