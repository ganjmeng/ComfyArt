"""#287: the home composer has the canvas's right group: model → settings → voice/send in image/video mode,
only model prefs in Agent mode (no Ref button: home has no canvas). The model picked on home is one saved store shared with
the canvas (modelPrefs.image / .video): a pick on either side shows on both. Mocks only, $0."""
from __future__ import annotations

import os

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


POP = """() => { const p = document.querySelector('.ca-pop'); const b = document.querySelector('.ca-landing__foot [data-pill=settings]');
  if (!p || !b) return null; const r = p.getBoundingClientRect(), a = b.getBoundingClientRect();
  return { top: r.top, bottom: r.bottom, btnTop: a.top, btnBottom: a.bottom, vh: innerHeight,
           maxH: parseFloat(p.style.maxHeight) || 0, scrolls: p.scrollHeight > p.clientHeight + 1 } }"""
COUNT_VISIBLE = """() => { const p = document.querySelector('.ca-pop');
  const l = [...p.querySelectorAll('.ca-gen__label')].find((e) => /^(数量|Count)$/.test(e.textContent.trim()));
  if (!l) return 'no label: ' + p.innerText.slice(0, 200);
  const ctl = l.nextElementSibling || l; ctl.scrollIntoView({ block: 'nearest' });
  const q = p.getBoundingClientRect();
  const ok = [l, ctl].every((e) => { const r = e.getBoundingClientRect(); return r.top >= q.top - 1 && r.bottom <= q.bottom + 1 });
  return ok || JSON.stringify([q, l.getBoundingClientRect(), ctl.getBoundingClientRect()]) }"""


async def _open_settings(app_url, p, w, h, scroll_to_bottom=False):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": w, "height": h})).new_page()
    await pg.add_init_script("localStorage.setItem('comfyart.lang','zh')")
    await pg.goto(app_url)
    await pg.wait_for_function("document.querySelector('.ca-landing__mode')?.dataset.agent", timeout=15000)
    await _mode(pg, "图像")
    if scroll_to_bottom:  # bar near the bottom edge: not enough room below
        await pg.evaluate("""() => { const f = document.querySelector('.ca-landing__foot');
          let s = f.parentElement; while (s && !(s.scrollHeight > s.clientHeight + 1 && /auto|scroll/.test(getComputedStyle(s).overflowY))) s = s.parentElement;
          s = s || document.scrollingElement; s.scrollTop += f.getBoundingClientRect().bottom - innerHeight + 24 }""")
    await pg.locator(".ca-landing__foot [data-pill=settings]").click()
    await pg.locator(".ca-pop").wait_for(timeout=5000)
    await pg.wait_for_timeout(200)
    return browser, pg


@pytest.mark.parametrize("case", ["down", "flip", "cap", "narrow"])
async def test_home_popover_placement(app_url, fake_tools, monkeypatch, case):  # noqa: F811
    """Product + EL rule: home popovers open down; flip up if no room below; if neither fits, cap to
    window - 64 with inner scroll. The 数量 row is never clipped (reachable inside the panel)."""
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    w, h = {"down": (1280, 800), "flip": (1280, 800), "cap": (1280, 360), "narrow": (360, 800)}[case]
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _open_settings(app_url, p, w, h, scroll_to_bottom=case == "flip")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        if os.environ.get("SHOT287"):
            await pg.screenshot(path=f"{os.environ['SHOT287']}-pop-{case}.png")
        m = await pg.evaluate(POP)
        assert m and m["top"] >= 0 and m["bottom"] <= m["vh"] + 1, m
        if case in ("down", "narrow"):
            assert m["top"] >= m["btnBottom"], m
        elif case == "flip":
            assert m["bottom"] <= m["btnTop"], m
        else:
            assert m["maxH"] and m["maxH"] <= m["vh"] - 64 + 1 and m["scrolls"], m
        assert (await pg.evaluate(COUNT_VISIBLE)) is True
        await browser.close()
