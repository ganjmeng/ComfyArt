"""#81 preview / re-extract control map, as a cloud extraction (mock server; no real calls)."""
from __future__ import annotations

import io
import os

import pytest
from PIL import Image

from ComfyArt.api import refprep, wavespeed
from tests.test_ref_structure import DEPTH, FLUX, SAM, _ctl, _photo, maps, ws  # noqa: F401  (fixtures)


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


def _job(ref, mode):
    return {"feature": "structure_control", "prompt": "p", "width": 512, "height": 512, "controls": [_ctl(mode, ref)]}


@pytest.mark.parametrize("mode,step", [("depth", DEPTH), ("normal", DEPTH), ("seg", SAM)])
async def test_generate_reuses_preview_map(maps, mode, step):
    """#81 product rule: same src / mode / res as the preview -> exactly one cloud extraction, no second charge."""
    ref = _photo()
    await wavespeed.control_preview({"image": ref, "mode": mode, "res": 512, "confirmed": True})
    assert wavespeed._map_steps(_job(ref, mode)) == []  # estimate no longer counts the map call
    await wavespeed.submit(_job(ref, mode))
    models = [m for m, _ in maps["submits"]]
    assert models.count(step) == 1 and models[0] == step and models[-1] == FLUX


async def test_generate_sends_preview_map(maps, monkeypatch):
    """The job's control image is built from the very map bytes the preview extracted."""
    seen = []
    real = refprep.process_image
    monkeypatch.setattr(refprep, "process_image", lambda data, *a, **k: (seen.append(data), real(data, *a, **k))[1])
    ref = _photo()
    png = await wavespeed.control_preview({"image": ref, "mode": "depth", "res": 512, "confirmed": True})
    await wavespeed.submit(_job(ref, "depth"))
    assert len(seen) == 2 and seen[0] is seen[1]
    assert png == refprep.to_png(real(seen[0], "depth", 512, None, "crop"))
    assert [m for m, _ in maps["submits"]].count(DEPTH) == 1


async def test_changed_res_extracts_again(maps):
    ref = _photo()
    await wavespeed.control_preview({"image": ref, "mode": "depth", "res": 1024, "confirmed": True})
    await wavespeed.submit(_job(ref, "depth"))  # job ref is res 512
    assert [m for m, _ in maps["submits"]] == [DEPTH, DEPTH, FLUX]


async def test_changed_mode_extracts_again(maps):
    ref = _photo()
    await wavespeed.control_preview({"image": ref, "mode": "depth", "res": 512, "confirmed": True})
    await wavespeed.submit(_job(ref, "normal"))  # same src / res, other mode (same DEPTH model, different map)
    assert [m for m, _ in maps["submits"]] == [DEPTH, DEPTH, FLUX]


async def test_changed_source_extracts_again(maps):
    await wavespeed.control_preview({"image": _photo("a.png"), "mode": "depth", "res": 512, "confirmed": True})
    await wavespeed.submit(_job(_photo("b.png"), "depth"))
    assert [m for m, _ in maps["submits"]] == [DEPTH, DEPTH, FLUX]


async def test_missing_fields_400(ws):
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.control_preview({"mode": "canny"})
    assert e.value.status == 400


def test_upstream_ui_restored():
    root = os.path.join(os.path.dirname(__file__), "..", "src")
    ui = open(os.path.join(root, "ui", "RefControls.tsx"), encoding="utf-8").read()
    assert "previewControl(src, mode, c.res)" in ui and "refControls.reextract" in ui and "ca-refctl__preview" in ui
    modes = open(os.path.join(root, "refModes.ts"), encoding="utf-8").read()
    assert "/comfyart/wavespeed/control_preview" in modes
    # #81: 60s preview timeout aborts the request and surfaces an error (the button's finally restores it)
    assert "PREVIEW_TIMEOUT_MS = 60_000" in modes and "signal: ctl.signal" in modes and "refControls.timeout" in modes
    assert "finally" in ui and "setBusy(false)" in ui


async def test_reextract_calls_cloud_again_when_cached(maps):
    """#81 product rule: 「重新提取」 (fresh) bypasses the (src, mode, res) cache and extracts again."""
    ref = _photo()
    await wavespeed.control_preview({"image": ref, "mode": "depth", "res": 512, "confirmed": True})
    await wavespeed.control_preview({"image": ref, "mode": "depth", "res": 512, "confirmed": True})  # cached
    assert [m for m, _ in maps["submits"]] == [DEPTH]
    await wavespeed.control_preview({"image": ref, "mode": "depth", "res": 512, "confirmed": True, "fresh": True})
    assert [m for m, _ in maps["submits"]] == [DEPTH, DEPTH]


async def test_reextract_asks_cost_confirmation_even_when_cached(maps, monkeypatch):
    ref = _photo()
    await wavespeed.control_preview({"image": ref, "mode": "depth", "res": 512, "confirmed": True})
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0.001)
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.control_preview({"image": ref, "mode": "depth", "res": 512, "fresh": True})
    assert e.value.status == 409 and e.value.confirm == 0.005
    assert [m for m, _ in maps["submits"]] == [DEPTH]


async def test_generate_after_reextract_uses_new_map(maps, monkeypatch):
    """The re-extracted map replaces the cache entry; generate uses it with 0 extra extractions."""
    seen = []
    real = refprep.process_image
    monkeypatch.setattr(refprep, "process_image", lambda data, *a, **k: (seen.append(data), real(data, *a, **k))[1])
    ref = _photo()
    await wavespeed.control_preview({"image": ref, "mode": "depth", "res": 512, "confirmed": True})
    await wavespeed.control_preview({"image": ref, "mode": "depth", "res": 512, "confirmed": True, "fresh": True})
    assert wavespeed._map_steps(_job(ref, "depth")) == []
    await wavespeed.submit(_job(ref, "depth"))
    assert [m for m, _ in maps["submits"]].count(DEPTH) == 2
    assert seen[-1] is seen[1] and seen[-1] is wavespeed._map_cache[(ref, "depth", 512)]


def test_reextract_estimate_includes_extraction(maps):
    ref = _photo()
    q = {"image": ref, "mode": "depth", "res": 512}
    wavespeed._map_cache[(ref, "depth", 512)] = b"old"
    assert wavespeed.preview_estimate(q) == []
    assert wavespeed.preview_estimate({**q, "fresh": True}) == [refprep.CLOUD_MAP["depth"][0]]


def test_ui_sends_fresh_on_reextract():
    root = os.path.join(os.path.dirname(__file__), "..", "src")
    modes = open(os.path.join(root, "refModes.ts"), encoding="utf-8").read()
    assert "previewed.has(seen) ? { fresh: true }" in modes and "previewed.add(seen)" in modes
