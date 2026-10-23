"""#81 preview / re-extract control map, as a cloud extraction (mock server; no real calls)."""
from __future__ import annotations

import io
import os

import pytest
from PIL import Image

from ComfyArt.api import refprep, wavespeed
from tests.test_ref_structure import DEPTH, SAM, _photo, maps, ws  # noqa: F401  (fixtures)


@pytest.mark.parametrize("mode", sorted(refprep.FILTERED | refprep.COLOR))
async def test_local_maps_are_free(ws, mode):
    ref = _photo()
    png = await wavespeed.control_preview({"image": ref, "mode": mode, "res": 32})
    img = Image.open(io.BytesIO(png))
    assert max(img.size) == 32 and ws["submits"] == [] and ws["uploads"] == 0


async def test_pose_previews_its_soft_edge_map(ws):
    ref = _photo()
    pose = await wavespeed.control_preview({"image": ref, "mode": "pose", "res": 64})
    soft = await wavespeed.control_preview({"image": ref, "mode": "softedge", "res": 64})
    assert pose == soft and ws["submits"] == []


@pytest.mark.parametrize("mode,step", [("depth", DEPTH), ("normal", DEPTH), ("seg", SAM)])
async def test_cloud_maps_run_their_map_call(maps, mode, step):
    png = await wavespeed.control_preview({"image": _photo(), "mode": mode, "res": 512})
    assert [m for m, _ in maps["submits"]] == [step]
    assert Image.open(io.BytesIO(png)).size == (64, 48)


async def test_cloud_map_asks_cost_confirmation(maps, monkeypatch):
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0.001)
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.control_preview({"image": _photo(), "mode": "depth", "res": 512})
    assert e.value.status == 409 and e.value.confirm == 0.005 and maps["submits"] == []
    await wavespeed.control_preview({"image": _photo(), "mode": "depth", "res": 512, "confirmed": True})
    assert [m for m, _ in maps["submits"]] == [DEPTH]


async def test_missing_fields_400(ws):
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.control_preview({"mode": "canny"})
    assert e.value.status == 400


def test_upstream_ui_restored():
    root = os.path.join(os.path.dirname(__file__), "..", "src")
    ui = open(os.path.join(root, "ui", "RefControls.tsx"), encoding="utf-8").read()
    assert "previewControl(src, mode, c.res)" in ui and "refControls.reextract" in ui and "ca-refctl__preview" in ui
    assert "/comfyart/wavespeed/control_preview" in open(os.path.join(root, "refModes.ts"), encoding="utf-8").read()
