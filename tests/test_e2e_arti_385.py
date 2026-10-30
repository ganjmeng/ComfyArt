"""#385 interaction + #78 shots (built dist, mock host, no paid API): switchable toggles persist,
chat composer open, evolution log from memoryLog.

Set SHOT_OUT=<dir> to save light+dark screenshots under docs/design/385/78/after/."""
from __future__ import annotations

import json
import os

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools, pytestmark  # noqa: F401

OUT = os.environ.get("SHOT_OUT")

SEED_LOG = [
    {"time": 1793096400000, "action": "add", "text": "我是插画师", "source": "对话改记忆"},
    {"time": 1793096460000, "action": "update", "text": "我喜欢蓝色 → 我喜欢绿色", "source": "对话改记忆"},
    {"time": 1793096520000, "action": "forget", "text": "我喜欢绿色", "source": "对话改记忆"},
]
# newest first in store (memoryLogAtom order)
SEED_LOG_NEWEST = list(reversed(SEED_LOG))


def seed_store(records=(), log=()):
    import folder_paths
    f = folder_paths.STATE["base"] / "user/default/comfyart/memory-store.json"
    cur = json.loads(f.read_text()) if f.is_file() else {}
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({
        "memory": [{**r, "owner_id": "local", "workspace_id": "local"} for r in records],
        "log": list(log),
        "meta": {"demoCleanup381": True},
        "rev": int(cur.get("rev", 0)) + 1,
        "ops": [],
    }, ensure_ascii=False))


async def shot(pg, name, theme, **kw):
    if OUT:
        os.makedirs(OUT, exist_ok=True)
        await pg.screenshot(path=f"{OUT}/{name}-{theme}.png", **kw)


@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_arti_toggles_chat_evolution_385(app_url, fake_tools, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(
            viewport={"width": 1440, "height": 900}, device_scale_factor=1, timezone_id="Asia/Shanghai",
        )).new_page()
        await pg.add_init_script(
            f"localStorage.setItem('comfyart.lang','zh');localStorage.setItem('comfyart.theme','{theme}');localStorage.setItem('comfyart.e2e','1')"
        )
        # mock LLM complete so chat intent never pays
        async def fake_llm(route):
            body = route.request.post_data_json or {}
            text = (body.get("text") or "")
            msg = text.split("User message:\n")[-1].strip() if "User message:" in text else text
            if "插画师" in msg:
                payload = {"action": "add", "text": "我是插画师", "category": "about"}
            elif "改成" in msg:
                payload = {"action": "correct", "old": "我喜欢蓝色", "new": "我喜欢绿色"}
            elif "忘记" in msg:
                payload = {"action": "forget", "text": "我喜欢蓝色"}
            else:
                payload = {"action": "none"}
            await route.fulfill(status=200, content_type="application/json", body=json.dumps({"text": json.dumps(payload, ensure_ascii=False)}))
        await pg.route("**/comfyart/llm/complete", fake_llm)

        await pg.goto(app_url.rstrip("/") + "/?view=arti")
        await pg.locator("[data-testid=arti-page]").wait_for(timeout=15000)
        await pg.wait_for_timeout(500)

        # AC1: toggle memory on → settings persist across reload
        mem_sw = pg.locator("[data-testid=arti-cap-memory] [role=switch]")
        assert await mem_sw.get_attribute("aria-checked") == "false"
        assert await mem_sw.evaluate("e => e.disabled === false")
        await mem_sw.click()
        await pg.wait_for_timeout(400)
        assert await mem_sw.get_attribute("aria-checked") == "true"
        st = await pg.evaluate("async () => (await (await fetch('/api/comfyart/settings')).json())['proactive-memory']")
        assert st is True
        await pg.reload()
        await pg.locator("[data-testid=arti-cap-memory] [role=switch]").wait_for(timeout=15000)
        assert await pg.locator("[data-testid=arti-cap-memory] [role=switch]").get_attribute("aria-checked") == "true"
        # skills same
        sk = pg.locator("[data-testid=arti-cap-skills] [role=switch]")
        assert await sk.evaluate("e => e.disabled === false")
        await sk.click()
        await pg.wait_for_timeout(300)
        assert await sk.get_attribute("aria-checked") == "true"
        # review stays disabled
        assert await pg.locator("[data-testid=arti-cap-review] [role=switch]").evaluate("e => e.disabled === true")

        boxes = [await c.bounding_box() for c in await pg.locator(".ca-arti__cap").all()]
        y0, y1 = boxes[0]["y"] - 56, boxes[-1]["y"] + boxes[-1]["height"] + 16
        await shot(pg, "arti-toggles", theme, full_page=True, clip={"x": 160, "y": y0, "width": 1120, "height": y1 - y0})

        # #436 (PR #445): an empty memory tab shows 「暂无记忆」+「去完善」 and no chat CTA;
        # the chat CTA only appears once there is at least one memory, so seed one first
        assert await pg.locator("[data-testid=arti-memory-tab-empty]").count() == 1
        assert await pg.locator("[data-testid=arti-memory-chat-open]").count() == 0
        seed_store(records=[{"id": "m385", "text": "我喜欢蓝色", "time": 1, "category": "taste", "label": "色彩偏好"}])
        await pg.reload()
        await pg.locator("[data-testid=arti-page]").wait_for(timeout=15000)
        # chat composer open
        await pg.locator("[data-testid=arti-memory-chat-open]").scroll_into_view_if_needed()
        await pg.locator("[data-testid=arti-memory-chat-open]").click()
        await pg.locator("[data-testid=arti-memory-composer]").wait_for()
        await pg.wait_for_timeout(200)
        await shot(pg, "arti-memory-chat-edit-composer", theme)

        # evolution log with 3 ops
        seed_store(log=SEED_LOG_NEWEST)
        await pg.reload()
        await pg.locator("[data-testid=arti-page]").wait_for(timeout=15000)
        await pg.locator("[data-testid=arti-tab-evolution]").click()
        await pg.locator("[data-testid=arti-evolution-log]").wait_for(timeout=10000)
        rows = pg.locator("[data-testid=arti-evolution-row]")
        assert await rows.count() == 3
        actions = await rows.evaluate_all("els => els.map(e => e.getAttribute('data-action'))")
        assert actions == ["forget", "update", "add"]
        head = await pg.locator("[data-testid=arti-evolution-head]").inner_text()
        assert "时间" in head and "操作" in head
        await pg.wait_for_timeout(200)
        await shot(pg, "arti-evolution-log", theme)

        # empty log
        seed_store(log=[])
        await pg.reload()
        await pg.locator("[data-testid=arti-tab-evolution]").click()
        await pg.locator("[data-testid=arti-evolution-empty]").wait_for(timeout=10000)
        assert await pg.locator("[data-testid=arti-evolution-placeholder]").count() == 0
        await shot(pg, "arti-evolution-empty", theme)

        await b.close()
