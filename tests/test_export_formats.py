"""#156 (#33): PNG / PDF / PPTX export are original features. Regression tests drive the real ExportDialog export
button and the real pptx.ts (pptxgenjs) once per format against a mock editor, then open the produced files and check
dimensions / page count. Mocks only: no network, no model call, no charge."""
from __future__ import annotations

import io
import json
import re
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PIL import Image
from conftest import node_ready

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not node_ready(), reason="COMFYART_SKIP_NODE_TESTS=1 and no node_modules")
EMU = 914400
COLORS = {(1600, 1200): (200, 30, 30), (800, 600): (30, 160, 60), (400, 300): (30, 60, 200)}


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    base = tmp_path_factory.mktemp("export")
    fix, out = base / "fix", base / "out"
    fix.mkdir(), out.mkdir()
    for (w, h), c in COLORS.items():
        Image.new("RGB", (w, h), c).save(fix / f"{w}x{h}.png")
        Image.new("RGB", (w, h), c).save(fix / f"{w}x{h}.jpg", quality=90)
    bundle = base / "run.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/export/rolldown.config.mjs"], cwd=ROOT,
                   check=True, capture_output=True, env={"PATH": "/usr/bin:/bin:/usr/local/bin", "OUT": str(bundle)})
    proc = subprocess.run(["node", str(bundle)], cwd=out, check=True, capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin:/usr/local/bin", "OUT_DIR": str(out), "FIXTURES": str(fix),
                               "NODE_PATH": str(ROOT / "node_modules")})
    return json.loads(proc.stdout.strip().splitlines()[-1]), out


@needs_node
def test_export_is_offline(exported):
    data, _ = exported
    assert data["net"] == []
    for fmt in ("png", "pdf", "pptx"):
        assert data["result"][fmt]["errors"] == [], fmt
        assert data["result"][fmt]["closed"] is True, fmt


@needs_node
def test_png_export_opens_with_scaled_size(exported):
    data, out = exported
    assert data["result"]["png"]["files"] == ["Export_ test_1.png"]
    img = Image.open(out / "png-Export_ test_1.png")
    img.load()
    assert img.format == "PNG" and img.size == (1600, 1200)  # 800x600 frame at the default 2x
    assert img.convert("RGB").getpixel((10, 10)) == COLORS[(1600, 1200)]
    assert {"ids": ["shape:f1"], "format": "png", "scale": 2, "background": False} in data["toImageCalls"]


@needs_node
def test_pdf_export_is_one_page_with_frame_size(exported):
    data, out = exported
    assert data["result"]["pdf"]["files"] == ["Export_ test_1.pdf"]
    raw = (out / "pdf-Export_ test_1.pdf").read_bytes()
    assert raw.startswith(b"%PDF-1.4") and raw.rstrip().endswith(b"%%EOF")
    assert re.findall(rb"/Type /Page\b", raw) == [b"/Type /Page"]
    assert b"/Count 1" in raw and b"/MediaBox [0 0 800 600]" in raw
    # xref offsets point at the objects they name, so readers can open it
    xref = int(re.search(rb"startxref\n(\d+)", raw).group(1))
    assert raw[xref:xref + 4] == b"xref"
    offsets = [int(m) for m in re.findall(rb"(\d{10}) 00000 n", raw)]
    for n, off in enumerate(offsets, start=1):
        assert raw[off:off + len(f"{n} 0 obj")] == f"{n} 0 obj".encode()
    length = int(re.search(rb"/DCTDecode /Length (\d+)", raw).group(1))
    start = raw.index(b"stream\n", raw.index(b"/DCTDecode")) + len(b"stream\n")
    img = Image.open(io.BytesIO(raw[start:start + length]))
    img.load()
    assert img.format == "JPEG" and img.size == (800, 600)
    assert {"ids": ["shape:f1"], "format": "jpeg", "scale": 1, "background": True} in data["toImageCalls"]


@needs_node
def test_pptx_export_one_slide_per_frame(exported):
    data, out = exported
    assert data["result"]["pptx"]["files"] == ["Export_ test_1.pptx"]
    with zipfile.ZipFile(out / "pptx-Export_ test_1.pptx") as z:
        assert z.testzip() is None
        names = z.namelist()
        slides = sorted(n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
        assert len(slides) == 2  # two frames -> two slides
        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
        size = ET.fromstring(z.read("ppt/presentation.xml")).find("p:sldSz", ns)
        cx, cy = int(size.get("cx")), int(size.get("cy"))
        assert abs(cx / EMU - 13.333) < 0.01 and abs(cy / cx - 600 / 800) < 0.001  # 4:3 from the first frame
        media = sorted(n for n in names if n.startswith("ppt/media/") and not n.endswith("/"))
        sizes = sorted(Image.open(io.BytesIO(z.read(n))).size for n in media)
        assert sizes == [(400, 300), (800, 600)]
    calls = [c["ids"] for c in data["toImageCalls"] if c["ids"][0] in ("shape:f1", "shape:f2") and c["scale"] == 1 and c["format"] == "png"]
    assert calls == [["shape:f1"], ["shape:f2"]]  # sorted top-to-bottom
