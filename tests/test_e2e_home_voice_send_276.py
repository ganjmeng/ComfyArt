"""#276: the home composer uses the same 32px voice/send slot as the canvas composer. Mocks only."""
from __future__ import annotations

import base64

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

SLOT = """() => { const w = document.querySelector('.ca-landing__foot .ca-composer__slotwrap'); const b = w.querySelector(':scope > :not([hidden])');
  const r = b.getBoundingClientRect(); const cs = getComputedStyle(b); const i = b.querySelector('.ca-icon').getBoundingClientRect();
  return { slot: w.dataset.slot, n: w.querySelectorAll(':scope > :not([hidden])').length, w: r.width, h: r.height, radius: cs.borderRadius,
    bg: cs.backgroundColor, fg: cs.color, iw: i.width, ih: i.height, old: document.querySelectorAll('.ca-landing__send').length,
    draft: document.querySelector('.ca-landing__input').value } }"""


async def _home(p, app_url, lang, theme):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
    await pg.goto(app_url)
    await pg.locator(".ca-landing__foot .ca-composer__slotwrap").wait_for(timeout=15000)
    return browser, pg


@pytest.mark.parametrize("theme,bg,fg", [("dark", "rgb(255, 255, 255)", "rgb(17, 17, 17)"), ("light", "rgb(17, 17, 17)", "rgb(255, 255, 255)")])
async def test_home_slot_theme(app_url, fake_tools, monkeypatch, theme, bg, fg):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _home(p, app_url, "en", theme)
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        s = await pg.evaluate(SLOT)
        assert s["slot"] == "voice" and s["n"] == 1 and s["old"] == 0 and s["w"] == 32 and s["h"] == 32 and s["radius"] == "50%", s
        assert s["bg"] == bg and s["fg"] == fg and s["iw"] == 16 and s["ih"] == 16, s
        await pg.locator(".ca-landing__input").fill("a cat")
        t = await pg.evaluate(SLOT)
        assert t["slot"] == "send" and t["bg"] == bg and t["fg"] == fg and t["iw"] == 16, t
        await browser.close()


async def test_home_slot_rules(app_url, fake_tools, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _home(p, app_url, "zh", "dark")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        inp = pg.locator(".ca-landing__input")
        await inp.fill(" \n\t ")
        assert (await pg.evaluate(SLOT))["slot"] == "voice"  # whitespace only = empty
        await inp.fill("")
        await inp.dispatch_event("compositionstart")
        await inp.fill("ni")
        assert (await pg.evaluate(SLOT))["slot"] == "voice"  # no switch while composing
        await inp.dispatch_event("compositionend")
        await pg.wait_for_timeout(150)
        assert (await pg.evaluate(SLOT))["slot"] == "send"
        await inp.fill("")
        assert (await pg.evaluate(SLOT))["slot"] == "voice"
        # an image with no text counts as content
        await pg.locator(".ca-landing__box input[type=file]").set_input_files({"name": "r.png", "mimeType": "image/png", "buffer": PNG})
        await pg.wait_for_function("document.querySelector('.ca-landing__foot .ca-composer__slotwrap').dataset.slot === 'send'", timeout=8000)
        # send clears the input
        await inp.fill("a red fox")
        await pg.locator(".ca-landing__foot .ca-composer__slot[data-slot=send]").click()
        await pg.wait_for_function("!document.querySelector('.ca-landing__input') || document.querySelector('.ca-landing__input').value === ''", timeout=8000)
        await browser.close()
