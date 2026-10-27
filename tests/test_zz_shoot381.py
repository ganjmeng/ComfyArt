import json, os
import pytest
pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa
from test_e2e_default_agent import fake_tools, pytestmark  # noqa

OUT = os.environ["SHOT_OUT"]
MEM = [
  {"id": "u1", "text": "我主要做咖啡与茶饮品牌的视觉内容。", "time": 1, "category": "basic", "label": "创作领域"},
  {"id": "u2", "text": "我习惯用简短直接的方式下达任务指令。", "time": 2, "category": "collab", "label": "指令风格"},
  {"id": "u3", "text": "我偏好暖色调视觉风格。", "time": 3, "category": "taste", "label": "色彩偏好"},
  {"id": "u4", "text": "我偏好极简、几何化与克制用色的视觉取向。", "time": 4, "category": "taste", "label": "视觉风格"},
]

@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_shoot(app_url, fake_tools, theme):  # noqa
    os.makedirs(OUT, exist_ok=True)
    async with pw.async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','zh');localStorage.setItem('comfyart.theme','{theme}')")
        url = app_url.rstrip('/') + '/?view=arti'
        await pg.goto(url)
        await pg.wait_for_timeout(4000); await pg.screenshot(path=f'{OUT}/dbg.png'); print('URL', pg.url, await pg.evaluate('document.body.innerText.slice(0,300)'))
        await pg.locator('[data-testid=arti-memory-center]').wait_for(timeout=15000)
        await pg.wait_for_timeout(800)
        await pg.screenshot(path=f"{OUT}/empty-{theme}.png")
        caps = pg.locator('.ca-arti__caps, [data-testid^=arti-cap-memory]').first
        await pg.screenshot(path=f"{OUT}/arti-toggles-{theme}.png", clip={"x": 0, "y": 0, "width": 1440, "height": 520})
        # seed user memories (both stores) and reload
        await pg.evaluate("""async (m) => { localStorage.setItem('comfyart.memory.local', JSON.stringify(m));
          localStorage.setItem('comfyart.memory.meta.local', JSON.stringify({demoCleanup381: true}));
          await fetch('/api/userdata/' + encodeURIComponent('comfyart/memory.json') + '?overwrite=true', {method: 'POST', body: JSON.stringify(m)});
          await fetch('/api/userdata/' + encodeURIComponent('comfyart/memory-meta.json') + '?overwrite=true', {method: 'POST', body: JSON.stringify({demoCleanup381: true})}) }""", MEM)
        await pg.reload()
        await pg.locator('[data-testid=arti-memory-row]').first.wait_for(timeout=15000)
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=f"{OUT}/list-{theme}.png")
        row = pg.locator('[data-testid=arti-memory-row][data-id=u3]')
        await row.hover()
        await row.locator('[data-testid=arti-memory-menu-btn]').click()
        await pg.locator('[data-testid=arti-memory-row-menu] button').last.click()
        await pg.locator('.ca-modal').wait_for(timeout=5000)
        await pg.wait_for_timeout(300)
        await pg.screenshot(path=f"{OUT}/delete-confirm-{theme}.png")
        await pg.locator('.ca-modal .ca-panel__primary').click()
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=f"{OUT}/delete-toast-{theme}.png")
        await pg.wait_for_timeout(2600)
        await pg.screenshot(path=f"{OUT}/after-delete-{theme}.png")
        await b.close()
