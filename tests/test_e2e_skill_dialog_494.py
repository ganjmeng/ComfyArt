"""#494-2 e2e (mock only, $0; NOT run until GO): card → the skill's own dialog, presets, required gating, handoff URL,
detail page, old personal skill keeps main's direct start."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_skill_cards_494 import _open

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_dialog_from_data_and_handoff(app_url, lang):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang)
        await pg.locator('[data-skill="poster"] .ca-swall__cover').click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        assert await dlg.get_attribute("data-skill") == "poster"
        keys = await dlg.get_by_test_id("skill-run-field").evaluate_all("fs => fs.map(f => f.dataset.key)")
        assert keys == ["topic", "headline", "ratio", "reference"]
        assert await pg.get_by_test_id("skill-run-preset").count() == 3
        go = pg.get_by_test_id("skill-run-go")
        assert await go.is_disabled()  # required topic empty
        await pg.locator('[data-key="topic"]').fill("Autumn launch")
        assert await go.is_enabled()
        await pg.get_by_test_id("skill-run-preset").nth(1).click()
        await go.click()
        await pg.wait_for_url(re.compile(r"[?&]skill=poster"), timeout=10_000)
        assert "preset=retro" in pg.url and "mode=agent" in pg.url
        await browser.close()


async def test_other_skill_has_other_fields(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "en")
        await pg.locator('[data-skill="custom-workflow"] .ca-swall__cover').click()
        keys = await pg.get_by_test_id("skill-run-field").evaluate_all("fs => fs.map(f => f.dataset.key)")
        assert keys == ["brief"] and await pg.get_by_test_id("skill-run-preset").count() == 0
        await browser.close()


async def test_detail_page_presets_and_back(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh")
        await pg.locator('[data-skill="poster"] .ca-swall__cover').click()
        await pg.get_by_test_id("skill-run-detail").click()
        d = pg.get_by_test_id("skill-detail")
        await d.wait_for()
        assert await pg.get_by_test_id("skill-detail-try").inner_text() == "试用该技能"
        assert await pg.get_by_test_id("skill-detail-edit-chat").count() == 0  # built-in: no chat edit / ⋯
        assert await d.get_by_test_id("skill-instructions").count() == 1 and await d.get_by_test_id("skill-tabs").count() == 1
        presets = pg.get_by_test_id("skill-detail-preset")
        await presets.nth(2).click()
        assert await presets.nth(2).get_attribute("aria-checked") == "true"
        assert "浏览" not in await d.inner_text() and "点赞" not in await d.inner_text()
        await pg.get_by_test_id("skill-detail-try").click()
        assert await pg.get_by_test_id("skill-run-preset").nth(2).get_attribute("aria-checked") == "true"
        await pg.keyboard.press("Escape")
        await pg.get_by_test_id("skill-detail-back").click()
        await pg.get_by_test_id("skills-wall").wait_for()
        await browser.close()


async def test_old_personal_skill_starts_directly(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh")
        await pg.get_by_test_id("skills-tab-personal").click()
        await pg.locator('[data-skill="old-skill"] .ca-swall__cover').click()
        await pg.wait_for_url(re.compile(r"[?&]skill=old-skill"), timeout=10_000)
        assert await pg.get_by_test_id("skill-run-dialog").count() == 0
        await browser.close()
