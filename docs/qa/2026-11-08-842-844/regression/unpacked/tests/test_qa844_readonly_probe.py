"""Temporary read-only QA probe for PR 844. Not part of the product suite. Do not commit."""
import asyncio
import builtins
import hashlib
import io
import os
import socket
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from ComfyArt.api import svg_image, wavespeed
from ComfyArt.api.wavespeed import WaveSpeedError
from ComfyArt.bot import plan_quote

FIX = svg_image.Path if False else None
ROOT_FIX = __import__("pathlib").Path(__file__).resolve().parent / "fixtures" / "svg826"
SENTINEL = __import__("pathlib").Path("/tmp/qa844/sentinel.txt")
FLARE_26 = svg_image.FLARE


def _load(name: str) -> bytes:
    return (ROOT_FIX / name).read_bytes()


def _png_size(verdict):
    im = Image.open(io.BytesIO(verdict.preview_png))
    return im.size


class _Resp:
    def __init__(self, body, status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = headers or {"Content-Type": "image/svg+xml"}

    async def read(self):
        return self.body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


class _Session:
    def __init__(self, body, status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = headers

    def get(self, _url):
        return _Resp(self.body, self.status, self.headers)


def test_probe_io_counters_on_safe_and_dangerous(monkeypatch):
    """In-process counters. A hit fails the probe; zero is evidence, not an OS sandbox."""
    SENTINEL.write_text("SENTINEL_QA844", encoding="utf-8")
    calls = {"socket": 0, "connect": 0, "open": 0, "os_open": 0, "fromstring": 0, "image_new": 0}
    real_fromstring = ET.fromstring
    real_open = builtins.open
    real_os_open = os.open
    real_image_new = Image.new

    def boom_socket(*_a, **_k):
        calls["socket"] += 1
        raise AssertionError("socket")

    def boom_connect(*_a, **_k):
        calls["connect"] += 1
        raise AssertionError("connect")

    def wrapped_open(path, *a, **k):
        calls["open"] += 1
        return real_open(path, *a, **k)

    def wrapped_os_open(path, *a, **k):
        calls["os_open"] += 1
        return real_os_open(path, *a, **k)

    def wrapped_fromstring(*a, **k):
        calls["fromstring"] += 1
        return real_fromstring(*a, **k)

    def wrapped_new(*a, **k):
        calls["image_new"] += 1
        return real_image_new(*a, **k)

    monkeypatch.setattr(socket, "socket", boom_socket)
    monkeypatch.setattr(socket, "create_connection", boom_connect)
    monkeypatch.setattr(builtins, "open", wrapped_open)
    monkeypatch.setattr(os, "open", wrapped_os_open)
    monkeypatch.setattr(ET, "fromstring", wrapped_fromstring)
    monkeypatch.setattr(Image, "new", wrapped_new)

    before = dict(calls)
    normal = svg_image.admit(_load("normal.svg"))
    assert normal.status == "normal" and normal.download == _load("normal.svg")
    assert calls["socket"] == before["socket"] and calls["connect"] == before["connect"]
    assert calls["open"] == before["open"] and calls["os_open"] == before["os_open"]
    assert calls["fromstring"] == before["fromstring"] + 1
    assert calls["image_new"] == before["image_new"] + 1

    before = dict(calls)
    external = svg_image.admit(_load("external.svg"))
    assert external.reason == "external" and external.download is None
    assert calls["socket"] == before["socket"] and calls["open"] == before["open"]
    assert calls["fromstring"] == before["fromstring"] + 1
    assert calls["image_new"] == before["image_new"]

    before = dict(calls)
    local = svg_image.admit(_load("local_file.svg"))
    assert local.reason == "local_file" and local.download is None
    assert calls["open"] == before["open"] and calls["os_open"] == before["os_open"]
    assert calls["socket"] == before["socket"]
    assert SENTINEL.read_text(encoding="utf-8") == "SENTINEL_QA844"

    before = dict(calls)
    entity = svg_image.admit(_load("entity.svg"))
    assert entity.reason == "entity" and entity.download is None
    assert calls["fromstring"] == before["fromstring"]
    assert calls["open"] == before["open"] and calls["image_new"] == before["image_new"]


def test_probe_classification_gaps_and_path_preview():
    stylesheet = (
        b'<?xml-stylesheet type="text/css" href="https://evil.example/a.css"?>'
        b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        b'<rect width="10" height="10" fill="#ff0000"/></svg>'
    )
    sheet = svg_image.admit(stylesheet)
    fill_url = svg_image.admit(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">'
        b'<rect width="32" height="32" fill="red"/>'
        b'<rect fill="url(https://evil.example/a.png)" width="4" height="4"/></svg>'
    )
    path_only = svg_image.admit(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">'
        b'<path d="M2 2 L30 30" stroke="#ff0000"/></svg>'
    )
    animate = svg_image.admit(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        b'<rect width="8" height="8" fill="#ff0000"><animate attributeName="x" to="4"/></rect></svg>'
    )
    data_image = svg_image.admit(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        b'<image href="data:image/png;base64,AAAA" width="8" height="8"/></svg>'
    )
    observed = {
        "stylesheet": (sheet.status, sheet.reason, sheet.download is not None),
        "fill_url": (fill_url.status, fill_url.reason, fill_url.download is not None),
        "path_only": (path_only.status, path_only.reason, path_only.download is not None, path_only.preview_type),
        "animate": (animate.status, animate.reason, animate.download is None),
        "data_image": (data_image.status, data_image.reason, data_image.download is None),
    }
    assert observed["animate"] == ("rejected", "script", True)
    assert observed["data_image"] == ("rejected", "external", True)
    assert observed["stylesheet"][0] == "rejected" and observed["stylesheet"][2] is False, observed
    assert observed["fill_url"][0] == "rejected" and observed["fill_url"][2] is False, observed
    assert observed["path_only"][0] == "normal", observed


def test_probe_utf16_doctype_and_invalid_encoding(monkeypatch):
    calls = {"n": 0}
    real = ET.fromstring

    def wrapped(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(ET, "fromstring", wrapped)
    utf16 = (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<!DOCTYPE svg [<!ENTITY x "x">]>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"></svg>'
    ).encode("utf-16")
    verdict = svg_image.admit(utf16)
    bad = svg_image.admit(b"\xff\xfe\x00\x00not-xml")
    assert verdict.status == "rejected" and verdict.download is None and calls["n"] == 0, (
        verdict.status, verdict.reason, verdict.download is not None, calls["n"])
    assert bad.status == "rejected" and bad.download is None, (bad.status, bad.reason, bad.download is not None)


def test_probe_xxe_utf8_rejected_before_parser(monkeypatch, tmp_path):
    marker = tmp_path / "marker.txt"
    marker.write_text("MARKER", encoding="utf-8")
    opened = []
    real_open = builtins.open

    def wrapped(path, *a, **k):
        opened.append(str(path))
        return real_open(path, *a, **k)

    monkeypatch.setattr(builtins, "open", wrapped)
    raw = (
        f'<!DOCTYPE svg [<!ENTITY x SYSTEM "file://{marker}">]>'
        f'<svg xmlns="http://www.w3.org/2000/svg">&x;</svg>'
    ).encode()
    verdict = svg_image.admit(raw)
    assert verdict.reason == "entity" and verdict.download is None
    assert all("marker.txt" not in p for p in opened)
    assert marker.read_text(encoding="utf-8") == "MARKER"


def test_probe_boundaries_equal_and_over(monkeypatch):
    allocated = {"n": 0}
    real_new = Image.new

    def wrapped_new(*a, **k):
        allocated["n"] += 1
        return real_new(*a, **k)

    monkeypatch.setattr(Image, "new", wrapped_new)
    edge_eq = svg_image.admit(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1"><rect width="1" height="1" fill="#ff0000"/></svg>'
    )
    assert edge_eq.status == "normal" and _png_size(edge_eq) == (1024, 1)
    area_eq = svg_image.admit(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024"><rect width="8" height="8" fill="#ff0000"/></svg>'
    )
    assert area_eq.status == "normal" and _png_size(area_eq) == (1024, 1024)
    before = allocated["n"]
    edge_over = svg_image.admit(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="1025" height="1"><rect width="1" height="1" fill="#ff0000"/></svg>'
    )
    area_over = svg_image.admit(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1025"><rect width="1" height="1" fill="#ff0000"/></svg>'
    )
    assert edge_over.reason == "too_many_pixels" and area_over.reason == "too_many_pixels"
    assert allocated["n"] == before
    exact = b"a" * svg_image.LIMITS.max_bytes
    over = b"a" * (svg_image.LIMITS.max_bytes + 1)
    assert svg_image.admit(exact).reason == "malformed" and svg_image.admit(exact).download == exact
    assert svg_image.admit(over).reason == "too_large" and svg_image.admit(over).download is None
    body_eq = "".join('<rect x="0" y="0" width="1" height="1" fill="#ff0000"/>' for _ in range(svg_image.LIMITS.max_elements - 1))
    raw_eq = f'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8">{body_eq}</svg>'.encode()
    body_over = body_eq + '<rect x="0" y="0" width="1" height="1" fill="#ff0000"/>'
    raw_over = f'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8">{body_over}</svg>'.encode()
    assert svg_image.admit(raw_eq).status == "normal"
    assert svg_image.admit(raw_over).reason == "too_many_elements"
    huge_vb = svg_image.admit(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 1000000000000 1000000000000">'
        b'<rect width="10" height="10" fill="#ff0000"/></svg>'
    )
    assert huge_vb.status in ("normal", "preview_failed") and _png_size(huge_vb) == (16, 16)
    missing = svg_image.admit(b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10" fill="#ff0000"/></svg>')
    assert missing.status == "normal" and _png_size(missing) == (64, 64)


def test_probe_clock_equality():
    def run(values):
        seq = iter(values)

        def clock():
            return next(seq)

        return svg_image.admit(_load("normal.svg"), clock=clock)

    assert run([0, 0, 0, 0.25]).status == "normal"
    assert run([0, 0, 0, 0.25 + 1e-9]).reason == "too_slow"
    assert run([0, 0, 0.25]).status == "normal"


def test_probe_count_and_unknown_format():
    def kind(value):
        blocked = svg_image.block_reason({"output_format": "svg", "count": value, "prompt": "logo"})
        return None if blocked is None else blocked["kind"]

    tiff = svg_image.route({"output_format": "tiff", "prompt": "svg logo", "model": "openai/gpt-image-2.5-flare/text-to-image"})
    old = svg_image.route({"output_format": "svg", "prompt": "logo", "model": "openai/gpt-image-2.5-flare/text-to-image"})
    observed = {
        "count_1_5": kind(1.5),
        "count_true": kind(True),
        "count_0": kind(0),
        "count_2": kind(2),
        "count_str_1_5": kind("1.5"),
        "tiff_error": tiff.get("svg_error", {}).get("kind") if isinstance(tiff.get("svg_error"), dict) else None,
        "tiff_model": tiff.get("model"),
        "old_model": old.get("model"),
        "old_error": old.get("svg_error", {}).get("kind") if isinstance(old.get("svg_error"), dict) else None,
    }
    assert observed == {
        "count_1_5": "svgCount",
        "count_true": "svgCount",
        "count_0": "svgCount",
        "count_2": "svgCount",
        "count_str_1_5": "svgCount",
        "tiff_error": "svgEdit",
        "tiff_model": None,
        "old_model": "openai/gpt-image-2.5-flare/text-to-image",
        "old_error": "svgEdit",
    }, observed


def test_probe_nonsvg_and_empty_are_saved(fresh_user_dir):
    import folder_paths
    root = __import__("pathlib").Path(folder_paths.get_output_directory()) / "wavespeed"
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    wavespeed._jobs["task-png"] = {"svg": True}
    with pytest.raises(WaveSpeedError) as png_err:
        asyncio.run(wavespeed._download(_Session(png, headers={"Content-Type": "image/png"}), "task-png", 0, "https://cdn.example/out"))
    assert png_err.value.kind == "svgRejected", (png_err.value.kind, str(png_err.value))
    assert not list(root.glob("ws_task-png*"))
    wavespeed._jobs["task-empty"] = {"svg": True}
    with pytest.raises(WaveSpeedError) as empty_err:
        asyncio.run(wavespeed._download(_Session(b"", headers={"Content-Type": "image/svg+xml"}), "task-empty", 0, "https://cdn.example/empty"))
    assert empty_err.value.kind == "svgRejected"
    assert not list(root.glob("ws_task-empty*"))
    wavespeed._jobs["task-html"] = {"svg": True}
    with pytest.raises(WaveSpeedError) as caught:
        asyncio.run(wavespeed._download(_Session(b"<html></html>", headers={"Content-Type": "text/html"}), "task-html", 0, "https://cdn.example/html"))
    assert caught.value.kind == "svgRejected"
    with pytest.raises(Exception) as timeout:
        asyncio.run(wavespeed._download(_Session(b"", status=504), "task-timeout", 0, "https://cdn.example/slow"))
    assert timeout.value.__class__.__name__ in {"_Transient", "WaveSpeedError"}


async def test_probe_download_headers_and_hash(bot_client, fresh_user_dir):
    out = fresh_user_dir / "output"
    out.mkdir(parents=True, exist_ok=True)
    raw = _load("text_only.svg")
    (out / "text.svg").write_bytes(raw)
    (out / "script.svg").write_bytes(_load("script.svg"))

    download = await bot_client.get("/comfyart/svg_download", params={"url": "/api/view?filename=text.svg&type=output"})
    body = await download.read()
    denied = await bot_client.get("/comfyart/svg_download", params={"url": "/api/view?filename=script.svg&type=output"})
    denied_body = await denied.read()
    thumb = await bot_client.get("/comfyart/thumb", params={"url": "/api/view?filename=text.svg&type=output"})
    thumb_body = await thumb.read()
    assert download.status == 200
    assert download.headers["Content-Type"] == "image/svg+xml"
    assert download.headers["Content-Disposition"].startswith("attachment;")
    assert download.headers["Content-Security-Policy"] == "sandbox; default-src 'none'"
    assert download.headers["X-Content-Type-Options"] == "nosniff"
    assert download.headers["Cache-Control"] == "no-store"
    assert hashlib.sha256(body).hexdigest() == hashlib.sha256(raw).hexdigest()
    assert denied.status == 404 and denied.headers["Content-Type"].startswith("text/plain")
    assert b"<svg" not in denied_body and b"<script" not in denied_body
    assert thumb.status == 200 and thumb.headers["Content-Type"] == "image/png"
    assert thumb_body.startswith(b"\x89PNG") and b"<svg" not in thumb_body


def test_probe_quote_fields(monkeypatch):
    class Boom:
        def __init__(self, *_a, **_k):
            raise AssertionError("vendor session")

    monkeypatch.setattr(wavespeed.aiohttp, "ClientSession", Boom)

    async def fake_catalog(refresh=False):
        import json
        from pathlib import Path
        return json.loads((Path(__file__).resolve().parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())

    monkeypatch.setattr(wavespeed, "catalog", fake_catalog)
    est = asyncio.run(wavespeed.estimate({
        "feature": "text_to_image",
        "model": "openai/gpt-image-2.5-flare/text-to-image",
        "prompt": "矢量标志",
        "params": {"output_format": "svg"},
    }))
    steps = plan_quote.normalize_steps([{
        "tool": "generate_image", "text": "矢量标志",
        "arguments": {"prompt": "red square logo", "output_format": "svg"},
    }])
    assert est["price"] == 0.07 and est["source"] == "estimate" and est["confirm"] is False
    assert est["svg"]["model"] == FLARE_26 and est["svg"]["n"] == 1 and est["svg"]["output_format"] == "svg"
    assert "SVG" in est["tier"] and "n=1" in est["tier"]
    assert steps[0]["model"] == FLARE_26 and steps[0]["arguments"]["count"] == 1
    assert "2.5" not in est["svg_note"], est["svg_note"]
    assert est.get("model") == FLARE_26
