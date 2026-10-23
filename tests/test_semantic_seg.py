"""#135: upstream's OneFormer COCO seg map rebuilt in the cloud (captioner -> sam3 per class -> upstream palette).
Mock WaveSpeed server only, no real calls."""
from __future__ import annotations

import io
import json
import os

import pytest
from PIL import Image, ImageDraw

from ComfyArt.api import refprep, wavespeed
from tests.test_ref_structure import CAP, FLUX, SAM, _ctl, _photo, maps  # noqa: F401  (fixtures)
from tests.test_wavespeed import ws  # noqa: F401


def _mask(box):
    m = Image.new("L", (64, 48), 0)
    ImageDraw.Draw(m).rectangle(box, fill=255)
    return refprep.to_png(m)


def test_palette_is_upstream_fixed_and_one_to_one():
    pal = json.load(open(os.path.join(os.path.dirname(refprep.__file__), "seg_palette.json"), encoding="utf-8"))
    assert len(pal["labels"]) == len(pal["colors"]) == 133 and "a587a4c" in pal["_source"]
    # spot values from upstream _generate_detectron2_style_palette (class 0 black, golden-angle HSV, OpenCV)
    assert refprep.SEG_COLORS["person"] == (0, 0, 0)
    assert refprep.SEG_COLORS["bicycle"] == (51, 255, 105)
    assert refprep.SEG_COLORS["car"] == (101, 0, 178)
    assert refprep.SEG_COLORS["motorcycle"] == (255, 235, 102)
    assert len(set(map(tuple, pal["colors"]))) == 133  # one class, one color


def test_categories_from_caption_are_capped_at_12():
    text = "a man and a dog by a car, a bicycle, a bus, a train, a truck, a boat, a bench, a bird, a cat, a horse, a sheep, a cow"
    cats = refprep.seg_categories(text)
    assert cats[:3] == ["person", "dog", "car"] and len(cats) == 12
    assert refprep.seg_categories("a swirling abstract gradient") == []


async def test_multi_class_map_is_composited_in_upstream_colors(maps, monkeypatch):
    maps["by_model"] = {CAP: ["a dog next to a car"]}
    masks = {"dog": _mask((0, 0, 20, 20)), "car": _mask((30, 20, 63, 47))}
    prompts = []

    async def fake_cloud(feature, params, image, prompt=None):
        prompts.append(prompt)
        return masks[prompt]
    monkeypatch.setattr(wavespeed, "_cloud_map", fake_cloud)
    png = await wavespeed._semantic_map(_photo())
    img = Image.open(io.BytesIO(png)).convert("RGB")
    assert prompts == ["dog", "car"]  # one sam3 call per class, class name as the prompt
    assert img.getpixel((5, 5)) == refprep.SEG_COLORS["dog"]
    assert img.getpixel((40, 30)) == refprep.SEG_COLORS["car"]
    assert img.getpixel((60, 2)) == (0, 0, 0)  # unlabeled stays black, like upstream


async def test_zero_classes_errors_without_any_sam3_charge(maps):
    maps["by_model"] = {CAP: ["a swirling abstract gradient"]}
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "structure_control", "prompt": "p", "width": 512, "height": 512,
                                "controls": [_ctl("seg", _photo())]})
    assert str(e.value) == wavespeed.SEG_NONE and e.value.status == 422
    assert [m for m, _ in maps["submits"]] == [CAP]  # no sam3, no flux


async def test_confirm_quotes_caption_plus_n_splits(maps, monkeypatch):
    maps["by_model"] = {CAP: ["a dog next to a car"]}
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0.001)
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "structure_control", "prompt": "p", "width": 512, "height": 512,
                                "controls": [_ctl("seg", _photo())]})
    assert e.value.status == 409 and e.value.seg_splits == 2
    assert e.value.confirm == round(0.03 + 0.001 + 2 * 0.005, 6)
    assert [m for m, _ in maps["submits"]] == [CAP]


def test_zh_en_strings():
    loc = os.path.join(os.path.dirname(refprep.__file__), "..", "src", "locales")
    zh = json.load(open(os.path.join(loc, "zh.json"), encoding="utf-8"))
    en = json.load(open(os.path.join(loc, "en.json"), encoding="utf-8"))
    assert zh["jobs.segNone"] == "未识别到可分割的对象" and "识别加 {0} 次分割" in zh["jobs.confirmSegSplits"]
    assert en["jobs.segNone"] == wavespeed.SEG_NONE and "{0}" in en["jobs.confirmSegSplits"]
