import os, pytest
pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: F401
SHOT = os.environ.get("SHOT_DIR")  # optional: save review shots
# #270: every settings chip/label stays on ONE line (zh 「固定镜头」 used to wrap); nothing spills out of its chip.
M = """() => [...document.querySelectorAll('.ca-gen__settings .ca-gen__chip, .ca-gen__settings .ca-gen__label')].filter(e => e.getBoundingClientRect().width > 0).map(e => {
  const r = document.createRange(); r.selectNodeContents(e); const lines = new Set([...r.getClientRects()].filter(x => x.width > 0).map(x => Math.round(x.top)));
  return [e.textContent, lines.size, e.scrollWidth - e.clientWidth] })"""
@pytest.mark.parametrize("width", [1280, 360])
@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("mode", ["video", "image"])
async def test_labels_one_line(app_url, fake_tools, monkeypatch, width, theme, lang, mode):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width": width, "height": 900}, device_scale_factor=2)).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
        await pg.goto(app_url + f"?project=l270{mode}{lang}{theme}{width}&new=1")
        await pg.locator(".ca-composer__mode").wait_for(); await pg.wait_for_timeout(1500)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
        await pg.locator(".ca-composer__mode").click(); await pg.wait_for_timeout(300)
        name = {("video", "zh"): "视频", ("image", "zh"): "图像", ("video", "en"): "Video", ("image", "en"): "Image"}[(mode, lang)]
        await pg.locator(".ca-agentpick .ca-menu__item:not(.ca-agentpick__row)").filter(has_text=name).first.click()
        await pg.wait_for_timeout(400)
        if await pg.locator(".ca-agentpick").count(): await pg.keyboard.press("Escape")
        await pg.locator(".ca-composer__foot [data-pill=settings]").first.click(); await pg.wait_for_timeout(500)
        rows = await pg.evaluate(M)
        assert rows, "settings popover did not open"
        if SHOT:
            os.makedirs(SHOT, exist_ok=True)
            await pg.locator(".ca-gen__settings").first.screenshot(path=f"{SHOT}/{mode}-{lang}-{theme}-{width}.png")
        bad = [r for r in rows if r[1] > 1 or r[2] > 0]
        assert not bad, bad
        await b.close()
