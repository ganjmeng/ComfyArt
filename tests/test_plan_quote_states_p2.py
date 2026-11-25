"""P2-1: ChatInlineConfirm as PlanQuote renders it.

Unpriced and estimate use Re-price + Cancel (ca-panel__primary / ca-panel__secondary).
No Start / Generate. An exact quote still uses jobs.confirmOk. PlanQuote's branch that
picks these labels is locked in test_chat_inline_confirm_contract.py.
"""
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


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("planp2")
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/plan_quote_states/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(
        "<!doctype html><style>html,body{margin:0;background:#888}" + css + "</style>"
        "<div id=root></div><script src=app.js></script>")
    return d


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


def _open(browser, bundle, lang, kind):
    page = browser.new_page(viewport={"width": 900, "height": 700})
    page.goto(f"{(bundle / 'index.html').as_uri()}?lang={lang}&kind={kind}")
    page.wait_for_selector("[data-testid=chat-inline-planquote]")
    return page


def _buttons(page):
    buttons = page.locator(".ca-panel__foot button")
    assert buttons.count() == 2
    secondary, primary = buttons.nth(0), buttons.nth(1)
    assert "ca-panel__secondary" in (secondary.get_attribute("class") or "")
    assert "ca-panel__primary" in (primary.get_attribute("class") or "")
    return secondary.inner_text(), primary.inner_text(), page.locator("[data-testid=chat-inline-planquote]").inner_text()


@pytest.mark.parametrize("lang,cancel,reprice", [("zh", "取消", "重新取价"), ("en", "Cancel", "Re-price")])
def test_unpriced_card_has_reprice_and_cancel_and_no_number(browser, bundle, lang, cancel, reprice):
    page = _open(browser, bundle, lang, "unpriced")
    secondary, primary, text = _buttons(page)
    assert secondary == cancel and primary == reprice
    assert "未定价" in text or "Unpriced" in text
    prices = page.locator(".ca-panel__val").all_inner_texts()
    assert prices == (["未定价", "未定价"] if lang == "zh" else ["Unpriced", "Unpriced"])
    assert all(not any(ch.isdigit() for ch in p) and "约" not in p and "about" not in p.lower() for p in prices)
    for word in ("开始", "Start", "Generate", "继续生成"):
        assert word not in text
    page.locator("[data-testid=chat-inline-confirm-ok]").click()
    page.wait_for_function("() => globalThis.__choice === 'reprice'")


@pytest.mark.parametrize("lang,cancel,reprice,amount", [
    ("zh", "取消", "重新取价", "约 5 积分"),
    ("en", "Cancel", "Re-price", "about 5 credits"),
])
def test_estimate_card_has_reprice_and_no_start(browser, bundle, lang, cancel, reprice, amount):
    page = _open(browser, bundle, lang, "estimate")
    secondary, primary, text = _buttons(page)
    assert secondary == cancel and primary == reprice
    assert amount in text
    for word in ("开始", "Start", "Generate", "继续生成"):
        assert word not in text
    page.locator("[data-testid=chat-inline-confirm-ok]").click()
    page.wait_for_function("() => globalThis.__choice === 'reprice'")


@pytest.mark.parametrize("lang,cancel,ok", [("zh", "取消", "继续生成"), ("en", "Cancel", "Generate")])
def test_exact_quote_still_has_generate(browser, bundle, lang, cancel, ok):
    page = _open(browser, bundle, lang, "exact")
    secondary, primary, text = _buttons(page)
    assert secondary == cancel and primary == ok
    assert "64" in text
    page.locator("[data-testid=chat-inline-confirm-ok]").click()
    page.wait_for_function("() => globalThis.__choice === 'start'")
