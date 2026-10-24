"""#249: multiple-angles request body. Mock catalog only, no WaveSpeed call, $0.

The panel caption and the distance field share angleDistance. horizontal 270 is clamped
into −90..90 before it is submitted, and the caption is not sent as a prompt.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ComfyArt.api import wavespeed
from test_wavespeed import MODELS, ws  # noqa: F401  (ws fixture)

ROOT = Path(__file__).resolve().parent.parent
ANGLE = "wavespeed-ai/qwen-image/edit-2509-multiple-angles"
IMG = "https://cdn.test/in.png"
# viewpoint words the panel shows and the request must not carry
BANNED = ("<qma>", "close-up", "medium shot", "wide shot", "eye-level", "front view", "quarter view", "side view")
EXPECT = [
    {"h": -90, "horizontal_angle": -90, "vertical_angle": 0, "distance": 2},
    {"h": 90, "horizontal_angle": 90, "vertical_angle": 0, "distance": 1},
    {"h": 270, "horizontal_angle": 90, "vertical_angle": 0, "distance": 0},  # 270 clamped to 90
    {"h": 0, "horizontal_angle": 0, "vertical_angle": 60, "distance": 0},  # v=80 clamped, z=7 close-up
    {"h": 0, "horizontal_angle": 0, "vertical_angle": -30, "distance": 2},  # v=-40 clamped, z=2.9 wide
]


def _built(tmp_path):
    out = tmp_path / "angle.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "angle_request.ts"},
    )
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_mock_catalog_defines_angle_params():
    meta = next(m for m in MODELS if m["model_id"] == ANGLE)
    props = meta["api_schema"]["api_schemas"][0]["request_schema"]["properties"]
    assert props["horizontal_angle"]["minimum"] == -90 and props["horizontal_angle"]["maximum"] == 90
    assert props["vertical_angle"]["minimum"] == -30 and props["vertical_angle"]["maximum"] == 60
    assert props["distance"]["minimum"] == 0 and props["distance"]["maximum"] == 2
    zh = json.loads((ROOT / "src/locales/zh.json").read_text())
    en = json.loads((ROOT / "src/locales/en.json").read_text())
    assert zh["modePanel.angleLimit"] == "最大 90°，不支持背面"
    assert en["modePanel.angleLimit"] == "Up to 90°, back view not supported"
    panel = (ROOT / "src/ui/ModePanel.tsx").read_text()
    assert "const ALL_ANGLES = [-90, -45, 45, 90]" in panel
    assert "min={-90}" in panel and "max={90}" in panel
    actions = (ROOT / "src/actions.ts").read_text()
    assert "params: angleParams(h, v, z)" in actions and "anglePrompt" not in actions


@pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")
async def test_angle_request_body(ws, tmp_path):  # noqa: F811
    built = _built(tmp_path)
    assert [row["h"] for row in built] == [row["h"] for row in EXPECT]
    for row, want in zip(built, EXPECT):
        for key in ("horizontal_angle", "vertical_angle", "distance"):
            assert row[key] == want[key], (row["h"], key)
        await wavespeed.submit({
            "feature": "change_angle", "image": IMG, "confirmed": True,
            "params": {k: row[k] for k in ("horizontal_angle", "vertical_angle", "distance")},
        })
    assert len(ws["submits"]) == len(EXPECT)
    for (model, payload), row in zip(ws["submits"], built):
        assert model == ANGLE
        assert payload["horizontal_angle"] == row["horizontal_angle"]
        assert payload["vertical_angle"] == row["vertical_angle"]
        assert payload["distance"] == row["distance"]
        assert payload["images"] == [IMG]
        assert "prompt" not in payload
        blob = json.dumps(payload)
        assert row["caption"] not in blob
        for word in BANNED:
            assert word not in blob
