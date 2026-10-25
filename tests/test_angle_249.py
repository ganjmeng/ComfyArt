"""#249: edit-multiple-angles request body. Mock catalog only, no WaveSpeed call, $0.

The panel matches main (0..360, back preset). Sent horizontal_angle is wrapped into 0..359
(360 becomes 0). NaN and other non-finite values are sent as 0. The caption is not a prompt.
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
ANGLE = "wavespeed-ai/qwen-image/edit-multiple-angles"
IMG = "https://cdn.test/in.png"
# viewpoint words the panel shows and the request must not carry
BANNED = ("<qma>", "close-up", "medium shot", "wide shot", "eye-level", "front view", "quarter view", "side view")
EXPECT = [
    {"h": -90, "horizontal_angle": 270, "vertical_angle": 0, "distance": 2},  # left, z=1.3 wide
    {"h": 90, "horizontal_angle": 90, "vertical_angle": 0, "distance": 1},  # right, z=5 medium
    {"h": 270, "horizontal_angle": 270, "vertical_angle": 0, "distance": 0},  # left stays 270, z=8 close-up
    {"h": 0, "horizontal_angle": 0, "vertical_angle": 60, "distance": 0},  # v=80 clamped, z=7 close-up
    {"h": 180, "horizontal_angle": 180, "vertical_angle": -30, "distance": 2},  # back, v=-40 clamped, z=2.9 wide
    {"h": 359, "horizontal_angle": 359, "vertical_angle": 0, "distance": 1},  # in 0..359, z=5
    {"h": 360, "horizontal_angle": 0, "vertical_angle": 0, "distance": 2},  # 360 → 0, z=1.3 wide
    {"h": 400, "horizontal_angle": 40, "vertical_angle": 0, "distance": 0},  # past 359 wraps, z=8 close-up
    {"h": "NaN", "horizontal_angle": 0, "vertical_angle": 0, "distance": 1},
    {"h": "Infinity", "horizontal_angle": 0, "vertical_angle": 0, "distance": 1},
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
    assert props["horizontal_angle"]["minimum"] == 0 and props["horizontal_angle"]["maximum"] == 359
    assert props["vertical_angle"]["minimum"] == -30 and props["vertical_angle"]["maximum"] == 60
    assert props["distance"]["minimum"] == 0 and props["distance"]["maximum"] == 2
    cfg = json.loads((ROOT / "api/wavespeed_models.json").read_text())
    feature = cfg["features"]["change_angle"]
    assert feature["default"] == ANGLE
    assert [m["id"] for m in feature["models"]] == [ANGLE]
    zh = json.loads((ROOT / "src/locales/zh.json").read_text())
    en = json.loads((ROOT / "src/locales/en.json").read_text())
    assert "modePanel.angleLimit" not in zh and "modePanel.angleLimit" not in en
    panel = (ROOT / "src/ui/ModePanel.tsx").read_text()
    assert "const ALL_ANGLES = [315, 45, 270, 90]" in panel
    assert "min={0}" in panel and "max={359}" in panel
    presets = panel.split("const ANGLE_PRESETS", 1)[1].split("const ALL_ANGLES", 1)[0]
    assert "modePanel.back" in presets and "modePanel.front" not in presets and "modePanel.chipFrontRight" in presets
    assert "angleReading" in panel and "modePanel.readLevel" in panel
    assert "modePanel.back" in panel and "modePanel.angleLimit" not in panel
    assert "data-scroll" not in panel
    actions = (ROOT / "src/actions.ts").read_text()
    assert "params: angleParams(h, v, z)" in actions and "anglePrompt" not in actions
    assert "angleReading" not in actions and "readLevel" not in actions


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
        wavespeed._jobs.clear()  # the case list is longer than the app's 8-job cap
    assert len(ws["submits"]) == len(EXPECT)
    for (model, payload), row in zip(ws["submits"], built):
        assert model == ANGLE
        assert payload["horizontal_angle"] == row["horizontal_angle"]
        assert payload["vertical_angle"] == row["vertical_angle"]
        assert payload["distance"] == row["distance"]
        assert 0 <= payload["horizontal_angle"] <= 359
        assert -30 <= payload["vertical_angle"] <= 60
        assert payload["distance"] in (0, 1, 2)
        assert payload["images"] == [IMG]
        assert "prompt" not in payload
        blob = json.dumps(payload)
        assert row["caption"] not in blob
        for word in BANNED:
            assert word not in blob
