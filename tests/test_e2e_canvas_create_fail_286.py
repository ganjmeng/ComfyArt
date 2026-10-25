"""#286: coming from home, the canvas page creates the project on its first save. When that PUT fails (mocked 500),
the prompt from the URL `ask` param goes back into the canvas chat box, an error toast shows, and nothing is sent.
Mock only, nothing paid is called ($0)."""
from __future__ import annotations

from urllib.parse import quote

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)

pw = pytest.importorskip("playwright.async_api")
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

ASK = "画一只橘猫 #286"
MSG = {"zh": "项目创建失败", "en": "Couldn’t create the project"}


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_create_fail_restores_prompt(app_url, lang):  # noqa: F811
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
        sent = []

        async def projects(route):
            if route.request.method == "PUT":
                await route.fulfill(status=500, body='{"error":"mock create failure"}', content_type="application/json")
            else:
                await route.fallback()

        await pg.route("**/comfyart/projects/p286fail*", projects)
        await pg.route("**/comfyart/bot/**", lambda r: (sent.append(r.request.url) if r.request.method == "POST" else None) or r.fallback())
        base = app_url.split("?")[0].rstrip("/")
        await pg.goto(f"{base}/?project=p286fail&new=1&mode=agent&ask={quote(ASK)}")
        await pg.locator(".tl-canvas").wait_for()
        box = pg.locator(".ca-composer__input").first
        await pg.wait_for_function("(a) => [...document.querySelectorAll('.ca-composer__input')].some((e) => e.value === a)", arg=ASK, timeout=8000)
        assert await box.input_value() == ASK
        await pg.get_by_text(MSG[lang]).first.wait_for(timeout=5000)
        assert "ask=" not in pg.url  # handoff params dropped: a reload won't auto-send
        assert not any(u.endswith("/send") for u in sent) and not any("/messages" in u for u in sent), sent
        await browser.close()
