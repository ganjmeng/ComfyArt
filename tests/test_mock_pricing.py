"""#211: the mock WaveSpeed price endpoint returns each model's catalog base_price, never a placeholder."""
import json
import pathlib
import re

from mock_wavespeed_pricing import load_catalog, mock_price

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _curated_ids():
    ids = set()

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str) and re.fullmatch(r"[a-z0-9.-]+(/[A-Za-z0-9._-]+)+", o):
            ids.add(o)

    walk(json.loads((ROOT / "api" / "curated_models.json").read_text(encoding="utf-8")))
    return ids


def test_every_curated_model_priced_at_catalog_base_price():
    cat = load_catalog()
    ids = _curated_ids()
    assert len(ids) > 50
    for mid in ids:
        assert mid in cat, mid
        assert mock_price(mid, cat) == cat[mid]["base_price"], mid


def test_lora_models_match_quoted_prices():
    cat = load_catalog()
    assert mock_price("wavespeed-ai/flux-dev-lora", cat) == 0.015
    assert mock_price("wavespeed-ai/qwen-image/text-to-image-lora", cat) == 0.025


def test_no_placeholder_fallback():
    cat = load_catalog()
    assert mock_price("acme/not-in-catalog", cat) is None
    assert mock_price("", cat) is None
    src = (ROOT / "tests" / "mock_wavespeed_pricing.py").read_text(encoding="utf-8")
    assert "0.039" not in src and "0.156" not in src


def test_extra_catalog_entries_used_but_fixture_wins():
    extra = [{"model_id": "acme/my-edit", "base_price": 0.03},
             {"model_id": "wavespeed-ai/flux-dev-lora", "base_price": 9.0}]
    cat = load_catalog(extra)
    assert mock_price("acme/my-edit", cat) == 0.03
    assert mock_price("wavespeed-ai/flux-dev-lora", cat) == 0.015
