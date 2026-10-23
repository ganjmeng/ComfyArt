"""#80 structure / color control on WaveSpeed (mock server from test_wavespeed; no real calls)."""
from __future__ import annotations

import io
import os

import pytest
from PIL import Image, ImageDraw

from ComfyArt.api import refprep, wavespeed
from tests.test_wavespeed import EDIT, MODELS, _meta, ws  # noqa: F401  (ws fixture)

FLUX = "wavespeed-ai/flux-controlnet-union-pro-2.0"
ZIMG = "wavespeed-ai/z-image-turbo/controlnet"
DEPTH = "wavespeed-ai/depth-anything-v3/image"
SAM = "wavespeed-ai/sam3-image"
MODELS.extend([
    _meta(FLUX, {"prompt": {"type": "string"}, "control_image": {"type": "string"}, "controlnet_conditioning_scale": {"type": "number"},
                 "control_guidance_start": {"type": "number"}, "control_guidance_end": {"type": "number"}, "size": {"type": "string"},
                 "seed": {"type": "integer"}, "output_format": {"type": "string", "enum": ["jpeg", "png", "webp"]}}, ("prompt", "control_image")),
    _meta(DEPTH, {"image": {"type": "string"}, "colormap": {"type": "string", "enum": ["grayscale", "inferno", "turbo"]},
                  "output_format": {"type": "string", "enum": ["jpeg", "png", "webp"]}}, ("image",), price=0.005),
    _meta(ZIMG, {"prompt": {"type": "string"}, "image": {"type": "string"}, "mode": {"type": "string", "enum": ["depth", "canny", "pose", "none"]},
                 "strength": {"type": "number"}, "size": {"type": "string"}, "seed": {"type": "integer"}}, ("prompt", "image"), price=0.012),
])

UPSTREAM_MODES = ["content", "style", "composition", "canny", "lineart", "mlsd", "scribble", "softedge", "depth", "normal", "pose", "seg", "tile", "recolor", "color", "shuffle", "brightness"]


def _photo(name="ref.png"):
    import folder_paths
    img = Image.new("RGB", (64, 48), (200, 180, 160))
    d = ImageDraw.Draw(img)
    d.rectangle((10, 10, 40, 30), fill=(20, 40, 200))
    d.line((0, 45, 63, 45), fill=(0, 0, 0), width=2)
    os.makedirs(folder_paths.get_input_directory(), exist_ok=True)
    img.save(os.path.join(folder_paths.get_input_directory(), name))
    return f"{name} [input]"


def test_upstream_ref_modes_all_present():
    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "refModes.ts"), encoding="utf-8").read()
    import re
    ids = re.findall(r"\{ id: '([a-z]+)', label: t\(", src)
    assert ids == UPSTREAM_MODES  # same modes, same order as 5231d59 (depth restored)


def test_every_mode_is_routed():
    structure = {"canny", "lineart", "mlsd", "scribble", "softedge", "depth", "normal", "pose", "seg", "tile"}
    routed = set(refprep.EXTRACTED) | refprep.FILTERED | set(refprep.CLOUD_MAP)
    assert routed == structure and refprep.COLOR == {"recolor", "color", "shuffle", "brightness"}


@pytest.mark.parametrize("mode", sorted(refprep.FILTERED | refprep.COLOR))
def test_preprocessors_change_the_image(mode):
    src = Image.new("RGB", (64, 48), (200, 180, 160))
    ImageDraw.Draw(src).rectangle((10, 10, 40, 30), fill=(20, 40, 200))
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    out = Image.open(io.BytesIO(refprep.process_bytes(buf.getvalue(), mode, 64, (32, 32))))
    assert out.size == (32, 32)
    assert out.convert("RGB").tobytes() != src.resize((32, 32)).tobytes()


async def test_canny_goes_to_flux_union_with_control_image(ws):
    ref = _photo()
    await wavespeed.submit({"feature": "structure_control", "prompt": "a house", "image": ref, "width": 1024, "height": 768,
                            "control": {"mode": "canny", "strength": 120, "start": 10, "end": 70, "res": 512, "resize": "crop"}})
    model, payload = ws["submits"][0]
    assert model == FLUX and ws["uploads"] == 1
    assert payload["control_image"] == "https://cdn.test/up1.png" and payload["controlnet_conditioning_scale"] == 1.2
    assert payload["control_guidance_start"] == 0.1 and payload["control_guidance_end"] == 0.7
    assert payload["size"] == "1024*768" and payload["prompt"] == "a house" and "image" not in payload


def _png(color=(128, 128, 128), size=(64, 48)):
    img = Image.new("RGB", size, (0, 0, 0))
    ImageDraw.Draw(img).ellipse((8, 8, 48, 40), fill=color)
    return refprep.to_png(img)


@pytest.fixture
def maps(ws, monkeypatch):
    """Cloud map calls answer with a real PNG at a cdn URL (mocked, nothing is fetched)."""
    ws["outputs"] = ["https://cdn.test/map.png"]
    real = wavespeed._source_bytes

    async def fake(value):
        return _png() if value == "https://cdn.test/map.png" else await real(value)
    monkeypatch.setattr(wavespeed, "_source_bytes", fake)
    return ws


def _ctl(mode, ref, strength=80, start=0, end=100):
    return {"mode": mode, "image": ref, "strength": strength, "start": start, "end": end, "res": 512, "resize": "crop"}


async def test_pose_alone_uses_model_extraction(ws):
    ref = _photo()
    await wavespeed.submit({"feature": "structure_control", "prompt": "p", "image": ref, "width": 512, "height": 512,
                            "control": {"mode": "pose", "strength": 150, "start": 0, "end": 100, "res": 1024, "resize": "crop"}})
    model, payload = ws["submits"][0]
    assert model == ZIMG and payload["mode"] == "pose" and payload["strength"] == 1.0
    assert payload["image"] == "https://cdn.test/up1.png"  # raw ref; WaveSpeed extracts the skeleton


async def test_pose_with_window_keeps_knobs_on_flux(ws):
    ref = _photo()
    seen = []
    real = refprep.process_image

    def spy(data, mode, *a):
        seen.append(mode)
        return real(data, mode, *a)
    import unittest.mock as um
    with um.patch.object(refprep, "process_image", spy):
        await wavespeed.submit({"feature": "structure_control", "prompt": "p", "width": 512, "height": 512,
                                "controls": [_ctl("pose", ref, 90, 15, 75)]})
    model, payload = ws["submits"][0]
    assert model == FLUX and seen == [refprep.POSE_FALLBACK]  # not silently dropped: soft-edge map of the pose ref
    assert payload["controlnet_conditioning_scale"] == 0.9
    assert payload["control_guidance_start"] == 0.15 and payload["control_guidance_end"] == 0.75
    est = await wavespeed.estimate({"feature": "structure_control", "prompt": "p", "width": 512, "height": 512,
                                    "controls": [_ctl("pose", ref, 90, 15, 75)]})
    assert est["price"] == 0.03


async def test_pose_mixed_with_other_refs_is_kept(maps):
    a, b = _photo("a.png"), _photo("b.png")
    seen = []
    real = refprep.composite

    def spy(items, size):
        seen.append([s for _, s in items])
        return real(items, size)
    import unittest.mock as um
    with um.patch.object(refprep, "composite", spy):
        await wavespeed.submit({"feature": "structure_control", "prompt": "p", "width": 512, "height": 512,
                                "controls": [_ctl("pose", a, 100), _ctl("depth", b, 50)]})
    assert [m for m, _ in maps["submits"]] == [DEPTH, FLUX]
    assert seen == [[1.0, 0.5]]


@pytest.mark.parametrize("mode,step", [("depth", DEPTH), ("normal", DEPTH), ("seg", SAM)])
async def test_cloud_map_then_flux_with_knobs(maps, mode, step):
    ref = _photo()
    await wavespeed.submit({"feature": "structure_control", "prompt": "a room", "width": 512, "height": 512,
                            "controls": [_ctl(mode, ref, strength=130, start=20, end=60)]})
    models = [m for m, _ in maps["submits"]]
    assert models == [step, FLUX]  # two-step cloud: map first, then ControlNet
    pre = maps["submits"][0][1]
    assert pre["image"].startswith("https://cdn.test/up")
    if step == DEPTH:
        assert pre["colormap"] == "grayscale"
    else:
        assert pre["apply_mask"] is False
    payload = maps["submits"][1][1]
    assert payload["controlnet_conditioning_scale"] == 1.3
    assert payload["control_guidance_start"] == 0.2 and payload["control_guidance_end"] == 0.6
    assert payload["control_image"].startswith("https://cdn.test/up") and payload["size"] == "512*512"


def test_normal_from_depth_is_a_normal_map():
    # left half far (black), right half near (white): the edge tilts normals along x, flat areas face the viewer
    d = Image.new("L", (16, 8), 0)
    d.paste(255, (8, 0, 16, 8))
    n = refprep.normal_from_depth(d.convert("RGB"))
    flat, edge = n.getpixel((2, 4)), n.getpixel((8, 4))
    assert flat == (128, 128, 255)
    assert edge[0] < 100 and edge[2] < 255


async def test_multiple_structure_refs_all_shape_one_control_image(maps):
    a, b = _photo("a.png"), _photo("b.png")
    seen = []
    real = refprep.composite

    def spy(items, size):
        seen.append([s for _, s in items])
        return real(items, size)
    import unittest.mock as um
    with um.patch.object(refprep, "composite", spy):
        await wavespeed.submit({"feature": "structure_control", "prompt": "p", "width": 512, "height": 512,
                                "controls": [_ctl("canny", a, 60, 10, 50), _ctl("depth", b, 120, 30, 90)]})
    models = [m for m, _ in maps["submits"]]
    assert models == [DEPTH, FLUX]
    assert seen == [[0.6, 1.2]]  # both refs went into the control image, weighted by their strength
    payload = maps["submits"][1][1]
    assert payload["controlnet_conditioning_scale"] == 1.2
    assert payload["control_guidance_start"] == 0.1 and payload["control_guidance_end"] == 0.9


def test_composite_keeps_every_map():
    left = Image.new("RGB", (8, 8)); left.paste((255, 255, 255), (0, 0, 4, 8))
    right = Image.new("RGB", (8, 8)); right.paste((255, 255, 255), (4, 0, 8, 8))
    out = refprep.composite([(left, 1.0), (right, 0.5)], (8, 8))
    assert out.getpixel((1, 1)) == (255, 255, 255) and out.getpixel((6, 1)) == (128, 128, 128)


@pytest.mark.parametrize("modes,total", [
    (["canny"], 0.03),
    (["depth"], 0.035),
    (["seg"], 0.035),
    (["normal", "seg", "canny"], 0.04),
    (["pose"], 0.012),
    (["pose", "depth"], 0.035),
])
async def test_estimate_includes_map_calls(ws, modes, total):
    ref = _photo()
    est = await wavespeed.estimate({"feature": "structure_control", "prompt": "p", "width": 512, "height": 512,
                                    "controls": [_ctl(m, ref) for m in modes]})
    assert est["price"] == total


async def test_confirm_amount_includes_map_calls(ws, monkeypatch):
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0.032)
    ref = _photo()
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "structure_control", "prompt": "p", "width": 512, "height": 512, "controls": [_ctl("depth", ref)]})
    assert e.value.status == 409 and e.value.confirm == 0.035 and ws["submits"] == []


async def test_color_modes_preprocess_refs_for_edit(ws):
    a, b = _photo("a.png"), _photo("b.png")
    await wavespeed.submit({"feature": "image_edit", "prompt": "p", "images": [a, b], "prep": [None, "recolor"]})
    model, payload = ws["submits"][0]
    assert model == EDIT and ws["uploads"] == 2 and len(payload["images"]) == 2
