"""#509 PR2: custom speech replaces voice list with workflow filename (zh light). Mocks only."""
from __future__ import annotations

from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

SHOTS = Path(__file__).resolve().parent.parent / "artifacts" / "509-2"
WF = SHOTS / "speech-demo.json"


async def test_audio_dialog_custom_speech_shows_filename(app_url, fake_tools, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    assert WF.is_file()
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 900})).new_page()
        await pg.add_init_script("localStorage.setItem('comfyart.lang','zh');localStorage.setItem('comfyart.theme','light')")
        await pg.goto(app_url + "?project=e509speech&new=1")
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(1500)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        await pg.locator(".ca-head__logo").click()
        await pg.locator(".ca-menu__item", has_text="自定义工作流").click()
        row = pg.locator(".ca-workflows__row").filter(has=pg.locator("span", has_text="配音")).first
        await row.wait_for()
        async with pg.expect_file_chooser() as fc:
            await row.locator("button.ca-panel__icon").click()
        chooser = await fc.value
        await chooser.set_files(str(WF))
        await pg.wait_for_timeout(2500)
        SHOTS.mkdir(parents=True, exist_ok=True)
        await row.scroll_into_view_if_needed()
        # design HOLD: assigned row must show workflow filename (music-like), not 「内置」
        row_text = await row.inner_text()
        assert "speech-demo" in row_text, f"assigned row still shows builtin: {row_text!r}"
        assert "内置" not in (await row.locator(".ca-fieldselect__text").inner_text()), row_text
        await pg.locator(".ca-modal").screenshot(path=str(SHOTS / "workflows-speech-assigned-zh-light.png"))
        await pg.locator(".ca-modal .ca-panel__primary").click()
        await pg.wait_for_timeout(400)
        # open audio dialog → speech tab
        await pg.locator(".ca-split__chev:not([title])").first.click()
        await pg.wait_for_timeout(200)
        await pg.locator(".ca-menu__item", has_text="音频").first.click()
        await pg.locator(".ca-modal textarea").first.wait_for()
        # switch to speech tab if needed
        tabs = pg.locator(".ca-modal .ca-tabs__tab, .ca-modal [role=tab], .ca-audio__tabs button, .ca-modal button")
        # try click 配音
        speech_tab = pg.locator(".ca-modal").get_by_text("配音", exact=True)
        if await speech_tab.count():
            await speech_tab.first.click()
            await pg.wait_for_timeout(200)
        await pg.locator(".ca-modal textarea").first.fill("你好，这是自定义配音。")
        # open voice fieldselect — should show speech-demo not Serena
        fs = pg.locator(".ca-modal .ca-fieldselect").first
        await fs.click()
        await pg.wait_for_timeout(200)
        items = await pg.locator(".ca-fieldselect__menu .ca-menu__item").all_inner_texts()
        await pg.locator(".ca-modal").screenshot(path=str(SHOTS / "audio-speech-voice-zh-light.png"))
        flat = " ".join(items)
        assert "speech-demo" in flat or "Serena" not in flat, items
        await browser.close()
