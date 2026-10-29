"""#441: memory rows (记忆已读取 / 记忆已更新 ›) match the reference DOM values, checked with computed style in the real app."""
import json
import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401,E402
from test_e2e_default_agent import fake_tools, _page  # noqa: F401,E402

_use = lambda i: {"type": "tool_use", "id": i, "name": "mcp__comfyart__memory", "input": {"action": "add"}}  # noqa: E731
_res = lambda i: {"type": "tool_result", "id": i, "name": "mcp__comfyart__memory", "status": "success", "text": "{}"}  # noqa: E731

_MEASURE = """()=>{
  const bot=[...document.querySelectorAll('.ca-chat__bot')].pop();
  const pr=bot.querySelector('.ca-process');
  const rows=[...pr.querySelectorAll(".ca-process__row[data-kind^='memory_']")];
  const next=pr.nextElementSibling;
  return {
    rows: rows.map(r=>{
      const i=r.querySelector('.ca-process__icon svg'), l=r.querySelector('.ca-process__label'), c=r.querySelector('.ca-process__memchev');
      const rg=document.createRange(); rg.selectNodeContents(l.firstChild); const t=rg.getBoundingClientRect();
      const ir=i.getBoundingClientRect(), rr=r.getBoundingClientRect(), ls=getComputedStyle(l), is=getComputedStyle(i), rs=getComputedStyle(r);
      return {top: rr.top, bottom: rr.bottom, mt: rs.marginTop, mb: rs.marginBottom,
        ico: [ir.width, ir.height, is.fill, is.stroke, is.strokeWidth, is.strokeLinecap, is.strokeLinejoin, is.color], icoGap: t.left-ir.right,
        font: [ls.fontSize, ls.lineHeight, ls.fontWeight, ls.color],
        chev: c ? (()=>{const b=c.getBoundingClientRect(), s=getComputedStyle(c.querySelector('svg'));return [b.width, b.height, b.left-t.right, s.fill, s.stroke, s.strokeWidth, s.strokeLinecap, s.strokeLinejoin]})() : null};
    }),
    stub: (()=>{const sp=rows[0].querySelector('.ca-process__spine'); if(!sp) return null; const cs=getComputedStyle(sp), b=sp.getBoundingClientRect();
      const a=rows[0].querySelector('.ca-process__icon svg').getBoundingClientRect(), z=rows[1].querySelector('.ca-process__icon svg').getBoundingClientRect();
      return {content: '""', w: b.width, h: b.height, bg: cs.backgroundColor, top: b.top, bottom: b.bottom, cx: (b.left+b.right)/2,
        icoCx: (a.left+a.right)/2, icoGap: z.top-a.bottom, clearTop: b.top-a.bottom, clearBottom: z.top-b.bottom};})(),
    lastRail: (()=>{const sp=rows[rows.length-1].querySelector('.ca-process__spine'); return sp ? getComputedStyle(sp).display : 'none'})(),
    parentGap: getComputedStyle(bot).rowGap,
    toReply: next.getBoundingClientRect().top - rows[rows.length-1].getBoundingClientRect().bottom,
    stepsMB: getComputedStyle(pr.querySelector('.ca-process__steps')).marginBottom,
    procMB: getComputedStyle(pr).marginBottom,
  };
}"""


@pytest.mark.parametrize("lang,theme,ink", [("zh", "light", "rgba(0, 0, 0, 0.55)"), ("en", "dark", "rgba(255, 255, 255, 0.55)")])
async def test_memory_rows_computed_441(app_url, fake_tools, lang, theme, ink):  # noqa: F811
    from ComfyArt.api import chat_store
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, app_url, lang, theme)
        user = await pg.evaluate("async()=>(await (await fetch('/api/comfyart/bot/status')).json()).user")
        proj = await pg.evaluate("()=>{for (const e of performance.getEntriesByType('resource')){const m=e.name.match(/bot\\/chats\\?project=([^&]+)/); if(m) return decodeURIComponent(m[1])} return null}")
        assert proj
        c = chat_store.create_chat(user=user, project=proj, provider="local-llm", title="m441")
        um = chat_store.create_message(chat_id=c["id"], role="user", blocks=[{"type": "text", "text": "remember"}])
        chat_store.create_message(chat_id=c["id"], role="assistant", parent_id=um["id"], blocks=[
            {"type": "text", "text": "ok"}, _use("c1"), _res("c1"),
            {"type": "memory_updated", "memory_ids": ["m1"], "texts": ["Brand colour: Klein blue"],
             "tool_id": "c1", "tool_ids": ["c1"], "updated_ids": ["m1"], "count": 1},
            {"type": "text", "text": "Got it."}])
        await pg.reload()
        await pg.locator(".ca-split__chev").first.click(timeout=8000)
        await pg.locator(".ca-history__item").first.click(timeout=8000)
        await pg.locator(".ca-process__row[data-kind='memory_updated']").last.wait_for(timeout=10000)
        await pg.mouse.move(5, 790)
        await pg.wait_for_timeout(300)
        m = await pg.evaluate(_MEASURE)
        print("M441", json.dumps(m))
        assert len(m["rows"]) == 2
        for r in m["rows"]:
            assert r["ico"] == [16, 16, "none", ink, "1.5px", "round", "round", ink]  # 16px thin outline (1px at 16), no solid fill, text colour .55
            assert abs(r["icoGap"] - 6) <= 1
            assert r["font"] == ["14px", "20px", "400", ink]
            assert r["mt"] == "0px" and r["mb"] == "0px"  # no margin on the rows
        assert m["rows"][0]["chev"] is None
        w, h, gap, *paint = m["rows"][1]["chev"]
        assert (w, h) == (16, 16) and abs(gap - 6) <= 1  # 16px ›, 6px gap
        assert paint == ["none", ink, "1.5px", "round", "round"]  # same outline weight, no fill
        assert abs(m["rows"][1]["top"] - m["rows"][0]["bottom"] - 8) <= 1  # 8px between rows
        st = m["stub"]
        assert st["content"] == '""' and st["w"] == 1 and st["h"] == 8  # fixed 8px x 1px stub
        assert abs(st["cx"] - st["icoCx"]) <= 0.5  # centred on the icon column
        assert st["icoGap"] == 12 and st["clearTop"] == 2 and st["clearBottom"] == 2  # centred in the 12px icon gap
        assert st["bg"] == ("rgba(0, 0, 0, 0.1)" if theme == "light" else "rgba(255, 255, 255, 0.12)")  # shared --ca-rail (base.css), same as #442's rail
        assert m["lastRail"] == "none"  # nothing after the last row; no full-length connector
        assert m["parentGap"] == "8px" and m["stepsMB"] == "0px" and m["procMB"] == "0px"
        assert abs(m["toReply"] - 8) <= 1  # 8px to the reply, from the parent gap
        await pg.locator(".ca-process__row[data-kind='memory_updated']").last.hover()
        await pg.wait_for_timeout(300)
        hov = await pg.locator(".ca-process__row[data-kind='memory_updated'] .ca-process__label").last.evaluate("e=>getComputedStyle(e).color")
        assert hov != ink  # default text colour on hover
        await browser.close()
