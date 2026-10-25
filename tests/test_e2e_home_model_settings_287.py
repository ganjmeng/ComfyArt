"""#287: the home composer has the canvas's right group: model → settings → voice/send in image/video mode,
only model prefs in Agent mode (no Ref button: home has no canvas). The model picked on home is one saved store shared with
the canvas (modelPrefs.image / .video): a pick on either side shows on both. Mocks only, $0."""
from __future__ import annotations

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

FITS = """() => { const f = document.querySelector('.ca-landing__foot').getBoundingClientRect();
  return [...document.querySelectorAll('.ca-landing__foot > *')].filter((el) => el.offsetParent !== null)
    .every((el) => { const r = el.getBoundingClientRect(); return r.left >= f.left - 1 && r.right <= f.right + 1 }) }"""


async def _home(p, app_url, lang, width):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": width, "height": 800})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
    await pg.goto(app_url)
    await pg.wait_for_function("document.querySelector('.ca-landing__mode')?.dataset.agent", timeout=15000)
    return browser, pg


async def _mode(pg, label):
    await pg.locator(".ca-landing__mode").click()
    await pg.locator(".ca-menu button", has_text=label).first.click()


@pytest.mark.parametrize("lang,image,video", [("zh", "图像", "视频"), ("en", "Image", "Video")])
@pytest.mark.parametrize("width", [1280, 360])
async def test_home_right_group(app_url, fake_tools, monkeypatch, lang, image, video, width):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _home(p, app_url, lang, width)
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        foot = pg.locator(".ca-landing__foot")
        # Agent mode: prefs only, no Ref button, no model/settings pills
        assert await foot.locator(".ca-refbtn").count() == 0
        assert await foot.locator("[data-pill]").count() == 0
        assert await foot.locator(".ca-bar__btn--icon").count() == 1
        for label in (image, video):
            await _mode(pg, label)
            pills = await foot.locator("[data-pill]").evaluate_all("els => els.map(e => e.dataset.pill)")
            assert pills == ["model", "settings"], pills
            # model → settings → voice/send, left to right
            xs = [await foot.locator(s).first.evaluate("e => e.getBoundingClientRect().left")
                  for s in ("[data-pill=model]", "[data-pill=settings]", ".ca-composer__slotwrap")]
            assert xs == sorted(xs), xs
            assert await foot.locator(".ca-bar__btn--icon").count() == 0  # prefs is agent-only
            assert await pg.evaluate(FITS), "a button spills out of the bar"
            # same popovers as the canvas
            await foot.locator("[data-pill=model]").click()
            await pg.locator("[data-testid=model-menu]").wait_for(timeout=5000)
            await pg.keyboard.press("Escape")
        await browser.close()


async def test_home_model_carries_into_project(app_url, fake_tools, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _home(p, app_url, "en", 1280)
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await _mode(pg, "Image")
        await pg.locator(".ca-landing__foot [data-pill=model]").click()
        menu = pg.locator("[data-testid=model-menu]")
        await menu.locator(".ca-switch").click()  # auto off
        row = menu.locator(".ca-modelprefs__row").nth(1)
        picked = await row.get_attribute("title")
        await row.click()
        assert picked in (await pg.locator(".ca-landing__foot [data-pill=model]").get_attribute("title"))
        await pg.locator(".ca-landing__input").fill("a cat")
        await pg.keyboard.press("Enter")
        await pg.wait_for_url("**project=*", timeout=15000)
        await pg.wait_for_function(
            "t => (document.querySelector('.ca-composer [data-pill=model]')?.title || '').includes(t)", arg=picked, timeout=15000)
        # one shared saved store: change it on the canvas, home shows the change
        await pg.locator(".ca-composer [data-pill=model]").click()
        menu2 = pg.locator("[data-testid=model-menu]")
        row2 = menu2.locator(".ca-modelprefs__row").nth(2)
        picked2 = await row2.get_attribute("title")
        await row2.click()
        await pg.wait_for_timeout(500)
        await pg.goto(app_url)
        await pg.locator(".ca-landing__mode").wait_for(timeout=15000)
        await _mode(pg, "Image")
        await pg.wait_for_function(
            "t => (document.querySelector('.ca-landing__foot [data-pill=model]')?.title || '').includes(t)", arg=picked2, timeout=10000)
        await browser.close()
