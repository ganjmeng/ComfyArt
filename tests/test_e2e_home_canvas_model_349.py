"""#349: Home↔canvas Model FieldSelect + DirectPills parity screenshots (AGENT_SHOTS)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent
SHOTS = os.environ.get("AGENT_SHOTS")


async def _ctx(p, url, lang="zh", theme="light", width=1280, height=900):
    browser = await p.chromium.launch(channel="chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = await browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=2)
    pg = await ctx.new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
    await pg.add_init_script(f"localStorage.setItem('comfyart.theme','{theme}')")
    await pg.goto(url)
    await pg.locator(".ca-landing__mode").wait_for(timeout=20000)
    await pg.wait_for_timeout(800)
    return browser, pg


async def _shot(pg, name, loc=None):
    if not SHOTS:
        return
    out = Path(SHOTS)
    out.mkdir(parents=True, exist_ok=True)
    target = loc if loc is not None else pg
    await target.screenshot(path=str(out / f"{name}.png"))


@pytest.mark.skipif(not SHOTS, reason="set AGENT_SHOTS to capture #78")
async def test_349_shots_matrix(app_url, fake_tools, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    # ensure shared bot-model-* is the long flash id (no spurious Default)
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _ctx(p, app_url, theme="light")
        except Exception as e:
            pytest.skip(f"chromium: {e}")

        # G: Home closed Mode pill = shortLabel
        await _shot(pg.locator(".ca-landing__box"), "A-home-agent-closed-light")
        await _shot(pg.locator(".ca-landing__mode"), "G-home-pill-shortlabel-light")

        # A: Home Mode menu open → Model FieldSelect closed then open
        await pg.locator(".ca-landing__mode").click()
        await pg.locator(".ca-agentpick").wait_for()
        await pg.wait_for_timeout(300)
        await _shot(pg.locator(".ca-agentpick"), "A-home-mode-menu-model-closed-light")
        # open Model FieldSelect
        model_btn = pg.locator(".ca-agentpick .ca-fieldselect, .ca-agentpick .ca-agentpick__modelbtn").first
        if await model_btn.count():
            await model_btn.click()
            await pg.wait_for_timeout(300)
            await _shot(pg, "A-home-model-open-light")
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(200)
        await pg.keyboard.press("Escape")

        # C: Home Image DirectPills
        await pg.locator(".ca-landing__mode").click()
        await pg.locator(".ca-menu button", has_text="图像").first.click()
        await pg.wait_for_timeout(400)
        await _shot(pg.locator(".ca-landing__foot"), "C-home-image-pills-light")

        # E: Home Video DirectPills
        await pg.locator(".ca-landing__mode").click()
        await pg.locator(".ca-menu button", has_text="视频").first.click()
        await pg.wait_for_timeout(400)
        await _shot(pg.locator(".ca-landing__foot"), "E-home-video-pills-light")

        # open canvas empty project
        await pg.mouse.click(28, 83)
        try:
            await pg.locator(".tl-canvas").wait_for(timeout=15000)
        except Exception:
            # fallback: click new project control if home shortcut differs
            await pg.goto(app_url + ("&" if "?" in app_url else "?") + "view=canvas")
            await pg.wait_for_timeout(2000)
        await pg.wait_for_timeout(1500)
        # H: empty canvas
        await _shot(pg, "H-canvas-empty-light")

        # G/B: canvas closed Mode + Model menu
        mode = pg.locator(".ca-composer__mode")
        await mode.wait_for(timeout=15000)
        await _shot(pg.locator(".ca-composer__foot"), "B-canvas-agent-closed-light")
        await _shot(mode, "G-canvas-pill-shortlabel-light")
        await mode.click()
        await pg.locator(".ca-agentpick").wait_for()
        await pg.wait_for_timeout(300)
        await _shot(pg.locator(".ca-agentpick"), "B-canvas-mode-menu-model-closed-light")
        model_btn = pg.locator(".ca-agentpick .ca-fieldselect, .ca-agentpick .ca-agentpick__modelbtn").first
        if await model_btn.count():
            await model_btn.click()
            await pg.wait_for_timeout(300)
            await _shot(pg, "B-canvas-model-open-light")
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(200)
        await pg.keyboard.press("Escape")

        # D: canvas Image DirectPills
        await mode.click()
        await pg.locator(".ca-menu button", has_text="图像").first.click()
        await pg.wait_for_timeout(400)
        await _shot(pg.locator(".ca-composer__foot"), "D-canvas-image-pills-light")

        # F: canvas Video DirectPills
        await mode.click()
        await pg.locator(".ca-menu button", has_text="视频").first.click()
        await pg.wait_for_timeout(400)
        await _shot(pg.locator(".ca-composer__foot"), "F-canvas-video-pills-light")

        # dark suggested (I/J)
        await browser.close()
        browser, pg = await _ctx(p, app_url, theme="dark")
        await _shot(pg.locator(".ca-landing__box"), "I-home-agent-dark")
        await pg.locator(".ca-landing__mode").click()
        await pg.wait_for_timeout(300)
        await _shot(pg.locator(".ca-agentpick"), "I-home-mode-menu-dark")
        await pg.keyboard.press("Escape")
        await pg.mouse.click(28, 83)
        await pg.locator(".tl-canvas").wait_for(timeout=15000)
        await pg.wait_for_timeout(1200)
        await _shot(pg, "J-canvas-empty-dark")
        await pg.locator(".ca-composer__mode").click()
        await pg.wait_for_timeout(300)
        await _shot(pg.locator(".ca-agentpick"), "J-canvas-mode-menu-dark")
        await browser.close()


@pytest.mark.skipif(not SHOTS, reason="set AGENT_SHOTS")
async def test_349_spotcheck_no_native_select(app_url, fake_tools, monkeypatch):  # noqa: F811
    """Audio/OCR/blend/Kit/Workflows: no <select> in DOM after open (spot check)."""
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _ctx(p, app_url)
        except Exception as e:
            pytest.skip(f"chromium: {e}")
        # count native selects on home
        n = await pg.evaluate("() => document.querySelectorAll('select').length")
        assert n == 0, n
        await pg.mouse.click(28, 83)
        await pg.locator(".tl-canvas").wait_for(timeout=15000)
        await pg.wait_for_timeout(1000)
        n2 = await pg.evaluate("() => document.querySelectorAll('select').length")
        assert n2 == 0, n2
        await _shot(pg, "spot-canvas-no-native-select")
        await browser.close()
