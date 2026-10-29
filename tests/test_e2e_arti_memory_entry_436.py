"""#436: Arti empty memory tab + chat 「记忆已更新 ›」 opens the same MemoryDialog without highlight."""
from __future__ import annotations

import os

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools, _page, pytestmark  # noqa: F401

_use = lambda i: {"type": "tool_use", "id": i, "name": "mcp__comfyart__memory", "input": {"action": "add"}}  # noqa: E731
_res = lambda i: {"type": "tool_result", "id": i, "name": "mcp__comfyart__memory", "status": "success", "text": "{}"}  # noqa: E731
OUT = os.environ.get("SHOT_OUT")


async def shot(pg, name):
    if OUT:
        os.makedirs(OUT, exist_ok=True)
        await pg.screenshot(path=f"{OUT}/{name}.png")


@pytest.mark.asyncio
async def test_arti_empty_tab_and_go_complete(app_url, fake_tools):  # noqa: F811
    async with pw.async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width": 1280, "height": 1600}, device_scale_factor=1)).new_page()
        await pg.add_init_script(
            "localStorage.setItem('comfyart.lang','zh');"
            "localStorage.setItem('comfyart.theme','light');"
            "localStorage.setItem('comfyart.e2e','1')"
        )
        await pg.goto(app_url.rstrip("/") + "/?view=arti")
        await pg.locator("[data-testid=arti-page]").wait_for(timeout=20000)
        await pg.locator("[data-testid=arti-intro-actions]").wait_for(timeout=5000)
        assert await pg.locator("[data-testid=arti-tell-yourself]").count() == 1
        assert await pg.locator("[data-testid=arti-learn-past]").is_disabled()
        empty = pg.locator("[data-testid=arti-memory-tab-empty]")
        await empty.wait_for(timeout=15000)
        assert "暂无记忆" in await empty.inner_text()
        assert await pg.locator("[data-testid=arti-memory-go-complete]").inner_text() == "去完善"
        await pg.locator("[data-testid=arti-memory-go-complete]").click()
        dlg = pg.locator(".ca-memory")
        await dlg.wait_for(timeout=5000)
        # onboard title
        assert "聊聊" in await dlg.inner_text() or "自己" in await dlg.inner_text()
        await shot(pg, "436-arti-go-complete-onboard")
        await b.close()


@pytest.mark.asyncio
async def test_chat_memory_updated_opens_dialog_no_highlight(app_url, fake_tools):  # noqa: F811
    from ComfyArt.api import chat_store
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, app_url, "zh")
        user = await pg.evaluate("async()=>(await (await fetch('/api/comfyart/bot/status')).json()).user")
        proj = await pg.evaluate("""() => {
          for (const e of performance.getEntriesByType('resource')) {
            try {
              const u = new URL(e.name)
              if (u.pathname.endsWith('/bot/chats')) return u.searchParams.get('project')
            } catch (_) {}
          }
          return null
        }""")
        assert proj
        c = chat_store.create_chat(user=user, project=proj, provider="local-llm", title="m436")
        um = chat_store.create_message(chat_id=c["id"], role="user", blocks=[{"type": "text", "text": "remember"}])
        chat_store.create_message(
            chat_id=c["id"], role="assistant", parent_id=um["id"],
            blocks=[
                {"type": "text", "text": "ok"}, _use("c1"), _res("c1"),
                {"type": "memory_updated", "memory_ids": ["m1"], "texts": ["暖色调"],
                 "tool_id": "c1", "tool_ids": ["c1"], "updated_ids": ["m1"], "count": 1},
                {"type": "text", "text": "记好了。"},
            ],
        )
        await pg.reload()
        await pg.locator(".ca-split__chev").first.click(timeout=8000)
        await pg.locator(".ca-history__item").first.click(timeout=8000)
        row = pg.locator("[data-testid=memory-updated-open]").last
        await row.wait_for(timeout=10000)
        await row.click()
        dlg = pg.locator(".ca-memory")
        await dlg.wait_for(timeout=5000)
        # no focus / undo chrome
        assert await dlg.locator("[data-focus], [data-testid=memory-focus-row], [data-testid=memory-updated-undo]").count() == 0
        await shot(pg, "436-chat-opens-dialog")
        await browser.close()
