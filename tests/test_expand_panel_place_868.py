"""#868 follow-up: expand panel placement after slider release. $0, no network."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)

SIDE_GAP, CLEAR, EDGE, VIEW_CLEAR = 16, 12, 8, 12
PANEL_W, PANEL_NARROW_W = 280, 220


@node
def test_place_expand_panel_follows_design_rules(tmp_path):
    out = tmp_path / "p.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "panel_place.ts"},
    )
    data = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    assert data["constants"] == {
        "SIDE_GAP": SIDE_GAP,
        "CLEAR": CLEAR,
        "EDGE": EDGE,
        "VIEW_CLEAR": VIEW_CLEAR,
        "PANEL_W": PANEL_W,
        "PANEL_NARROW_W": PANEL_NARROW_W,
    }

    # 1× / 2× path: 280px on the right, then the left. Unchanged.
    right, left = data["right"], data["left"]
    assert right == {"left": 740 + SIDE_GAP, "top": 200, "side": "right", "width": PANEL_W}
    assert left["side"] == "left" and left["width"] == PANEL_W
    assert left["left"] + PANEL_W == 400 - SIDE_GAP

    # 280px fits neither side → narrow to 220px and try right, then left.
    n_right, n_both, n_left = data["nRight"], data["nBoth"], data["nLeft"]
    assert n_right == {"left": 1160 + SIDE_GAP, "top": 40, "side": "narrow-right", "width": PANEL_NARROW_W}
    assert n_right["left"] >= VIEW_CLEAR and n_right["left"] + PANEL_NARROW_W <= 1440 - VIEW_CLEAR
    # When 220px fits on both sides, the right side wins.
    assert n_both["side"] == "narrow-right" and n_both["left"] == n_right["left"]
    assert n_left == {"left": 250 - SIDE_GAP - PANEL_NARROW_W, "top": 40, "side": "narrow-left", "width": PANEL_NARROW_W}
    assert n_left["left"] >= VIEW_CLEAR

    # 220px still fits neither side → dock to the viewport right edge at 220px.
    docked = data["docked"]
    assert docked["side"] == "dock" and docked["width"] == PANEL_NARROW_W
    assert docked["left"] == 1440 - VIEW_CLEAR - PANEL_NARROW_W

    # Docked: shift vertically to stay ≥12px from the right handle when a slot exists.
    shifted = data["shifted"]
    assert shifted["side"] == "dock" and shifted["width"] == PANEL_NARROW_W
    assert shifted["left"] == 800 - VIEW_CLEAR - PANEL_NARROW_W
    assert shifted["top"] == data["handle"]["shift"]["b"] + CLEAR  # below the handle
    assert data["handle"]["shiftedClearsHandle"] is True

    # If no vertical slot clears the handle, covering it is allowed, but toolbars / 生成 stay clear.
    covered = data["covered"]
    assert covered["side"] == "dock" and data["handle"]["coveredHitsHandle"] is True

    # expandBox applies pads in screen pixels (scale is screen/image).
    assert data["scaled"] == {"l": 410, "t": 180, "r": 770, "b": 660}

    for name, flags in data["clear"].items():
        assert flags == {"tools": True, "dock": True, "gen": True}, name


def test_mode_panel_wires_placement_and_transition():
    src = (ROOT / "src/ui/ModePanel.tsx").read_text(encoding="utf-8")
    css = (ROOT / "src/styles/canvas.css").read_text(encoding="utf-8")
    assert "from './panelPlace'" in src
    assert "placeExpandPanel(" in src
    assert "PANEL_NARROW_W" in src
    assert "obstacleRects(editor.getContainer(), host)" in src
    assert "if (held) ({ left, top, width: panelW } = held)" in src
    assert "data-move={moving || undefined}" in src
    assert "data-narrow={(mode === 'expand' && panelW === PANEL_NARROW_W) || undefined}" in src
    assert ".ca-panel[data-move] { transition: left 150ms ease, top 150ms ease; }" in css
    assert ".ca-panel[data-narrow] { width: 220px; }" in css
    # 220px layout: slider + value, size/price line, and 取消/生成 stay on one row.
    assert "grid-template-columns: max-content minmax(0, 1fr) max-content;" in css
    assert ".ca-panel[data-narrow] .ca-panel__foot { flex-wrap: nowrap; }" in css
    assert ".ca-panel[data-narrow] .ca-panel__foot > button" in css
    assert "white-space: nowrap" in css
    assert "text-overflow: clip" in css
