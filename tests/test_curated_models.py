"""#95: api/curated_models.json is the single source for the picker and list_models.
Fixture/mock only: no network, and nothing here imports scripts/check_curated_models.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from ComfyArt.api import wavespeed
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot._cli_common import TOOL_RESULT_CAP

ROOT = Path(__file__).parent.parent
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())
CURATED = wavespeed.load_curated()
RAW = json.loads((ROOT / "api" / "wavespeed_models.json").read_text())


@pytest.fixture(autouse=True)
def mock_catalog(monkeypatch):
    async def fake_catalog(refresh=False):
        return FIXTURE
    monkeypatch.setattr(wavespeed, "catalog", fake_catalog)
    monkeypatch.setattr(canvas, "grouped_models", wavespeed.grouped_models)


def _rec(c):
    """#134: curated 'models', plus the explicit default when it sits in 'more' (flare edit)."""
    d = c.get("default")
    return c["models"] + ([d] if d and d not in c["models"] else [])


def _props(mid):
    return FIXTURE[mid]["api_schema"]["api_schemas"][0]["request_schema"]["properties"]


CURATED_IDS = [(f, m) for f, c in CURATED.items() for m in c["models"] + c.get("more", [])]


@pytest.mark.parametrize("feature,mid", CURATED_IDS)
def test_curated_id_in_catalog_with_declared_params(feature, mid):
    assert mid in FIXTURE, f"{mid} missing from catalog fixture (run scripts/check_curated_models.py --update-fixture)"
    assert set(CURATED[feature].get("needs", [])) <= set(_props(mid))


def test_more_is_disjoint_and_unique():
    for f, c in CURATED.items():
        more = c.get("more", [])
        assert len(more) == len(set(more)) and not set(more) & set(c["models"]), f


def test_curated_features_exist_and_sizes():
    for f, c in CURATED.items():
        assert f in RAW["features"], f
        ids = c["models"]
        cap = 6 if f in ("text_to_image", "image_edit") else 5  # #95: qwen-image-3.0 re-added as 6th
        assert len(ids) == len(set(ids)) and 1 <= len(ids) <= cap, f


def test_defaults_are_first_curated_and_config_matches():
    cfg = wavespeed.load_config()["features"]
    for f, c in CURATED.items():
        # #134: an explicit "default" wins, else the first curated id
        assert cfg[f]["default"] == c.get("default", c["models"][0])
        assert [m["id"] for m in cfg[f]["models"]] == c["models"] + c.get("more", [])
        assert cfg[f]["recommended"] == _rec(c)


def test_every_original_feature_keeps_a_model_and_valid_default():
    cfg = wavespeed.load_config()["features"]
    assert set(cfg) == set(RAW["features"])
    for f, feat in cfg.items():
        ids = [m["id"] for m in feat["models"]]
        assert ids and feat["default"] in ids, f


def test_product_defaults():
    cfg = wavespeed.load_config()["features"]
    assert cfg["text_to_image"]["default"] == "openai/gpt-image-2.5-flare/text-to-image"
    assert cfg["text_to_video"]["default"] == "bytedance/seedance-2.0/text-to-video"
    assert cfg["image_to_3d"]["default"] == "tripo3d/h3.1/image-to-3d"


async def test_picker_endpoint_data_is_curated():
    g = await wavespeed.grouped_models()
    for f, c in CURATED.items():
        assert [m["id"] for m in g[f]["models"]] == c["models"] + c.get("more", [])
        assert [m["id"] for m in g[f]["models"] if m["recommended"]] == [i for i in c["models"] + c.get("more", []) if i in _rec(c)]
        assert all(m["vendor"] for m in g[f]["models"])
        assert [m["id"] for m in g[f]["models"] if m["default"]] == [c.get("default", c["models"][0])]


def test_resolve_model_rejects_uncurated():
    with pytest.raises(wavespeed.WaveSpeedError):
        wavespeed.resolve_model("text_to_image", "acme/not-curated")
    assert wavespeed.resolve_model("text_to_image", None) == CURATED["text_to_image"]["default"]


@pytest.mark.parametrize("kind", [None, *wavespeed.MODEL_KINDS, *CURATED])
async def test_list_models_under_cap(kind):
    out = await canvas._list_models({"type": kind} if kind else {})
    assert len(json.dumps(out, ensure_ascii=False, default=str)) < TOOL_RESULT_CAP


def test_tests_do_not_touch_live_script():
    for p in (ROOT / "tests").glob("*.py"):
        assert "check_curated_models" not in p.read_text() or p.name == "test_curated_models.py"
