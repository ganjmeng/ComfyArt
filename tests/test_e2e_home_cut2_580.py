"""#580 cut 2 — home feed tabs, category chips (sticky), floating composer, full-bleed masonry with natural ratios,
two embedded special cards (coming-soon toast), placeholder tabs."""
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_home_tools_537 import pw


async def _page(p, url, w=1280):
    b = await p.chromium.launch()
    pg = await (await b.new_context(viewport={"width": w, "height": 800})).new_page()
    await pg.goto(url)
    await pg.get_by_test_id("home-featured-card").first.wait_for()
    return b, pg


async def test_tabs_chips_special_cards_and_full_bleed(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        b, pg = await _page(p, app_url)
        tabs = [await x.get_attribute("data-testid") for x in await pg.get_by_test_id("home-tabs").locator("button").all()]
        assert tabs == ["home-tab-explore", "home-tab-assets", "home-tab-inspiration", "home-tab-pinterest"]
        assert await pg.get_by_test_id("home-tab-explore").get_attribute("aria-selected") == "true"
        # chips from real categories; sticky
        assert await pg.get_by_test_id("home-chip-forYou").count() == 1
        assert await pg.get_by_test_id("home-chips").evaluate("e=>getComputedStyle(e).position") == "sticky"
        # exactly two special cards, in the masonry
        specials = pg.get_by_test_id("home-feed-special")
        assert await specials.count() == 2
        assert sorted([await s.get_attribute("data-special") for s in await specials.all()]) == ["capture", "connector"]
        # design v2: placed by column — capture = col 1 slot 2, connector in col 2; grey card, connector has an input
        cols = pg.get_by_test_id("home-featured-col")
        assert await cols.nth(0).locator(":scope > *").nth(1).get_attribute("data-special") == "capture"
        assert await cols.nth(1).get_by_test_id("home-feed-special").get_attribute("data-special") == "connector"
        assert await pg.locator(".ca-featured__special-body").first.evaluate("e=>getComputedStyle(e).backgroundColor") == "rgb(245, 245, 245)"
        assert await pg.get_by_test_id("home-feed-special-input").count() == 1
        # full-bleed: cover has no base plate and its ratio follows the loaded image
        card = pg.get_by_test_id("home-featured-card").first
        await card.scroll_into_view_if_needed()
        await pg.wait_for_function("()=>{const i=document.querySelector('[data-testid=home-featured-card] img');return i&&i.complete&&i.naturalWidth>0}", timeout=30000)
        await pg.wait_for_timeout(300)
        r = await card.evaluate("c=>{const s=c.querySelector('.ca-featured__cover'),i=s.querySelector('img');const b=s.getBoundingClientRect();return {bg:getComputedStyle(s).backgroundColor,box:b.width/b.height,nat:i.naturalWidth/i.naturalHeight,fit:getComputedStyle(i).objectFit}}")
        assert r["bg"] in ("rgba(0, 0, 0, 0)", "transparent")
        assert r["fit"] == "cover"
        assert abs(r["box"] - r["nat"]) < 0.03 or r["box"] < r["nat"]  # equal unless capped by max-height
        # special card button → coming-soon toast, stays on home
        await pg.get_by_test_id("home-feed-special-connector").scroll_into_view_if_needed()
        await pg.get_by_test_id("home-feed-special-connector").click()
        await pg.get_by_text("即将上线").or_(pg.get_by_text("Coming soon")).first.wait_for(timeout=5000)
        # chip filters the feed to that category
        n_all = await pg.get_by_test_id("home-featured-card").count()
        await pg.get_by_test_id("home-chips").locator("button").nth(1).click()
        await pg.wait_for_timeout(200)
        assert 0 < await pg.get_by_test_id("home-featured-card").count() < n_all
        # floating composer once scrolled away
        assert await pg.get_by_test_id("home-box").get_attribute("data-floating") == "true"
        # placeholder tabs
        for t in ("inspiration", "pinterest"):
            await pg.get_by_test_id(f"home-tab-{t}").click()
            await pg.get_by_test_id(f"home-tab-panel-{t}").wait_for()
            assert await pg.get_by_test_id("home-featured").count() == 0
            assert await pg.get_by_test_id("home-chips").count() == 0
            await pg.get_by_test_id(f"home-tab-action-{t}").click()
        await pg.get_by_test_id("home-tab-assets").click()
        await pg.get_by_test_id("assets-page").wait_for()
        assert await pg.get_by_test_id("home-asset-chips").locator("button").count() == 4
        await pg.get_by_test_id("home-tab-explore").click()
        await pg.get_by_test_id("home-featured").wait_for()
        await b.close()
