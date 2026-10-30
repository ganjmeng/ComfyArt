"""#421: failed generate_image row — main|ours side-by-side screenshots (zh light, en dark)."""
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

SHOT_DIR = Path(os.environ.get("COMFYART_421_SHOTS", str(ROOT / "tmp-421-shots")))
CASES = [("zh", "light"), ("en", "dark")]


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("fail421")
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/fail421/rolldown.config.mjs"],
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
def test_failed_row_label_and_shot(browser, bundle, lang, theme):
    page = browser.new_page(viewport={"width": 900, "height": 520}, device_scale_factor=2)
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
    page.goto(f"{bundle}/index.html?lang={lang}&theme={theme}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(200)
    main_label = page.locator("#main .ca-process__row[data-kind=image] .ca-process__label").inner_text()
    ours_label = page.locator("#ours .ca-process__row[data-kind=image] .ca-process__label").inner_text()
    # main still shows the model name (success-looking); ours shows · 失败 / · Failed
    assert "seedream" in main_label.lower() or "bytedance" in main_label.lower()
    assert "·" in ours_label
    if lang == "zh":
        assert "失败" in ours_label
    else:
        assert "Failed" in ours_label
    assert page.locator("#ours [data-testid=process-row-failed]").count() == 1
    assert page.locator("#main [data-testid=process-row-failed]").count() == 0
    # same-locale body on both panels (design HOLD: no mixed zh/en copy)
    main_body = page.locator("#main").inner_text()
    ours_body = page.locator("#ours").inner_text()
    if lang == "zh":
        assert "生成失败" in main_body and "生成失败" in ours_body
        assert "Generation failed" not in ours_body
        assert "失败" in ours_label and "Generate image" not in ours_label
    else:
        assert "Generation failed" in main_body and "Generation failed" in ours_body
        assert "生成失败" not in main_body
        assert "Failed" in ours_label
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.locator(".ca-root").screenshot(path=str(SHOT_DIR / f"sbs-fail-gen-{lang}-{theme}.png"))
    page.close()
