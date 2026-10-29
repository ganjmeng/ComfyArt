"""#433 interaction test (real built UI, mock host, $0): the project-menu memory dialog shows four vertical groups
in the measured order, title + body cards, empty-group add rows, the bottom 「通过对话修改记忆」 pill and the measured
empty state; nothing is highlighted and there is no undo; delete goes through the confirm dialog.

Set SHOT_OUT=<dir> to save the review screenshots (zh light, en dark)."""
import os

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import fake_tools, pytestmark  # noqa: F401
from test_e2e_memory_381 import SEED_JS

OUT = os.environ.get("SHOT_OUT")
MEM = [{"id": "c1", "text": "你偏好暖色调，品牌主色是橙色，后续视觉创作默认以此为基调。", "time": 1, "category": "taste", "label": "色彩偏好"}]
MEM_EN = [{"id": "c1", "text": "You prefer warm tones; the brand colour is orange, used as the default base for visuals.", "time": 1, "category": "taste", "label": "Colour preference"}]
TEXT = {
    "zh": {"menu": "记忆", "groups": ["审美偏好", "基础信息", "协作方式", "常用资产"], "pill": "通过对话修改记忆",
           "empty": ["Oops.", "Arti 还不认识你"], "add": "添加你的基础信息", "del": "删除此记忆？", "menuitems": ["更正记忆", "删除"], "edited": "你偏好冷色调，品牌主色改为蓝色。"},
    "en": {"menu": "Memory", "groups": ["Visual taste", "About you", "How we work", "Reused assets"], "pill": "Chat with Arti to edit memory",
           "empty": ["Oops.", "Arti doesn't know you yet"], "add": "Add your background", "del": "Delete this memory?", "menuitems": None, "edited": "You prefer cool tones; the brand colour is now blue."},
}


async def shot(pg, name, tag):
    if OUT:
        os.makedirs(OUT, exist_ok=True)
        await pg.screenshot(path=f"{OUT}/{name}-{tag}.png")


async def open_dialog(pg, menu):
    await pg.locator(".ca-head__logo").click()
    await pg.locator(".ca-menu__item", has_text=menu).first.click()
    dlg = pg.locator(".ca-memory")
    await dlg.wait_for(timeout=5000)
    await pg.wait_for_timeout(300)
    return dlg


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_memory_dialog_433(app_url, fake_tools, lang, theme):  # noqa: F811
    tx = TEXT[lang]
    tag = f"{lang}-{theme}"
    async with pw.async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width": 1024, "height": 640}, device_scale_factor=1, timezone_id="Asia/Shanghai")).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}');localStorage.setItem('comfyart.e2e','1')")
        await pg.goto(app_url.rstrip("/") + "/?project=e433&new=1")
        await pg.locator(".ca-composer__mode").wait_for(timeout=15000)
        await pg.wait_for_timeout(800)

        # measured empty state
        dlg = await open_dialog(pg, tx["menu"])
        empty = dlg.locator("[data-testid=memory-empty-state]")
        await empty.wait_for(timeout=5000)
        for s in tx["empty"]:
            assert s in await empty.inner_text()
        assert (await dlg.locator("[data-testid=memory-dialog-chat-open]").inner_text()).strip() == tx["pill"]
        await shot(pg, "433-empty", tag)
        await pg.keyboard.press("Escape")

        await pg.evaluate(SEED_JS, MEM if lang == "zh" else MEM_EN)
        await pg.reload()
        await pg.locator(".ca-composer__mode").wait_for(timeout=15000)
        await pg.wait_for_timeout(800)
        dlg = await open_dialog(pg, tx["menu"])
        await dlg.locator("[data-testid=memory-dialog-card]").first.wait_for(timeout=5000)

        # four vertical groups, measured order, no counts
        ids = await dlg.locator("[data-testid^=memory-dialog-group-]").evaluate_all("els => els.map(e => e.dataset.testid)")
        assert ids == [f"memory-dialog-group-{c}" for c in ("taste", "about", "work", "assets")]
        titles = [t.strip() for t in await dlg.locator(".ca-arti-mem__grouptitle").all_inner_texts()]
        if tx["groups"]:
            assert titles == tx["groups"]
        ys = [(await g.bounding_box())["y"] for g in await dlg.locator("[data-testid^=memory-dialog-group-]").all()]
        assert ys == sorted(ys) and len(set(ys)) == 4  # stacked vertically
        # title + body card
        card = dlg.locator("[data-testid=memory-dialog-card]").first
        assert int(await card.locator(".ca-arti-mem__label").evaluate("e => getComputedStyle(e).fontWeight")) == 500
        assert await card.evaluate("e => getComputedStyle(e).borderTopStyle") == "solid"
        # #439 reference DOM values, checked with getComputedStyle
        CS = """(e, props) => { const c = getComputedStyle(e); return props.map(p => c.getPropertyValue(p)) }"""
        light = theme == "light"
        async def cs(loc, props):
            return await loc.evaluate(CS, props)
        head = pg.locator("[data-testid=memory-dialog-head]")
        assert await cs(head, ["font-size", "line-height", "font-weight"]) == ["18px", "26px", "600"]
        if light:
            assert (await cs(head, ["color"]))[0] == "rgba(0, 0, 0, 0.9)"
        upd = dlg.locator("[data-testid=memory-dialog-updated]")
        assert await cs(upd, ["font-size", "line-height"]) == ["13px", "20px"]
        if light:
            assert (await cs(upd, ["color"]))[0] == "rgba(0, 0, 0, 0.55)"
        close = dlg.locator(".ca-side__head > .ca-panel__icon")
        cb = await close.bounding_box()
        assert (round(cb["width"]), round(cb["height"])) == (26, 26) and (await cs(close, ["border-top-left-radius"]))[0] == "8px"
        assert round((await close.locator("svg").bounding_box())["width"]) == 16
        gt = dlg.locator("[data-testid=memory-dialog-grouptitle]").first
        assert await cs(gt, ["font-size", "line-height", "font-weight", "column-gap", "padding-left", "padding-right"]) == ["13px", "22px", "400", "6px", "8px", "8px"]
        for gsvg in await dlg.locator("[data-testid=memory-dialog-grouptitle] .ca-icon svg").all():
            # true filled icons: fill on the svg, no stroke, 16px, .55 like the title
            assert await gsvg.get_attribute("fill") == "currentColor" and await gsvg.get_attribute("stroke") is None
            assert round((await gsvg.bounding_box())["width"]) == 16 and (await cs(gsvg, ["stroke"]))[0] == "none"
            if light:
                assert (await cs(gsvg, ["color"]))[0] == "rgba(0, 0, 0, 0.55)"
        if OUT and light:
            await dlg.locator("[data-testid=memory-dialog-grouptitle]").first.wait_for()
            c4 = await b.new_context(viewport={"width": 320, "height": 80}, device_scale_factor=4)
            p4 = await c4.new_page()
            svgs = await dlg.locator("[data-testid=memory-dialog-grouptitle] .ca-icon").evaluate_all("els => els.map(e => e.innerHTML)")
            cells = "".join(f'<span style="display:inline-flex;width:16px;height:16px;margin:12px;color:rgba(0,0,0,.55)">{h}</span>' for h in svgs)
            await p4.set_content(f'<body style="margin:0;background:#fff"><div id=r style="display:inline-flex;padding:4px">{cells}</div><style>svg{{width:16px;height:16px}}</style></body>')
            await p4.locator("#r").screenshot(path=f"{OUT}/433-icons4x.png")
            await c4.close()
        if light:
            assert (await cs(gt, ["color"]))[0] == "rgba(0, 0, 0, 0.55)"
        lab, body = card.locator(".ca-arti-mem__label"), card.locator(".ca-arti-mem__text")
        assert await cs(lab, ["font-size", "line-height", "font-weight"]) == ["13px", "22px", "500"]
        assert await cs(body, ["font-size", "line-height", "font-weight"]) == ["13px", "22px", "400"]
        assert await cs(card, ["padding-top", "padding-left", "border-top-left-radius"]) == ["12px", "16px", "16px"]
        if light:
            assert await cs(lab, ["color"]) == await cs(body, ["color"]) == ["rgba(0, 0, 0, 0.9)"]
        addl = dlg.locator("[data-testid=memory-dialog-add-about]")
        assert abs((await addl.bounding_box())["height"] - 48) < 0.6
        assert await cs(addl, ["border-top-width", "border-top-style", "border-top-left-radius", "padding-top", "padding-left", "font-size", "line-height"]) == ["1px", "dashed", "16px", "12px", "16px", "13px", "22px"]
        if light:
            assert await cs(addl, ["border-top-color", "color"]) == ["rgba(0, 0, 0, 0.1)", "rgba(0, 0, 0, 0.3)"]
        pill = dlg.locator("[data-testid=memory-dialog-chat-open]")
        pb = await pill.bounding_box()
        assert abs(pb["height"] - 48) < 0.6
        assert await cs(pill, ["background-color", "color", "font-size", "line-height"]) == ["rgb(44, 44, 44)", "rgb(255, 255, 255)", "14px", "22px"]
        assert float((await cs(pill, ["border-top-left-radius"]))[0][:-2]) >= 24
        if lang == "zh":
            assert abs(pb["width"] - 144) < 1
        else:
            assert abs(pb["width"] - 225.5) < 12  # width follows the text
        dcard = pg.locator(".ca-modal__card.ca-memory")
        db_ = await dcard.bounding_box()
        assert round(db_["width"]) == 720 and round(db_["height"]) == min(698, 640 - 64)
        assert (await cs(dcard, ["border-top-left-radius", "border-top-width"])) == ["16px", "1px"]
        if light:
            assert await cs(dcard, ["border-top-color", "box-shadow"]) == ["rgba(0, 0, 0, 0.07)", "rgba(0, 0, 0, 0.06) 0px 16px 24px -8px, rgba(0, 0, 0, 0.04) 0px 4px 8px -4px, rgba(0, 0, 0, 0.02) 0px 1px 1px 0px"]
        assert tx["add"] in await dlg.locator("[data-testid=memory-dialog-add-about]").inner_text()
        assert await dlg.locator("[data-testid=memory-dialog-add-about]").evaluate("e => getComputedStyle(e).borderTopStyle") == "dashed"
        # product ruling: nothing highlighted, no undo
        assert await dlg.locator("[data-focus], [data-testid=memory-focus-row], [data-testid=memory-updated-undo]").count() == 0
        await pg.mouse.move(1000, 620)
        await pg.wait_for_timeout(200)
        await shot(pg, "433-loaded", tag)
        if OUT:  # dialog-only crop at 2x for the measurement comparison
            c2 = await b.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=2, timezone_id="Asia/Shanghai")
            await c2.add_cookies(await pg.context.cookies())
            p2 = await c2.new_page()
            await p2.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}');localStorage.setItem('comfyart.e2e','1')")
            await p2.goto(pg.url)
            await p2.locator(".ca-composer__mode").wait_for(timeout=15000)
            await p2.evaluate(SEED_JS, MEM if lang == "zh" else MEM_EN)
            await p2.reload()
            await p2.locator(".ca-composer__mode").wait_for(timeout=15000)
            await p2.wait_for_timeout(800)
            d2 = await open_dialog(p2, tx["menu"])
            await d2.locator("[data-testid=memory-dialog-card]").first.wait_for(timeout=5000)
            await p2.mouse.move(1000, 620)
            await p2.wait_for_timeout(200)
            await d2.screenshot(path=f"{OUT}/433-dialog2x-{tag}.png")
            await c2.close()

        # #434: hover reveals edit + ··· menu (更正记忆 / 删除)
        acts = card.locator(".ca-arti-mem__actions")
        assert float(await acts.evaluate("e => getComputedStyle(e).opacity")) < 0.5
        await card.hover()
        await pg.wait_for_timeout(250)
        assert float(await acts.evaluate("e => getComputedStyle(e).opacity")) > 0.9
        await card.locator("[data-testid=arti-memory-menu-btn]").click()
        menu = card.locator("[data-testid=arti-memory-row-menu]")
        items = [x.strip() for x in await menu.locator("button").all_inner_texts()]
        assert len(items) == 2 and (tx["menuitems"] is None or items == tx["menuitems"])
        await shot(pg, "434-hover", tag)

        # real edit: 更正记忆 -> inline textarea, save disabled until changed, persisted
        await menu.locator("button").first.click()
        edit = dlg.locator("[data-testid=arti-memory-edit-row]")
        await edit.wait_for(timeout=5000)
        save = edit.locator("[data-testid=arti-memory-edit-save]")
        assert await save.is_disabled()
        await edit.locator("textarea").fill(tx["edited"])
        assert await save.is_enabled()
        await shot(pg, "434-edit", tag)
        await save.click()
        await edit.wait_for(state="detached", timeout=5000)
        await dlg.locator("[data-testid=memory-dialog-saving]").wait_for(state="detached", timeout=5000)
        await dlg.locator("[data-testid=memory-dialog-card]", has_text=tx["edited"]).wait_for(timeout=5000)
        await pg.keyboard.press("Escape")
        await pg.reload()
        await pg.locator(".ca-composer__mode").wait_for(timeout=15000)
        await pg.wait_for_timeout(800)
        dlg = await open_dialog(pg, tx["menu"])
        card = dlg.locator("[data-testid=memory-dialog-card]").first
        await card.wait_for(timeout=5000)
        assert tx["edited"] in await card.inner_text()  # persisted

        # real delete only through the confirm dialog, no undo
        await card.hover()
        await card.locator("[data-testid=arti-memory-menu-btn]").click()
        await card.locator("[data-testid=arti-memory-row-menu] button[data-danger]").click()
        conf = pg.locator("[data-testid=confirm-dialog]")
        await conf.wait_for(timeout=5000)
        assert tx["del"] in await pg.locator(".ca-modal:has([data-testid=confirm-dialog])").inner_text()
        assert await dlg.locator("[data-testid=memory-dialog-card]").count() == 1  # not removed before confirming
        await shot(pg, "434-confirm", tag)
        await pg.locator(".ca-modal:has([data-testid=confirm-dialog]) .ca-panel__primary").click()
        await dlg.locator("[data-testid=memory-empty-state]").wait_for(timeout=5000)
        assert await pg.locator("[data-testid=memory-updated-undo]").count() == 0
        await pg.keyboard.press("Escape")
        await pg.reload()
        await pg.locator(".ca-composer__mode").wait_for(timeout=15000)
        await pg.wait_for_timeout(800)
        dlg = await open_dialog(pg, tx["menu"])
        await dlg.locator("[data-testid=memory-empty-state]").wait_for(timeout=5000)  # persisted
        await b.close()


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_memory_dialog_skeleton_and_saving_433(app_url, fake_tools, lang, theme):  # noqa: F811
    """Reference states: skeleton while the dialog's read is in flight; pill turns into 「记忆更新中」 + spinner and the
    entry dims while a manual save is in flight. Requests are held with page.route (mock host, $0)."""
    import asyncio
    tx = TEXT[lang]
    tag = f"{lang}-{theme}"
    saving_txt = {"zh": "记忆更新中", "en": "Updating memory"}[lang]
    async with pw.async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width": 1024, "height": 640}, device_scale_factor=1, timezone_id="Asia/Shanghai")).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}');localStorage.setItem('comfyart.e2e','1')")
        await pg.goto(app_url.rstrip("/") + "/?project=e433s&new=1")
        await pg.locator(".ca-composer__mode").wait_for(timeout=15000)
        await pg.evaluate(SEED_JS, MEM if lang == "zh" else MEM_EN)
        await pg.reload()
        await pg.locator(".ca-composer__mode").wait_for(timeout=15000)
        await pg.wait_for_timeout(800)

        gate = {"get": None, "post": None}

        async def hold(route):
            kind = "post" if route.request.method == "POST" else "get"
            ev = gate[kind]
            if ev is not None:
                await ev.wait()
            await route.continue_()
        await pg.route("**/api/comfyart/memory", hold)

        # skeleton while the open-time read is held
        gate["get"] = asyncio.Event()
        dlg = await open_dialog(pg, tx["menu"])
        sk = dlg.locator("[data-testid=memory-dialog-skeleton]")
        await sk.wait_for(timeout=5000)
        assert await dlg.locator("[data-testid=memory-dialog-card]").count() == 0
        assert await sk.locator(".ca-memory__skcard").count() >= 4
        await pg.mouse.move(1000, 620)
        await shot(pg, "433-skeleton", tag)
        gate["get"].set(); gate["get"] = None
        await sk.wait_for(state="detached", timeout=5000)
        card = dlg.locator("[data-testid=memory-dialog-card]").first
        await card.wait_for(timeout=5000)

        # saving state while the write is held
        await card.hover()
        await card.locator("[data-testid=arti-memory-edit-btn]").click()
        edit = dlg.locator("[data-testid=arti-memory-edit-row]")
        await edit.locator("textarea").fill(tx["edited"])
        gate["post"] = asyncio.Event()
        await edit.locator("[data-testid=arti-memory-edit-save]").click()
        pill = dlg.locator("[data-testid=memory-dialog-saving]")
        await pill.wait_for(timeout=5000)
        assert saving_txt in await pill.inner_text()
        assert await pill.locator(".ca-memory__spin").count() == 1
        assert await dlg.locator("[data-testid=memory-dialog-chat-open]").count() == 0
        dim = dlg.locator("[data-testid=memory-dialog-card][data-saving]")
        assert await dim.count() == 1  # entry dimmed
        assert tx["edited"] in await dim.inner_text()  # new text shown while saving
        await pg.mouse.move(1000, 620)
        await shot(pg, "433-saving", tag)
        gate["post"].set(); gate["post"] = None
        await pill.wait_for(state="detached", timeout=5000)
        await dlg.locator("[data-testid=memory-dialog-chat-open]").wait_for(timeout=5000)
        await dlg.locator("[data-testid=memory-dialog-card]", has_text=tx["edited"]).wait_for(timeout=5000)
        await b.close()


async def test_memory_dialog_save_failure_reverts_433(app_url, fake_tools):  # noqa: F811
    """A failed save drops the pending text: the entry goes back to the old text, undimmed."""
    import asyncio
    async with pw.async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width": 1024, "height": 640})).new_page()
        await pg.add_init_script("localStorage.setItem('comfyart.lang','zh');localStorage.setItem('comfyart.e2e','1')")
        await pg.goto(app_url.rstrip("/") + "/?project=e433f&new=1")
        await pg.locator(".ca-composer__mode").wait_for(timeout=15000)
        await pg.evaluate(SEED_JS, MEM)
        await pg.reload()
        await pg.locator(".ca-composer__mode").wait_for(timeout=15000)
        await pg.wait_for_timeout(800)
        dlg = await open_dialog(pg, "记忆")
        card = dlg.locator("[data-testid=memory-dialog-card]").first
        await card.wait_for(timeout=5000)
        release = asyncio.Event()

        async def fail(route):
            if route.request.method == "POST":
                await release.wait()
                await route.fulfill(status=500, body="boom")
            else:
                await route.continue_()
        await pg.route("**/api/comfyart/memory", fail)
        await card.hover()
        await card.locator("[data-testid=arti-memory-edit-btn]").click()
        edit = dlg.locator("[data-testid=arti-memory-edit-row]")
        await edit.locator("textarea").fill(TEXT["zh"]["edited"])
        await edit.locator("[data-testid=arti-memory-edit-save]").click()
        dim = dlg.locator("[data-testid=memory-dialog-card][data-saving]")
        await dim.wait_for(timeout=5000)
        assert TEXT["zh"]["edited"] in await dim.inner_text()
        release.set()
        await dim.wait_for(state="detached", timeout=5000)
        txt = await dlg.locator("[data-testid=memory-dialog-card]").first.inner_text()
        assert MEM[0]["text"] in txt and TEXT["zh"]["edited"] not in txt
        await b.close()
