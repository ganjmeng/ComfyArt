import json, pytest
pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: F401
CASES = [("image", "plus", ".ca-composer__foot .ca-bar__btn--icon[title]"), ("image", "mode", ".ca-composer__mode"), ("image", "model", "[data-pill=model]"),
         ("image", "settings", "[data-pill=settings]"), ("video", "settings", "[data-pill=settings]"), ("video", "model", "[data-pill=model]"),
         ("agent", "ref", ".ca-refbtn"), ("agent", "prefs", ".ca-composer__foot [title] .ca-icon >> xpath=..")]
@pytest.mark.parametrize("width", [1280, 360])
@pytest.mark.parametrize("mode,name,sel", CASES)
async def test_pop(app_url, fake_tools, monkeypatch, width, mode, name, sel):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width": width, "height": 800}, device_scale_factor=2)).new_page()
        await pg.add_init_script("localStorage.setItem('comfyart.lang','zh');localStorage.setItem('comfyart.theme','dark')")
        await pg.goto(app_url + f"?project=p268{mode}{name}{width}&new=1")
        await pg.locator(".ca-composer__mode").wait_for(); await pg.wait_for_timeout(1500)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
        await pg.locator(".ca-composer__mode").click(); await pg.wait_for_timeout(300)
        if mode == "agent":
            await pg.locator(".ca-agentpick .ca-menu__item").filter(has_text="ComfyArt Agent").first.click()
        else:
            await pg.locator(".ca-agentpick .ca-menu__item:not(.ca-agentpick__row)").filter(has_text={"image": "图像", "video": "视频"}[mode]).first.click()
        await pg.wait_for_timeout(400)
        if await pg.locator(".ca-agentpick").count(): await pg.keyboard.press("Escape")
        if name == "prefs":
            btn = pg.locator(".ca-composer__foot .ca-bar__btn--icon").last
        elif name == "plus":
            btn = pg.locator(".ca-composer__foot .ca-bar__btn--icon").first
        else:
            btn = pg.locator(f".ca-composer__foot {sel}").first
        await btn.click(); await pg.wait_for_timeout(500)
        box = await btn.evaluate("e => { const c = e.closest('.ca-composer').getBoundingClientRect(), b = e.getBoundingClientRect(); return [c.left, c.right, b.left, b.right] }")
        r = await pg.evaluate("""() => { const ms = [...document.querySelectorAll('.ca-menu, .ca-gen__pop, [data-radix-popper-content-wrapper], .ca-pop')].filter(e => e.getBoundingClientRect().width > 0);
          return ms.map(m => { const b = m.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.right), Math.round(b.bottom)] }) }""")
        for l, t, rr, bb in r:
            assert l >= 0 and t >= 0 and rr <= width and bb <= 800, (name, r)
            assert l >= box[0] - 1 and rr <= box[1] + 1 and (width > 360 or rr - l <= 336), (name, r, box)  # every popover inside the composer panel
            if name == "model":
                assert abs(l - box[0]) <= 1, (name, r, box)  # v3: 340px model popover can't fit left of its button, clamps to the panel's LEFT edge
            if name in ("settings", "prefs"):
                assert abs(rr - box[3]) <= 1 or (abs(l - box[0]) <= 1 and rr - l > box[3] - box[0]), (name, r, box)  # right-aligned to its button; clamped to the panel left edge only when it cannot fit left of the button
        await b.close()
