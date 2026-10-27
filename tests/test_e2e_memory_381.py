"""#381 interaction test (real built UI, mock host, no paid API): /arti caption contrast, delete confirm (no ✕, full-width ？,
bold title), Lovart-size toast, multi-match chooser (scroll affordance, row 6 reachable, primary-token radios), read-error state.

Set SHOT_OUT=<dir> to also save the #78 design screenshots (light + dark)."""
import os

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import fake_tools, pytestmark  # noqa: F401

OUT = os.environ.get("SHOT_OUT")
MEM = [
    {"id": "u1", "text": "我主要做咖啡与茶饮品牌的视觉内容。", "time": 1, "category": "about", "label": "创作领域"},
    {"id": "u2", "text": "我习惯用简短直接的方式下达任务指令。", "time": 2, "category": "work", "label": "指令风格"},
    {"id": "u3", "text": "我偏好暖色调视觉风格。", "time": 3, "category": "taste", "label": "色彩偏好"},
    {"id": "u4", "text": "我偏好极简、几何化与克制用色的视觉取向。", "time": 4, "category": "taste", "label": "视觉风格"},
]
DUP = "我偏好暖色调视觉风格（海报）。"
SEED_JS = """async (m) => { const cur = await (await fetch('/api/comfyart/memory')).json();
  const r = await fetch('/api/comfyart/memory', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({memory: m, log: [], meta: {demoCleanup381: true}, base_rev: cur.rev})});
  if (!r.ok) throw new Error('seed ' + r.status) }"""
# effective opacity = product over the ancestor chain; colour of a token resolved through a probe element
OPACITY_JS = "(el) => { let o = 1; for (let n = el; n; n = n.parentElement) o *= +getComputedStyle(n).opacity; return o }"
TOKEN_JS = """(name) => { const p = document.createElement('span'); p.style.color = `var(${name})`; document.querySelector('.ca-root, body').appendChild(p);
  const c = getComputedStyle(p).color; p.remove(); return c }"""


async def shot(pg, name, theme, **kw):
    if OUT:
        os.makedirs(OUT, exist_ok=True)
        await pg.screenshot(path=f"{OUT}/{name}-{theme}.png", **kw)


@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_memory_ui_381(app_url, fake_tools, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','zh');localStorage.setItem('comfyart.theme','{theme}');localStorage.setItem('comfyart.e2e','1')")
        await pg.goto(app_url.rstrip("/") + "/?view=arti")
        await pg.locator("[data-testid=arti-memory-center]").wait_for(timeout=15000)
        await pg.wait_for_timeout(600)

        # MUST 2: 即将开放 uses --ca-text-2 straight, not under any opacity
        cap = pg.locator("[data-testid=arti-cap-memory-soon]")
        assert await cap.evaluate("e => getComputedStyle(e).color") == await pg.evaluate(TOKEN_JS, "--ca-text-2")
        assert await cap.evaluate(OPACITY_JS) == 1
        # criterion 6, RENDERED: memory/skills switches mirror api/settings (both off by default), are disabled, say 即将开放
        from ComfyArt.api import settings as _st
        cur = _st.all_settings()
        for cid, key in (("memory", "proactive-memory"), ("skills", "proactive-skills")):
            sw = pg.locator(f"[data-testid=arti-cap-{cid}] [role=switch]")
            assert await sw.get_attribute("aria-checked") == ("true" if cur.get(key) else "false"), (cid, cur.get(key))
            assert cur.get(key) is False  # shipped default
            assert await sw.evaluate("e => e.disabled === true") and await sw.get_attribute("aria-disabled") == "true"  # native disabled, not just aria
            assert (await pg.locator(f"[data-testid=arti-cap-{cid}-soon]").inner_text()).strip() == "即将开放"
        # whole 我能主动做的 section: heading + every capability card with its toggle
        boxes = [await c.bounding_box() for c in await pg.locator(".ca-arti__cap").all()]
        y0, y1 = boxes[0]["y"] - 56, boxes[-1]["y"] + boxes[-1]["height"] + 16
        await shot(pg, "arti-toggles", theme, full_page=True, clip={"x": 160, "y": y0, "width": 1120, "height": y1 - y0})

        await pg.locator("[data-testid=arti-memory-center]").scroll_into_view_if_needed()
        await pg.wait_for_timeout(300)
        await shot(pg, "empty", theme)
        await pg.evaluate(SEED_JS, MEM)
        await pg.reload()
        await pg.locator("[data-testid=arti-memory-row]").first.wait_for(timeout=15000)
        await pg.wait_for_timeout(400)
        await shot(pg, "list", theme)

        # delete confirm: no ✕, full-width ？, bold title
        row = pg.locator("[data-testid=arti-memory-row][data-id=u3]")
        await row.hover()
        await row.locator("[data-testid=arti-memory-menu-btn]").click()
        await pg.locator("[data-testid=arti-memory-row-menu] button").last.click()
        dlg = pg.locator(".ca-modal:has([data-testid=confirm-dialog])")
        await dlg.wait_for(timeout=5000)
        head = dlg.locator(".ca-side__head")
        assert await head.locator(".ca-panel__icon, button").count() == 0  # product: only 取消 + 删除
        assert "？" in await head.inner_text() and "?" not in await head.inner_text()
        assert int(await head.evaluate("e => getComputedStyle(e).fontWeight")) >= 600
        assert await dlg.locator(".ca-panel__foot button").all_inner_texts() == ["取消", "删除"]
        await pg.wait_for_timeout(200)
        await shot(pg, "delete-confirm", theme)
        await dlg.locator(".ca-panel__primary").click()
        await pg.mouse.move(1400, 880)  # no row left in hover for the toast shot

        toast = pg.locator("[data-testid=memory-toast]")
        await toast.wait_for(timeout=5000)
        assert "记忆已删除" in await toast.inner_text()
        box = await toast.bounding_box()
        assert box["height"] >= 44 and await toast.evaluate("e => getComputedStyle(e).fontSize") == "14px"
        assert (await toast.locator("svg").bounding_box())["width"] == 16
        assert await toast.evaluate("e => getComputedStyle(e).borderRadius") == "14px"
        await pg.wait_for_timeout(300)
        await shot(pg, "delete-toast", theme)
        assert await pg.locator("[data-testid=arti-memory-row][data-id=u3]").count() == 0
        await toast.wait_for(state="detached", timeout=5000)
        await shot(pg, "after-delete", theme)

        # multi-match chooser: 6 exact matches → nothing written, user picks; list scrolls with a visible cue
        await pg.evaluate(SEED_JS, [{"id": f"d{i}", "text": DUP, "time": 10 + i, "category": "taste"} for i in range(6)])
        await pg.reload()
        await pg.locator("[data-testid=arti-memory-row]").first.wait_for(timeout=15000)
        await pg.evaluate("t => window.__comfyartMemory.forget([t], 'agent')", DUP)
        chooser = pg.locator("[data-testid=memory-chooser]")
        await chooser.wait_for(timeout=5000)
        modal = pg.locator(".ca-modal:has([data-testid=memory-chooser])")
        assert await modal.locator(".ca-side__head button").count() == 0
        assert "？" in await modal.locator(".ca-side__head").inner_text()
        lst = pg.locator("[data-testid=memory-chooser-list]")
        assert await pg.locator("[data-testid=memory-chooser-row]").count() == 6
        # matching is exact full text, so every candidate carries the same text → the title says 相同, and N = rows rendered
        texts = await pg.locator("[data-testid=memory-chooser-row]").all_inner_texts()
        assert len({x.strip() for x in texts}) == 1, texts
        assert "找到 6 条相同记忆，要改哪一条？" in await modal.inner_text()
        assert await lst.evaluate("e => getComputedStyle(e).overflowY") == "auto"
        assert await lst.evaluate("e => e.scrollHeight > e.clientHeight")
        scroll = pg.locator("[data-testid=memory-chooser-scroll]")
        assert await scroll.get_attribute("data-more") is not None
        assert "gradient" in await scroll.evaluate("e => getComputedStyle(e, '::after').backgroundImage")
        bar = pg.locator("[data-testid=memory-chooser-bar]")  # always-visible scrollbar (thumb ≈ 5/6 of the track)
        assert (await bar.bounding_box())["height"] > 100 and await bar.locator("i").evaluate("e => e.getBoundingClientRect().height") < (await bar.bounding_box())["height"]
        radio = pg.locator("[data-testid=memory-chooser-row] input").first
        assert await radio.evaluate("e => getComputedStyle(e).accentColor") == await pg.evaluate(TOKEN_JS, "--ca-strong")
        await pg.locator("[data-testid=memory-chooser-row]").first.click()
        await pg.mouse.move(1400, 880)
        await pg.wait_for_timeout(200)
        await shot(pg, "chooser-forget-selected", theme)
        await lst.evaluate("e => { e.scrollTop = e.scrollHeight }")
        await pg.wait_for_timeout(300)
        last = pg.locator("[data-testid=memory-chooser-row]").nth(5)
        lb, sb = await last.bounding_box(), await lst.bounding_box()
        assert lb["y"] >= sb["y"] - 1 and lb["y"] + lb["height"] <= sb["y"] + sb["height"] + 1  # row 6 fully visible
        assert await scroll.get_attribute("data-more") is None  # fade gone at the bottom
        await shot(pg, "chooser-scrolled-bottom", theme)
        await last.click()
        await pg.locator("[data-testid=memory-chooser-ok]").click()
        await toast.wait_for(timeout=5000)
        remaining = await pg.evaluate("async () => (await (await fetch('/api/comfyart/memory')).json()).memory.map(m => m.id)")
        assert sorted(remaining) == ["d0", "d1", "d2", "d3", "d4"]

        # correct chooser (non-danger primary)
        await pg.evaluate("t => window.__comfyartMemory.correct([{ old: t, new: '我偏好冷色调视觉风格。' }], 'agent')", DUP)
        await chooser.wait_for(timeout=5000)
        await pg.locator("[data-testid=memory-chooser-row]").nth(1).click()
        ok = pg.locator("[data-testid=memory-chooser-ok]")
        assert await ok.evaluate("e => getComputedStyle(e).backgroundColor") == await pg.evaluate("n => { const p = document.createElement('span'); p.style.backgroundColor = `var(${n})`; document.body.appendChild(p); const c = getComputedStyle(p).backgroundColor; p.remove(); return c }", "--ca-strong")
        await pg.mouse.move(1400, 880)
        await pg.wait_for_timeout(200)
        await shot(pg, "chooser-correct-selected", theme)
        await pg.locator("[data-testid=memory-chooser-cancel]").click()

        # EL MUST 2 in the UI: read error → error state, no list (the server is the only truth)
        await pg.route("**/api/comfyart/memory", lambda r: r.fulfill(status=500, body="boom") if r.request.method == "GET" else r.continue_())
        await pg.reload()
        await pg.locator("[data-testid=arti-memory-error]").wait_for(timeout=15000)
        assert await pg.locator("[data-testid=arti-memory-row]").count() == 0
        await pg.locator("[data-testid=arti-memory-error]").scroll_into_view_if_needed()
        await shot(pg, "read-error", theme)
        # EL MUST 1 in the UI: write fails → 保存失败，请重试 toast, nothing shown as saved
        await pg.unroute("**/api/comfyart/memory")
        await pg.locator("[data-testid=arti-memory-retry]").click()
        await pg.locator("[data-testid=arti-memory-row]").first.wait_for(timeout=15000)
        n_rows = await pg.locator("[data-testid=arti-memory-row]").count()
        await pg.route("**/api/comfyart/memory", lambda r: r.abort() if r.request.method == "POST" else r.continue_())
        row = pg.locator("[data-testid=arti-memory-row]").first
        await row.hover()
        await row.locator("[data-testid=arti-memory-menu-btn]").click()
        await pg.locator("[data-testid=arti-memory-row-menu] button").last.click()
        await dlg.locator(".ca-panel__primary").click()
        await pg.mouse.move(1400, 880)
        await toast.wait_for(timeout=8000)
        assert "保存失败，请重试" in await toast.inner_text() and await toast.get_attribute("data-kind") == "error"
        assert await pg.locator("[data-testid=arti-memory-row]").count() == n_rows
        await pg.wait_for_timeout(200)
        await shot(pg, "save-failed-toast", theme)
        await b.close()
