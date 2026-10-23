"""#182: the storyboard estimate prices exactly the params that are submitted. A field the chained model's schema
doesn't take (e.g. duration) is dropped from the submit, so it must not price either, including when the model's
schema is empty (model missing from the catalog). Mocks only: no network, no charge."""
from __future__ import annotations

import copy

import pytest

from test_wavespeed import MODELS, uncurated, wavespeed, ws  # noqa: F401  (fixtures)

T2V = "wavespeed-ai/minimax-h3/text-to-video"
I2V = "wavespeed-ai/minimax-h3/image-to-video"
PRICED = ("duration", "resolution", "quality", "aspect_ratio", "size")
SCENES = [{"prompt": "skyline", "duration": 5}, {"prompt": "cat jumps", "duration": 8}, {"prompt": "cat yawns", "duration": 4}]
BOARD = {"feature": "text_to_video", "model": T2V, "prompt": "storyboard", "duration": 5, "scenes": SCENES}


def per_second(inputs: dict) -> float:
    # mock price API: $0.10/s for the duration it is asked about; without one the model runs its 5 s default
    return round(0.1 * int(inputs.get("duration", 5)), 4)


def scene_jobs():
    # the same per-scene jobs _submit_scenes builds (first scene on T2V, the rest chained on image-to-video)
    return [{**{k: v for k, v in BOARD.items() if k != "scenes"}, "feature": "text_to_video" if i == 0 else "image_to_video",
             "model": T2V if i == 0 else I2V, "image": None if i == 0 else "https://cdn.test/last-frame.png",
             "confirmed": True, "prompt": sc["prompt"], "duration": sc["duration"]} for i, sc in enumerate(SCENES)]


async def billed(ws) -> tuple[list[dict], float]:
    """Submit every scene as the chain would and price what was actually sent."""
    for job in scene_jobs():
        await wavespeed.submit({k: v for k, v in job.items() if v is not None})
    payloads = [p for _, p in ws["submits"]]
    return payloads, round(sum(per_second(p) for p in payloads), 4)


async def quoted_inputs() -> list[dict]:
    # what the quote prices per scene (identical bodies are served from the 5-minute quote cache, so read them here)
    return [await wavespeed.priced_inputs(j["model"], j) for j in scene_jobs()]


def chain_meta():
    return next(m for m in MODELS if m["model_id"] == I2V)


@pytest.fixture
def priced(ws):
    ws["prices"].update({T2V: per_second, I2V: per_second})
    return ws


async def test_chain_schema_without_duration_quotes_what_is_submitted(priced, monkeypatch):
    schema = chain_meta()["api_schema"]["api_schemas"][0]["request_schema"]
    monkeypatch.setitem(schema, "properties", {k: v for k, v in schema["properties"].items() if k != "duration"})
    est = await wavespeed.estimate(copy.deepcopy(BOARD))
    quoted = await quoted_inputs()
    payloads, charge = await billed(priced)
    assert [p.get("duration") for p in payloads] == [5, None, None]  # submit drops duration on the chain model
    assert quoted == [{"duration": 5}, {}, {}]  # ...and so does the quote
    for q, p in zip(quoted, payloads):
        assert q == {k: p[k] for k in PRICED if k in p}
    assert est["price"] == charge == pytest.approx(0.5 + 0.5 + 0.5) and est["source"] == "quote"


async def test_chain_model_missing_from_catalog_quotes_what_is_submitted(priced, monkeypatch):
    # empty schema: build_payload sends no priced field, so the quote must not invent one (the old code priced 8 s / 4 s)
    monkeypatch.setattr("test_wavespeed.MODELS", [m for m in MODELS if m["model_id"] != I2V])
    monkeypatch.setitem(wavespeed._catalog, "models", {})  # refetch from the patched mock
    est = await wavespeed.estimate(copy.deepcopy(BOARD))
    quoted = await quoted_inputs()
    payloads, charge = await billed(priced)
    assert [p.get("duration") for p in payloads] == [5, None, None]
    assert quoted == [{"duration": 5}, {}, {}]
    assert est["price"] == charge == pytest.approx(1.5)


async def test_chain_schema_with_duration_unchanged(priced):
    est = await wavespeed.estimate(copy.deepcopy(BOARD))
    quoted = await quoted_inputs()
    payloads, charge = await billed(priced)
    assert [p.get("duration") for p in payloads] == [5, 8, 4]
    assert quoted == [{"duration": 5}, {"duration": 8}, {"duration": 4}]
    assert est["price"] == charge == pytest.approx(0.5 + 0.8 + 0.4)
