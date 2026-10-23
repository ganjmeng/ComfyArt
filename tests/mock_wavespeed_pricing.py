"""Pricing for the mock WaveSpeed server used for docs screenshots and manual e2e runs (#211).

Every model is priced at its catalog ``base_price``: first the recorded catalog subset
(tests/fixtures/wavespeed_catalog_subset.json), then any extra catalog entries the caller passes in
(e.g. test_wavespeed.MODELS). There is no hardcoded fallback price: a model missing from the catalog
gets ``None`` so the mock answers with an error instead of inventing a
number (the old mock showed placeholder tier prices for anything outside the fixture).
"""
import json
import pathlib

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json"


def load_catalog(extra=()):
    cat = {m["model_id"]: m for m in extra if m.get("model_id")}
    cat.update(json.loads(FIXTURE.read_text(encoding="utf-8")))
    return cat


def mock_price(model_id, catalog):
    m = catalog.get(model_id or "")
    return None if m is None else m.get("base_price")
