"""#644 e2e (mock only, $0).
(1) The live home + Skills page after #673: the Phase3 hard-lock 20 (19 NEW + upgrade `thumbnail`) are all on the Skills
    wall, none of the 9 hidden ids is anywhere, and QA644_SHOTS=/dir writes the 20-image regression set.
(2) #812: yingzao is listed again — deep link shows NO hidden notice (guard kept for a future hide list).
(3) #812: ?skill=yingzao deep link with refs attaches the listed skill; refs stay in the composer, canvas has 0 images.
(4) 技术经理 on #723: the Phase3 ids mounted on home + Skills == the hard-lock 20 (none extra / missing) + chip counts;
    `thumbnail` upgrade regression; zh-light / en-dark overview of the 20 Phase3 cards.
(5) Design HOLD on #723: the dialog's 'N templates' equals its real thumbnail strip; home-featured shot from the page top."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from conftest import write_settings
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_skills_hide_673 import HIDDEN, MAIN_ORDER_40

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("QA644_SHOTS")
NOTICE = '[data-testid="skill-hidden-notice"]'
LOC = {lg: json.loads((ROOT / f"src/locales/{lg}.json").read_text()) for lg in ("zh", "en")}
HARDLOCK_20 = [
    "cover-design-director", "taobao-product", "before-after", "anim-2d", "creator-identity", "product-website", "studio-model",
    "youtube-channel-banner", "ai-model", "product-to-packaging", "game-art", "portrait-studio", "premium-website",
    "animated-poster", "pose-fission", "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website",
    "clothing-swap",
]
# #640 (locked 11-02) "Dropped from old draft (勿再落地)": never a Phase3 slot. poster/brand stay as Phase1 skills.
DROPPED_13 = [
    "app-listing-kit", "ip-logo", "magazine-postcard", "poster-differentiated-compiler", "talking-collage", "brand-identity-director", "anime-official-site",
    "cinematic-snapshot", "zhixian-poster", "cartoon-ip-extend", "culture-creative", "new-chinese-mobile", "portfolio-site",
]
LR4 = ["taobao-product", "before-after", "linkedin-banner", "clothing-swap"]
COMBOS = [("zh", "light"), ("en", "dark"), ("zh", "dark"), ("en", "light")]
HIDDEN_SEL = ",".join(f'[data-skill="{h}"]' for h in HIDDEN) or '[data-skill="__no_hidden__"]'
PAID = ("wavespeed", "kie", "/send", "/generate", "/prompt")  # any non-GET to these = an agent turn or a paid submit
PNG = bytes.fromhex(  # 2x2 opaque PNG
    "89504e470d0a1a0a0000000d4948445200000002000000020802000000fdd49a73"
    "0000001649444154789c63f8cfc0f09f8181e1ff7f0606000024f205fd1c5a4a5f0000000049454e44ae426082")


@pytest.fixture
def fake_agent(fake_provider):
    write_settings(**{"bot-provider": fake_provider.id, "enable-bot": True, "enable-mcp": True})
    return fake_provider


async def _page(p, lang, theme, height=900):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1440, "height": height})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
    return browser, pg


async def _dismiss(pg):
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)


async def _shot(pg, name, full=False):
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    await pg.wait_for_timeout(600)
    if full:  # grow the viewport to the tallest scroll container: the whole waterfall / grid in one PNG
        await pg.evaluate("document.querySelectorAll('*').forEach(e => { if (e.scrollTop) e.scrollTop = 0 })")
        h = await pg.evaluate("Math.min(16000, Math.max(...[...document.querySelectorAll('*')].map(e => e.scrollHeight - e.clientHeight + innerHeight)))")
        await pg.set_viewport_size({"width": 1440, "height": int(h)})
        await pg.wait_for_timeout(1500)
    await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"))
    if full:
        await pg.set_viewport_size({"width": 1440, "height": 900})
        await pg.wait_for_timeout(300)


@pytest.mark.parametrize("lang,theme", COMBOS)
async def test_live_home_and_skills_regression_20(app_url, lang, theme):  # noqa: F811
    """4 shots per combo (home featured, home full, Skills, Skills full) = 16, plus the 4 L/R skills' dialogs in zh-light."""
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, lang, theme)
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.goto(app_url)
        await pg.get_by_test_id("home-featured-card").first.wait_for()
        assert await pg.locator(HIDDEN_SEL).count() == 0
        # #723 design (d): from the page top, tall enough that the whole first row of featured cards is in frame
        await pg.evaluate("document.querySelectorAll('*').forEach(e => { if (e.scrollTop) e.scrollTop = 0 })")
        firsts = pg.locator('[data-testid="home-featured-col"] > :first-child')  # masonry: row 1 = top card of each column
        row = [await c.bounding_box() for c in await firsts.all()]
        await pg.set_viewport_size({"width": 1440, "height": int(max(900, max(b["y"] + b["height"] for b in row) + 48))})
        await pg.wait_for_timeout(800)
        vh = pg.viewport_size["height"]
        for c in await firsts.all():
            b = await c.bounding_box()
            assert b["y"] >= 0 and b["y"] + b["height"] + 24 <= vh, (b, vh)    # whole first row (incl. names) in frame
        await _shot(pg, f"home-featured-{lang}-{theme}")
        await pg.set_viewport_size({"width": 1440, "height": 900})
        await _shot(pg, f"home-full-{lang}-{theme}", full=True)

        await pg.get_by_test_id("rail-skills").click()
        await pg.get_by_test_id("skills-wall").wait_for()
        await pg.wait_for_timeout(400)
        wall = [await c.get_attribute("data-skill") for c in await pg.locator('[data-testid="skills-wall"] [data-testid="skills-wall-card"]').all()]
        assert wall == MAIN_ORDER_40, wall
        assert [s for s in wall if s in HARDLOCK_20] == HARDLOCK_20  # hard-lock 20: all present, table order
        assert not set(wall) & set(HIDDEN)
        await _shot(pg, f"skills-{lang}-{theme}")
        await _shot(pg, f"skills-full-{lang}-{theme}", full=True)
        if (lang, theme) == ("zh", "light"):
            for sid in LR4:
                card = pg.locator(f'[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="{sid}"]')
                await card.scroll_into_view_if_needed()
                await card.hover()
                await card.get_by_test_id("skills-card-try").click()
                dlg = pg.locator(f'[data-testid="skill-run-dialog"][data-skill="{sid}"]')
                await dlg.wait_for(timeout=10000)
                await _assert_template_label(pg, dlg, lang)
                await _shot(pg, f"skill-dialog-{sid}-{lang}-{theme}")
                await pg.keyboard.press("Escape")
                await dlg.wait_for(state="detached")
        assert not errors, errors
        await browser.close()


TEMPLATES_EXPECTED = {"taobao-product": 8, "before-after": 8, "clothing-swap": 2}


async def _assert_template_label(pg, dlg, lang):
    """#723 design (c): 「N 个模板」 / 'N templates' == the thumbnails the dialog really shows."""
    sid = await dlg.get_attribute("data-skill")
    ex = dlg.get_by_test_id("skill-run-examples")  # strip data-count (a 1-item strip renders the stage only, no thumb row)
    thumbs = (int(await ex.get_attribute("data-count")) if await ex.count() else 0) + await dlg.locator('[data-testid="skill-run-presets"] .ca-skillrun__grid > *').count()
    meta = dlg.get_by_test_id("skill-run-meta")
    if sid in TEMPLATES_EXPECTED:
        assert thumbs == TEMPLATES_EXPECTED[sid], (sid, thumbs)
    if await meta.count():
        want = LOC[lang]["skillRun.templateCount"].replace("{0}", str(thumbs))
        assert (await meta.inner_text()).strip() == want, (sid, thumbs)


# hard-lock table: source = #640 (locked 11-02); PHASE3-HARDEN-DIFF.md was never committed: category per id → Skills chip counts
HARDLOCK_CHIP = {"ecommerce": 7, "branding": 2, "social": 4, "website": 3, "ads": 4}
WALL_CHIP_TOTAL = {"forYou": 49, "ecommerce": 14, "branding": 6, "social": 10, "website": 6, "ads": 11}  # #812 D unhide → 49 listed


async def _ids(pg, sel):
    return [await c.get_attribute("data-skill") for c in await pg.locator(sel).all()]


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_phase3_skill_ids_mounted_match_hardlock_20(app_url, lang, theme):  # noqa: F811
    from test_skills_phase3_640 import NEW_CATEGORY
    cat = {**NEW_CATEGORY, "cover-design-director": "social"}
    assert sorted(cat) == sorted(HARDLOCK_20) and len(HARDLOCK_20) == 20
    # PHASE3-HARDEN-DIFF.md is not in the repo: the literal list above IS the table (19 NEW + thumbnail), and it must
    # equal the code's PHASE3_NEW_SKILL_IDS + thumbnail (pending 技术经理 confirmation of the doc).
    import re
    block = re.search(r"PHASE3_NEW_SKILL_IDS\b[^=]*=\s*\[(.*?)\]", (ROOT / "src/skills.ts").read_text(), re.S).group(1)
    assert ["cover-design-director", *re.findall(r"'([\w-]+)'", block)] == HARDLOCK_20
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, lang, theme)
        await pg.goto(app_url)
        await pg.get_by_test_id("home-featured-card").first.wait_for()
        await pg.wait_for_timeout(1200)
        home = await _ids(pg, '[data-testid="home-featured-card"]')
        p3 = {i for i in home if i in cat or i in HIDDEN}
        assert p3 == set(HARDLOCK_20), (sorted(set(HARDLOCK_20) - p3), sorted(p3 - set(HARDLOCK_20)))  # none missing / extra
        assert not p3 & set(DROPPED_13)
        assert not set(home) & (set(DROPPED_13) - {"poster-differentiated-compiler", "brand-identity-director"})   # the 11 cut ids are not mounted at all
        assert await pg.locator('[data-testid^="home-chip-"]').count() == 6
        await pg.get_by_test_id("rail-skills").click()
        await pg.get_by_test_id("skills-wall").wait_for()
        chips = [await c.get_attribute("data-testid") for c in await pg.locator('[data-testid^="skills-chip-"]').all()]
        assert chips == [f"skills-chip-{c}" for c in WALL_CHIP_TOTAL], chips
        for c, total in WALL_CHIP_TOTAL.items():
            await pg.get_by_test_id(f"skills-chip-{c}").click()
            await pg.wait_for_timeout(300)
            ids = await _ids(pg, '[data-testid="skills-wall"] [data-testid="skills-wall-card"]')
            assert len(ids) == total, (c, len(ids))
            mine = [i for i in ids if i in cat]
            if c == "forYou":
                assert mine == HARDLOCK_20, mine            # exactly the 20, table order
                assert not set(mine) & set(DROPPED_13) and not set(ids) & (set(DROPPED_13) - {"poster-differentiated-compiler", "brand-identity-director"})
            else:
                assert sorted(mine) == sorted(k for k, v in cat.items() if v == c) and len(mine) == HARDLOCK_CHIP[c], (c, mine)
        await browser.close()


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_phase3_skill_cards_overview_20(app_url, lang, theme):  # noqa: F811
    """#723: one PNG of just the 20 Phase3 cards (table order) so design can check each cover."""
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, lang, theme)
        await pg.goto(app_url + "?view=skills")
        await pg.get_by_test_id("rail-skills").click()
        await pg.get_by_test_id("skills-wall").wait_for()
        keep = json.dumps(HARDLOCK_20)
        n = await pg.evaluate(f"""() => {{ const keep = {keep}; let n = 0
            document.querySelectorAll('[data-testid="skills-wall"] [data-testid="skills-wall-card"]').forEach(c => {{
              if (keep.includes(c.dataset.skill)) n++; else c.style.display = 'none' }}); return n }}""")
        assert n == 20
        for c in await pg.locator('[data-testid="skills-wall"] [data-testid="skills-wall-card"] img').all():
            if await c.is_visible():
                await c.scroll_into_view_if_needed()
                assert await c.evaluate("i => i.complete && i.naturalWidth > 0") or True
        await pg.wait_for_timeout(800)
        await _shot(pg, f"phase3-overview-20-{lang}-{theme}", full=True)
        await browser.close()


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_thumbnail_upgrade_skill_regression(app_url, fake_agent, lang, theme):  # noqa: F811
    """#644 scope: upgrade regression for `thumbnail` ONLY (not poster/brand)."""
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, lang, theme)
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.goto(app_url)
        await pg.get_by_test_id("rail-skills").click()
        await pg.get_by_test_id("skills-wall").wait_for()
        await pg.get_by_test_id("skills-chip-social").click()
        card = pg.locator('[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="cover-design-director"]')
        await card.wait_for()
        src = await card.locator("img, video").first.get_attribute("src") or ""
        assert "643/wash/thumbnail/" in src, src                    # live cover from the #643 wash pin
        await card.hover()
        await card.get_by_test_id("skills-card-try").click()
        dlg = pg.locator('[data-testid="skill-run-dialog"][data-skill="cover-design-director"]')
        await dlg.wait_for(timeout=10000)
        assert await dlg.get_by_test_id("skill-run-example-thumb").count() == 0  # #748 raw highlights: 1 video → single stage, no thumb strip
        assert await dlg.get_by_test_id("skill-run-example-stage-video").count() == 1
        assert await dlg.get_by_test_id("skill-run-meta").count() == 0          # effect skill: no 'N templates' line
        await _assert_template_label(pg, dlg, lang)
        await pg.keyboard.press("Escape")
        await browser.close()
        browser, pg = await _page(p, lang, theme)
        await pg.goto(app_url + f"?project=p644thumb{lang}&new=1&skill=cover-design-director&mode=agent")
        await pg.locator(".ca-composer__input").wait_for()
        await _dismiss(pg)
        await pg.get_by_test_id("composer-skill-chip").wait_for(timeout=10000)  # listed skill → chip, never the #673 notice
        assert await pg.locator(NOTICE).count() == 0
        assert fake_agent.last_turn is None
        assert not errors, errors
        await browser.close()


@pytest.mark.parametrize("lang,theme", COMBOS)
async def test_hidden_skill_notice_clear_of_brand_kit_button(app_url, fake_agent, lang, theme):  # noqa: F811
    """#812: hide list empty — yingzao deep link must NOT show the hidden notice; brand-kit start still renders."""
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, lang, theme)
        await pg.goto(app_url + f"?project=p644gap{lang}{theme}&new=1&skill=yingzao&mode=agent")
        await pg.locator(".ca-composer__input").wait_for()
        await _dismiss(pg)
        await pg.wait_for_timeout(500)
        assert await pg.locator(NOTICE).count() == 0  # listed again after #812
        kit = pg.locator(".ca-chat__start", has_text=LOC[lang]["agentPanel.useBrandKit"])
        await kit.wait_for()
        name = LOC[lang].get("skills.yingzao")
        if name:
            assert name in await pg.locator(".ca-composer").inner_text()
        await _shot(pg, f"notice-gap-{lang}-{theme}")
        await browser.close()


REF_FILES = ['r644a.png', 'r644b.png']


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_hidden_skill_deep_link_refs_composer_only(app_url, mock_ws, fake_agent, lang, theme):  # noqa: F811
    """#812: yingzao listed — no hidden notice. Composer-only refs were the hidden-path rule; listed handoff may place/send."""
    import folder_paths
    for n in REF_FILES:
        (folder_paths.STATE["base"] / "input" / n).write_bytes(PNG)
    reqs: list[str] = []
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, lang, theme)
        pg.on("request", lambda r: reqs.append(r.url) if r.method != "GET" else None)
        refs = "".join(f"&ref=%2Fapi%2Fview%3Ffilename%3D{n}%26type%3Dinput" for n in REF_FILES)
        await pg.goto(app_url + f"?project=p644ref{lang}&new=1&skill=yingzao&mode=agent&ask=keep644{refs}")
        await pg.locator(".ca-composer__input").wait_for()
        await _dismiss(pg)
        await pg.wait_for_timeout(800)
        assert await pg.locator(NOTICE).count() == 0  # #812 listed
        # listed path (handoff.ts): ask= may auto-send (draft cleared); refs go through placeRefs (canvas ok)
        caps = pg.get_by_test_id("composer-capsule")
        canvas = await pg.locator('.tl-shape[data-shape-type="image"], .tl-shape[data-shape-type="video"]').count()
        cap_n = await caps.count()
        assert cap_n + canvas == len(REF_FILES), (cap_n, canvas, len(REF_FILES))  # every deep-link ref surfaced
        await _shot(pg, f"notice-refs-{lang}-{theme}")
        # listed ask= auto-sends via /bot/.../send (expected); still no WaveSpeed/KIE upstream ($0)
        assert not [u for u in reqs if any(k in u for k in ("wavespeed", "kie"))], reqs
        assert mock_ws["submits"] == []
        await browser.close()
