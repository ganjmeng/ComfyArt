import pytest
pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: F401
# #274: input-bar polish — spacing / size / radius / shadow only; order, colours and the one-row fit stay as #268 shipped them.
MEASURE = """() => { const c = document.querySelector('.ca-composer'), f = c.querySelector('.ca-composer__foot'), cb = c.getBoundingClientRect();
  const vis = e => e.getBoundingClientRect().width > 0, R = e => e.getBoundingClientRect(), cs = e => getComputedStyle(e);
  const plus = f.querySelector('.ca-bar__btn--icon'), mode = f.querySelector('.ca-composer__mode'), pills = [...f.querySelectorAll('.ca-gen__pill')].filter(vis);
  const slot = [...f.querySelectorAll('.ca-composer__slot')].filter(vis)[0], glyph = slot.querySelector('.ca-icon');
  const chev = [[...mode.querySelectorAll('.ca-icon')].filter(vis).pop(), ...pills.map(b => b.querySelector('.ca-gen__chev svg'))].map(e => [R(e).width, R(e).height, cs(e).color]);
  const mi = [...mode.children].filter(vis).map(R);
  return { radius: cs(c).borderRadius, padL: cs(c).paddingLeft, right: cb.right - R(slot).right, bottom: cb.bottom - R(slot).bottom,
    plusToMode: R(mode).left - R(plus).right, modeGap: cs(mode).columnGap, modePad: [cs(mode).paddingLeft, cs(mode).paddingRight],
    modeIconText: mi[1].left - mi[0].right, modeTextArrow: mi[2].left - mi[1].right, pillGaps: pills.map(p => cs(p).columnGap),
    slot: [R(slot).width, R(slot).height, cs(slot).backgroundColor, cs(slot).color], glyph: [R(glyph).width, R(glyph).height],
    tops: [plus, mode, ...pills, slot].map(e => Math.round(R(e).top + R(e).height / 2)), chev,
    modeFont: cs(mode).fontSize } }"""
@pytest.mark.parametrize("width", [1280, 360])
async def test_input_bar_polish(app_url, fake_tools, monkeypatch, width):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width": width, "height": 800}, device_scale_factor=2)).new_page()
        await pg.add_init_script("localStorage.setItem('comfyart.lang','zh');localStorage.setItem('comfyart.theme','dark')")
        await pg.goto(app_url + f"?project=p274{width}&new=1")
        await pg.locator(".ca-composer__mode").wait_for(); await pg.wait_for_timeout(1500)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
        await pg.locator(".ca-composer__mode").click(); await pg.wait_for_timeout(300)
        await pg.locator(".ca-agentpick .ca-menu__item:not(.ca-agentpick__row)").filter(has_text="图像").first.click()
        await pg.wait_for_timeout(300)
        if await pg.locator(".ca-agentpick").count(): await pg.keyboard.press("Escape")
        await pg.mouse.move(0, 0); await pg.wait_for_timeout(300)
        m = await pg.evaluate(MEASURE)
        assert m["radius"] == "20px" and m["padL"] == "12px", m  # radius 18 → 20; left padding unchanged
        assert abs(m["right"] - 9) <= 0.5 and abs(m["bottom"] - 8) <= 0.5, m  # voice/send button 9 from the right edge, 8 from the bottom
        assert abs(m["plusToMode"] - 6) <= 0.5, m  # + → mode 4 → 6
        assert m["modeGap"] == "6px" and m["modePad"] == ["6px", "6px"], m
        assert abs(m["modeIconText"] - 6) <= 0.5 and abs(m["modeTextArrow"] - 6) <= 0.5, m  # mode icon → text → arrow 2 → 6
        assert m["pillGaps"] == ["4px"], m  # settings text → arrow 2 → 4 (#287: model is a 32px icon button, no text/arrow)
        assert m["slot"][:2] == [32, 32] and m["glyph"] == [16, 16], m  # glyph 18 → 16, button stays 32
        assert m["slot"][2] == "rgb(255, 255, 255)" and m["slot"][3] == "rgb(17, 17, 17)", m  # dark: white circle, black icon
        assert max(m["tops"]) - min(m["tops"]) <= 1, m  # still one row (360 included)
        assert all(c[:2] == [16, 16] for c in m["chev"]) and len({c[2] for c in m["chev"]}) == 1, m  # 16×16 same-colour arrows
        assert m["modeFont"] == "14px", m  # font size unchanged
        await pg.locator(".ca-composer textarea").fill("hello"); await pg.wait_for_timeout(300)
        m2 = await pg.evaluate(MEASURE)
        assert m2["glyph"] == [16, 16] and m2["slot"][:2] == [32, 32] and abs(m2["right"] - 9) <= 0.5, m2  # send state too
        # light theme popover: soft shadow + 1px ring; radius stays 12
        await pg.evaluate("localStorage.setItem('comfyart.theme','light')"); await pg.add_init_script("localStorage.setItem('comfyart.theme','light')")
        await pg.reload(); await pg.locator(".ca-composer__mode").wait_for(); await pg.wait_for_timeout(1200)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
        await pg.locator(".ca-composer__mode").click(); await pg.wait_for_timeout(400)
        sh = await pg.evaluate("() => [...document.querySelectorAll('.ca-menu')].filter(e => e.getBoundingClientRect().width > 0).map(e => [getComputedStyle(e).boxShadow, getComputedStyle(e).borderRadius])")
        assert sh and all(s == ["rgba(0, 0, 0, 0.08) 0px 4px 24px 0px, rgba(0, 0, 0, 0.04) 0px 0px 0px 1px", "12px"] for s in sh), sh
        await b.close()
