"""#423: one 记忆已更新 › per turn + 「已保存 N 条」 detail — main|ours screenshots (zh light, en dark)."""
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

SHOT_DIR = Path(os.environ.get("COMFYART_423_SHOTS", str(ROOT / "tmp-423-shots")))
CASES = [("zh", "light"), ("en", "dark")]


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("mem423")
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/mem423/rolldown.config.mjs"],
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
def test_one_row_with_saved_count_and_shot(browser, bundle, lang, theme):
    page = browser.new_page(viewport={"width": 900, "height": 560}, device_scale_factor=2)
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
    page.goto(f"{bundle}/index.html?lang={lang}&theme={theme}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(200)
    main_rows = page.locator("#main .ca-process__row[data-kind=memory_updated]")
    ours_rows = page.locator("#ours .ca-process__row[data-kind=memory_updated]")
    assert main_rows.count() == 3
    assert ours_rows.count() == 1
    assert page.locator("#main [data-testid=memory-saved-detail]").count() == 0
    detail = page.locator("#ours [data-testid=memory-saved-detail]")
    assert detail.count() == 1
    text = detail.inner_text()
    if lang == "zh":
        assert "已保存 3 条" in text
        assert "品牌色：蓝色" in text
    else:
        assert "Saved 3" in text
        assert "Brand colour: blue" in text
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.locator(".ca-root").screenshot(path=str(SHOT_DIR / f"sbs-memory-once-{lang}-{theme}.png"))
    page.close()
