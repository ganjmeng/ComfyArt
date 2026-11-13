"""product-to-packaging e2e (Lovart e304e2fa): the real built app in headless Chromium, real ComfyArt routes,
real MCP tool dispatch (api.mcp._tools_call), real chat panel. $0: the agent is a scripted in-process
provider (no LLM), WaveSpeed is the local mock and nothing is submitted to it.

Card: the agent sends the card as Lovart wrote it for the dropper bottle (zh UI), or the en equivalent
(en UI), plus a sloppy default, a recommended flag and an extra question. The docked question card in the
real chat panel shows 1 of 3, the three titles, question 1 and 2 options from the photo, question 3's fixed
scope list (multi-select) and the free-text placeholders, nothing preselected, no 推荐. Answering A / A /
A+B returns the answers to the agent.

dist/ must be a local build of this tree (`npx vite build`, not committed); a missing or stale dist/ or a
missing Chromium is a hard failure, never a skip. PACKAGING_E2E_SHOTS=/dir keeps the screenshots.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import re
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures: real routes + local mock WaveSpeed)
from test_product_packaging_flow import CALL, FIXED, LIVE, PLACEHOLDERS
from test_skill_e2e_portrait_studio import ScriptedAgent, _call, _send, agent, ws_forward  # noqa: F401

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
SHOTS = os.environ.get("PACKAGING_E2E_SHOTS")
LOC = {lg: json.loads((ROOT / f"src/locales/{lg}.json").read_text(encoding="utf-8")) for lg in ("zh", "en")}
USER_TEXT = {"zh": "用这张产品图做一套包装。", "en": "Make a packaging set from this product photo."}


@pytest.fixture(autouse=True, scope="module")
def built_dist():
    index = ROOT / "dist" / "index.html"
    if not index.is_file():
        pytest.fail("dist/index.html is missing: run `npx vite build` (local build, not committed) before this e2e")
    bundle = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "dist").rglob("*.js"))
    if "pk_product" not in bundle:
        pytest.fail("dist/ is stale (no product-to-packaging card in skills): run `npx vite build` (local, not committed)")


@pytest.fixture(autouse=True)
def no_paid_keys(monkeypatch):
    for key in ("WAVESPEED_API_KEY", "DEEPSEEK_API_KEY", "REPLICATE_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)


async def _page(p, app_url, lang, sockets):  # noqa: F811
    try:
        browser = await p.chromium.launch()
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"chromium not available, this e2e must not skip: {e}")
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN" if lang == "zh" else "en-US")
    await ctx.route_web_socket(re.compile(r"/ws(\?|$)"), lambda ws: sockets.append(ws))
    pg = await ctx.new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','light')")
    await pg.goto(app_url + f"?project=ppk{lang}&new=1&skill=product-to-packaging&mode=agent")
    await pg.locator(".ca-composer__input").wait_for(timeout=20000)
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)
    await pg.locator(".ca-composer").get_by_text(LOC[lang]["skills.productToPackaging"]).first.wait_for(timeout=15000)
    await pg.locator(".ca-composer").get_by_text(ScriptedAgent.label, exact=True).wait_for(timeout=15000)
    return browser, pg


async def _shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def _paid(mock_ws):  # noqa: F811
    return mock_ws["submits"] + mock_ws["quotes"]


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_skill_e2e_product_packaging_card_renders_the_reference_card(app_url, mock_ws, agent, ws_forward, lang):  # noqa: F811
    sloppy = copy.deepcopy(CALL[lang])
    sloppy["questions"][0]["defaults"] = ["A"]
    sloppy["questions"][1]["options"][0]["recommended"] = True
    sloppy["questions"][2]["page"] = 3
    sloppy["questions"].append({"id": "q4", "prompt": "要不要烫金？", "options": [{"id": "a", "label": "要"}, {"id": "b", "label": "不要"}]})
    sloppy["page_count"] = 4

    async def steps(a, turn, emit):
        await _call(a, emit, "ask_user", sloppy, 1)
    agent.steps = steps
    p1, p2, p3, scope = FIXED[lang]
    labels = [LIVE[lang]["pk_product"], LIVE[lang]["pk_color"], scope]
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, app_url, lang, ws_forward)
        await _send(pg, USER_TEXT[lang])
        card = pg.locator('[data-testid="question-dock"] .ca-q')
        await card.wait_for(timeout=20000)
        head = await card.locator(".ca-q__head").inner_text()
        assert re.search(r"1\s*(of|/)\s*3", head), head
        prompts = [t.strip() for t in await card.locator(".ca-q__prompt").all_inner_texts()]
        assert [x.replace("\n", " ") for x in prompts][:2] == [p1, p2], prompts
        assert prompts[2].startswith(p3), prompts  # the UI may add its own multi-select hint after the title
        blocks = card.locator(".ca-q__block")
        assert await blocks.count() == 3
        for i, (want, placeholder) in enumerate(zip(labels, PLACEHOLDERS[lang])):
            blk = blocks.nth(i)
            assert [t.strip() for t in await blk.locator(".ca-q__text").all_inner_texts()] == want
            assert await blk.locator(".ca-q__letter").all_inner_texts() == list("ABCDE")[:len(want) + 1]
            assert await blk.locator(".ca-q__input").get_attribute("placeholder") == placeholder
            assert await blk.locator(".ca-q__opt[data-on]").count() == 0  # nothing preselected
        assert await card.locator(".ca-q__rec").count() == 0  # no 推荐 marker
        assert await card.locator(".ca-q__skip").count() == 1
        visible = await card.inner_text()
        assert "要不要烫金" not in visible and "推荐" not in visible and "ecommended" not in visible
        for needle in ("pk_product", "pk_color", "pk_scope", "e304e2fa", "Lovart", "product-to-packaging"):
            assert needle not in visible, needle
        body = "\n".join(await card.locator(".ca-q__body").all_inner_texts())
        assert bool(re.search(r"[\u4e00-\u9fff]", body)) is (lang == "zh"), body
        await _shot(pg, f"card-{lang}")
        await card.locator(".ca-q__body").evaluate("el => { el.scrollTop = el.scrollHeight }")
        await _shot(pg, f"card-{lang}-bottom")
        await blocks.nth(0).locator(".ca-q__opt").first.click()
        await blocks.nth(1).locator(".ca-q__opt").first.click()
        await blocks.nth(2).locator(".ca-q__opt").nth(0).click()
        await blocks.nth(2).locator(".ca-q__opt").nth(1).click()  # 可多选
        assert await blocks.nth(2).locator(".ca-q__opt[data-on]").count() == 2
        await _shot(pg, f"card-{lang}-selected")
        submit = card.locator(".ca-q__submit")
        for _ in range(6):  # scroll card: Next scrolls, Submit appears at the bottom
            if LOC[lang]["chatMessage.submit"] in await submit.inner_text():
                break
            await submit.click()
            await pg.wait_for_timeout(400)
        await submit.click()
        for _ in range(100):
            if agent.results:
                break
            await asyncio.sleep(0.1)
        name, answer = agent.results[0]
        assert name == "ask_user" and answer["status"] == "answered", answer
        assert {k: sorted(v["selected"]) for k, v in answer["answers"].items()} == {
            "pk_product": ["A"], "pk_color": ["A"], "pk_scope": ["A", "B"]}
        assert _paid(mock_ws) == []
        await browser.close()
