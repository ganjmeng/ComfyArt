"""#479: chat memory steps in the real app — update shows 记忆已读取 then 记忆已更新 ›; add shows only 记忆已更新 ›.

记忆已读取 is a plain, non-clickable row; the 「已保存 N 条」 detail under 记忆已更新 is unchanged.
Set SHOTS479=/dir to also save screenshots of the chat (mock data, no model calls).
"""
import os
import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401,E402
from test_e2e_default_agent import fake_tools, _page  # noqa: F401,E402

_use = lambda i: {"type": "tool_use", "id": i, "name": "mcp__comfyart__memory", "input": {"action": "add"}}  # noqa: E731
_res = lambda i: {"type": "tool_result", "id": i, "name": "mcp__comfyart__memory", "status": "success", "text": "{}"}  # noqa: E731

_LABELS = {"zh": ("记忆已读取", "记忆已更新", "已保存 {0} 条"), "en": ("Memory retrieved", "Memory updated", "Saved {0}")}
_TEXTS = {"zh": ["品牌色：克莱因蓝", "画幅：4:3"], "en": ["Brand colour: Klein blue", "Aspect ratio: 4:3"]}


async def _open(pg, lang, title, updated_ids):
    from ComfyArt.api import chat_store
    user = await pg.evaluate("async()=>(await (await fetch('/api/comfyart/bot/status')).json()).user")
    proj = await pg.evaluate(r"()=>{for (const e of performance.getEntriesByType('resource')){const m=e.name.match(/bot\/chats\?project=([^&]+)/); if(m) return decodeURIComponent(m[1])} return null}")
    assert proj
    texts = _TEXTS[lang]
    c = chat_store.create_chat(user=user, project=proj, provider="local-llm", title=title)
    um = chat_store.create_message(chat_id=c["id"], role="user", blocks=[{"type": "text", "text": "记住我的品牌色和画幅" if lang == "zh" else "Remember my brand colour and aspect ratio"}])
    chat_store.create_message(chat_id=c["id"], role="assistant", parent_id=um["id"], blocks=[
        {"type": "text", "text": "好的。" if lang == "zh" else "Sure."}, _use("c1"), _res("c1"),
        {"type": "memory_updated", "memory_ids": ["m1", "m2"], "texts": texts,
         "tool_id": "c1", "tool_ids": ["c1"], "updated_ids": updated_ids, "count": 2},
        {"type": "text", "text": "已记住。" if lang == "zh" else "Got it."}])
    await pg.reload()
    await pg.locator(".ca-split__chev").first.click(timeout=8000)
    await pg.locator(".ca-history__item", has_text=title).first.click(timeout=8000)
    await pg.locator("[data-testid=memory-updated-row]").last.wait_for(timeout=10000)
    await pg.mouse.move(5, 790)
    await pg.wait_for_timeout(300)


async def _rows(pg):
    return await pg.locator(".ca-chat__bot").last.locator(".ca-process__row[data-kind^='memory_']").evaluate_all(
        "els => els.map(e => [e.dataset.kind, (e.querySelector('.ca-process__label')?.childNodes[0]?.textContent || '').trim()])")


async def _detail(pg, lang):
    d = pg.locator("[data-testid=memory-saved-detail]")
    assert await d.count() == 1
    assert (await d.locator(".ca-process__memcount").inner_text()).strip() == _LABELS[lang][2].format(2)
    assert [x.strip() for x in await d.locator(".ca-process__memlist li").all_inner_texts()] == _TEXTS[lang]
    # detail sits under 记忆已更新, not under 记忆已读取
    assert await pg.locator("[data-testid=memory-retrieved-row] ~ [data-testid=memory-saved-detail]").count() == 0


def _shot_dir():
    d = os.environ.get("SHOTS479")
    if d:
        os.makedirs(d, exist_ok=True)
    return d


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("zh", "dark"), ("en", "light"), ("en", "dark")])
async def test_update_shows_retrieved_then_updated_479(app_url, fake_tools, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, app_url, lang, theme)
        await _open(pg, lang, f"u479{lang}{theme}", ["m1"])
        ret, upd, _ = _LABELS[lang]
        assert await _rows(pg) == [["memory_retrieved", ret], ["memory_updated", upd]]
        r = pg.locator("[data-testid=memory-retrieved-row]")
        # retrieved is a plain row: no button, no ›, no pointer, click opens nothing
        assert await r.locator("button, a, [role=button]").count() == 0
        assert await r.locator(".ca-process__memchev").count() == 0
        assert await r.evaluate("e => getComputedStyle(e.querySelector('.ca-process__label')).cursor") != "pointer"
        await r.click()
        await pg.wait_for_timeout(300)
        assert await pg.locator(".ca-memory").count() == 0
        assert await pg.locator("[data-testid=memory-updated-chev]").count() == 1
        await _detail(pg, lang)
        d = _shot_dir()
        if d:
            await pg.mouse.move(5, 790)
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=f"{d}/479-update-{lang}-{theme}.png")
        # updated › still opens the memory dialog
        await pg.locator("[data-testid=memory-updated-open]").click()
        await pg.locator(".ca-memory").first.wait_for(timeout=5000)
        await browser.close()


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_add_shows_only_updated_479(app_url, fake_tools, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, app_url, lang, theme)
        await _open(pg, lang, f"a479{lang}{theme}", [])
        assert await _rows(pg) == [["memory_updated", _LABELS[lang][1]]]
        assert await pg.locator("[data-testid=memory-retrieved-row]").count() == 0
        assert await pg.locator("[data-testid=memory-updated-chev]").count() == 1
        await _detail(pg, lang)
        d = _shot_dir()
        if d:
            await pg.screenshot(path=f"{d}/479-add-{lang}-{theme}.png")
        await browser.close()
