"""#420: canvas tools on continuous process rail — main|ours SBS (zh light, en dark)."""
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

SHOT_DIR = Path(os.environ.get("COMFYART_420_SHOTS", str(ROOT / "tmp-420-shots")))
CASES = [("zh", "light"), ("en", "dark")]


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("rail420")
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rail420/rolldown.config.mjs"],
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
def test_canvas_tools_on_rail_and_shot(browser, bundle, lang, theme):
    page = browser.new_page(viewport={"width": 960, "height": 560}, device_scale_factor=2)
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
    page.goto(f"{bundle}/index.html?lang={lang}&theme={theme}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(200)

    # ours: one continuous process rail with canvas tool rows + failed add_text
    ours = page.locator("#ours")
    assert ours.locator(".ca-process").count() == 1
    kinds = ours.locator(".ca-process__row").evaluate_all("els => els.map(e => e.getAttribute('data-kind'))")
    assert "thought" in kinds
    assert kinds.count("tool") >= 3 or sum(1 for k in kinds if k == "tool") >= 3
    assert ours.locator("[data-testid=process-row-failed]").count() == 1
    fail_label = ours.locator("[data-testid=process-row-failed] .ca-process__label").inner_text()
    assert "·" in fail_label
    if lang == "zh":
        assert "失败" in fail_label
        assert "添加文字" in fail_label or "文字" in fail_label
    else:
        assert "Failed" in fail_label
        assert "Add text" in fail_label or "text" in fail_label.lower()
    # continuous spine stubs between non-last groups (no off-rail ca-chat__tool under ours)
    assert ours.locator(".ca-chat__tool").count() == 0
    spines = ours.locator("[data-testid=process-rail]")
    assert spines.count() >= 2

    # main: broken off-rail tools (no .ca-process)
    main = page.locator("#main")
    assert main.locator(".ca-process").count() == 0
    assert main.locator(".ca-chat__tool").count() >= 3

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.locator(".ca-root").screenshot(path=str(SHOT_DIR / f"sbs-rail-canvas-{lang}-{theme}.png"))
    page.close()
