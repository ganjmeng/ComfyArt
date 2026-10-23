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
    touched = (wavespeed.feather_mask(grown) > 0) | moved
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
    assert len(quoted.pop("images")) == len(payload["images"]) == 1  # #192: priced for the references it submits
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


async def test_box_partly_outside_is_clipped_quote_equals_charge(curated, monkeypatch):
    H, W = 600, 800
    orig = noise(H, W)
    seen = []

    def price(inp):
        seen.append(dict(inp))
        return {"1k": 0.039, "2k": 0.078}.get(inp.get("resolution"), 0.039)
    curated["prices"][SUNBURST] = price
    req = {"x": 600, "y": -100, "w": 400, "h": 400}  # clipped to x 600..800, y 0..300 -> 200x300
    inputs = {"feature": "image_edit", "image": put("o.png", png(orig)), "mask": put("m.png", comfy_mask(400, 400, (0, 0, 400, 400))),
              "paste": req, "prompt": "x"}
    est = await wavespeed.estimate(dict(inputs))
    quote_inputs = dict(seen[-1]) if seen else None
    fake_result(monkeypatch, np.full((512, 512, 3), 7, np.uint8))
    group = await wavespeed.submit(dict(inputs))
    [(model, payload)] = curated["submits"]
    assert model == SUNBURST and "quality" not in payload
    assert est["price"] == pytest.approx(price(payload)) and est["source"] == "quote"
    assert quote_inputs is None or quote_inputs.get("resolution") == payload.get("resolution")
    assert wavespeed._jobs[group]["box"] == {"x": 600, "y": 0, "w": 200, "h": 300}
    out = output(await finish(group))
    assert out.shape == orig.shape
    inside = np.zeros((H, W), bool)
    inside[0:300, 600:800] = True
    assert np.array_equal(out[~inside], orig[~inside])
    assert (out[inside] == 7).all()


async def test_box_fully_outside_is_400_before_any_wavespeed_call(curated):
    inputs = {"feature": "image_edit", "image": put("o.png", png(noise(256, 256))), "mask": put("m.png", comfy_mask(64, 64, (0, 0, 64, 64))),
              "paste": {"x": 300, "y": 10, "w": 64, "h": 64}, "prompt": "x"}
    before = (curated["uploads"], len(curated["quotes"]))
    for call in (wavespeed.estimate, wavespeed.submit):
        with pytest.raises(wavespeed.WaveSpeedError) as e:
            await call(dict(inputs))
        assert e.value.status == 400
    assert not curated["submits"] and (curated["uploads"], len(curated["quotes"])) == before


async def test_move_hole_edge_is_feathered_but_object_is_not(curated, monkeypatch):
    H, W = 300, 300
    orig = np.full((H, W, 3), 200, np.uint8)
    obj = (100, 100, 40, 40)
    inputs = {"feature": "move_object", "image": put("o.png", png(orig)), "mask": put("m.png", comfy_mask(H, W, obj)), "dx": 100, "dy": 100}
    fake_result(monkeypatch, np.full((384, 384, 3), 0, np.uint8))
    out = output(await finish(await wavespeed.submit(inputs)))[..., 0].astype(int)
    m = np.zeros((H, W), np.float32)
    m[100:140, 100:140] = 1
    grown = wavespeed.grow_mask(m, 12)
    ring = (wavespeed.feather_mask(grown) > 0) & (grown == 0)
    vals = out[ring]
    assert ring.any() and ((vals > 0) & (vals < 200)).mean() > 0.9  # hole edge blends erase result into the original
    row = out[120, 60:100]
    assert (np.diff(row) <= 0).all() and len(set(row.tolist())) > 3  # soft ramp, not a hard step
    assert (out[grown == 1] == 0).all()  # hole itself fully filled
    assert (out[200:240, 200:240] == 200).all()  # moved object: original pixels, no feathering


@pytest.mark.parametrize("paste,size", [({"x": 200, "y": 200, "w": 100, "h": 100}, (56, 56)),
                                        ({"x": -22, "y": -12, "w": 100, "h": 100}, (78, 88))])
async def test_clamp_sizes_for_quote_and_submitted_crop(curated, monkeypatch, paste, size):
    seen, saved = [], []
    curated["prices"][SUNBURST] = lambda inp: seen.append(dict(inp)) or 0.039
    real_save = wavespeed._save_input
    monkeypatch.setattr(wavespeed, "_save_input", lambda data, tag: saved.append((tag, data)) or real_save(data, tag))
    real_ri = wavespeed.region_inputs
    sizes = []
    monkeypatch.setattr(wavespeed, "region_inputs", lambda i, c=None: (lambda r: (c and sizes.append((r["width"], r["height"]))) or r)(real_ri(i, c)))
    inputs = {"feature": "image_edit", "image": put("o.png", png(noise(256, 256))), "mask": put("m.png", comfy_mask(100, 100, (0, 0, 100, 100))),
              "paste": paste, "prompt": "x"}
    est = await wavespeed.estimate(dict(inputs))
    await wavespeed.submit(dict(inputs))
    crop = Image.open(io.BytesIO(next(d for t, d in saved if t == "crop")))
    assert crop.size == size
    assert sizes == [size, size]  # estimate + submit both priced/sent at the clipped size
    assert est["source"] == "quote" and est["price"] == pytest.approx(0.039) and curated["submits"]


@pytest.mark.parametrize("model", [None, SUNBURST, FLARE])
async def test_189_edit_sends_no_quality_and_quote_equals_medium_charge(curated, monkeypatch, model):
    """#189: no quality pin; the mock price API (like WaveSpeed) prices a missing quality at the default medium tier,
    so quote = charge = $0.039 (sunburst/flare edit, medium, 1k)."""
    tiers = {"low": 0.013, "medium": 0.039, "high": 0.156}
    seen = []

    def price(inp):
        seen.append(dict(inp))
        return tiers[inp.get("quality", "medium")]
    for m in (SUNBURST, FLARE):
        curated["prices"][m] = price
    inputs = {"feature": "image_edit", "image": put("o.png", png(noise(256, 256))), "mask": put("m.png", comfy_mask(100, 100, (10, 10, 50, 50))),
              "paste": {"x": 20, "y": 20, "w": 100, "h": 100}, "prompt": "x", **({"model": model} if model else {})}
    est = await wavespeed.estimate(dict(inputs))
    await wavespeed.submit(dict(inputs))
    [(sent, payload)] = curated["submits"]
    assert sent == (model or SUNBURST)
    assert "quality" not in payload and all("quality" not in q for q in seen)
    assert est["source"] == "quote" and est["price"] == pytest.approx(0.039) == price(payload)
