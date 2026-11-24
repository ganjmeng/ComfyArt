"""#425: catalog / cost display follow the schema-default quote, not WaveSpeed's cheapest-tier base_price.

pruna-ai/p-image/ideogram lists $0.003 (thinking=very low) while schema default thinking=high —
and a prompt-only submit — quotes and bills $0.015. Product (YohakuX 2026-10-30): catalog price
and cost display must match the actual quote. thinking is a priced tier field like quality.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ComfyArt.api import wavespeed
from ComfyArt.tests.test_wavespeed import MODELS, _meta, ws  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
IDEO = "pruna-ai/p-image/ideogram"
THINK = ["very low", "low", "medium", "high"]
# Live WaveSpeed POST /api/v3/model/price (2026-10-30): default / omitted thinking → $0.015;
# thinking=very low → $0.003 (the old catalog figure).
TABLE = {"very low": 0.003, "low": 0.005, "medium": 0.01, "high": 0.015}


def _ideo_props():
    return {
        "prompt": {"type": "string"},
        "aspect_ratio": {"type": "string", "enum": ["1:1", "16:9", "9:16"], "default": "1:1"},
        "thinking": {"type": "string", "enum": THINK, "default": "high"},
        "output_format": {"type": "string", "enum": ["png", "jpeg", "webp"], "default": "png"},
    }


@pytest.fixture
def ideo(ws, monkeypatch):
    # Simulate live WaveSpeed: catalog still advertises the cheapest tier ($0.003).
    MODELS.append(_meta(IDEO, _ideo_props(), ("prompt",), price=0.003))
    yield ws
    MODELS[:] = [m for m in MODELS if m["model_id"] != IDEO]


def per_tier(inputs):
    t = inputs.get("thinking", "high")  # omitted → schema default
    if t not in TABLE:
        raise ValueError("invalid thinking")
    return TABLE[t]


def test_catalog_price_fix_overrides_cheapest_tier_listing():
    assert wavespeed.CATALOG_PRICE_FIXES[IDEO] == 0.015
    # Raw WaveSpeed-shaped meta still says 0.003; readers must see the quote price.
    raw = {"base_price": 0.003, "name": IDEO}
    assert wavespeed.base_price_of(IDEO, raw) == 0.015
    patched = wavespeed.apply_catalog_price_fixes({IDEO: dict(raw)})
    assert patched[IDEO]["base_price"] == 0.015
    assert wavespeed.base_price_of("acme/other", {"base_price": 0.04}) == 0.04
    assert wavespeed.base_price_of("acme/missing", None) is None


async def test_grouped_models_exposes_quote_price_not_cheapest(ideo):
    groups = await wavespeed.grouped_models()
    found = None
    for feat in groups.values():
        for m in feat.get("models") or []:
            if m["id"] == IDEO:
                found = m
                break
    assert found is not None, "ideogram must be curated"
    assert found["price"] == 0.015


async def test_quote_matches_thinking_tier(ideo):
    ideo["prices"][IDEO] = per_tier
    job = {"feature": "text_to_image", "model": IDEO, "prompt": "a cat"}
    # Omit thinking → WaveSpeed schema default high → $0.015
    price, src = await wavespeed.quote(IDEO, job)
    assert src == "quote" and price == pytest.approx(0.015)
    assert "thinking" not in ideo["quotes"][-1]["inputs"] or ideo["quotes"][-1]["inputs"].get("thinking") == "high"
    # Explicit cheap tier → $0.003 (catalog used to show this for every run)
    price_low, src_low = await wavespeed.quote(IDEO, {**job, "thinking": "very low"})
    assert src_low == "quote" and price_low == pytest.approx(0.003)
    assert ideo["quotes"][-1]["inputs"]["thinking"] == "very low"


async def test_price_api_down_default_thinking_estimates_quote_price(ideo, monkeypatch):
    ideo["prices"].pop(IDEO, None)  # force catalog / estimate path
    job = {"feature": "text_to_image", "model": IDEO, "prompt": "a cat"}
    est = await wavespeed.estimate(job)
    assert est["source"] == "estimate" and est["price"] == pytest.approx(0.015)


async def test_price_api_down_non_default_thinking_is_unpriced(ideo):
    ideo["prices"].pop(IDEO, None)
    job = {"feature": "text_to_image", "model": IDEO, "prompt": "a cat", "thinking": "very low"}
    est = await wavespeed.estimate(job)
    # Must not fall back to catalog $0.015 (or the old $0.003) for a non-default tier.
    assert est["source"] == "unpriced" and est["price"] is None and est["confirm"] is True


def test_fixture_base_price_matches_schema_default_quote():
    cat = json.loads((ROOT / "tests/fixtures/wavespeed_catalog_subset.json").read_text())
    assert cat[IDEO]["base_price"] == 0.015
    props = cat[IDEO]["api_schema"]["api_schemas"][0]["request_schema"]["properties"]
    # Fixture strips schema defaults; live WaveSpeed default is "high" (verified 2026-10-30).
    assert "high" in (props.get("thinking") or {}).get("enum") or []
    assert "thinking" in wavespeed._PRICE_FIELDS
    src = (ROOT / "api/wavespeed.py").read_text()
    assert "CATALOG_PRICE_FIXES" in src and "apply_catalog_price_fixes" in src


def test_thinking_is_a_default_tier_field():
    props = _ideo_props()
    assert wavespeed._is_default_tier(props, {}) is True
    assert wavespeed._is_default_tier(props, {"thinking": "high"}) is True
    assert wavespeed._is_default_tier(props, {"thinking": "very low"}) is False
