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


def _props(mid):
    return FIXTURE[mid]["api_schema"]["api_schemas"][0]["request_schema"]["properties"]


CURATED_IDS = [(f, m) for f, c in CURATED.items() for m in c["models"]]


@pytest.mark.parametrize("feature,mid", CURATED_IDS)
def test_curated_id_in_catalog_with_declared_params(feature, mid):
    assert mid in FIXTURE, f"{mid} missing from catalog fixture (run scripts/check_curated_models.py --update-fixture)"
    assert set(CURATED[feature].get("needs", [])) <= set(_props(mid))


def test_curated_features_exist_and_sizes():
    for f, c in CURATED.items():
        assert f in RAW["features"], f
        ids = c["models"]
        assert len(ids) == len(set(ids)) and 1 <= len(ids) <= 5, f


def test_defaults_are_first_curated_and_config_matches():
    cfg = wavespeed.load_config()["features"]
    for f, c in CURATED.items():
        assert cfg[f]["default"] == c["models"][0]
        assert [m["id"] for m in cfg[f]["models"]] == c["models"]


def test_every_original_feature_keeps_a_model_and_valid_default():
    cfg = wavespeed.load_config()["features"]
    assert set(cfg) == set(RAW["features"])
    for f, feat in cfg.items():
        ids = [m["id"] for m in feat["models"]]
        assert ids and feat["default"] in ids, f


def test_product_defaults():
    cfg = wavespeed.load_config()["features"]
    assert cfg["text_to_image"]["default"] == "openai/gpt-image-2/text-to-image"
    assert cfg["text_to_video"]["default"] == "bytedance/seedance-2.0/text-to-video"
    assert cfg["image_to_3d"]["default"] == "tripo3d/h3.1/image-to-3d"


async def test_picker_endpoint_data_is_curated():
    g = await wavespeed.grouped_models()
    for f, c in CURATED.items():
        assert [m["id"] for m in g[f]["models"]] == c["models"]
        assert [m["id"] for m in g[f]["models"] if m["default"]] == [c["models"][0]]


def test_resolve_model_rejects_uncurated():
    with pytest.raises(wavespeed.WaveSpeedError):
        wavespeed.resolve_model("text_to_image", "ideogram-ai/ideogram-v4.5")
    assert wavespeed.resolve_model("text_to_image", None) == CURATED["text_to_image"]["models"][0]


@pytest.mark.parametrize("kind", [None, *wavespeed.MODEL_KINDS, *CURATED])
async def test_list_models_under_cap(kind):
    out = await canvas._list_models({"type": kind} if kind else {})
    assert len(json.dumps(out, ensure_ascii=False, default=str)) < TOOL_RESULT_CAP


def test_tests_do_not_touch_live_script():
    for p in (ROOT / "tests").glob("*.py"):
        assert "check_curated_models" not in p.read_text() or p.name == "test_curated_models.py"
