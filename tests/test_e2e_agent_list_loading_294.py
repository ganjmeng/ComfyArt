"""#294: while the Agent list (/comfyart/bot/status) is still loading, send is disabled and comes back once it
arrives; if loading fails, the real error is shown instead of 「没有可用的 Agent」. zh and en. Mocks only ($0)."""
from __future__ import annotations

import asyncio
import json

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import fake_tools  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

NO_AGENT = {"zh": "没有可用的 Agent", "en": "No Agent available"}
FAILED = {"zh": "Agent 列表加载失败", "en": "Couldn’t load the Agent list"}
SEND = ".ca-composer__slotwrap [data-slot=send]"


async def _open(p, app_url, lang, project, handler):  # noqa: F811
    try:
        browser = await p.chromium.launch()
    except Exception as e:
        pytest.skip(f"chromium not available: {e}")
    pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
    await pg.route("**/comfyart/bot/status*", handler)
    await pg.goto(app_url + f"?project={project}&new=1")
    await pg.locator(".ca-composer__input").wait_for()
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)
    return browser, pg


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_send_disabled_while_agent_list_loads(app_url, fake_tools, monkeypatch, lang):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    release = asyncio.Event()
    sends: list[str] = []

    async def slow(route):
        await release.wait()
        await route.continue_()

    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, f"e294s{lang}", slow)
        pg.on("request", lambda r: sends.append(r.url) if r.method == "POST" and "/comfyart/bot/chats" in r.url else None)
        await pg.locator(".ca-composer__input").fill("a cat")
        await pg.wait_for_timeout(400)
        btn = pg.locator(SEND)
        assert await btn.is_disabled()  # list still loading -> send not clickable
        await pg.locator(".ca-composer__input").press("Enter")  # Enter must not slip through either
        await pg.wait_for_timeout(400)
        assert sends == [], sends
        assert NO_AGENT[lang] not in await pg.locator("body").inner_text()
        assert await pg.locator(".ca-composer__input").input_value() == "a cat"  # draft kept
        release.set()
        await pg.wait_for_function(f"() => !document.querySelector('{SEND}')?.disabled", timeout=10000)  # list arrived -> back
        await browser.close()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_agent_list_error_shows_real_error(app_url, fake_tools, monkeypatch, lang):  # noqa: F811
    """Failed load: send stays clickable; each click re-loads the list once; still failing -> real error, draft kept."""
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    detail = "bot status exploded (mock)"
    hits: list[str] = []

    async def fail(route):
        hits.append(route.request.url)
        await route.fulfill(status=500, content_type="application/json", body=json.dumps({"error": detail}))

    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, f"e294e{lang}", fail)
        await pg.wait_for_timeout(800)
        await pg.locator(".ca-composer__input").fill("a cat")
        await pg.wait_for_timeout(300)
        btn = pg.locator(SEND)
        assert await btn.is_enabled()  # loading is over (failed), so send stays clickable
        before = len(hits)
        await btn.click()
        await pg.get_by_text(FAILED[lang]).first.wait_for(timeout=5000)
        assert len(hits) == before + 1, hits  # the click re-loaded the Agent list exactly once
        body = await pg.locator("body").inner_text()
        assert FAILED[lang] in body and detail in body, body[-800:]
        assert NO_AGENT[lang] not in body
        assert await pg.locator(".ca-composer__input").input_value() == "a cat"  # draft kept
        await btn.click()  # every click retries once
        await pg.wait_for_timeout(800)
        assert len(hits) == before + 2, hits
        assert await pg.locator(".ca-composer__input").input_value() == "a cat"
        await browser.close()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_agent_list_recovers_on_send(app_url, fake_tools, monkeypatch, lang):  # noqa: F811
    """First status load 500s; the reload on send succeeds -> the message goes out normally."""
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    hits: list[str] = []
    sends: list[str] = []

    async def flaky(route):
        hits.append(route.request.url)
        if len(hits) == 1:
            await route.fulfill(status=500, content_type="application/json", body=json.dumps({"error": "first load fails (mock)"}))
        else:
            await route.continue_()

    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, f"e294r{lang}", flaky)
        pg.on("request", lambda r: sends.append(r.url) if r.method == "POST" and "/comfyart/bot/chats" in r.url else None)
        await pg.wait_for_timeout(800)
        assert len(hits) == 1, hits
        await pg.locator(".ca-composer__input").fill("a cat")
        await pg.wait_for_timeout(300)
        await pg.locator(SEND).click()
        await pg.wait_for_function("() => document.querySelector('.ca-composer__input').value === ''", timeout=10000)  # sent -> cleared
        assert len(hits) >= 2, hits
        await pg.wait_for_timeout(500)
        assert any(u.endswith("/send") for u in sends), sends
        body = await pg.locator("body").inner_text()
        assert FAILED[lang] not in body and NO_AGENT[lang] not in body
        await browser.close()
