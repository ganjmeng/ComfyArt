"""#45: masked/region edits only send the selection crop (default gpt-image-2.5-sunburst/edit) and paste the
result back through the mask; move object = cloud erase on a crop + local composite (no edit model).
Mocks only (local aiohttp WaveSpeed stand-in + catalog fixture): no network, no charge."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import folder_paths
from ComfyArt.api import auto_models, wavespeed

from test_wavespeed import MODELS, uncurated, ws  # noqa: F401  (fixtures)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())
SUNBURST = "openai/gpt-image-2.5-sunburst/edit"
FLARE = "openai/gpt-image-2.5-flare/edit"
ERASER = "wavespeed-ai/image-eraser"
REAL_CURATED = wavespeed.load_curated


@pytest.fixture
def curated(monkeypatch, ws):
    monkeypatch.setattr(wavespeed, "load_curated", REAL_CURATED)
    extra = [FIXTURE[m] for m in (SUNBURST, FLARE, ERASER)]
    monkeypatch.setattr("test_wavespeed.MODELS", [m for m in MODELS if m["model_id"] != ERASER] + extra)
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    return ws


def png(arr) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr.astype(np.uint8), "RGBA" if arr.shape[-1] == 4 else "RGB").save(buf, format="PNG")
    return buf.getvalue()


def put(name: str, data: bytes) -> str:
    os.makedirs(folder_paths.get_input_directory(), exist_ok=True)
    wavespeed._write(os.path.join(folder_paths.get_input_directory(), name), data)
    return f"{name} [input]"


def noise(h, w, seed=1):
    return np.random.default_rng(seed).integers(0, 256, (h, w, 3), dtype=np.uint8)


def comfy_mask(h, w, box):
    """ComfyArt mask file: white, target transparent."""
    a = np.full((h, w), 255, np.uint8)
    x, y, bw, bh = box
    a[y:y + bh, x:x + bw] = 0
    return png(np.dstack([np.full_like(a, 255)] * 3 + [a]))


def fake_result(monkeypatch, arr):
    """The mock CDN returns b'PNGDATA'; hand the poller a real image instead (what the model 'returned')."""
    real = wavespeed._read

    def read(path):
        data = real(path)
        return png(arr) if data == b"PNGDATA" else data
    monkeypatch.setattr(wavespeed, "_read", read)


async def finish(group):
    for _ in range(5):
        h = (await wavespeed.poll(group))[f"ws:{group}"]
        if h["status"]["completed"] or h["status"]["status_str"] == "error":
            return h
    raise AssertionError(h)


def output(h):
    ref = h["outputs"]["ws"]["images"][0]
    return np.asarray(Image.open(io.BytesIO(wavespeed._read(wavespeed._ref_path(ref)))).convert("RGB"))


async def test_region_edit_sends_only_the_crop_to_sunburst_and_keeps_outside_pixels(curated, monkeypatch):
    H, W = 600, 800
    orig = noise(H, W)
    crop = {"x": 200, "y": 100, "w": 400, "h": 400}
    sel = (100, 120, 150, 100)  # inside the crop, crop coords
    inputs = {"feature": "image_edit", "image": put("orig.png", png(orig)), "mask": put("m.png", comfy_mask(400, 400, sel)),
              "paste": crop, "prompt": "make it red"}
    fake_result(monkeypatch, np.full((512, 512, 3), 7, np.uint8))  # model answers at another size: scaled to the crop
    group = await wavespeed.submit(inputs)
    [(model, payload)] = curated["submits"]
    assert model == SUNBURST
    assert "mask_image" not in payload and len(payload["images"]) == 1  # only the crop goes up
    out = output(await finish(group))
    assert out.shape == orig.shape
    inside = np.zeros((H, W), bool)
    inside[crop["y"] + sel[1]:crop["y"] + sel[1] + sel[3], crop["x"] + sel[0]:crop["x"] + sel[0] + sel[2]] = True
    assert np.array_equal(out[~inside], orig[~inside])  # byte-identical outside the selection
    assert (out[inside] == 7).all()


async def test_user_model_wins_and_mask_free_edit_keeps_flare(curated):
    base = {"feature": "image_edit", "image": put("o.png", png(noise(64, 64))), "mask": put("m.png", comfy_mask(64, 64, (0, 0, 8, 8))),
            "paste": {"x": 0, "y": 0, "w": 64, "h": 64}, "prompt": "x"}
    await wavespeed.submit({**base, "model": FLARE})
    await wavespeed.submit({"feature": "image_edit", "images": ["https://example.com/a.png"], "prompt": "x"})
    assert [m for m, _ in curated["submits"]] == [FLARE, FLARE]
    assert wavespeed.load_config()["features"]["image_edit"]["default"] == FLARE  # global default unchanged


async def test_move_object_erases_a_crop_and_composites_locally(curated, monkeypatch):
    H, W = 500, 700
    orig = noise(H, W, 2)
    obj = (300, 200, 40, 30)
    dx, dy = 120, -50
    inputs = {"feature": "move_object", "image": put("o.png", png(orig)), "mask": put("m.png", comfy_mask(H, W, obj)),
              "dx": dx, "dy": dy, "model": SUNBURST, "prompt": "move"}
    fake_result(monkeypatch, np.full((384, 384, 3), 9, np.uint8))
    group = await wavespeed.submit(inputs)
    [(model, payload)] = curated["submits"]
    assert model == ERASER  # erase only: no edit-model call even with an edit model picked
    assert set(payload) >= {"image", "mask_image"}
    out = output(await finish(group))
    m = np.zeros((H, W), np.float32)
    m[obj[1]:obj[1] + obj[3], obj[0]:obj[0] + obj[2]] = 1
    grown = wavespeed.grow_mask(m, 12)
    box = wavespeed.crop_around(wavespeed.bbox(grown), W, H)
    assert box["w"] < W and box["h"] < H  # erase ran on a crop around the old spot
    moved = np.zeros((H, W), bool)
    moved[obj[1] + dy:obj[1] + dy + obj[3], obj[0] + dx:obj[0] + dx + obj[2]] = True
    touched = (grown > 0) | moved
    assert np.array_equal(out[~touched], orig[~touched])  # byte-identical everywhere else
    assert np.array_equal(out[moved], orig[obj[1]:obj[1] + obj[3], obj[0]:obj[0] + obj[2]].reshape(-1, 3))  # object, no feathering
    hole = (grown > 0) & ~moved
    assert (out[hole] == 9).all()  # background filled by the erase result


async def test_quote_equals_charge_for_sunburst_crop(curated):
    seen = []

    def price(inp):
        seen.append(dict(inp))
        return 0.039 * (2 if inp.get("resolution") == "2k" else 1)
    curated["prices"][SUNBURST] = price
    inputs = {"feature": "image_edit", "image": put("o.png", png(noise(900, 1200))), "mask": put("m.png", comfy_mask(512, 512, (10, 10, 50, 50))),
              "paste": {"x": 100, "y": 100, "w": 512, "h": 512}, "prompt": "x"}
    est = await wavespeed.estimate(dict(inputs))
    quoted = await wavespeed.priced_inputs(SUNBURST, wavespeed.region_inputs(inputs))
    await wavespeed.submit(dict(inputs))
    model, payload = curated["submits"][0]
    assert model == SUNBURST
    assert quoted == {k: payload[k] for k in ("resolution", "quality", "aspect_ratio", "size") if k in payload}
    assert est["price"] == pytest.approx(price(payload)) and est["source"] == "quote"


def test_auto_rule_maps_masked_edits_to_sunburst():
    cfg = {"features": {"image_edit": {"models": [{"id": FLARE}, {"id": SUNBURST}], "default": FLARE}}}
    row = auto_models.load_table()["image_edit"]["masked"]
    assert row["model"] == SUNBURST and "edit_region" in row["tools"]
    assert auto_models.tool_feature("edit_region") == "image_edit"
    assert auto_models.choose("image_edit", "redo the sky", None, cfg, masked=True)["model"] == SUNBURST
    assert auto_models.choose("image_edit", "redo the sky", FLARE, cfg, masked=True)["model"] == FLARE  # user-named wins
    assert auto_models.choose("image_edit", "redo the sky", None, cfg)["category"] != "masked"  # mask-free: normal rules


async def test_quote_uses_crop_tier_not_full_image_tier(curated):
    """Full image 3072x3072 would be a 4k job, the 512 crop is 1k: the quote must price the crop (= the charge).
    No quality passed (model default)."""
    tiers = {"1k": 0.039, "2k": 0.078, "4k": 0.156}
    curated["prices"][SUNBURST] = lambda inp: tiers.get(inp.get("resolution"), 0.5)
    inputs = {"feature": "image_edit", "image": put("big.png", png(noise(3072, 3072))), "mask": put("m.png", comfy_mask(512, 512, (100, 100, 80, 80))),
              "paste": {"x": 1200, "y": 1200, "w": 512, "h": 512}, "prompt": "x"}
    est = await wavespeed.estimate(dict(inputs))
    await wavespeed.submit(dict(inputs))
    model, payload = curated["submits"][0]
    assert model == SUNBURST and payload.get("resolution") == "1k" and "quality" not in payload
    full = await wavespeed.priced_inputs(SUNBURST, {**wavespeed.region_inputs(inputs), "width": 3072, "height": 3072})
    assert full.get("resolution") != "1k"  # quoting by the full image would land in another tier
    assert est["price"] == pytest.approx(tiers[payload["resolution"]]) != pytest.approx(tiers.get(full.get("resolution"), 0.5))


async def test_masked_edit_falls_back_to_flare_with_a_warning_when_sunburst_missing(curated, monkeypatch, caplog):
    monkeypatch.setattr("test_wavespeed.MODELS", [m for m in __import__("test_wavespeed").MODELS if m["model_id"] != SUNBURST])
    cfg = wavespeed.load_config()
    monkeypatch.setitem(cfg["features"]["image_edit"], "models", [m for m in cfg["features"]["image_edit"]["models"] if m["id"] != SUNBURST])
    monkeypatch.setattr(wavespeed, "load_config", lambda: cfg)
    assert wavespeed.masked_edit_model() is None
    assert "falling back" in caplog.text


@pytest.mark.parametrize("case", ["zero_box", "empty_mask", "empty_move"])
async def test_empty_selection_is_400_before_any_wavespeed_call(curated, case):
    img = put("o.png", png(noise(256, 256)))
    if case == "zero_box":
        inputs = {"feature": "image_edit", "image": img, "mask": put("m.png", comfy_mask(64, 64, (0, 0, 8, 8))), "paste": {"x": 0, "y": 0, "w": 0, "h": 0}, "prompt": "x"}
    elif case == "empty_mask":
        inputs = {"feature": "image_edit", "image": img, "mask": put("m.png", comfy_mask(64, 64, (0, 0, 0, 0))), "paste": {"x": 0, "y": 0, "w": 64, "h": 64}, "prompt": "x"}
    else:
        inputs = {"feature": "move_object", "image": img, "mask": put("m.png", comfy_mask(256, 256, (0, 0, 0, 0))), "dx": 5, "dy": 5}
    before = (curated["uploads"], len(curated["quotes"]))
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit(inputs)
    assert e.value.status == 400
    assert not curated["submits"] and (curated["uploads"], len(curated["quotes"])) == before  # no WaveSpeed call at all
