"""#568: canvas chat panel top bar fits its 400px panel at 1280×800 and 1920×1080 (zh light + en dark).
Every button stays visible and there is no 「已保存」/Saved label; last button 12px from the panel edge, first canvas tool 10px
from the divider, logo → title 8px, nothing overlaps the canvas
toolbar (.ca-top), the head does not overflow, and a very long title ellipsizes without hiding buttons."""
from __future__ import annotations

import os

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import pytestmark  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
SHOTS = os.environ.get("TOPBAR_SHOTS")

MEASURE = """() => {
  const r = (e) => e.getBoundingClientRect()
  const panel = document.querySelector('.ca-agent'), head = panel.querySelector('.ca-head')
  const btns = [...head.querySelectorAll('button')].filter((b) => !b.classList.contains('ca-head__logo') && b.offsetParent)
  const tools = [...document.querySelectorAll('.ca-top button')].filter((b) => b.offsetParent)
  const save = head.querySelector('.ca-save'), name = head.querySelector('.ca-head__name')
  const box = (e) => { const b = r(e); return { l: b.left, r: b.right, t: b.top, b: b.bottom } }
  const sv = save && box(save)
  const top = save && document.elementFromPoint((sv.l + sv.r) / 2, (sv.t + sv.b) / 2)
  return {
    panelRight: r(panel).right, padRight: parseFloat(getComputedStyle(head).paddingRight),
    btns: btns.map(box), tools: tools.map(box), divider: r(panel).right,
    scrollW: head.scrollWidth, clientW: head.clientWidth,
    save: sv, saveOnTop: !!top && (top === save || save.contains(top)),
    logoR: r(head.querySelector('.ca-head__logo')).right, logoSvgR: r(head.querySelector('.ca-head__logo svg')).right, nameL: r(name).left, namePadL: parseFloat(getComputedStyle(name).paddingLeft),
    nameScroll: name.scrollWidth, nameClient: name.clientWidth, nameOverflow: getComputedStyle(name).textOverflow,
  }
}"""


async def _measure(pg):
    await pg.wait_for_timeout(2500)  # let autosave persist; the top bar must still show no status text
    return await pg.evaluate(MEASURE)


def _hit(a, b):
    return a["l"] < b["r"] - 0.5 and b["l"] < a["r"] - 0.5 and a["t"] < b["b"] - 0.5 and b["t"] < a["b"] - 0.5


def _check(m):
    edge = m["panelRight"] - m["padRight"]
    assert m["padRight"] == 12, m
    assert abs(m["panelRight"] - m["btns"][-1]["r"] - 12) <= 1, m  # chat gap 12±1
    assert abs(m["tools"][0]["l"] - m["divider"] - 10) <= 1, m  # canvas gap 10±1
    assert abs(m["nameL"] - m["logoR"] - 8) <= 1, m  # logo box → title box 8±1 (unchanged from main)
    assert len(m["btns"]) == 5, m["btns"]  # new chat, history ▾, notices, maximize, collapse
    for b in m["btns"]:
        assert b["r"] <= edge + 1 and b["l"] >= 0, (b, edge)
    w = [b["r"] - b["l"] for b in m["btns"]]
    assert all(x >= 31.5 for i, x in enumerate(w) if i != 1) and w[1] >= 21.5, w  # no squeezed buttons (history ▾ is 22)
    assert m["scrollW"] <= m["clientW"], m
    assert m["tools"] and m["tools"][0]["l"] > m["divider"], m
    assert not any(_hit(a, b) for a in m["btns"] for b in m["tools"]), m
    assert m["save"] is None, m  # #568: no 「已保存」/Saved label in the top bar


@pytest.mark.parametrize("vw,vh", [(1280, 800), (1920, 1080)])
@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_chat_topbar_fits_panel(app_url, lang, theme, vw, vh):  # noqa: F811
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pg = await (await browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=1)).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
        await pg.goto(app_url)
        await pg.wait_for_timeout(1500)
        await pg.mouse.click(28, 83)  # home: new project
        await pg.locator(".tl-canvas").wait_for()
        await pg.wait_for_timeout(2000)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        name = pg.locator(".ca-agent .ca-head__name")
        await name.fill("Brief")
        await pg.keyboard.press("Enter")
        short = await _measure(pg)
        print("MEAS", lang, theme, vw, short)
        _check(short)
        if SHOTS:
            await pg.screenshot(path=f"{SHOTS}/{vw}-{lang}-{theme}.png")
            await pg.screenshot(path=f"{SHOTS}/crop-{vw}-{lang}-{theme}.png", clip={"x": 0, "y": 0, "width": 640, "height": 48})
        await name.fill("A very long project name that keeps going well past the title slot width 一个非常长的项目名称")
        await pg.keyboard.press("Enter")
        long = await _measure(pg)
        _check(long)
        assert len(long["btns"]) == len(short["btns"])
        assert long["nameScroll"] > long["nameClient"] and long["nameOverflow"] == "ellipsis", long
        await browser.close()
