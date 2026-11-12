"""#910 follow-up: GPT Image 2.5-series prices, and a record of every other edit model on the
gif_image / canvas quote paths, measured with WaveSpeed's free POST /api/v3/model/price.

2.5 (tests/fixtures/wavespeed_price_2_5_910.json, 2026-11-12 08:27:29-08:28:25 Asia/Shanghai,
balance 29.848866 unchanged): every quality x resolution cell matches TABLE_25; an edit is that
cell + $0.015 per input image (images + mask_image). markup_image did not change the 2.5 price.
STILL_MEDIUM_1K for openai/gpt-image-2.5-flare/text-to-image medium 1k stays $0.024 (re-measured,
unchanged). Charged price equals list (discount_rate 100).

Other edit models are recorded in tests/fixtures/wavespeed_price_other_edits_910.json only; this
PR does not add a price-API-down table for them.

Mocks only: no key, no network, $0.
"""
from __future__ import annotations

import json
from pathlib import Path

import aiohttp
import pytest

from ComfyArt.api import gif_image, wavespeed

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
LIVE_25 = json.loads((FIX / "wavespeed_price_2_5_910.json").read_text())["rows"]
LIVE_OTHER = json.loads((FIX / "wavespeed_price_other_edits_910.json").read_text())["rows"]
CATALOG = json.loads((FIX / "wavespeed_catalog_subset.json").read_text())

FLARE_25_T2I = "openai/gpt-image-2.5-flare/text-to-image"
SUNBURST_25_T2I = "openai/gpt-image-2.5-sunburst/text-to-image"
FLARE_25_EDIT = "openai/gpt-image-2.5-flare/edit"
SUNBURST_25_EDIT = "openai/gpt-image-2.5-sunburst/edit"
FOUR_25 = (FLARE_25_T2I, FLARE_25_EDIT, SUNBURST_25_T2I, SUNBURST_25_EDIT)


def _live(model, quality="medium", resolution="1k", images=0, **extra):
    for r in LIVE_25:
        if (r["model_id"], r["quality"], r["resolution"], r["images"]) == (model, quality, resolution, images) \
                and all(r.get(k) == v for k, v in extra.items()) \
                and (extra or not (r.get("mask_image") or r.get("markup_image") or r.get("default_inputs"))):
            return r
    raise KeyError((model, quality, resolution, images, extra))


@pytest.fixture
def cat(monkeypatch):
    async def catalog():
        return {m: CATALOG[m] for m in FOUR_25}

    monkeypatch.setattr(wavespeed, "catalog", catalog)
    wavespeed._quotes.clear()
    yield
    wavespeed._quotes.clear()


@pytest.mark.parametrize("model,list_usd,inputs", [
    (FLARE_25_T2I, 0.024, 0),
    (SUNBURST_25_T2I, 0.024, 0),
    (FLARE_25_EDIT, 0.039, 1),
    (SUNBURST_25_EDIT, 0.039, 1),
])
def test_catalog_base_price_of_the_four_2_5_models(model, list_usd, inputs):
    assert CATALOG[model]["base_price"] == list_usd
    assert wavespeed.base_price_of(model, CATALOG[model]) == list_usd
    assert gif_image.documented_usd(model, "medium", "1k", inputs) == list_usd


def test_still_medium_1k_2_5_flare_is_unchanged():
    assert gif_image.STILL_MEDIUM_1K[FLARE_25_T2I] == 0.024
    assert gif_image.TABLE_25[("medium", "1k")] == 0.024
    assert gif_image.documented_usd(FLARE_25_T2I) == 0.024


@pytest.mark.parametrize(
    "row",
    LIVE_25,
    ids=lambda r: f"{r['model_id']}:{r['quality']}:{r['resolution']}:{r['images']}"
    + (":mask" if r.get("mask_image") else "")
    + (":markup" if r.get("markup_image") else "")
    + (":default" if r.get("default_inputs") else ""),
)
def test_price_table_matches_every_recorded_2_5_price_api_cell(row):
    n = row["images"] + (1 if row.get("mask_image") else 0)
    # markup_image was sent and did not change the 2.5 price, so it is not counted.
    if row["model_id"].endswith("/text-to-image"):
        assert gif_image.TABLE_25[(row["quality"], row["resolution"])] == row["price"]
    assert gif_image.documented_usd(row["model_id"], row["quality"], row["resolution"], n) == row["price"]
    assert row["discount_rate"] == 100
    assert row["discounted_price"] == row["price"]


def test_2_5_edit_input_surcharge_is_the_recorded_step():
    assert gif_image.EDIT_INPUT_USD == 0.015
    for m in (FLARE_25_EDIT, SUNBURST_25_EDIT):
        assert _live(m, images=0)["price"] == 0.024
        assert _live(m, images=1)["price"] == 0.039
        assert _live(m, images=2)["price"] == 0.054
        assert _live(m, images=1, mask_image=True)["price"] == 0.054
        assert _live(m, images=1, markup_image=True)["price"] == 0.039


@pytest.mark.parametrize("model", [FLARE_25_EDIT, SUNBURST_25_EDIT])
async def test_price_api_down_2_5_edit_estimate_counts_input_images(cat, monkeypatch, model):
    class Down:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            raise aiohttp.ClientError("down")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(wavespeed.aiohttp, "ClientSession", Down)
    monkeypatch.setattr(wavespeed, "_headers", lambda: {})
    for n, usd in ((1, 0.039), (2, 0.054), (3, 0.069)):
        price, source = await wavespeed.quote(model, {"feature": "image_edit", "prompt": "p", "images": [f"r{i}.png" for i in range(n)]})
        assert (price, source) == (usd, "estimate")
    price, _ = await wavespeed.quote(model, {"feature": "image_edit", "prompt": "p", "images": ["r.png"], "quality": "high", "resolution": "2k"})
    assert price == _live(model, "high", "2k", 1)["price"] == 0.165


@pytest.mark.parametrize("model", [FLARE_25_T2I, SUNBURST_25_T2I])
async def test_price_api_down_2_5_t2i_uses_the_cell(cat, monkeypatch, model):
    class Down:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            raise aiohttp.ClientError("down")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(wavespeed.aiohttp, "ClientSession", Down)
    monkeypatch.setattr(wavespeed, "_headers", lambda: {})
    price, source = await wavespeed.quote(model, {"feature": "text_to_image", "prompt": "p"})
    assert (price, source) == (0.024, "estimate")
    price, source = await wavespeed.quote(model, {"feature": "text_to_image", "prompt": "p", "quality": "max", "resolution": "4k"})
    assert (price, source) == (1.00, "estimate")


@pytest.mark.parametrize(
    "row",
    LIVE_OTHER,
    ids=lambda r: f"{r['model_id']}:{r['group']}:{r.get('quality') or r.get('resolution') or 'default'}:n{r['images']}"
    + (":mask" if r.get("mask_image") or r.get("mask_url") else ""),
)
def test_other_edit_models_are_recorded_not_guessed(row):
    """Every other canvas/gif_image quote-path edit model was measurable. No price-API-down table is added."""
    assert isinstance(row["price"], (int, float)) and not isinstance(row["price"], bool)
    assert row["discounted_price"] is not None
    assert row["discount_rate"] in (90, 100)
    assert gif_image.documented_usd(row["model_id"], str(row.get("quality") or "medium"), str(row.get("resolution") or "1k"), row["images"]) is None


def test_other_edit_recorded_rules_match_the_fixture():
    def prices(mid, resolution=None, quality=None, group="other-edit"):
        out = {}
        for r in LIVE_OTHER:
            if r["model_id"] != mid or r["group"] != group:
                continue
            if resolution is not None and r.get("resolution") != resolution:
                continue
            if quality is not None and r.get("quality") != quality:
                continue
            if r.get("mask_image") or r.get("mask_url"):
                continue
            out[r["images"]] = r["price"]
        return out

    assert prices("alibaba/qwen-image-3.0/edit", "1k") == {0: 0.03, 1: 0.033, 2: 0.036, 3: 0.039}
    assert prices("alibaba/qwen-image-3.0/edit", "2k") == {0: 0.03, 1: 0.033, 2: 0.036, 3: 0.039}
    assert prices("wavespeed-ai/qwen-image-2.0/edit") == {0: 0.03, 1: 0.03, 2: 0.03, 3: 0.03}
    assert prices("google/nano-banana-2.1/edit", "1k") == {0: 0.04, 1: 0.042, 2: 0.044}
    assert prices("google/nano-banana-2.1/edit", "2k") == {0: 0.06, 1: 0.062, 2: 0.064}
    assert prices("google/nano-banana-2.1/edit", "4k") == {0: 0.135, 1: 0.137, 2: 0.139}
    assert prices("google/nano-banana-pro/edit", "1k") == {0: 0.14, 1: 0.14, 2: 0.14}
    assert prices("google/nano-banana-pro/edit", "2k") == {0: 0.14, 1: 0.14, 2: 0.14}
    assert prices("google/nano-banana-pro/edit", "4k") == {0: 0.24, 1: 0.24, 2: 0.24}
    assert prices("bytedance/seedream-v5.0-pro/edit", "1k") == {0: 0.045, 1: 0.045, 2: 0.048}
    assert prices("bytedance/seedream-v5.0-pro/edit", "1.5k") == {0: 0.045, 1: 0.045, 2: 0.048}
    assert prices("bytedance/seedream-v5.0-pro/edit", "2k") == {0: 0.09, 1: 0.09, 2: 0.093}
    assert prices("black-forest-labs/flux-3/image-edit", "1k") == {0: 0.048, 1: 0.048, 2: 0.048}
    assert prices("black-forest-labs/flux-3/image-edit", "2k") == {0: 0.1, 1: 0.1, 2: 0.1}
    assert prices("black-forest-labs/flux-3/image-edit", "4k") == {0: 0.607, 1: 0.607, 2: 0.607}
    assert prices("wavespeed-ai/flux-2-klein-9b/edit") == {0: 0.016, 1: 0.016, 2: 0.016, 3: 0.016}
    assert prices("ideogram-ai/ideogram-v4.5/edit", quality="very_low", group="other-edit-ideogram") == {0: 0.008, 1: 0.008, 2: 0.008, 3: 0.008}
    assert prices("ideogram-ai/ideogram-v4.5/edit", quality="low", group="other-edit-ideogram") == {0: 0.03, 1: 0.03, 2: 0.03, 3: 0.03}
    assert prices("ideogram-ai/ideogram-v4.5/edit", quality="medium", group="other-edit-ideogram") == {0: 0.06, 1: 0.06, 2: 0.06, 3: 0.06}
    assert prices("ideogram-ai/ideogram-v4.5/edit", quality="high", group="other-edit-ideogram") == {0: 0.22, 1: 0.22, 2: 0.22, 3: 0.22}
