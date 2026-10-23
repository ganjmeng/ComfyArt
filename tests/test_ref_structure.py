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
MODELS.extend([
    _meta(FLUX, {"prompt": {"type": "string"}, "control_image": {"type": "string"}, "controlnet_conditioning_scale": {"type": "number"},
                 "control_guidance_start": {"type": "number"}, "control_guidance_end": {"type": "number"}, "size": {"type": "string"},
                 "seed": {"type": "integer"}, "output_format": {"type": "string", "enum": ["jpeg", "png", "webp"]}}, ("prompt", "control_image")),
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
    routed = set(refprep.EXTRACTED) | refprep.FILTERED | refprep.NO_MODEL
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


@pytest.mark.parametrize("mode", ["depth", "pose"])
async def test_depth_and_pose_use_model_extraction(ws, mode):
    ref = _photo()
    await wavespeed.submit({"feature": "structure_control", "prompt": "p", "image": ref, "width": 512, "height": 512,
                            "control": {"mode": mode, "strength": 150, "start": 0, "end": 100, "res": 1024, "resize": "crop"}})
    model, payload = ws["submits"][0]
    assert model == ZIMG and payload["mode"] == mode and payload["strength"] == 1.0
    assert payload["image"] == "https://cdn.test/up1.png"  # raw ref; WaveSpeed extracts the map


async def test_color_modes_preprocess_refs_for_edit(ws):
    a, b = _photo("a.png"), _photo("b.png")
    await wavespeed.submit({"feature": "image_edit", "prompt": "p", "images": [a, b], "prep": [None, "recolor"]})
    model, payload = ws["submits"][0]
    assert model == EDIT and ws["uploads"] == 2 and len(payload["images"]) == 2
