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


_JOB = {"feature": "structure_control", "prompt": "p", "width": 512, "height": 512}


async def test_confirm_quotes_upper_bound_and_nothing_is_submitted_before_confirm(maps, monkeypatch):
    """#138 product: no charge before the confirm dialog. The quote is caption + 12 sam3 (upper bound)."""
    maps["by_model"] = {CAP: ["a dog next to a car"]}
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0.001)
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({**_JOB, "controls": [_ctl("seg", _photo())]})
    assert e.value.status == 409 and e.value.seg_splits == 12 and e.value.seg_capped is True
    assert e.value.confirm == round(0.03 + 0.001 + 12 * 0.005, 6)
    assert maps["submits"] == []  # WaveSpeed received 0 submits before confirm (no captioner either)
    resp = json.loads(wavespeed._respond_error(e.value).body)
    assert resp["error"]["seg_splits"] == 12 and resp["error"]["seg_capped"] is True


async def test_confirmed_job_charges_per_class_found(maps):
    maps["by_model"] = {CAP: ["a dog next to a car"]}
    await wavespeed.submit({**_JOB, "confirmed": True, "controls": [_ctl("seg", _photo())]})
    assert [m for m, _ in maps["submits"]] == [CAP, SAM, SAM, FLUX]  # caption, 2 classes, then the job


async def test_all_black_classes_stop_before_sam3(maps):
    """#138 product: only 'person' (black in upstream palette, same as unlabeled) -> stop, recognition only."""
    maps["by_model"] = {CAP: ["a man and a woman standing"]}
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({**_JOB, "confirmed": True, "controls": [_ctl("seg", _photo())]})
    assert str(e.value) == wavespeed.SEG_ALL_BLACK and e.value.status == 422
    assert [m for m, _ in maps["submits"]] == [CAP]  # 0 sam3 calls
    assert refprep.SEG_COLORS["person"] == (0, 0, 0)  # palette unchanged


async def test_retry_reruns_only_failed_classes(maps, monkeypatch):
    """#138 product: masks cached per (image, class); a retry never resubmits a class that succeeded,
    and the confirm on retry quotes only the classes still missing."""
    maps["by_model"] = {CAP: ["a dog next to a car and a bus"]}
    ref = _photo()
    real = wavespeed._cloud_map
    asked = []
    fail = {"car"}

    async def flaky(feature, params, image, prompt=None):
        asked.append(prompt)
        if prompt in fail:
            raise wavespeed.WaveSpeedError("sam3 failed", 502)
        return await real(feature, params, image, prompt)
    monkeypatch.setattr(wavespeed, "_cloud_map", flaky)
    with pytest.raises(wavespeed.WaveSpeedError):
        await wavespeed.submit({**_JOB, "confirmed": True, "controls": [_ctl("seg", ref)]})
    assert asked == ["dog", "car"]
    fail.clear()
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0.001)
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({**_JOB, "controls": [_ctl("seg", ref)]})
    assert e.value.seg_splits == 2 and e.value.seg_capped is False  # car + bus, no second caption
    assert e.value.confirm == round(0.03 + 2 * 0.005, 6)
    await wavespeed.submit({**_JOB, "confirmed": True, "controls": [_ctl("seg", ref)]})
    assert asked == ["dog", "car", "car", "bus"]  # dog never resubmitted
    assert [m for m, _ in maps["submits"]].count(CAP) == 1


def test_zh_en_strings():
    loc = os.path.join(os.path.dirname(refprep.__file__), "..", "src", "locales")
    zh = json.load(open(os.path.join(loc, "zh.json"), encoding="utf-8"))
    en = json.load(open(os.path.join(loc, "en.json"), encoding="utf-8"))
    assert zh["jobs.confirmSegMax"].startswith("最多 ${0}（识别加最多 {1} 次分割）")
    assert "{0}" in en["jobs.confirmSegMax"] and "{1}" in en["jobs.confirmSegMax"]
    assert "仅收识别费用" in zh["jobs.segNone"] and en["jobs.segNone"] == wavespeed.SEG_NONE
    assert zh["jobs.segAllBlack"] == "只识别到与背景同色的类别，分割图会是全黑，已停止，仅收识别费用"
    assert en["jobs.segAllBlack"] == wavespeed.SEG_ALL_BLACK


async def test_reextract_always_reconfirms_with_zero_submits(maps, monkeypatch):
    """#138 tester: 「重新提取」 on an already extracted seg ref must show the confirm (upper bound) and
    make 0 WaveSpeed submits until confirmed, even though recognition and masks were cached."""
    maps["by_model"] = {CAP: ["a dog next to a car"]}
    ref = _photo()
    await wavespeed.control_preview({"image": ref, "mode": "seg", "res": 512, "confirmed": True})
    assert wavespeed._seg_cats and wavespeed._seg_masks  # extracted once, caches filled
    before = len(maps["submits"])
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0.001)
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.control_preview({"image": ref, "mode": "seg", "res": 512, "fresh": True})
    assert e.value.status == 409 and e.value.seg_splits == 12 and e.value.seg_capped is True
    assert e.value.confirm == round(0.001 + 12 * 0.005, 6)
    assert len(maps["submits"]) == before  # 0 submits for the unconfirmed re-extract
