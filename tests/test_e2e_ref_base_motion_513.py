"""#513 step1 / #528: WorkflowsDialog video group shows motion + lipsync (zh light) + generate optional refs note (en dark). Mocks only."""
from __future__ import annotations

from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

SHOTS = Path(__file__).resolve().parent.parent / "artifacts" / "513-1"
WF_MOTION = SHOTS / "motion-demo.json"
WF_LIP = SHOTS / "lipsync-demo.json"


async def _dismiss(pg):
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)


async def test_workflows_dialog_motion_lipsync_assigned_zh_light(app_url, fake_tools, monkeypatch):  # noqa: F811
    """Video group lists 动作控制 / 对口型; assigned motion shows filename in dropdown."""
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    assert WF_MOTION.is_file() and WF_LIP.is_file()
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 900})).new_page()
        await pg.add_init_script("localStorage.setItem('comfyart.lang','zh');localStorage.setItem('comfyart.theme','light')")
        await pg.goto(app_url + "?project=e513motion&new=1")
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(1500)
        await _dismiss(pg)
        await pg.locator(".ca-head__logo").click()
        await pg.locator(".ca-menu__item", has_text="自定义工作流").click()
        await pg.locator(".ca-modal").wait_for()
        video = pg.locator(".ca-workflows__group").filter(has=pg.locator(".ca-gen__label", has_text="视频"))
        await video.scroll_into_view_if_needed()
        assert await video.locator(".ca-workflows__row", has_text="动作控制").count() == 1
        assert await video.locator(".ca-workflows__row", has_text="对口型").count() == 1
        row = pg.locator(".ca-workflows__row").filter(has=pg.locator("span", has_text="动作控制")).first
        await row.scroll_into_view_if_needed()
        async with pg.expect_file_chooser() as fc:
            await row.locator("button.ca-panel__icon").click()
        await (await fc.value).set_files(str(WF_MOTION))
        await pg.wait_for_timeout(2500)
        row_text = await row.inner_text()
        assert "motion-demo" in row_text, f"motion not assigned: {row_text!r}"
        assert "内置" not in (await row.locator(".ca-fieldselect__text").inner_text()), row_text
        SHOTS.mkdir(parents=True, exist_ok=True)
        await row.scroll_into_view_if_needed()
        await pg.wait_for_timeout(200)
        await pg.screenshot(path=str(SHOTS / "workflows-motion-assigned-zh-light.png"))
        await video.scroll_into_view_if_needed()
        await pg.wait_for_timeout(150)
        await pg.screenshot(path=str(SHOTS / "workflows-video-motion-lipsync-zh-light.png"))
        await browser.close()


async def test_workflows_dialog_generate_and_lipsync_en_dark(app_url, fake_tools, monkeypatch):  # noqa: F811
    """Image group Text to image + video Lip sync rows visible (en dark overview)."""
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 900})).new_page()
        await pg.add_init_script("localStorage.setItem('comfyart.lang','en');localStorage.setItem('comfyart.theme','dark')")
        await pg.goto(app_url + "?project=e513gen&new=1")
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(1500)
        await _dismiss(pg)
        await pg.locator(".ca-head__logo").click()
        await pg.locator(".ca-menu__item", has_text="Custom workflows").click()
        await pg.locator(".ca-modal").wait_for()
        image = pg.locator(".ca-workflows__group").filter(has=pg.locator(".ca-gen__label", has_text="Image generation"))
        await image.scroll_into_view_if_needed()
        assert await image.locator(".ca-workflows__row", has_text="Text to image").count() == 1
        video = pg.locator(".ca-workflows__group").filter(has=pg.locator(".ca-gen__label", has_text="Video"))
        await video.scroll_into_view_if_needed()
        assert await video.locator(".ca-workflows__row", has_text="Motion control").count() == 1
        assert await video.locator(".ca-workflows__row", has_text="Lip sync").count() == 1
        lip = pg.locator(".ca-workflows__row").filter(has=pg.locator("span", has_text="Lip sync")).first
        async with pg.expect_file_chooser() as fc:
            await lip.locator("button.ca-panel__icon").click()
        await (await fc.value).set_files(str(WF_LIP))
        await pg.wait_for_timeout(2500)
        assert "lipsync-demo" in await lip.inner_text()
        SHOTS.mkdir(parents=True, exist_ok=True)
        await video.scroll_into_view_if_needed()
        await pg.wait_for_timeout(200)
        await pg.screenshot(path=str(SHOTS / "workflows-lipsync-assigned-en-dark.png"))
        await browser.close()
