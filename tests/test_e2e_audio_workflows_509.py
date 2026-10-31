"""#509 PR2: WorkflowsDialog audio group lists 配音 / 声音克隆 / 音效 (zh light screenshot). Mocks only."""
from __future__ import annotations

from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

SHOTS = Path(__file__).resolve().parent.parent / "artifacts" / "509-2"


@pytest.mark.parametrize("lang,theme", [("zh", "light")])
async def test_workflows_dialog_lists_speech_clone_sfx(app_url, fake_tools, monkeypatch, lang, theme):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 900})).new_page()
        await pg.add_init_script(
            f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')"
        )
        await pg.goto(app_url + f"?project=e509audio{lang}&new=1")
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(1500)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        await pg.locator(".ca-head__logo").click()
        await pg.locator(".ca-menu__item", has_text="自定义工作流").click()
        modal = pg.locator(".ca-modal")
        await modal.wait_for()
        for label in ("配音", "声音克隆", "音效", "配乐"):
            row = pg.locator(".ca-workflows__row").filter(has=pg.locator("span", has_text=label)).first
            await row.wait_for()
            await row.scroll_into_view_if_needed()
        SHOTS.mkdir(parents=True, exist_ok=True)
        # scroll audio group into view for the shot
        audio_hdr = pg.locator(".ca-workflows__group", has_text="音频").first
        if await audio_hdr.count():
            await audio_hdr.scroll_into_view_if_needed()
        else:
            await pg.locator(".ca-workflows__row").filter(has=pg.locator("span", has_text="配音")).first.scroll_into_view_if_needed()
        await pg.wait_for_timeout(300)
        path = SHOTS / "workflows-audio-zh-light.png"
        await modal.screenshot(path=str(path))
        assert path.is_file() and path.stat().st_size > 1000
        await browser.close()
