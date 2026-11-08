"""#826: GPT Image 2.6 text-to-image SVG, n=1, no edit.

Mock and local raster only. No WaveSpeed submit, no price-API call, no paid smoke.
Medium 1k at $0.07 is the existing still cell $0.05 plus $0.02, not a new price check.
"""
import asyncio
import io
import json
import os
import shutil
import socket
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from ComfyArt.api import gif_image, svg_image, wavespeed
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.wavespeed import WaveSpeedError
from ComfyArt.bot import plan_quote

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).resolve().parent / "fixtures" / "svg826"
CATALOG = json.loads((Path(__file__).resolve().parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())
FLARE_25 = "openai/gpt-image-2.5-flare/text-to-image"
FLARE_26 = svg_image.FLARE
SUN_26 = svg_image.SUNBURST
EDIT_26 = gif_image.FLARE_EDIT
PNG = b"\x89PNG\r\n\x1a\n"


def _load(name: str) -> bytes:
    return (FIX / name).read_bytes()


def _schema(mid):
    return CATALOG[mid]["api_schema"]["api_schemas"][0]["request_schema"]


def _png(verdict):
    assert verdict.preview_png and verdict.preview_png.startswith(PNG)
    assert b"<svg" not in verdict.preview_png and b"<script" not in verdict.preview_png
    assert verdict.inline_svg is False and verdict.preview_type == "image/png"
    return Image.open(io.BytesIO(verdict.preview_png))


def test_limits_are_the_production_caps():
    info = svg_image.audit()
    assert info["limits"] == {
        "max_bytes": 512 * 1024, "max_edge": 1024, "max_pixels": 1024 * 1024,
        "max_elements": 2000, "max_seconds": 0.25,
    }
    assert svg_image.LIMITS.max_seconds == 0.25
    assert info["inline_svg"] is False and info["dangerous_download"] is False
    assert info["safe_preview_failure_download"] is True
    assert info["addon_usd"] == 0.02 and info["medium_1k_usd"] == 0.07
    src = (ROOT / "api" / "svg_image.py").read_text(encoding="utf-8")
    for banned in ("eval(", "exec(", "import socket", "import urllib", "subprocess", "urlopen"):
        assert banned not in src
    download = (ROOT / "api" / "wavespeed.py").read_text(encoding="utf-8")
    assert "svg_image.admit(data)" in download
    assert "admit(data, limits" not in download


def test_normal_preview_is_opaque_png_and_keeps_svg():
    raw = _load("normal.svg")
    verdict = svg_image.admit(raw)
    assert verdict.status == "normal" and verdict.download == raw
    im = _png(verdict)
    assert im.getpixel((0, 0))[0] > 250 and im.getpixel((0, 0))[3] == 255
    assert im.getpixel((16, 16))[:3] == (255, 0, 0)


def test_transparent_preview_keeps_clear_corners_and_svg():
    raw = _load("transparent.svg")
    verdict = svg_image.admit(raw)
    assert verdict.status == "transparent" and verdict.download == raw
    assert "透明" in verdict.message_zh
    im = _png(verdict)
    assert im.getpixel((0, 0))[3] == 0
    assert im.getpixel((16, 16))[:3] == (0, 0, 255) and im.getpixel((16, 16))[3] == 255


def test_safe_undrawable_preview_failure_still_downloads():
    """Independent from the rejection tests: a safe file that cannot be drawn stays downloadable."""
    for name, reason in (("text_only.svg", "undrawable"), ("truncated.svg", "malformed")):
        raw = _load(name)
        verdict = svg_image.admit(raw)
        assert (name, verdict.status, verdict.reason) == (name, "preview_failed", reason)
        assert verdict.download == raw and verdict.kind == ""
        assert "预览失败" in verdict.message_zh and "downloaded" in verdict.message_en
        im = _png(verdict)
        assert im.getpixel((0, 0))[:3] == (0, 0, 0)
        assert im.getpixel((16, 16))[:3] == (128, 128, 128)


@pytest.mark.parametrize("name,reason", [
    ("script.svg", "script"),
    ("onload.svg", "script"),
    ("javascript_href.svg", "script"),
    ("foreign.svg", "script"),
    ("external.svg", "external"),
    ("style_external.svg", "external"),
    ("local_file.svg", "local_file"),
    ("entity.svg", "entity"),
    ("huge_pixels.svg", "too_many_pixels"),
])
def test_dangerous_files_are_rejected_without_download(name, reason):
    verdict = svg_image.admit(_load(name))
    assert verdict.status == "rejected" and verdict.reason == reason
    assert verdict.download is None and verdict.preview_png is None
    assert verdict.kind == "svgRejected"
    assert "不会提供下载" in verdict.message_zh and "not available to download" in verdict.message_en


def test_malformed_external_url_is_still_rejected():
    raw = b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://evil.example/a.png"'
    verdict = svg_image.admit(raw)
    assert verdict.status == "rejected" and verdict.reason == "external" and verdict.download is None


def test_relative_file_ref_is_rejected():
    raw = b'<svg xmlns="http://www.w3.org/2000/svg"><use href="../secret.svg"/></svg>'
    verdict = svg_image.admit(raw)
    assert verdict.status == "rejected" and verdict.reason == "local_file" and verdict.download is None


def test_entity_is_rejected_before_the_parser(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("parser ran")
    monkeypatch.setattr(ET, "fromstring", boom)
    verdict = svg_image.admit(_load("entity.svg"))
    assert verdict.reason == "entity" and verdict.download is None


def test_oversize_is_rejected_before_the_parser(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("parser ran")
    monkeypatch.setattr(ET, "fromstring", boom)
    verdict = svg_image.admit(b"a" * (svg_image.LIMITS.max_bytes + 1))
    assert verdict.reason == "too_large" and verdict.download is None


def test_huge_pixels_do_not_allocate(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("bitmap allocated")
    monkeypatch.setattr(Image, "new", boom)
    verdict = svg_image.admit(_load("huge_pixels.svg"))
    assert verdict.reason == "too_many_pixels" and verdict.preview_png is None


def test_too_many_elements_is_rejected(monkeypatch):
    body = "".join(f'<rect x="{i}" y="0" width="1" height="1" fill="#ff0000"/>' for i in range(svg_image.LIMITS.max_elements + 5))
    raw = f'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">{body}</svg>'.encode()
    def boom(*_a, **_k):
        raise AssertionError("bitmap allocated")
    monkeypatch.setattr(Image, "new", boom)
    verdict = svg_image.admit(raw)
    assert verdict.reason == "too_many_elements" and verdict.download is None


def test_clock_past_the_limit_rejects_even_a_safe_file():
    calls = {"n": 0}

    def clock():
        calls["n"] += 1
        return 0 if calls["n"] < 3 else 10

    verdict = svg_image.admit(_load("normal.svg"), clock=clock)
    assert verdict.status == "rejected" and verdict.reason == "too_slow" and verdict.download is None


def test_external_svg_does_not_open_a_socket(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("network")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    verdict = svg_image.admit(_load("external.svg"))
    assert verdict.reason == "external" and verdict.download is None


def test_default_model_stays_25_flare():
    curated = json.loads((ROOT / "api" / "curated_models.json").read_text(encoding="utf-8"))["features"]
    assert curated["text_to_image"]["default"] == FLARE_25
    assert wavespeed.resolve_model("text_to_image", None) == FLARE_25
    assert "quality" not in wavespeed.model_defaults(FLARE_25)
    assert "quality" not in wavespeed.model_defaults(FLARE_26)


def test_svg_copy_names_26_and_does_not_claim_a_site_default():
    """User-facing SVG text must not pin the site default to 2.5 or say it is already 2.6."""
    zh = json.loads((ROOT / "src" / "locales" / "zh.json").read_text(encoding="utf-8"))["genSettings.svgNote"]
    en = json.loads((ROOT / "src" / "locales" / "en.json").read_text(encoding="utf-8"))["genSettings.svgNote"]
    guide = (ROOT / "bot" / "guide.py").read_text(encoding="utf-8")
    svg_guide = guide.split("SVG / 矢量", 1)[1].split("- Copy ids", 1)[0]
    tool = canvas.SPECS["generate_image"]["description"]
    svg_tool = tool.split("SVG / 矢量", 1)[1].split("Do not pass refs", 1)[0]
    for text in (svg_image.NOTE["zh"], svg_image.NOTE["en"], zh, en, svg_guide, svg_tool,
                 (ROOT / "docs" / "qa" / "826" / "SECURITY.md").read_text(encoding="utf-8")):
        assert "2.5" not in text
        assert "默认模型仍是" not in text
        assert "default model stays" not in text.lower()
        assert "stable image default" not in text.lower()
        assert "线上默认" not in text
    assert "2.6" in svg_image.NOTE["zh"] and "不改全局默认" in svg_image.NOTE["zh"]
    assert "explicitly uses GPT Image 2.6" in svg_image.NOTE["en"]
    assert "does not change the global default" in svg_image.NOTE["en"]
    assert "does not change the global default" in svg_guide
    assert "does not change the global default" in svg_tool


def test_route_is_26_t2i_n1_and_does_not_pin_quality():
    out = svg_image.route({"prompt": "一个可编辑路径的矢量标志", "model": FLARE_25})
    assert out["feature"] == "text_to_image" and out["model"] == FLARE_26
    assert out["output_format"] == "svg" and out["n"] == 1 and out["count"] == 1
    assert out["params"]["output_format"] == "svg"
    assert "quality" not in out and "quality" not in out["params"]
    sun = svg_image.route({"prompt": "x", "output_format": "svg", "model": SUN_26})
    assert sun["model"] == SUN_26
    choice = svg_image.choice(FLARE_25)
    assert choice["model"] == FLARE_26 and choice["category"] == "svg" and "edit_model" not in choice


def test_edit_and_count_are_refused_with_readable_errors():
    edit = svg_image.route({"feature": "image_edit", "image": "a.png", "prompt": "svg", "output_format": "svg"})
    assert edit["svg_error"]["kind"] == "svgEdit" and "不能从编辑" in edit["svg_error"]["message"]
    refs = svg_image.block_reason({"prompt": "矢量", "refs": ["shape:1"]})
    assert refs["kind"] == "svgEdit"
    count = svg_image.block_reason({"output_format": "svg", "count": 4, "prompt": "logo"})
    assert count["kind"] == "svgCount" and "1" in count["message"]
    assert svg_image.local_usd(FLARE_26) == 0.07
    assert svg_image.local_usd(SUN_26, "high", "2k") == 0.14
    assert svg_image.local_usd(FLARE_26, "high", "1k") == 0.08


def test_locale_copy_matches_the_reject_messages():
    zh = json.loads((ROOT / "src" / "locales" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "src" / "locales" / "en.json").read_text(encoding="utf-8"))
    assert zh["wsErr.svgRejected"] == svg_image.USER["rejected"]["zh"]
    assert en["wsErr.svgRejected"] == svg_image.USER["rejected"]["en"]
    assert zh["wsErr.svgEdit"] == svg_image.USER["edit"]["zh"]
    assert en["wsErr.svgCount"] == svg_image.USER["count"]["en"]
    assert zh["wsErr.svgPreviewFailed"] == svg_image.USER["preview_failed"]["zh"]


@pytest.fixture
def catalog(monkeypatch):
    async def fake_catalog(refresh=False):
        return CATALOG
    monkeypatch.setattr(wavespeed, "catalog", fake_catalog)


def test_payload_matches_the_local_quote_and_does_not_call_out(monkeypatch, catalog):
    class Boom:
        def __init__(self, *_a, **_k):
            raise AssertionError("vendor session")
    monkeypatch.setattr(wavespeed.aiohttp, "ClientSession", Boom)
    payload = asyncio.run(wavespeed.build_payload(None, _schema(FLARE_26), {
        "prompt": "a red square", "params": {"output_format": "svg"},
    }, FLARE_26))
    assert payload["output_format"] == "svg"
    assert "quality" not in payload and "num_images" not in payload
    assert "frame_count" not in payload
    priced = asyncio.run(wavespeed.build_payload(None, _schema(FLARE_26), {
        "prompt": "a red square", "params": {"output_format": "svg", "quality": "high", "resolution": "2k"},
    }, FLARE_26))
    assert priced["output_format"] == "svg" and priced["quality"] == "high" and priced["resolution"] == "2k"
    est = asyncio.run(wavespeed.estimate({
        "feature": "text_to_image", "model": FLARE_25, "prompt": "矢量标志",
        "params": {"output_format": "svg"},
    }))
    assert est["price"] == 0.07 and est["source"] == "estimate"
    assert est["svg"]["model"] == FLARE_26 and est["svg"]["n"] == 1 and est["svg"]["output_format"] == "svg"
    assert est["svg"]["quality_sent"] is False and est["svg"]["priced_as"] == "still_plus_0.02"
    assert "SVG" in est["tier"] and "n=1" in est["tier"]
    high = asyncio.run(wavespeed.estimate({
        "feature": "text_to_image", "model": FLARE_26, "prompt": "logo",
        "params": {"output_format": "svg", "quality": "high", "resolution": "1k"},
    }))
    assert high["price"] == 0.08 and high["svg"]["quality_sent"] is True and high["svg"]["quality"] == "high"
    refused = asyncio.run(wavespeed.estimate({
        "feature": "image_edit", "image": "still.png", "prompt": "svg", "output_format": "svg", "count": 2,
    }))
    assert refused["source"] == "rejected" and refused["kind"] == "svgEdit" and refused["price"] is None


def test_edit_schema_cannot_emit_svg():
    with pytest.raises(WaveSpeedError) as caught:
        asyncio.run(wavespeed.build_payload(None, _schema(EDIT_26), {
            "prompt": "x", "params": {"output_format": "svg"},
        }, EDIT_26))
    assert caught.value.kind == "svgEdit"


def test_submit_refuses_edit_svg_before_any_session(monkeypatch):
    class Boom:
        def __init__(self, *_a, **_k):
            raise AssertionError("vendor session")
    monkeypatch.setattr(wavespeed.aiohttp, "ClientSession", Boom)
    with pytest.raises(WaveSpeedError) as caught:
        asyncio.run(wavespeed.submit({
            "feature": "image_edit", "image": "still.png", "prompt": "make it svg", "output_format": "svg",
        }))
    assert caught.value.kind == "svgEdit"


def test_agent_svg_picks_26_and_plain_auto_stays_25():
    svg = canvas._auto_choice("generate_image", {"prompt": "画一个 SVG 矢量标志"})
    assert svg["model"] == FLARE_26 and svg["category"] == "svg" and svg["n"] == 1
    assert "edit_model" not in svg
    plain = canvas._auto_choice("generate_image", {"prompt": "a red apple on a table"})
    assert plain["model"] == FLARE_25
    blocked = canvas._auto_choice("generate_image", {"prompt": "svg", "refs": ["shape:1"], "output_format": "svg"})
    assert blocked["category"] == "svg_rejected" and blocked["svg_error"]["kind"] == "svgEdit"
    enum = canvas.SPECS["generate_image"]["inputSchema"]["properties"]["output_format"]["enum"]
    assert "svg" in enum and "gif" in enum
    assert "count=1" in canvas.SPECS["generate_image"]["description"] or "count to 1" in canvas.SPECS["generate_image"]["description"]


def test_plan_quote_prices_one_svg_and_blocks_edit():
    assert plan_quote.feature_of_step("generate_image", {"output_format": "svg", "refs": ["a"]}) == "text_to_image"
    assert plan_quote.units_of("generate_image", {"output_format": "svg", "count": 4}) == 1
    steps = plan_quote.normalize_steps([{
        "tool": "generate_image", "text": "矢量标志",
        "arguments": {"prompt": "red square logo", "output_format": "svg"},
    }])
    assert steps[0]["model"] == FLARE_26
    assert steps[0]["arguments"]["output_format"] == "svg" and steps[0]["arguments"]["count"] == 1
    assert "quality" not in steps[0]["arguments"]
    blocked = plan_quote.normalize_steps([{
        "tool": "generate_image", "arguments": {"prompt": "svg", "refs": ["shape:1"], "output_format": "svg", "count": 3},
    }])
    assert blocked[0]["svg_blocked"]["kind"] == "svgEdit"


def test_download_saves_svg_and_png_and_rejects_script(fresh_user_dir):
    import folder_paths
    root = Path(folder_paths.get_output_directory()) / "wavespeed"
    root.mkdir(parents=True, exist_ok=True)

    class Resp:
        status = 200
        headers = {"Content-Type": "image/svg+xml"}
        def __init__(self, body):
            self.body = body
        async def read(self):
            return self.body
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_a):
            return False

    class Session:
        def __init__(self, body):
            self.body = body
        def get(self, _url):
            return Resp(self.body)

    wavespeed._jobs["task-normal"] = {"svg": True}
    saved = asyncio.run(wavespeed._download(Session(_load("normal.svg")), "task-normal", 0, "https://cdn.example/out"))
    assert saved["filename"].endswith(".svg") and saved["svg_state"] == "normal"
    assert (root / saved["filename"]).read_bytes() == _load("normal.svg")
    preview = (root / saved["svg_preview"]).read_bytes()
    assert preview.startswith(PNG) and b"<svg" not in preview
    wavespeed._jobs["task-bad"] = {"svg": True}
    with pytest.raises(WaveSpeedError) as caught:
        asyncio.run(wavespeed._download(Session(_load("script.svg")), "task-bad", 0, "https://cdn.example/bad"))
    assert caught.value.kind == "svgRejected"
    assert not list(root.glob("*script*")) and not any(p.name.startswith("ws_task-bad") for p in root.iterdir())


async def test_thumb_rejects_script_and_download_keeps_safe_failure(bot_client, fresh_user_dir):
    out = fresh_user_dir / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "script.svg").write_bytes(_load("script.svg"))
    (out / "text.svg").write_bytes(_load("text_only.svg"))
    thumb = await bot_client.get("/comfyart/thumb", params={"url": "/api/view?filename=script.svg&type=output"})
    body = await thumb.read()
    assert thumb.status == 404
    assert b"<script" not in body and b"alert" not in body and b"<svg" not in body
    ok = await bot_client.get("/comfyart/thumb", params={"url": "/api/view?filename=text.svg&type=output"})
    png = await ok.read()
    assert ok.status == 200 and ok.headers["Content-Type"] == "image/png" and png.startswith(PNG)
    download = await bot_client.get("/comfyart/svg_download", params={"url": "/api/view?filename=text.svg&type=output"})
    assert download.status == 200
    assert download.headers["Content-Disposition"].startswith("attachment;")
    assert await download.read() == _load("text_only.svg")
    denied = await bot_client.get("/comfyart/svg_download", params={"url": "/api/view?filename=script.svg&type=output"})
    denied_body = await denied.read()
    assert denied.status == 404 and b"alert" not in denied_body and b"<script" not in denied_body


def test_frontend_svg_preview_is_not_an_svg_url():
    rolldown = ROOT / "node_modules" / ".bin" / "rolldown"
    if not rolldown.exists() or not shutil.which("node"):
        pytest.skip("needs node + npm install")
    out = ROOT / "tests" / "js" / ".svg-file-out.mjs"
    subprocess.run([str(rolldown), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "svg_file.ts"})
    try:
        got = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    finally:
        out.unlink(missing_ok=True)
    assert got["model"] == [FLARE_26, FLARE_26, SUN_26, FLARE_26]
    assert got["spec"] == {"output_format": "svg", "n": 1}
    assert got["none"] is None
    assert got["inline"] is False
    assert got["allowed"] == [True, False, True]
    assert got["failPng"] is True
    assert got["placed"]["displaySrc"].endswith("ws_abc_0.preview.png") or "preview.png" in got["placed"]["displaySrc"]
    assert got["placed"]["downloadUrl"].startswith("/comfyart/svg_download?")
    assert "filename=ws_abc_0.svg" not in got["placed"]["displaySrc"]
    assert got["failed"]["state"] == "preview_failed"
