"""#397: #78 screenshots for cloud confirm + settings confirm-line (credits, no $)."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install")

CASES = [("zh", "light"), ("zh", "dark"), ("en", "light"), ("en", "dark")]
VIEWS = ("cloud", "settings")


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("credits397")
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/credits397/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text()
                    for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(
        f"<!doctype html><style>html,body{{margin:0;background:#888}}{css}</style>"
        f"<div id=root></div><script src=app.js></script>")
    return d


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome")
        except Exception:
            try:
                b = p.chromium.launch()
            except Exception as e:
                pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("lang,theme", CASES)
def test_credits_ui_no_dollar(browser, bundle, view, lang, theme):
    page = browser.new_page(viewport={"width": 900, "height": 700},
                            color_scheme="dark" if theme == "dark" else "light")
    page.goto(f"{(bundle / 'index.html').as_uri()}?lang={lang}&theme={theme}&view={view}")
    page.wait_for_selector(".ca-modal__card")
    text = page.locator(".ca-modal__card").inner_text()
    assert "$" not in text
    if view == "cloud":
        assert ("积分" in text) if lang == "zh" else ("credits" in text)
    else:
        assert ("积分" in text) if lang == "zh" else ("credits" in text)
        assert page.locator("[data-testid=ws-confirm-credits]").input_value() == "50"
    out = os.environ.get("CREDITS397_SHOTS")
    if out:
        Path(out).mkdir(parents=True, exist_ok=True)
        page.locator(".ca-modal__card").screenshot(path=str(Path(out) / f"{view}-{lang}-{theme}.png"))
