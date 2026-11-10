"""#826: three product-canvas states from local admit() fixtures. No vendor request.

The page is the real Tldraw canvas, ImageToolbar, and generator card.
The banner only labels the harness. Screenshots are LOCAL FIXTURE evidence.
"""
import hashlib
import importlib.util
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "tests" / "js" / "svg826"
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
    (public / "path.svg").write_bytes((fix / "path.svg").read_bytes())
    (public / "text_only.svg").write_bytes((fix / "text_only.svg").read_bytes())
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


def _shot(page, art, name: str) -> None:
    art.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(art / name), full_page=False)


def _save_download(page, button_name: str, expected_name: str, expected: bytes) -> None:
    with page.expect_download() as caught:
        page.locator(".ca-toolbar--image").get_by_role("button", name=button_name).last.click()
    download = caught.value
    assert download.suggested_filename == expected_name
    got = Path(download.path()).read_bytes()
    assert got == expected
    assert hashlib.sha256(got).hexdigest() == hashlib.sha256(expected).hexdigest()


def test_three_product_states_are_local_fixtures(browser, fixture_page, tmp_path):
    # Do not write to /opt/cursor/artifacts (often unwritable in this environment).
    art = tmp_path / "svg826"
    art.mkdir(parents=True, exist_ok=True)
    page = browser.new_page(viewport={"width": 960, "height": 640})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    fix = ROOT / "tests" / "fixtures" / "svg826"
    path_svg = (fix / "path.svg").read_bytes()
    text_svg = (fix / "text_only.svg").read_bytes()

    page.goto(f"{fixture_page}/?state=path")
    page.wait_for_function("() => window.__svg826Ready === true", timeout=30000)
    page.wait_for_selector(".ca-toolbar--image", timeout=15000)
    page.wait_for_selector("[data-testid=svg-checker] img", timeout=15000)
    assert "LOCAL FIXTURE" in page.locator(".ca-fixture-banner").inner_text()
    assert page.locator(".ca-toolbar--image").get_by_role("button", name="下载").count() >= 1
    assert page.locator(".ca-gen-card__error").count() == 0
    assert page.locator("[data-testid=svg-preview-failed]").count() == 0
    checker = art / "01-checker-face.png"
    page.locator("[data-testid=svg-checker]").screenshot(path=str(checker))
    face = Image.open(checker).convert("RGB")
    corner, neighbor = face.getpixel((4, 4)), face.getpixel((12, 4))
    assert corner != neighbor
    assert corner != (0, 170, 0) and neighbor != (0, 170, 0)
    mid = face.getpixel((face.size[0] // 2, face.size[1] // 2))
    assert mid[1] > 120 and mid[0] < 90
    _save_download(page, "下载", "path.svg", path_svg)
    _shot(page, art, "01-path-preview.png")

    page.goto(f"{fixture_page}/?state=failed")
    page.wait_for_function("() => window.__svg826Ready === true", timeout=30000)
    page.wait_for_selector(".ca-toolbar--image", timeout=15000)
    placeholder = page.locator("[data-testid=svg-preview-failed]")
    placeholder.wait_for()
    assert placeholder.locator("img").count() == 0
    assert "预览失败，原 SVG 仍可下载。" in placeholder.inner_text()
    assert page.locator(".ca-toolbar--image").get_by_role("button", name="预览失败，原 SVG 仍可下载。").count() >= 1
    failed_face = art / "02-fail-face.png"
    placeholder.screenshot(path=str(failed_face))
    blank = Image.open(failed_face).convert("RGB")
    assert blank.getpixel((2, 2))[0] > 200
    assert blank.getpixel((2, 2)) != (0, 0, 0)
    _save_download(page, "预览失败，原 SVG 仍可下载。", "text_only.svg", text_svg)
    _shot(page, art, "02-preview-failed-download.png")

    page.goto(f"{fixture_page}/?state=rejected")
    page.wait_for_function("() => window.__svg826Ready === true", timeout=30000)
    page.wait_for_selector(".ca-gen-card__error", timeout=15000)
    assert "不会提供下载" in page.locator(".ca-gen-card__error").inner_text()
    assert page.locator(".ca-toolbar--image").count() == 0
    assert page.locator("a[download]").count() == 0
    assert page.locator("[data-testid=svg-preview-failed]").count() == 0
    assert page.locator("[data-testid=svg-checker]").count() == 0
    _shot(page, art, "03-rejected-no-download.png")

    page.close()
    assert not errors, errors
