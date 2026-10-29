"""#381 interaction test (real built UI, mock host, no paid API): /arti caption contrast, delete confirm (no ✕, full-width ？,
bold title), Lovart-size toast, multi-match chooser (scroll affordance, row 6 reachable, primary-token radios), read-error state.

Set SHOT_OUT=<dir> to also save the #78 design screenshots (light + dark)."""
import json
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
CAP_TEXT = [("review", "画布巡检", "Arti 会定期翻看你的画布，发现问题提前告诉你。"),
            ("research", "设计调研", "新项目？我帮你全网找参考。竞品、配色、案例，整理成报告，齐活。"),
            ("memory", "自动更新记忆", "说过的偏好、传过的作品集，Arti 都记着，不用再交代。"),
            ("skills", "自进化技能", "你做顺手的流程，Arti 会存成技能，用得上时主动提给你。")]
DUP = "我偏好暖色调视觉风格（海报）。"
# record times (Asia/Shanghai): d0 oldest … d5 = 2026-10-27 18:20, newest
_T0 = 1793096400000  # 2026-10-27 18:20:00 +08:00
DUP_TIMES = [_T0 - m * 60_000 for m in (3 * 1440 + 125, 1440 + 7, 1440, 95, 12, 0)]
DUP_LABELS = ["10月27日 18:20", "10月27日 18:08", "10月27日 16:45", "10月26日 18:20", "10月26日 18:13", "10月24日 16:15"]
SEED_JS = """async (m) => { const cur = await (await fetch('/api/comfyart/memory')).json();
  const r = await fetch('/api/comfyart/memory', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({memory: m, log: [], meta: {demoCleanup381: true}, base_rev: cur.rev})});
  if (!r.ok) throw new Error('seed ' + r.status) }"""


def seed_store(records, log=()):
    """Mock-only: record times are server-authoritative (a POST re-stamps them), so the chooser fixtures with known
    record times are written straight into the store file, as if the server had stamped them at those times."""
    import folder_paths
    f = folder_paths.STATE["base"] / "user/default/comfyart/memory-store.json"
    cur = json.loads(f.read_text()) if f.is_file() else {}
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"memory": [{**r, "owner_id": "local", "workspace_id": "local"} for r in records], "log": list(log),
                             "meta": {"demoCleanup381": True}, "rev": int(cur.get("rev", 0)) + 1, "ops": []}, ensure_ascii=False))


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
        pg = await (await b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1, timezone_id="Asia/Shanghai")).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','zh');localStorage.setItem('comfyart.theme','{theme}');localStorage.setItem('comfyart.e2e','1')")
        await pg.goto(app_url.rstrip("/") + "/?view=arti")
        await pg.locator("[data-testid=arti-memory-center]").wait_for(timeout=15000)
        await pg.wait_for_timeout(600)

        # product MUST 1: grey cards (review/research) say 即将开放; #385 memory/skills are switchable (no soon)
        text2 = await pg.evaluate(TOKEN_JS, "--ca-text-2")
        GREY = {"review", "research"}
        for cid, title, desc in CAP_TEXT:
            card = pg.locator(f"[data-testid=arti-cap-{cid}]")
            assert (await card.locator(".ca-arti__captitle").inner_text()).strip() == title, cid
            assert (await card.locator(".ca-arti__capdesc").inner_text()).strip() == desc, cid
            soon = card.locator(f"[data-testid=arti-cap-{cid}-soon]")
            if cid in GREY:
                assert (await soon.inner_text()).strip() == "即将开放", cid
                assert await soon.evaluate("e => getComputedStyle(e).color") == text2, cid
                assert await soon.evaluate(OPACITY_JS) == 1, cid
                assert await soon.evaluate("e => getComputedStyle(e).fontSize") == "12px", cid
                assert await card.locator(".ca-arti__capbody").evaluate("e => e.innerText.split('\\n').filter(Boolean).length") == 3, cid
            else:
                assert await soon.count() == 0, cid
                assert await card.locator(".ca-arti__capbody").evaluate("e => e.innerText.split('\\n').filter(Boolean).length") == 2, cid
            assert "后端就绪前暂不可用" not in await card.inner_text(), cid
            for part in (".ca-arti__captitle", ".ca-arti__capdesc"):
                assert await card.locator(part).evaluate(OPACITY_JS) == 1, (cid, part)
            assert float(await card.evaluate("e => getComputedStyle(e).opacity")) == 1, cid
        assert "后端就绪前暂不可用" not in await pg.locator("body").inner_text()  # page-wide
        assert await pg.locator("[data-testid=arti-cap-feedback-soon]").count() == 0  # 反馈改稿 has no switch, no caption
        # #385: memory/skills switches mirror api/settings (off by default) and are ENABLED (switchable); no 即将开放
        from ComfyArt.api import settings as _st
        cur = _st.all_settings()
        for cid, key in (("memory", "proactive-memory"), ("skills", "proactive-skills")):
            sw = pg.locator(f"[data-testid=arti-cap-{cid}] [role=switch]")
            assert await sw.get_attribute("aria-checked") == ("true" if cur.get(key) else "false"), (cid, cur.get(key))
            assert cur.get(key) is False  # shipped default
            assert await sw.evaluate("e => e.disabled === false")
            assert await pg.locator(f"[data-testid=arti-cap-{cid}-soon]").count() == 0
        # review/research stay grey + 即将开放
        for cid in ("review", "research"):
            sw = pg.locator(f"[data-testid=arti-cap-{cid}] [role=switch]")
            assert await sw.evaluate("e => e.disabled === true")
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
        # 6 identical rows, distinct record times, seeded out of order (d0 oldest … d5 newest)
        seed_store([{"id": f"d{i}", "text": DUP, "time": DUP_TIMES[i], "category": "taste"} for i in (3, 0, 5, 1, 4, 2)])
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
        texts = await pg.locator("[data-testid=memory-chooser-row] .ca-mem-choose__text").all_inner_texts()
        assert len({x.strip() for x in texts}) == 1, texts
        assert (await modal.locator(".ca-side__head").inner_text()).strip().startswith("找到 6 条相同记忆，要删除哪一条？")  # delete flow
        assert "要改哪一条" not in await modal.inner_text()
        n_rows6 = await pg.locator("[data-testid=memory-chooser-row]").count()
        assert f"找到 {n_rows6} 条相同记忆，要删除哪一条？" in await modal.inner_text()  # N = rendered rows
        # product MUST 3: record time on the right, secondary color, 「10月27日 18:20」, newest first
        ids = [await r.get_attribute("data-id") for r in await pg.locator("[data-testid=memory-chooser-row]").all()]
        assert ids == ["d5", "d4", "d3", "d2", "d1", "d0"], ids
        times = [x.strip() for x in await pg.locator("[data-testid=memory-chooser-time]").all_inner_texts()]
        assert times == DUP_LABELS, times
        t0 = pg.locator("[data-testid=memory-chooser-time]").first
        assert await t0.evaluate("e => getComputedStyle(e).color") == text2
        tb, xb = await t0.bounding_box(), await pg.locator("[data-testid=memory-chooser-row] .ca-mem-choose__text").first.bounding_box()
        rb = await pg.locator("[data-testid=memory-chooser-row]").first.bounding_box()
        assert tb["x"] > xb["x"] + xb["width"] - 1 and rb["x"] + rb["width"] - (tb["x"] + tb["width"]) < 16  # right-aligned
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
        assert sorted(remaining) == ["d1", "d2", "d3", "d4", "d5"]  # row 6 = oldest (d0) was the one deleted

        # correct chooser (non-danger primary)
        await pg.evaluate("t => window.__comfyartMemory.correct([{ old: t, new: '我偏好冷色调视觉风格。' }], 'agent')", DUP)
        await chooser.wait_for(timeout=5000)
        assert (await modal.locator(".ca-side__head").inner_text()).strip().startswith("找到 5 条相同记忆，要改哪一条？")  # correct flow
        await pg.locator("[data-testid=memory-chooser-row]").nth(1).click()
        ok = pg.locator("[data-testid=memory-chooser-ok]")
        assert await ok.evaluate("e => getComputedStyle(e).backgroundColor") == await pg.evaluate("n => { const p = document.createElement('span'); p.style.backgroundColor = `var(${n})`; document.body.appendChild(p); const c = getComputedStyle(p).backgroundColor; p.remove(); return c }", "--ca-strong")
        await pg.mouse.move(1400, 880)
        await pg.wait_for_timeout(200)
        await shot(pg, "chooser-correct-selected", theme)
        await pg.locator("[data-testid=memory-chooser-cancel]").click()

        # EL: legacy records without a (valid) time render no time and sort last — never 'NaN月NaN日 NaN:NaN'
        seed_store([{"id": "L1", "text": DUP, "category": "taste"}, {"id": "T1", "text": DUP, "time": DUP_TIMES[5], "category": "taste"},
                    {"id": "L2", "text": DUP, "time": "x", "category": "taste"}, {"id": "T0", "text": DUP, "time": DUP_TIMES[0], "category": "taste"}],
                   log=[{"time": DUP_TIMES[0], "action": "add", "text": DUP, "source": "seed"}])
        await pg.reload()
        await pg.locator("[data-testid=arti-memory-row]").first.wait_for(timeout=15000)
        await pg.evaluate("t => window.__comfyartMemory.forget([t], 'agent')", DUP)
        await chooser.wait_for(timeout=5000)
        assert "NaN" not in await modal.inner_text()
        ids = [await r.get_attribute("data-id") for r in await pg.locator("[data-testid=memory-chooser-row]").all()]
        assert ids[:2] == ["T1", "T0"] and sorted(ids[2:]) == ["L1", "L2"], ids
        times = [x.strip() for x in await pg.locator("[data-testid=memory-chooser-row]").all_inner_texts()]
        assert times[0].endswith(DUP_LABELS[0]) and times[1].endswith(DUP_LABELS[5]) and times[2] == times[3] == DUP, times
        assert await pg.locator("[data-testid=memory-chooser-time]").count() == 2
        await pg.locator("[data-testid=memory-chooser-cancel]").click()

        # tester: a read failure AFTER a loaded list (no page reload) clears the in-memory list + log and every row
        assert await pg.locator("[data-testid=arti-memory-row]").count() > 0
        assert len(await pg.evaluate("() => window.__comfyartMemory.list()")) > 0
        assert len(await pg.evaluate("() => window.__comfyartMemory.log()")) > 0
        await pg.route("**/api/comfyart/memory", lambda r: r.fulfill(status=500, body="boom") if r.request.method == "GET" else r.continue_())
        assert await pg.evaluate("async () => (await window.__comfyartMemory.load()).length") == 0
        await pg.locator("[data-testid=arti-memory-error]").wait_for(timeout=5000)
        assert await pg.evaluate("() => window.__comfyartMemory.list()") == []
        assert await pg.evaluate("() => window.__comfyartMemory.log()") == []
        assert await pg.locator("[data-testid=arti-memory-row]").count() == 0
        await pg.unroute("**/api/comfyart/memory")

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
