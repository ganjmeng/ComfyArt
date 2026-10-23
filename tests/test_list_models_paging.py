"""#95 full Lovart list: list_models shows recommended models by default, pages through all of them with
all=true (every page under the 4000-char TOOL_RESULT_CAP) and model_id gives params and quality tiers.
Mock catalog fixture only: no WaveSpeed calls."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from ComfyArt.api import wavespeed
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot._cli_common import TOOL_RESULT_CAP

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())
KINDS = [*wavespeed.MODEL_KINDS, *wavespeed.load_config()["features"]]


@pytest.fixture(autouse=True)
def mock_catalog(monkeypatch):
    async def fake_catalog(refresh=False):
        return FIXTURE
    monkeypatch.setattr(wavespeed, "catalog", fake_catalog)
    monkeypatch.setattr(canvas, "grouped_models", wavespeed.grouped_models)


def _len(out) -> int:
    return len(json.dumps(out, ensure_ascii=False, default=str))


def _cfg():
    return wavespeed.load_config()["features"]


async def _pages(kind):
    first = await canvas._list_models({"type": kind, "all": True})
    pages = [first] + [await canvas._list_models({"type": kind, "all": True, "page": p}) for p in range(2, first["pages"] + 1)]
    return pages


@pytest.mark.parametrize("kind", KINDS)
async def test_every_page_of_every_query_fits(kind):
    assert _len(await canvas._list_models({"type": kind})) <= TOOL_RESULT_CAP
    for page in await _pages(kind):
        assert _len(page) <= TOOL_RESULT_CAP


@pytest.mark.parametrize("kind", KINDS)
async def test_all_pages_cover_every_model_once_in_order(kind):
    pages = await _pages(kind)
    assert [p["page"] for p in pages] == list(range(1, len(pages) + 1))
    assert all(p["pages"] == len(pages) for p in pages)
    seen: dict[str, list[str]] = {}
    for p in pages:
        for n, f in p["features"].items():
            seen.setdefault(n, []).extend(m["id"] for m in f["models"])
            assert f["total"] == len(_cfg()[n]["models"])
    for n, ids in seen.items():
        assert ids == [m["id"] for m in _cfg()[n]["models"]]


async def test_default_view_is_recommended_first_with_hint():
    out = (await canvas._list_models({"type": "image"}))["features"]
    cfg = _cfg()
    assert [m["id"] for m in out["text_to_image"]["models"]] == cfg["text_to_image"]["recommended"]
    assert out["text_to_image"]["models"][0]["id"] == cfg["text_to_image"]["default"]
    total = sum(len(cfg[n]["models"]) for n in out if n != "hint")
    assert out["hint"] == f"{total} models in total; pass all=true and page=1.. to see them all"
    row = out["text_to_image"]["models"][0]
    assert set(row) == {"id", "usd", "desc"} and "\n" not in row["desc"] and len(row["desc"]) <= 90


async def test_model_id_details_and_tiers():
    out = (await canvas._list_models({"model_id": "openai/gpt-image-2.5-sunburst/text-to-image"}))["model"]
    assert out["features"] == ["text_to_image"] and out["tiers"][:3] == ["low", "medium", "high"]
    assert "aspect_ratios" in out and _len(out) <= TOOL_RESULT_CAP
    with pytest.raises(wavespeed.WaveSpeedError, match="unknown model"):
        await canvas._list_models({"model_id": "acme/nope"})


async def test_bad_page():
    with pytest.raises(wavespeed.WaveSpeedError, match="out of range"):
        await canvas._list_models({"type": "video", "all": True, "page": 99})


def test_schema_and_cap_unchanged():
    props = canvas.TOOLS["list_models"]["inputSchema"]["properties"]
    assert set(props) == {"type", "all", "page", "model_id"}
    assert TOOL_RESULT_CAP == 4000


def _tier(price: float | None) -> str:
    return "cheap" if (price or 0) < 0.05 else "mid" if price < 0.3 else "premium"


# Mock acceptance (#95): 10 sample requests, a scripted agent reads list_models (default view, as the
# real agent does) and picks; the pick must be a recommended model of the right feature and in the same
# price tier as the Lovart default for that request (Lovart defaults from the #95 capture; EL's list may refine).
REQUESTS = [
    ("产品海报，白底", "image", "text_to_image", "openai/gpt-image-2/text-to-image"),
    ("给这张图换背景", "image", "image_edit", "openai/gpt-image-2/edit"),
    ("赛博朋克城市夜景插画", "image", "text_to_image", "openai/gpt-image-2/text-to-image"),
    ("logo 草图上色", "image", "image_edit", "openai/gpt-image-2/edit"),
    ("电商主图 4 张", "image", "text_to_image", "openai/gpt-image-2/text-to-image"),
    ("5 秒产品旋转视频", "video", "text_to_video", "bytedance/seedance-2.0/text-to-video"),
    ("让这张照片动起来", "video", "image_to_video", "bytedance/seedance-2.0/image-to-video"),
    ("海边日落延时", "video", "text_to_video", "bytedance/seedance-2.0/text-to-video"),
    ("人物挥手动画", "video", "image_to_video", "bytedance/seedance-2.0/image-to-video"),
    ("广告片开场镜头", "video", "text_to_video", "bytedance/seedance-2.0/text-to-video"),
]


@pytest.mark.parametrize("text,kind,feature,lovart", REQUESTS)
async def test_mock_acceptance_pick_is_reasonable(text, kind, feature, lovart):
    listing = (await canvas._list_models({"type": kind}))["features"]
    pick = listing[feature]["models"][0]  # scripted agent: no stated preference -> the listed default
    cfg = _cfg()[feature]
    assert pick["id"] in cfg["recommended"]
    assert wavespeed.resolve_model(feature, pick["id"]) == pick["id"]
    lovart_price = next(m["price"] for m in (await wavespeed.grouped_models())[feature]["models"] if m["id"] == lovart)
    assert _tier(pick["usd"]) == _tier(lovart_price), (text, pick)
