"""#826: three product-canvas states from local admit() fixtures. No vendor request.

The page is the real Tldraw canvas, ImageToolbar, and generator card.
The banner only labels the harness. Screenshots are LOCAL FIXTURE evidence.
"""
import importlib.util
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "tests" / "js" / "svg826"
ART = Path("/opt/cursor/artifacts/svg826")
pw = pytest.importorskip("playwright.sync_api")


def _raster():
    spec = importlib.util.spec_from_file_location("svg_raster", ROOT / "api" / "svg_raster.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["svg_raster"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fixture_page():
    public = ROOT / ".tmp-svg826-public"
    public.mkdir(exist_ok=True)
    raster = _raster()
    fix = ROOT / "tests" / "fixtures" / "svg826"
    path = raster.admit((fix / "path.svg").read_bytes())
    failed = raster.admit((fix / "text_only.svg").read_bytes())
    rejected = raster.admit((fix / "script.svg").read_bytes())
    assert path.status == "transparent" and path.preview_png
    assert failed.status == "preview_failed" and failed.download
    assert rejected.status == "rejected" and rejected.download is None
    (public / "path.png").write_bytes(path.preview_png)
    (public / "fail.png").write_bytes(failed.preview_png)
    (public / "logo.svg").write_bytes(failed.download)
    log = public / "vite.log"
    proc = subprocess.Popen(
        [str(ROOT / "node_modules" / ".bin" / "vite"), "--config", str(HERE / "vite.config.ts")],
        cwd=ROOT,
        stdout=log.open("w"),
        stderr=subprocess.STDOUT,
        env={**os.environ, "SVG826_PUBLIC": str(public)},
    )
    url = "http://127.0.0.1:8766"
    try:
        deadline = time.time() + 40
        last = ""
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.fail(f"vite exited {proc.returncode}\n{log.read_text(errors='replace')[-2000:]}")
            try:
                with urllib.request.urlopen(url, timeout=1) as res:
                    if res.status == 200:
                        break
            except OSError as exc:
                last = str(exc)
            time.sleep(0.2)
        else:
            pytest.fail(f"vite did not listen ({last})\n{log.read_text(errors='replace')[-2000:]}")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            launched = p.chromium.launch(channel="chrome", args=["--no-sandbox"])
        except Exception as exc:
            pytest.fail(f"chrome did not launch: {exc}")
        yield launched
        launched.close()


def _shot(page, name: str) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ART / name), full_page=False)


def test_three_product_states_are_local_fixtures(browser, fixture_page):
    page = browser.new_page(viewport={"width": 960, "height": 640})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto(f"{fixture_page}/?state=path")
    page.wait_for_function("() => window.__svg826Ready === true", timeout=30000)
    page.wait_for_selector(".ca-toolbar--image", timeout=15000)
    page.wait_for_selector("img", timeout=15000)
    assert "LOCAL FIXTURE" in page.locator(".ca-fixture-banner").inner_text()
    assert page.locator(".ca-toolbar--image").get_by_role("button", name="下载").count() >= 1
    assert page.locator(".ca-gen-card__error").count() == 0
    _shot(page, "01-path-preview.png")

    page.goto(f"{fixture_page}/?state=failed")
    page.wait_for_function("() => window.__svg826Ready === true", timeout=30000)
    page.wait_for_selector(".ca-toolbar--image", timeout=15000)
    body = page.locator("body").inner_text()
    assert "预览失败，原 SVG 仍可下载。" in body
    assert page.locator(".ca-toolbar--image").get_by_role("button", name="预览失败，原 SVG 仍可下载。").count() >= 1
    _shot(page, "02-preview-failed-download.png")

    page.goto(f"{fixture_page}/?state=rejected")
    page.wait_for_function("() => window.__svg826Ready === true", timeout=30000)
    page.wait_for_selector(".ca-gen-card__error", timeout=15000)
    assert "不会提供下载" in page.locator(".ca-gen-card__error").inner_text()
    assert page.locator(".ca-toolbar--image").count() == 0
    assert page.locator("a[download]").count() == 0
    _shot(page, "03-rejected-no-download.png")

    page.close()
    assert not errors, errors
