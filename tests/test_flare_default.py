"""#134: image default is gpt-image-2.5 flare via the single 'default' field in api/curated_models.json;
Auto resolves to it and the picker order does not move. #189: no GPT Image request pins a quality tier; quality is
left out so WaveSpeed runs its schema default (medium), and the confirm price is quoted for that same tier. Mock only: no WaveSpeed calls."""
import asyncio
import json

import pytest

from ComfyArt.api import wavespeed

T2I = "openai/gpt-image-2.5-flare/text-to-image"
EDIT = "openai/gpt-image-2.5-flare/edit"
SCHEMA = {"properties": {"prompt": {}, "quality": {"enum": ["low", "medium", "high", "xhigh", "max"]}}}


def test_auto_resolves_to_flare():
    assert wavespeed.resolve_model("text_to_image", None) == T2I
    assert wavespeed.resolve_model("image_edit", None) == EDIT
    assert wavespeed.resolve_model("text_to_image", "openai/gpt-image-2/text-to-image") == "openai/gpt-image-2/text-to-image"


def test_single_default_field_and_order_unchanged():
    cur = json.loads(open(wavespeed.CURATED, encoding="utf-8").read())["features"]
    assert cur["text_to_image"]["default"] == T2I and cur["image_edit"]["default"] == EDIT
    # design rule: the dropdown keeps its order; gpt-image-2 stays a normal option in first place
    assert cur["text_to_image"]["models"][0] == "openai/gpt-image-2/text-to-image"
    models = [{"id": i, "name": i} for i in cur["text_to_image"]["models"]]
    models[3]["default"] = True
    assert wavespeed.picker_order("text_to_image", models)[0] == "openai/gpt-image-2/text-to-image"


GPT_IMAGE = [T2I, EDIT, "openai/gpt-image-2.5-sunburst/text-to-image", "openai/gpt-image-2.5-sunburst/edit",
             "openai/gpt-image-2/text-to-image", "openai/gpt-image-2/edit"]
MEDIUM_1K = 0.039  # product table: sunburst/flare edit, medium, 1k


def test_no_quality_pin_in_curated_or_auto_models():
    cur = json.loads(open(wavespeed.CURATED, encoding="utf-8").read())["features"]
    for name, f in cur.items():
        assert "quality" not in (f.get("default_params") or {}), name
    for m in GPT_IMAGE:
        assert "quality" not in wavespeed.model_defaults(m), m
    auto = open(wavespeed.CURATED.replace("curated_models.json", "auto_models.json"), encoding="utf-8").read()
    assert '"quality"' not in auto


@pytest.mark.parametrize("model", GPT_IMAGE)
def test_payload_omits_quality_unless_user_picks(model):
    p = asyncio.run(wavespeed.build_payload(None, SCHEMA, {"prompt": "x"}, model))
    assert "quality" not in p
    p = asyncio.run(wavespeed.build_payload(None, SCHEMA, {"prompt": "x", "params": {"quality": "max"}}, model))
    assert p["quality"] == "max"  # an explicit user pick still goes through unchanged


@pytest.mark.parametrize("inputs,tier", [({"feature": "text_to_image"}, None),
                                         ({"feature": "image_edit"}, None),
                                         ({"feature": "text_to_image", "model": T2I, "params": {"quality": "high"}}, "high")])
def test_confirm_price_is_for_chosen_tier(monkeypatch, inputs, tier):
    seen = []
    prices = {"low": 0.024, "medium": 0.06, "high": 0.18}

    async def fake_quote(model, inp):
        q = wavespeed._price_inputs(inp, model)
        seen.append((model, q.get("quality")))
        return prices[q.get("quality") or "medium"], "quote"  # unset = WaveSpeed default tier (medium)
    monkeypatch.setattr(wavespeed, "quote", fake_quote)
    est = asyncio.run(wavespeed.estimate(inputs))
    assert seen[0][1] == tier and est["price"] == prices[tier or "medium"]
    assert seen[0][0] in (T2I, EDIT)
