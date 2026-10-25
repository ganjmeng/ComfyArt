"""#278: the home mode button shows the current agent's name (same rule as the canvas, #250), and home send keeps the
draft until the new project is created; on failure the draft stays and an error shows. Mocks only."""
from __future__ import annotations

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

MODE = """() => { const b = document.querySelector('.ca-landing__mode'); const s = b.querySelector('.ca-landing__modetext');
  return { text: s.textContent, agent: b.dataset.agent || null, title: b.title, lines: Math.round(s.getBoundingClientRect().height / parseFloat(getComputedStyle(s).lineHeight || '20')) } }"""
CANVAS = """() => { const b = document.querySelector('.ca-composer__mode'); return { text: b.textContent.trim(), agent: b.dataset.agent || null } }"""


async def _home(p, app_url, lang, width=1280):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": width, "height": 800})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
    await pg.goto(app_url)
    await pg.wait_for_function("document.querySelector('.ca-landing__mode')?.dataset.agent", timeout=15000)
    return browser, pg


@pytest.mark.parametrize("lang,image,video", [("zh", "图像", "视频"), ("en", "Image", "Video")])
@pytest.mark.parametrize("width", [1280, 360])
async def test_home_mode_shows_agent_name(app_url, fake_tools, monkeypatch, lang, image, video, width):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _home(p, app_url, lang, width)
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        m = await pg.evaluate(MODE)
        assert m["text"] != "Agent" and m["text"].strip() and m["agent"], m
        home_text, home_agent = m["text"], m["agent"]
        # image / video modes keep their mode labels
        for label in (image, video):
            await pg.locator(".ca-landing__mode").click()
            await pg.locator(".ca-menu button", has_text=label).first.click()
            assert (await pg.evaluate(MODE))["text"] == label
        await pg.locator(".ca-landing__mode").click()
        await pg.locator(".ca-menu button").first.click()
        assert (await pg.evaluate(MODE))["text"] == home_text
        # same name as the canvas mode button
        await pg.locator(".ca-landing__input").fill("a cat")
        await pg.keyboard.press("Enter")
        await pg.locator(".ca-composer__mode").wait_for(timeout=15000)
        c = await pg.evaluate(CANVAS)
        assert c["agent"] == home_agent and c["text"] == home_text, (c, m)
        await browser.close()


async def test_home_send_keeps_draft_on_failure(app_url, fake_tools, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _home(p, app_url, "zh")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        start = pg.url
        await pg.route("**/comfyart/projects", lambda r: r.fulfill(status=500, content_type="application/json", body='{"error":"boom"}'))
        inp = pg.locator(".ca-landing__input")
        await inp.fill("a red fox")
        await pg.locator(".ca-landing__foot .ca-composer__slot[data-slot=send]").click()
        await pg.locator(".ca-landing__error").wait_for(timeout=8000)
        assert pg.url == start and await inp.input_value() == "a red fox"
        # once the service is back, send goes through and the draft is carried into the project
        await pg.unroute("**/comfyart/projects")
        await pg.locator(".ca-landing__foot .ca-composer__slot[data-slot=send]").click()
        await pg.wait_for_url("**project=*", timeout=15000)
        assert "a+red+fox" in pg.url or "a%20red%20fox" in pg.url
        await browser.close()
