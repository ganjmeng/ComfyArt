"""#825: 2.6-flare is the Auto/default. 2.5 stays selectable. GIF stays text-to-image.

No WaveSpeed submit and no price-API spend. The 2.6 fee is the published table stub.
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


def test_auto_default_is_26_flare_and_25_still_resolves():
    cur = _curated()
    assert cur["text_to_image"]["default"] == FLARE_26
    assert cur["image_edit"]["default"] == EDIT_26
    assert wavespeed.resolve_model("text_to_image", None) == FLARE_26
    assert wavespeed.resolve_model("text_to_image", "auto") == FLARE_26
    assert wavespeed.resolve_model("image_edit", None) == EDIT_26
    assert wavespeed.resolve_model("image_edit", "auto") == EDIT_26
    assert wavespeed.resolve_model("text_to_image", FLARE_25) == FLARE_25
    assert wavespeed.resolve_model("image_edit", EDIT_25) == EDIT_25
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


def test_still_gif_is_refused_for_image_images_refs_and_base():
    schemas = {EDIT_26: _schema(EDIT_26), FLARE_26: _schema(FLARE_26), SUN_26: _schema(SUN_26)}
    jobs = [
        {"feature": "image_edit", "model": EDIT_25, "image": "still.png", "prompt": "做成动图", "output_format": "gif"},
        {"feature": "text_to_image", "images": ["https://cdn.test/a.png"], "output_format": "gif", "prompt": "loop"},
        {"feature": "text_to_image", "refs": ["shape:1"], "prompt": "做成动图"},
        {"feature": "text_to_image", "base": "shape:base", "output_format": "gif", "prompt": "loop"},
        {"prompt": "gif", "params": {"output_format": "gif", "base": "shape:nested"}},
    ]
    for job in jobs:
        with pytest.raises(gif_image.StillGifUnsupported) as err:
            gif_image.route_gif(job, schemas)
        text = str(err.value)
        assert "不支持" in text and "do not start" in text
        assert "不会送进请求" not in text
    pure = gif_image.route_gif({
        "feature": "text_to_image", "prompt": "做成动图", "frame_count": 99, "frame_duration_ms": 1,
    }, schemas)
    assert pure["feature"] == "text_to_image" and pure["model"] == FLARE_26
    assert pure["gif_route"] == "text_to_image"
    assert "images" not in pure and "image" not in pure
    assert pure["params"]["frame_count"] == 16 and pure["params"]["frame_duration_ms"] == 20
    assert gif_image.still_fields({"base": "", "refs": [], "images": [""], "output_format": "gif"}) == []


def test_edit_schema_cannot_authorize_a_still_gif():
    schema = json.loads(json.dumps(_schema(EDIT_26)))
    schema["properties"]["output_format"]["enum"] = ["png", "gif"]
    with pytest.raises(gif_image.StillGifUnsupported):
        gif_image.route_gif({"feature": "image_edit", "image": "still.png", "output_format": "gif"}, {EDIT_26: schema})


def test_video_feature_without_a_still_leaves_video_models():
    with pytest.raises(gif_image.StillGifUnsupported):
        gif_image.route_gif({
            "feature": "image_to_video", "model": "kwaivgi/kling-v3.0-std/image-to-video",
            "prompt": "GIF", "image": "still.png",
        }, {EDIT_26: _schema(EDIT_26)})
    out = gif_image.route_gif({
        "feature": "image_to_video", "model": "kwaivgi/kling-v3.0-std/image-to-video", "prompt": "GIF",
    }, {EDIT_26: _schema(EDIT_26)})
    assert out["feature"] == "text_to_image"
    assert out["model"] == FLARE_26
    assert "kling" not in out["model"]


def test_named_sunburst_is_kept_and_25_is_not():
    assert gif_image.pick_t2i(SUN_26) == SUN_26
    assert gif_image.pick_t2i(FLARE_25) == FLARE_26
    assert gif_image.pick_t2i("") == FLARE_26
    choice = gif_image.choice(SUN_26, has_still_image=False)
    assert choice["model"] == SUN_26 and choice["auto"] is False and "edit_model" not in choice
    switched = gif_image.choice(FLARE_25, has_still_image=True)
    assert switched["blocked"] is True and switched["category"] == "gif_still_unsupported"
    assert switched["model"] == ""


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


def test_generate_image_refuses_still_gif_before_approval_and_submit(monkeypatch):
    async def boom(*_a, **_k):
        raise AssertionError("must not ask, quote, or submit")

    monkeypatch.setattr(canvas, "submit_command", boom)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", boom)
    handler = canvas.TOOLS["generate_image"]["handler"]
    jobs = (
        {"prompt": "loop", "output_format": "gif", "refs": ["shape:1"]},
        {"prompt": "loop", "output_format": "gif", "base": "shape:b"},
        {"prompt": "做成动图", "images": ["https://cdn.test/still.png"]},
        {"prompt": "gif of a cat", "output_format": "gif", "image": "https://cdn.test/still.png"},
    )
    for args in jobs:
        got = asyncio.run(handler(dict(args)))
        assert got["kind"] == "gifStillUnsupported"
        assert got["submitted"] is False and got["generation_succeeded"] is False
        assert "不支持" in got["user_message"] and "do not start" in got["user_message"]


def test_agent_gif_picks_26_and_plain_auto_stays_25():
    gif = canvas._auto_choice("generate_image", {"prompt": "把这张图做成动图", "refs": ["shape:1"]})
    assert gif["blocked"] is True and gif["category"] == "gif_still_unsupported"
    assert gif["model"] == ""
    base = canvas._auto_choice("generate_image", {"prompt": "做成动图", "base": "shape:b"})
    assert base["blocked"] is True
    plain = canvas._auto_choice("generate_image", {"prompt": "a red apple on a table"})
    assert plain["model"] == FLARE_26 and plain["category"] == "default"
    gift = canvas._auto_choice("generate_image", {"prompt": "a gift box poster"})
    assert gift["model"] == SUN_26 and gift["category"] == "poster_text"  # #825 poster/text -> 2.6 sunburst
    sun = canvas._auto_choice("generate_image", {"prompt": "loop", "output_format": "gif", "model": SUN_26})
    assert sun["model"] == SUN_26 and sun["auto"] is False


def test_plan_quote_refuses_still_gif_before_any_price():
    with pytest.raises(gif_image.StillGifUnsupported):
        plan_quote.feature_of_step("generate_image", {"refs": ["a"], "output_format": "gif"})
    with pytest.raises(gif_image.StillGifUnsupported):
        plan_quote.feature_of_step("generate_image", {"base": "shape:b", "output_format": "gif"})
    assert plan_quote.feature_of_step("generate_image", {"refs": ["a"], "prompt": "换背景"}) == "image_edit"
    assert plan_quote.feature_of_step("generate_image", {"output_format": "gif", "prompt": "a flag"}) == "text_to_image"
    with pytest.raises(gif_image.StillGifUnsupported):
        plan_quote.normalize_steps([{
            "tool": "generate_image", "text": "做成动图",
            "arguments": {"prompt": "wave the flag", "refs": ["shape:1"], "frame_count": 3},
        }])
    pure = plan_quote.normalize_steps([{
        "tool": "generate_image", "text": "做成动图",
        "arguments": {"prompt": "wave the flag", "frame_count": 3},
    }])
    assert pure[0]["model"] == FLARE_26
    assert pure[0]["arguments"]["output_format"] == "gif"
    assert pure[0]["arguments"]["frame_count"] == 3
    assert "quality" not in pure[0]["arguments"]
    assert gif_image.gif_quote_label(3, None).startswith("GIF 3×")

    async def pricer(model, inputs):
        raise AssertionError(f"price call {model} {inputs}")

    async def models_for(feature):
        raise AssertionError(f"model list {feature}")

    with pytest.raises(gif_image.StillGifUnsupported):
        asyncio.run(plan_quote.build_quote([{
            "tool": "generate_image", "text": "做成动图",
            "arguments": {"prompt": "wave", "images": ["https://cdn.test/a.png"]},
        }], "zh", threshold=0, pricer=pricer, models_for=models_for))


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
    with pytest.raises(wavespeed.WaveSpeedError) as refused:
        asyncio.run(wavespeed.estimate({
            "feature": "image_edit", "image": "still.png", "prompt": "做成动图",
            "params": {"output_format": "gif", "frame_count": 12},
        }))
    assert refused.value.status == 400 and refused.value.kind == "gifStillUnsupported"
    still = asyncio.run(wavespeed.estimate({"feature": "text_to_image", "model": FLARE_26, "prompt": "a cup"}))
    assert still["price"] == 0.05
    gif_again = asyncio.run(wavespeed.estimate({"feature": "text_to_image", "model": FLARE_26, "prompt": "a cup", "params": {"output_format": "gif", "frame_count": 16}}))
    # The unsaved GIF route is now Replicate; never borrow the WaveSpeed table price.
    assert gif_again["price"] is None and gif_again["source"] == "unpriced"
    assert gif_again["confirm"] is True


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
    assert grouped["text_to_image"]["default"] == FLARE_26
    ids = [m["id"] for m in grouped["text_to_image"]["models"]]
    assert FLARE_26 in ids and SUN_26 in ids and FLARE_25 in ids


def test_visible_confirm_text_uses_request_frames_local_mock(tmp_path):
    """Sentence test only. 0.05 is a local stand-in inside confirm_desc.ts, not a live price API."""
    root = Path(__file__).resolve().parents[1]
    rolldown = root / "node_modules" / ".bin" / "rolldown"
    if not rolldown.exists() or not shutil.which("node"):
        pytest.skip("needs node + npm install")
    out = tmp_path / "confirm.mjs"
    subprocess.run([str(rolldown), "-c", "tests/js/rolldown.config.mjs"], cwd=root, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "confirm_desc.ts"})
    got = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    assert got["mockPrice"] is True and got["credits"] == 5
    assert got["live99"] == "这次云端生成约需 5 积分，GIF 16 帧（已从 99 帧调整），每帧 20 毫秒（已从 5 毫秒调整），确定继续吗？"
    assert got["live1"] == "这次云端生成约需 5 积分，GIF 2 帧（已从 1 帧调整），每帧 200 毫秒，确定继续吗？"
    assert "毫秒调整" not in got["live1"]
    assert got["unpriced"] == "暂时查不到准确价格。GIF 16 帧（已从 99 帧调整），每帧 20 毫秒（已从 5 毫秒调整）。继续会按这个档位实际扣费，确定继续吗？"
    assert "积分" not in got["unpriced"]
    assert "没有可核对的封顶价" in got["openGif"]
    assert "GIF 16 帧" in got["openGif"] and "每帧 20 毫秒" in got["openGif"]
    assert "积分" not in got["openGif"]
    assert "no hard price cap" in got["openEn"]
    assert got["estimate"] == "估算价：GIF 16 帧（已从 99 帧调整），每帧 20 毫秒，约 5 积分（暂时查不到实时价格，以实际扣费为准），确定继续吗？"


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
    assert got["still"] == [True, True, True, True, False, False]
    assert got["refusal"] is True
