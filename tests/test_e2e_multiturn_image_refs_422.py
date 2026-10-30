"""#422: multi-turn image refs — main|ours SBS screenshots (zh light, en dark)."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install")

SHOT_DIR = Path(os.environ.get("COMFYART_422_SHOTS", str(ROOT / "tmp-422-shots")))
CASES = [("zh", "light"), ("en", "dark")]


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("ctx422")
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/ctx422/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text()
                    for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><style>html,body{{margin:0}}{css}</style>"
        f"<div id=root></div><script type=module src=app.js></script>")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


@pytest.mark.parametrize("lang,theme", CASES)
def test_context_shape_id_and_shot(browser, bundle, lang, theme):
    page = browser.new_page(viewport={"width": 980, "height": 720}, device_scale_factor=2)
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
    page.goto(f"{bundle}/index.html?lang={lang}&theme={theme}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(200)

    main_ctx = page.locator("#main").inner_text()
    ours_ctx = page.locator("#ours").inner_text()
    # main: old bare form, no shape id
    assert "[attached image:" in main_ctx
    assert "shape id shape:poster1" not in main_ctx
    # ours: canonical Attached-line with shape id
    assert "shape id shape:poster1" in ours_ctx
    assert "[Attached image 1" in ours_ctx
    assert "generation ref" in ours_ctx
    # thinking never appears
    assert "thinking" not in ours_ctx.lower() or "Thinking" not in ours_ctx
    # same-locale chrome
    if lang == "zh":
        assert "多轮" in page.locator(".ca-root").inner_text()
        assert "Multi-turn LLM" not in page.locator(".ca-root").inner_text()
    else:
        assert "Multi-turn" in page.locator(".ca-root").inner_text()
        assert "多轮" not in page.locator(".ca-root").inner_text()

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.locator(".ca-root").screenshot(path=str(SHOT_DIR / f"sbs-ctx-image-refs-{lang}-{theme}.png"))
    page.close()
