"""#95 product ruling on order + tester checks (mock catalog fixture, no WaveSpeed calls):
- dropdown (GET /comfyart/wavespeed/models picker_order): feature default first, then Lovart's in-app order;
  recommended models are NOT pulled to the top. Video order = #95 comment 6355690165 (31 models).
- list_models (agent): recommended first, then the rest in Lovart order; multi-page results end with
  「共 N 个，第 x/y 页」 as the last line, every page under 4000 chars.
- the dropdown only contains models that exist on WaveSpeed."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from ComfyArt.api import wavespeed
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot._cli_common import TOOL_RESULT_CAP

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())
DISPLAY = json.loads((Path(wavespeed.__file__).parent / "model_display.json").read_text())
CURATED = json.loads((Path(wavespeed.__file__).parent / "curated_models.json").read_text())["features"]
FEATS = ["text_to_image", "image_edit", "text_to_video", "image_to_video"]


@pytest.fixture(autouse=True)
def mock_catalog(monkeypatch):
    async def fake_catalog(refresh=False):
        return FIXTURE
    monkeypatch.setattr(wavespeed, "catalog", fake_catalog)
    monkeypatch.setattr(canvas, "grouped_models", wavespeed.grouped_models)


def test_video_lovart_order_matches_comment_6355690165():
    lovart31 = ("Seedance 2.5|Seedance 2.0|Seedance 2.0 Fast|Seedance 2.0 Mini|Kling 4.0|Kling 3.0|Kling 3.0 Omni|Veo 3.1|"
                "Veo 3.1 Fast|Gemini Omni 1.1 Flash|Gemini Omni Flash|Kling O1|Kling 2.6|Kling 2.5 Turbo|Wan 3.0|Wan 3.0 Prime|"
                "Wan 2.6|Wan 2.5|Vidu Q3|Vidu Q2 Pro|Vidu Q2|Veo 3|Veo 3 Fast|Seedance Pro 1.0|Vidu Q1|Hailuo 02|Hailuo 2.3|"
                "Hailuo 2.3 Fast|MiniMax-H3|MiniMax-H3-Max|LTXV 2.0").split("|")
    assert len(lovart31) == 31
    ours = [n for n in DISPLAY["lovart_order"]["video"] if n in lovart31]
    assert ours == [n for n in lovart31 if n != "MiniMax-H3-Max"]  # H3-Max: WaveSpeed 无


@pytest.mark.parametrize("feature", FEATS)
async def test_dropdown_default_first_then_lovart_order(feature):
    f = (await wavespeed.grouped_models())[feature]
    order = f["picker_order"]
    assert order[0] == f["default"]
    assert sorted(order) == sorted(m["id"] for m in f["models"])
    rank = {n: i for i, n in enumerate(DISPLAY["lovart_order"]["video" if "video" in feature else "image"])}
    by_id = {m["id"]: m for m in f["models"]}
    ranks = [rank.get(by_id[i].get("name"), len(rank)) for i in order[1:]]
    assert ranks == sorted(ranks)


async def test_dropdown_does_not_pull_recommended_to_top():
    f = (await wavespeed.grouped_models())["text_to_video"]
    rec = CURATED["text_to_video"]["models"]
    rest = f["picker_order"][1:]
    # some non-recommended model sits before some recommended one (Lovart order wins)
    assert any(rest.index(a) < rest.index(b) for a in rest if a not in rec for b in rest if b in rec), rest


@pytest.mark.parametrize("feature", FEATS)
async def test_dropdown_only_wavespeed_models(feature):
    f = (await wavespeed.grouped_models())[feature]
    assert all(m["id"] in FIXTURE for m in f["models"])
    assert not any("minimax-h3-max" in m["id"] or "uni-1-max" in m["id"] for m in f["models"])


async def test_list_models_recommended_first_and_footer_at_bottom():
    first = await canvas._list_models({"type": "image_tools", "all": True})
    assert first["pages"] > 1
    pages = [first] + [await canvas._list_models({"type": "image_tools", "all": True, "page": p}) for p in range(2, first["pages"] + 1)]
    total = sum(len(f["models"]) for p in pages for f in p["features"].values()) if isinstance(first["features"], dict) else None
    for p in pages:
        assert len(json.dumps(p, ensure_ascii=False, default=str)) < TOOL_RESULT_CAP
        assert list(p)[-1] == "footer"
        assert p["footer"].startswith(f"共 ") and f"第 {p['page']}/{p['pages']} 页" in p["footer"]
    assert first["footer"].endswith("翻页传 page=2")
    if total is not None:
        assert first["footer"].startswith(f"共 {total} 个")


async def test_list_models_text_to_image_recommended_first():
    out = await canvas._list_models({"type": "text_to_image", "all": True})
    pages = [out] + [await canvas._list_models({"type": "text_to_image", "all": True, "page": p}) for p in range(2, out.get("pages", 1) + 1)]
    text = "\n".join(json.dumps(p, ensure_ascii=False, default=str) for p in pages)
    rec = [i for i in CURATED["text_to_image"]["models"] if i in FIXTURE]
    more = [i for i in CURATED["text_to_image"].get("more", []) if i in FIXTURE]
    pos = [text.index(i) for i in rec + more if i in text]
    assert pos == sorted(pos)


@pytest.mark.parametrize("feature", FEATS)
async def test_dropdown_is_lovart_list_only(feature):
    """Steering (#95 comment 6355690165): no models beyond Lovart's 25 image / 31 video."""
    f = (await wavespeed.grouped_models())[feature]
    allowed = set(DISPLAY["lovart_order"]["video" if "video" in feature else "image"])
    assert {m.get("name") for m in f["models"]} <= allowed
