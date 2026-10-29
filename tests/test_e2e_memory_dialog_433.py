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
    "en": {"menu": "Memory", "groups": None, "pill": "Edit memory via chat",
           "empty": ["Oops.", "Arti doesn't know you yet"], "add": "Add your basic info", "del": "Delete this memory?", "menuitems": None, "edited": "You prefer cool tones; the brand colour is now blue."},
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
        assert int(await card.locator(".ca-arti-mem__label").evaluate("e => getComputedStyle(e).fontWeight")) >= 600
        assert await card.evaluate("e => getComputedStyle(e).borderTopStyle") == "solid"
        assert tx["add"] in await dlg.locator("[data-testid=memory-dialog-add-about]").inner_text()
        assert await dlg.locator("[data-testid=memory-dialog-add-about]").evaluate("e => getComputedStyle(e).borderTopStyle") == "dashed"
        # product ruling: nothing highlighted, no undo
        assert await dlg.locator("[data-focus], [data-testid=memory-focus-row], [data-testid=memory-updated-undo]").count() == 0
        await pg.mouse.move(1000, 620)
        await pg.wait_for_timeout(200)
        await shot(pg, "433-loaded", tag)

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
