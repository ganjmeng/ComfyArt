"""#235: the plan quote reuses the cost-confirm card. Real Confirm + the app CSS, nothing reaches WaveSpeed."""
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


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("plan235")
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/plan235/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
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


def _open(browser, bundle, lang, theme):
    page = browser.new_page(viewport={"width": 900, "height": 700}, color_scheme="dark" if theme == "dark" else "light")
    page.goto(f"{(bundle / 'index.html').as_uri()}?lang={lang}&theme={theme}")
    page.wait_for_selector(".ca-modal__card")
    return page


@pytest.mark.parametrize("lang,theme", CASES)
def test_plan_card_reuses_confirm_styles(browser, bundle, lang, theme):
    page = _open(browser, bundle, lang, theme)
    card = page.locator(".ca-modal__card")
    buttons = page.locator(".ca-panel__foot button")
    assert buttons.count() == 2
    secondary, primary = buttons.nth(0), buttons.nth(1)
    assert "ca-panel__secondary" in (secondary.get_attribute("class") or "")
    assert "ca-panel__primary" in (primary.get_attribute("class") or "")
    if lang == "zh":
        assert secondary.inner_text() == "取消" and primary.inner_text() == "开始"
        assert "这个任务共 2 步，预计约 $0.64，超过了你设置的 $0.50 确认线。确定开始吗？" in card.inner_text()
        assert "约 $0.24" in card.inner_text() and "总价" in card.inner_text()
    else:
        assert secondary.inner_text() == "Cancel" and primary.inner_text() == "Start"
        assert "This task has 2 steps and will cost about $0.64, above your $0.50 confirm limit. Start?" in card.inner_text()
        assert "about $0.24" in card.inner_text() and "Total" in card.inner_text()
    metrics = page.evaluate("""() => {
      const card = document.querySelector('.ca-modal__card')
      const btn = document.querySelector('.ca-panel__primary')
      const price = document.querySelector('.ca-panel__val')
      const label = price.previousElementSibling
      const cs = getComputedStyle(card), bs = getComputedStyle(btn), ps = getComputedStyle(price)
      const pr = price.getBoundingClientRect(), lr = label.getBoundingClientRect()
      return {
        radius: cs.borderRadius, btnRadius: bs.borderRadius, btnH: bs.height, btnSize: bs.fontSize,
        numeric: ps.fontVariantNumeric, align: ps.textAlign,
        priceRight: pr.right > lr.right, theme: document.documentElement.dataset.theme || 'light',
      }
    }""")
    assert metrics["radius"] == "16px"
    assert metrics["btnRadius"] == "10px" and metrics["btnH"] == "36px" and metrics["btnSize"] == "14px"
    assert "tabular-nums" in metrics["numeric"] and metrics["align"] == "right" and metrics["priceRight"]
    assert metrics["theme"] == theme
    out = os.environ.get("PLAN235_SHOTS")
    if out:
        Path(out).mkdir(parents=True, exist_ok=True)
        card.screenshot(path=str(Path(out) / f"confirm-{lang}-{theme}.png"))
    page.close()
