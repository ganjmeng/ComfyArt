"""#825 phase 1: 2.6 is a picker option and GIF is text-to-image. Auto/default stay on 2.5-flare.

No WaveSpeed submit and no price-API spend. The 2.6 fee is the published table stub.
Default flip to 2.6-flare is a follow-up after product+QA+Tech PASS.
"""
import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ComfyArt.api import gif_image, wavespeed
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot import plan_quote

CATALOG = Path(__file__).resolve().parent / "fixtures" / "wavespeed_catalog_subset.json"
_CATALOG_DATA = json.loads(CATALOG.read_text())

FLARE_25 = "openai/gpt-image-2.5-flare/text-to-image"
EDIT_25 = "openai/gpt-image-2.5-flare/edit"
FLARE_26 = gif_image.FLARE_T2I
SUN_26 = gif_image.SUNBURST_T2I
EDIT_26 = gif_image.FLARE_EDIT
def _curated():
    return json.loads(open(wavespeed.CURATED, encoding="utf-8").read())["features"]


def _schema(mid):
    return _CATALOG_DATA[mid]["api_schema"]["api_schemas"][0]["request_schema"]


def test_auto_default_stays_on_25_flare():
    cur = _curated()
    assert cur["text_to_image"]["default"] == FLARE_25
    assert cur["image_edit"]["default"] == EDIT_25
    assert wavespeed.resolve_model("text_to_image", None) == FLARE_25
    assert wavespeed.resolve_model("image_edit", None) == EDIT_25
    assert "quality" not in wavespeed.model_defaults(FLARE_25)
    assert "quality" not in wavespeed.model_defaults(FLARE_26)
    assert "quality" not in wavespeed.model_defaults(EDIT_26)


def test_26_is_selectable_and_25_stays_optional():
    cur = _curated()
    for mid in (FLARE_26, SUN_26):
        assert mid in cur["text_to_image"]["more"]
        assert mid not in cur["text_to_image"]["models"]
        assert wavespeed.resolve_model("text_to_image", mid) == mid
    for mid in (EDIT_26, gif_image.SUNBURST_EDIT):
        assert mid in cur["image_edit"]["more"]
        assert wavespeed.resolve_model("image_edit", mid) == mid
    assert FLARE_25 in cur["text_to_image"]["models"]
    assert EDIT_25 in cur["image_edit"]["models"] + cur["image_edit"].get("more", [])
    assert wavespeed.display_of(FLARE_26)["name"] == "GPT Image 2.6 Flare"
    assert wavespeed.display_of(SUN_26)["name"] == "GPT Image 2.6 Sunburst"
    assert wavespeed.display_of(FLARE_25)["name"] == "GPT Image 2.5 Flare"


def test_edit_schema_has_no_gif_t2i_schema_has_gif_and_complexity():
    t2i = _schema(FLARE_26)["properties"]
    edit = _schema(EDIT_26)["properties"]
    assert "gif" in t2i["output_format"]["enum"]
    assert "gif" not in edit["output_format"]["enum"]
    assert t2i["complexity"]["enum"] == ["low", "medium", "high"]
    assert t2i["frame_count"]["minimum"] == 2 and t2i["frame_count"]["maximum"] == 16
    assert t2i["frame_duration_ms"]["default"] == 200
    assert not gif_image.has_gif(_schema(EDIT_26))
    assert gif_image.has_gif(_schema(FLARE_26))
    assert gif_image.has_gif(_schema(SUN_26))


def test_still_to_gif_is_reference_plus_t2i_not_video_or_edit():
    schemas = {EDIT_26: _schema(EDIT_26), FLARE_26: _schema(FLARE_26), SUN_26: _schema(SUN_26)}
    out = gif_image.route_gif({
        "feature": "image_edit", "model": EDIT_25, "image": "still.png", "prompt": "做成动图",
        "output_format": "gif", "frame_count": 99, "frame_duration_ms": 1,
    }, schemas)
    assert out["feature"] == "text_to_image"
    assert out["model"] == FLARE_26
    assert out["gif_route"] == "reference_t2i"
    assert out["images"] == ["still.png"]
    assert out["params"]["output_format"] == "gif"
    assert out["params"]["frame_count"] == 16
    assert out["params"]["frame_duration_ms"] == 20
    assert "quality" not in out["params"]
    assert "complexity" not in out["params"]
    assert "video" not in out["feature"]
    assert "编辑模型没有 gif" in out["gif_note"]
    assert "not a video" in out["gif_note"]


def test_edit_gif_is_used_when_the_schema_allows_it():
    schema = json.loads(json.dumps(_schema(EDIT_26)))
    schema["properties"]["output_format"]["enum"] = ["png", "gif"]
    out = gif_image.route_gif({"feature": "image_edit", "image": "still.png", "output_format": "gif"}, {EDIT_26: schema})
    assert out["gif_route"] == "edit" and out["model"] == EDIT_26 and out["feature"] == "image_edit"


def test_video_feature_is_rewritten_off_video_models():
    out = gif_image.route_gif({
        "feature": "image_to_video", "model": "kwaivgi/kling-v3.0-std/image-to-video",
        "prompt": "GIF", "image": "still.png",
    }, {EDIT_26: _schema(EDIT_26)})
    assert out["feature"] == "text_to_image"
    assert out["model"] == FLARE_26
    assert "kling" not in out["model"]


def test_named_sunburst_is_kept_and_25_is_not():
    assert gif_image.pick_t2i(SUN_26) == SUN_26
    assert gif_image.pick_t2i(FLARE_25) == FLARE_26
    assert gif_image.pick_t2i("") == FLARE_26
    choice = gif_image.choice(SUN_26, has_still=False)
    assert choice["model"] == SUN_26 and choice["auto"] is False and "edit_model" not in choice
    switched = gif_image.choice(FLARE_25, has_still=True)
    assert switched["model"] == FLARE_26 and switched["gif_route"] == "reference_t2i"


def test_gift_is_not_a_gif_and_frames_default():
    assert not gif_image.prompt_wants_gif("a gift box on a table")
    assert gif_image.prompt_wants_gif("做成动图")
    assert gif_image.prompt_wants_gif("export a GIF")
    args = gif_image.ensure_args({"prompt": "做成动态图"})
    assert args["output_format"] == "gif"
    assert args["frame_count"] == 9 and args["frame_duration_ms"] == 200
    assert "quality" not in args and "complexity" not in args
    kept = gif_image.ensure_args({"prompt": "x", "output_format": "gif", "frame_count": 4, "params": {"complexity": "low"}})
    assert kept["frame_count"] == 4 and kept["params"]["complexity"] == "low"
    assert "quality" not in kept["params"]


def test_payload_clamps_gif_and_does_not_pin_quality():
    t2i = _schema(FLARE_26)
    p = asyncio.run(wavespeed.build_payload(None, t2i, {"prompt": "loop", "params": {"output_format": "gif", "frame_count": 1}}, FLARE_26))
    assert p["output_format"] == "gif" and p["frame_count"] == 2 and p["frame_duration_ms"] == 200
    bare = asyncio.run(wavespeed.build_payload(None, t2i, {"prompt": "loop", "params": {"output_format": "gif"}}, FLARE_26))
    assert bare["frame_count"] == 9 and bare["frame_duration_ms"] == 200
    assert "quality" not in p and "complexity" not in p
    picked = asyncio.run(wavespeed.build_payload(None, t2i, {"prompt": "loop", "params": {"output_format": "gif", "quality": "high", "complexity": "low", "frame_count": 4, "frame_duration_ms": 500}}, FLARE_26))
    assert picked["quality"] == "high" and picked["complexity"] == "low" and picked["frame_count"] == 4
    old = asyncio.run(wavespeed.build_payload(None, _schema(FLARE_25), {"prompt": "x", "params": {"output_format": "gif", "frame_count": 9}}, FLARE_25))
    assert "output_format" not in old and "frame_count" not in old and "quality" not in old


def test_quote_stub_prices_gif_like_a_still_and_names_frames():
    assert gif_image.documented_usd(FLARE_25) == 0.024
    assert gif_image.documented_usd(FLARE_26) == 0.05
    assert gif_image.documented_usd(SUN_26, "high", "2k") == 0.12
    assert gif_image.documented_usd(FLARE_26, "medium", "1k") == gif_image.documented_usd(SUN_26)
    priced = {"output_format": "gif", "frame_count": 16, "frame_duration_ms": 200, "quality": "medium", "resolution": "1k"}
    assert "frame_count" not in gif_image.billable(priced)
    assert gif_image.billable(priced)["output_format"] == "gif"
    assert wavespeed.tier_label(priced) == "1k · GIF · 16f · 200ms"
    assert wavespeed.output_ext("https://cdn.example/out", b"GIF89a" + b"\x00", "") == ".gif"
    assert wavespeed.output_ext("https://cdn.example/out.png", b"GIF87a", "image/png") == ".gif"
    assert wavespeed.output_ext("https://cdn.example/a.png", b"\x89PNG", "image/png") == ".png"


def test_agent_gif_picks_26_and_plain_auto_stays_25():
    gif = canvas._auto_choice("generate_image", {"prompt": "把这张图做成动图", "refs": ["shape:1"]})
    assert gif["model"] == FLARE_26
    assert gif["category"] == "gif"
    assert "edit_model" not in gif
    assert "video" not in gif["model"]
    plain = canvas._auto_choice("generate_image", {"prompt": "a red apple on a table"})
    assert plain["model"] == FLARE_25
    gift = canvas._auto_choice("generate_image", {"prompt": "a gift box poster"})
    assert gift["model"] == FLARE_25
    sun = canvas._auto_choice("generate_image", {"prompt": "loop", "output_format": "gif", "model": SUN_26})
    assert sun["model"] == SUN_26 and sun["auto"] is False


def test_plan_quote_keeps_gif_on_t2i_and_shows_frames():
    assert plan_quote.feature_of_step("generate_image", {"refs": ["a"], "output_format": "gif"}) == "text_to_image"
    assert plan_quote.feature_of_step("generate_image", {"refs": ["a"], "prompt": "换背景"}) == "image_edit"
    steps = plan_quote.normalize_steps([{
        "tool": "generate_image", "text": "做成动图",
        "arguments": {"prompt": "wave the flag", "refs": ["shape:1"], "frame_count": 3},
    }])
    assert steps[0]["model"] == FLARE_26
    assert steps[0]["arguments"]["output_format"] == "gif"
    assert steps[0]["arguments"]["frame_count"] == 3
    assert "quality" not in steps[0]["arguments"]
    assert gif_image.gif_quote_label(3, None).startswith("GIF 3×")


@pytest.fixture
def catalog(monkeypatch):
    async def fake_catalog(refresh=False):
        return _CATALOG_DATA
    monkeypatch.setattr(wavespeed, "catalog", fake_catalog)
    return _CATALOG_DATA


def test_estimate_stub_for_gif_uses_published_medium_and_does_not_call_out(monkeypatch, catalog):
    """Price API is forced to fail. The stub is local. Nothing is submitted."""
    import aiohttp

    class _Boom(aiohttp.ClientError):
        pass

    class _Resp:
        async def __aenter__(self):
            raise _Boom("no network")
        async def __aexit__(self, *a):
            return False

    class _Session:
        def __init__(self, *a, **k):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        def post(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(wavespeed, "_headers", lambda: {})
    monkeypatch.setattr(wavespeed.aiohttp, "ClientSession", _Session)
    est = asyncio.run(wavespeed.estimate({
        "feature": "image_edit", "image": "still.png", "prompt": "做成动图",
        "params": {"output_format": "gif", "frame_count": 12},
    }))
    assert est["price"] == 0.05
    assert est["source"] == "estimate"
    assert est["gif_route"] == "reference_t2i"
    assert est["gif"]["priced_as"] == "still"
    assert est["gif"]["frame_count"] == 12
    assert "GIF" in est["tier"] and "12f" in est["tier"]
    still = asyncio.run(wavespeed.estimate({"feature": "text_to_image", "model": FLARE_26, "prompt": "a cup"}))
    assert still["price"] == 0.05
    gif_again = asyncio.run(wavespeed.estimate({"feature": "text_to_image", "model": FLARE_26, "prompt": "a cup", "params": {"output_format": "gif", "frame_count": 16}}))
    assert gif_again["price"] == still["price"]


def test_list_models_exposes_26_complexity_without_changing_default(catalog):
    async def run():
        details = await canvas._list_models({"model_id": FLARE_26})
        grouped = await wavespeed.grouped_models()
        return details, grouped
    details, grouped = asyncio.run(run())
    model = details["model"]
    assert model["id"] == FLARE_26
    assert model["complexities"] == ["low", "medium", "high"]
    assert "gif" in model["output_formats"]
    assert model["frame_count"]["default"] == 9
    assert grouped["text_to_image"]["default"] == FLARE_25
    ids = [m["id"] for m in grouped["text_to_image"]["models"]]
    assert FLARE_26 in ids and SUN_26 in ids and FLARE_25 in ids


def test_frontend_gif_file_names_and_clamps(tmp_path):
    root = Path(__file__).resolve().parents[1]
    rolldown = root / "node_modules" / ".bin" / "rolldown"
    if not rolldown.exists() or not shutil.which("node"):
        pytest.skip("needs node + npm install")
    out = tmp_path / "gif.mjs"
    subprocess.run([str(rolldown), "-c", "tests/js/rolldown.config.mjs"], cwd=root, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "gif_file.ts"})
    got = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    assert got["clamp"] == [2, 16, 9, 20, 200]
    assert got["model"] == [FLARE_26, FLARE_26, SUN_26]
    assert got["spec"] == {"output_format": "gif", "frame_count": 4, "frame_duration_ms": 40}
    assert got["none"] is None
    assert got["gif"] == {"name": "poster.gif", "mimeType": "image/gif", "isAnimated": True}
    assert got["png"]["mimeType"] == "image/png" and got["png"]["isAnimated"] is False
    assert got["flare"] == FLARE_26
