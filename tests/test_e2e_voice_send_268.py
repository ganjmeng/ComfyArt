"""#268: voice and send share one 32px round button (edge rules + theme colours). Mocks only."""
from __future__ import annotations

import base64

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

SLOT = """() => { const w = document.querySelector('.ca-composer__slotwrap'); const b = w.querySelector(':scope > :not([hidden])');
  const r = b.getBoundingClientRect(); const cs = getComputedStyle(b);
  return { slot: w.dataset.slot, n: w.querySelectorAll(':scope > :not([hidden])').length, w: r.width, h: r.height, radius: cs.borderRadius,
    bg: cs.backgroundColor, fg: cs.color, anim: getComputedStyle(b.querySelector('.ca-icon')).animationDuration,
    mics: document.querySelectorAll('.ca-composer__foot .ca-bar__btn.ca-voice').length, draft: document.querySelector('.ca-composer__input').value } }"""


async def _open(p, width, lang, theme):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": width, "height": 800})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
    return browser, pg


async def _ready(pg, app_url, proj):
    await pg.goto(app_url + f"?project={proj}&new=1")
    await pg.locator(".ca-composer__mode").wait_for()
    await pg.wait_for_timeout(1500)
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)


@pytest.mark.parametrize("theme,bg,fg", [("dark", "rgb(255, 255, 255)", "rgb(17, 17, 17)"), ("light", "rgb(17, 17, 17)", "rgb(255, 255, 255)")])
async def test_slot_theme_colours(app_url, fake_tools, monkeypatch, theme, bg, fg):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _open(p, 1280, "en", theme)
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await _ready(pg, app_url, f"e268t{theme}")
        s = await pg.evaluate(SLOT)
        assert s["slot"] == "voice" and s["n"] == 1 and s["mics"] == 0 and s["w"] == 32 and s["h"] == 32 and s["radius"] == "50%", s
        assert s["bg"] == bg and s["fg"] == fg and s["anim"] == "0.12s", s
        await pg.locator(".ca-composer__input").fill("a cat")
        t = await pg.evaluate(SLOT)
        assert t["slot"] == "send" and t["bg"] == bg and t["fg"] == fg and t["anim"] == "0.12s", t
        await browser.close()


async def test_slot_ime_image_and_send(app_url, fake_tools, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _open(p, 1280, "zh", "dark")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await _ready(pg, app_url, "e268i")
        inp = pg.locator(".ca-composer__input")
        await inp.fill(" \n\t ")
        assert (await pg.evaluate(SLOT))["slot"] == "voice"  # whitespace only = empty
        await inp.fill("")
        # IME: no switch while composing, switch once composition ends
        await inp.dispatch_event("compositionstart")
        await inp.fill("ni")
        assert (await pg.evaluate(SLOT))["slot"] == "voice"
        await inp.dispatch_event("compositionend")
        await pg.wait_for_timeout(150)
        assert (await pg.evaluate(SLOT))["slot"] == "send"
        await inp.fill("")
        assert (await pg.evaluate(SLOT))["slot"] == "voice"
        # an image with no text counts as content
        await pg.locator(".ca-composer input[type=file]").set_input_files({"name": "r.png", "mimeType": "image/png", "buffer": PNG})
        await pg.wait_for_function("document.querySelector('.ca-composer__slotwrap').dataset.slot === 'send'", timeout=8000)
        assert (await pg.evaluate(SLOT))["draft"] == ""
        await browser.close()


async def test_slot_after_send_returns_to_voice(app_url, fake_tools, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _open(p, 1280, "en", "dark")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await _ready(pg, app_url, "e268s")
        await pg.locator(".ca-composer__input").fill("hello")
        assert (await pg.evaluate(SLOT))["slot"] == "send"
        await pg.locator(".ca-composer__slotwrap [data-slot=send]").click()
        await pg.wait_for_timeout(500)
        s = await pg.evaluate(SLOT)
        assert s["draft"] == "" and s["slot"] == "voice", s
        await browser.close()
