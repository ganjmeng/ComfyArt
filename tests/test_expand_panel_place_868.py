"""#868 follow-up: expand panel placement after slider release (design 4 rules). $0, no network."""
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

SIDE_GAP, CLEAR, EDGE = 16, 12, 8
SIZE_W, SIZE_H = 280, 520


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
    assert data["constants"] == {"SIDE_GAP": SIDE_GAP, "CLEAR": CLEAR, "EDGE": EDGE}

    # 1/2: room on the right → right of the expand box with a 16px gap.
    right = data["right"]
    assert right["side"] == "right"
    assert right["left"] == 740 + SIDE_GAP
    assert right["top"] >= EDGE
    assert data["gaps"]["rightBox"] == SIDE_GAP
    assert data["gaps"]["rightTools"] >= CLEAR
    assert data["gaps"]["rightDock"] >= CLEAR
    assert right["top"] + SIZE_H <= 900 - 64 - 44 - CLEAR  # above .ca-tools

    # No room on the right, room on the left → left side, 16px gap.
    left = data["left"]
    assert left["side"] == "left"
    assert left["left"] + SIZE_W == 400 - SIDE_GAP
    assert data["gaps"]["leftBox"] == SIDE_GAP
    assert data["gaps"]["leftTools"] >= CLEAR
    assert data["gaps"]["leftDock"] >= CLEAR

    # Neither side fits → pin to the viewport right edge, bottom above the toolbar.
    pin = data["pin"]
    assert pin["side"] == "pin"
    assert pin["left"] == 1440 - EDGE - SIZE_W
    assert pin["top"] + SIZE_H <= 900 - 64 - 44 - CLEAR
    assert data["gaps"]["pinTools"] >= CLEAR
    assert data["gaps"]["pinDock"] >= CLEAR
    assert pin["top"] >= EDGE

    # Narrow 1280 viewport: still pins with 12px clearance from the zoom bar.
    narrow = data["narrow"]
    assert narrow["side"] == "pin"
    assert data["gaps"]["narrowRight"] == 0
    assert narrow["left"] == 1280 - EDGE - SIZE_W
    assert data["gaps"]["narrowTools"] >= CLEAR
    assert narrow["top"] + SIZE_H <= 800 - 64 - 44 - CLEAR

    # expandBox applies pads in screen pixels (scale is screen/image).
    assert data["scaled"] == {"l": 500 - 90, "t": 300 - 120, "r": 680 + 90, "b": 540 + 120}


def test_mode_panel_wires_placement_and_transition():
    src = (ROOT / "src/ui/ModePanel.tsx").read_text(encoding="utf-8")
    css = (ROOT / "src/styles/canvas.css").read_text(encoding="utf-8")
    assert "from './panelPlace'" in src
    assert "placeExpandPanel(" in src
    assert "obstacleRects(editor.getContainer(), host)" in src
    assert "if (held) ({ left, top } = held)" in src
    assert "data-move={moving || undefined}" in src
    assert ".ca-panel[data-move] { transition: left 150ms ease, top 150ms ease; }" in css
