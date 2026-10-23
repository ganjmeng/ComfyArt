"""#120: sam3-image always gets a prompt type (text, boxes or points); an empty request is stopped
before submit. Mock WaveSpeed server only (no real calls)."""
from __future__ import annotations

import pytest

from ComfyArt.api import wavespeed
from tests.test_ref_structure import FLUX, SAM, _ctl, _photo, maps  # noqa: F401  (fixtures)
from tests.test_wavespeed import _input_png, ws  # noqa: F401


async def test_edit_elements_boxes_and_points_are_sent_as_given(ws):
    image = _input_png()
    box = [{"x_min": 1, "y_min": 1, "x_max": 5, "y_max": 6}]
    await wavespeed.submit({"feature": "segment", "image": image, "prompt": "logo", "params": {"box_prompts": box}})
    payload = ws["submits"][0][1]
    assert payload["box_prompts"] == box


async def test_edit_elements_object_description_is_the_text_prompt(ws):
    await wavespeed.submit({"feature": "segment", "image": _input_png(), "object": "the red cup", "params": {"apply_mask": False}})
    model, payload = ws["submits"][0]
    assert model == SAM and payload["prompt"] == "the red cup"
    assert "box_prompts" not in payload and "point_prompts" not in payload


async def test_edit_elements_without_text_falls_back_to_full_image_box(ws):
    await wavespeed.submit({"feature": "segment", "image": _input_png(), "params": {"apply_mask": False}})
    payload = ws["submits"][0][1]
    assert payload["box_prompts"] == [{"x_min": 0, "y_min": 0, "x_max": 8, "y_max": 8}]
    assert "prompt" not in payload


async def test_empty_segment_request_is_blocked_before_submit(ws):
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "segment", "params": {"apply_mask": False}})
    assert str(e.value) == wavespeed.SEG_TARGET_MISSING and e.value.status == 400
    assert ws["submits"] == []  # nothing sent, nothing charged


async def test_unreadable_image_without_text_is_blocked_before_submit(ws):
    with pytest.raises(wavespeed.WaveSpeedError, match="segment first"):
        await wavespeed.submit({"feature": "segment", "image": "missing.png [input]"})
    assert ws["submits"] == []


async def test_structure_seg_passes_generation_prompt_as_text(maps):
    wavespeed._map_cache.clear()
    await wavespeed.submit({"feature": "structure_control", "prompt": "a cozy living room", "width": 512, "height": 512,
                            "controls": [_ctl("seg", _photo())]})
    (m1, pre), (m2, _) = maps["submits"]
    assert (m1, m2) == (SAM, FLUX)
    assert pre["prompt"] == "a cozy living room" and "box_prompts" not in pre


async def test_structure_seg_without_prompt_uses_full_image_box(maps):
    wavespeed._map_cache.clear()
    await wavespeed.submit({"feature": "structure_control", "prompt": "", "width": 512, "height": 512,
                            "controls": [_ctl("seg", _photo())]})
    pre = maps["submits"][0][1]
    assert maps["submits"][0][0] == SAM and "prompt" not in pre
    box = pre["box_prompts"][0]
    assert box["x_min"] == 0 and box["y_min"] == 0 and box["x_max"] > 0 and box["y_max"] > 0
