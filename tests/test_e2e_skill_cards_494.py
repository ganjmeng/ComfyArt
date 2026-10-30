"""#494-1 e2e: Explore cards from real data, category chips, bookmark, old personal skill (mock only, $0)."""
from __future__ import annotations

import json
import re
import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
BRAND_NAME = re.search(r"name: '([^']+)'", (Path(__file__).resolve().parents[1] / "src/brand.ts").read_text()).group(1)

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("SKILL_CARDS_SHOTS")
OLD_MD = "---\nname: 旧技能\ndescription: 老的个人技能\n---\nDo things.\n"


async def _seed_personal(pg):
    async def handle(route):
        url = route.request.url
        if "userdata?dir=comfyart%2Fskills" in url:
            return await route.fulfill(json=["old-skill/SKILL.md", "old-skill/images.json"])
        if "SKILL.md" in url:
            return await route.fulfill(body=OLD_MD)
        if "images.json" in url:
            return await route.fulfill(body=json.dumps({"ref.png": "input/ref.png"}))
        return await route.fallback()
    await pg.route(re.compile(r"/userdata"), handle)  # glob `*` stops at `?`; match the query too


async def _open(p, app_url, lang, theme="light"):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
    await _seed_personal(pg)
    await pg.goto(app_url + "?view=skills")
    await pg.get_by_test_id("skills-wall-card").first.wait_for()
    return browser, pg


async def _shot(pg, name):
    if SHOTS:
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=f"{SHOTS}/{name}.png")


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_cards_chips_bookmark(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, theme)
        cards = pg.get_by_test_id("skills-wall-card")
        assert await cards.count() == 11
        await pg.locator('[data-skill="custom-workflow"]').scroll_into_view_if_needed()  # no-cover card in the list shot
        await _shot(pg, f"list-{lang}-{theme}")
        chips = await pg.get_by_test_id("skills-chips").locator("button").all_inner_texts()
        zh_chips, en_chips = ['为你推荐', '电商', '品牌', '社交媒体', '广告创意'], ['For you', 'E-commerce', 'Branding', 'Social Media', 'Ads & Creative']
        assert chips == (zh_chips if lang == "zh" else en_chips)
        assert await pg.get_by_test_id("skills-chip-website").count() == 0
        await pg.get_by_test_id("skills-chip-ecommerce").click()
        assert sorted(await cards.evaluate_all("cs => cs.map(c => c.dataset.skill)")) == ["packaging", "product"]
        await _shot(pg, f"chip-ecommerce-{lang}-{theme}")
        await pg.get_by_test_id("skills-chip-forYou").click()
        cw = pg.locator('[data-skill="custom-workflow"]')
        assert await cw.get_by_test_id("skills-card-placeholder").count() == 1
        # 图片 badge on every card (no-cover too), inside the cover at bottom-left; icon colour = --ca-text-2
        assert await cards.locator(".ca-swall__cover [data-testid=skills-card-kind]").count() == 11
        box, badge = await cw.locator(".ca-swall__cover").bounding_box(), await cw.get_by_test_id("skills-card-kind").bounding_box()
        assert badge["x"] - box["x"] < 16 and (box["y"] + box["height"]) - (badge["y"] + badge["height"]) < 16
        assert await cw.locator(".ca-swall__placeholder").evaluate(
            "e => { const p = document.createElement('i'); p.style.color = 'var(--ca-text-2)'; e.parentNode.append(p);"
            " const ok = getComputedStyle(e).color === getComputedStyle(p).color; p.remove(); return ok }")
        poster = pg.locator('[data-skill="poster"]')
        src = await poster.get_by_test_id("skills-card-cover").get_attribute("src")
        assert src.endswith("/skills/poster/cover.webp")
        assert await pg.evaluate("s => fetch(s).then(r => r.status)", src) == 200
        assert await poster.get_by_test_id("skills-card-cover").get_attribute("alt") == await poster.locator("h3").inner_text()
        assert await poster.get_by_test_id("skills-card-author").inner_text() == BRAND_NAME
        assert await poster.get_by_test_id("skills-card-kind").count() == 1
        await poster.hover()
        assert await poster.get_by_test_id("skills-card-bookmark").is_visible()
        assert await poster.get_by_test_id("skills-card-try").count() == 0
        await _shot(pg, f"hover-{lang}-{theme}")
        before = pg.url
        await poster.get_by_test_id("skills-card-bookmark").click()
        assert pg.url == before  # bookmark only toggles favourite
        assert "poster" in await pg.evaluate("localStorage.getItem('comfyart.skillFavourites')")
        await pg.get_by_test_id("skills-tab-favourites").click()
        assert await cards.evaluate_all("cs => cs.map(c => c.dataset.skill)") == ["poster"]
        await browser.close()


@pytest.mark.parametrize("lang,theme", [("zh", "dark"), ("en", "light")])
async def test_old_personal_skill_renders(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, theme)
        await pg.get_by_test_id("skills-tab-personal").click()
        card = pg.locator('[data-skill="old-skill"]')
        await card.wait_for()
        assert await card.get_by_test_id("skills-card-author").inner_text() == ("个人" if lang == "zh" else "Personal")
        await _shot(pg, f"personal-old-{lang}-{theme}")
        # old import with images.json → its own images[0] via /view thumb (AC 5), no migration
        assert "ref.png" in (await card.get_by_test_id("skills-card-cover").get_attribute("src"))
        await card.get_by_test_id("skills-card-bookmark").click()
        assert "old-skill" in await pg.evaluate("localStorage.getItem('comfyart.skillFavourites')")
        assert "社" + "区" not in await card.inner_text()
        await browser.close()
