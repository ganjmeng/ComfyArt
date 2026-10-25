"""#246: the composer mode button shows the agent (logo + short name ▾) and the agent list lives in the mode menu
(agents on top, image / video below). Back from image/video returns to the last agent with no second MCP confirm;
an undetected tool's row opens Agent settings. Provider probes are mocked; nothing paid is called ($0)."""
from __future__ import annotations

import os

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import CONFIRM, _page, fake_tools  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

SHOTS = os.environ.get("AGENT_SHOTS")


async def _dismiss(pg):
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)


async def _shot(pg, name):
    if SHOTS:
        await pg.screenshot(path=f"{SHOTS}/{name}.png")


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_mode_menu_agent_flow(app_url, fake_tools, monkeypatch, lang, theme):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    from ComfyArt.api import settings
    image = "图像" if lang == "zh" else "Image"
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, lang, theme)
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await _dismiss(pg)
        assert await pg.evaluate("document.documentElement.dataset.theme || 'light'") == theme
        btn = pg.locator(".ca-composer__mode")
        assert await btn.count() == 1  # no separate agent button any more
        assert (await btn.inner_text()).strip() == "ComfyArt"
        await _shot(pg, f"01-closed-{lang}-{theme}")
        await btn.click()
        menu = pg.locator(".ca-agentpick")
        await menu.wait_for()
        rows = menu.locator(".ca-agentpick__row")
        h = [(await rows.nth(i).bounding_box())["height"] for i in range(await rows.count())]
        assert all(x >= 31.5 for x in h), h  # 32px rows
        mb, vb = await menu.bounding_box(), pg.viewport_size
        assert mb["y"] >= 0 and mb["y"] + mb["height"] <= vb["height"], mb  # both groups fit at 1280×800
        await _shot(pg, f"02-menu-{lang}-{theme}")
        await rows.filter(has_text="Claude Code").click()
        dialog = pg.locator(".ca-modal")
        await dialog.wait_for()
        assert CONFIRM[lang] in await dialog.inner_text()
        await dialog.locator(".ca-panel__primary").click()
        await pg.wait_for_timeout(800)
        assert (await btn.inner_text()).strip() == "Claude Code"
        assert await btn.get_attribute("title") == "Claude Code"
        await _shot(pg, f"03-switched-{lang}-{theme}")
        # to image and back: the last agent comes back, no second confirm
        await btn.click()
        await menu.locator(".ca-menu__item:not(.ca-agentpick__row)").filter(has_text=image).click()
        await pg.wait_for_timeout(300)
        assert image in await btn.inner_text()
        await btn.click()
        await rows.filter(has_text="Claude Code").click()
        await pg.wait_for_timeout(500)
        assert await pg.locator(".ca-modal").count() == 0
        assert (await btn.inner_text()).strip() == "Claude Code"
        assert settings.get_setting("bot-provider") == "claude-code"
        # undetected tool: whole row dimmed, click opens Agent settings
        await btn.click()
        off = rows.filter(has_text="Qwen Code")
        logo = off.locator(".ca-agentlogo")
        assert await logo.evaluate("e => getComputedStyle(e).filter") == "grayscale(1)"
        assert await logo.evaluate("e => getComputedStyle(e).opacity") == await off.locator(".ca-agentpick__name").evaluate("e => getComputedStyle(e).opacity")
        assert await logo.evaluate("e => getComputedStyle(e).backgroundColor") == "rgba(0, 0, 0, 0)"  # no tile
        ob = await off.bounding_box()
        assert ob["height"] <= 32.5, ob  # name and 去配置 on one 32px line
        nb = await off.locator(".ca-agentpick__name").bounding_box()
        # #247 align: 去配置 lives in the ✓ column (ca-agentpick__check), same right edge as checks
        sb = await off.locator(".ca-agentpick__setup").bounding_box()
        cb = await off.locator(".ca-agentpick__check").bounding_box()
        assert abs(nb["y"] - sb["y"]) < 4 and nb["x"] < sb["x"], (nb, sb)
        assert abs((sb["x"] + sb["width"]) - (cb["x"] + cb["width"])) < 2, (sb, cb)
        on = rows.filter(has_text="Claude Code").first
        on_check = await on.locator(".ca-agentpick__check").bounding_box()
        assert abs((cb["x"] + cb["width"]) - (on_check["x"] + on_check["width"])) < 2, (cb, on_check)
        await off.click()
        await pg.locator(".ca-modal").wait_for()
        await _shot(pg, f"04-setup-{lang}-{theme}")
        assert settings.get_setting("bot-provider") == "claude-code"  # opening setup doesn't switch the agent
        await browser.close()
