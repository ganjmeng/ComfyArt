"""#944 HOLD: Full App zh/en screenshots of the still-generating card (no stuck card, no 继续生成).

Drives the real composer -> HTTP -> agent loop -> persisted run_stop -> dist UI.
Only LLM and MCP boundaries/clock are scripted; no summary card injection, no paid submit.
Set CA_943_SHOTS=<dir> to write the review screenshots (always written to that dir when set;
defaults to tmp-943-shots under the repo).
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from test_agent_budget_391 import Rig, calls, reply, store  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401,E402
from test_e2e_default_agent import fake_tools, _page  # noqa: F401,E402

ROOT = Path(__file__).resolve().parent.parent
SHOT_DIR = Path(os.environ.get("CA_943_SHOTS", str(ROOT / "tmp-943-shots")))
ZH = "图片还在生成，生成好后会自动出现在画布上，不会重复扣费。"
EN = "The image is still generating. It will appear on the canvas when it's ready, with no extra charge."


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_full_app_still_generating_card(app_url, fake_tools, monkeypatch, store, lang, theme):  # noqa: F811
    from ComfyArt.bot import providers as registry

    r = None

    def script(messages, n):
        if n == 0:
            return calls(("generate_image", {"prompt": "local fixture", "model": "m"}))
        if n == 1:
            return calls(("wait_generation", {"ids": ["holder1"]}))
        return reply("done")

    def mcp(name, args, n):
        if name == "generate_image":
            return json.dumps({"ids": ["holder1"]})
        if name == "wait_generation":
            r.clock.t += 1801
            return json.dumps({"status": "running", "results": [{"id": "holder1", "status": "running"}]})
        return json.dumps({})

    r = Rig(monkeypatch, script, store=store, mcp=mcp, prices={"generate_image": 0.09})
    monkeypatch.setitem(registry._REGISTRY, "local-llm", r.p)
    want = ZH if lang == "zh" else EN
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, lang, theme)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"chromium/full app boot failed: {e}")
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(100)
        await pg.locator(".ca-composer__input").fill("画一张图" if lang == "zh" else "Draw an image")
        await pg.locator(".ca-composer__slotwrap > :not([hidden])").click()
        # The shared HTTP fixture stubs Comfy's websocket host. Read the real
        # persisted conversation after completion instead of fabricating events.
        from ComfyArt.api.bot_turns import ACTIVE_TURNS
        for _ in range(100):
            if r.n == 2 and not ACTIVE_TURNS:
                break
            await asyncio.sleep(0.05)
        assert r.n == 2 and not ACTIVE_TURNS
        await pg.reload()
        await pg.locator(".ca-split__chev").first.click(timeout=8000)
        await pg.locator(".ca-history__item").first.click(timeout=8000)
        card = pg.locator("[data-testid=run-stop-still-generating]").first
        try:
            await card.wait_for(timeout=10000)
        except Exception:
            Path(f"/tmp/944-chain-{lang}.txt").write_text(await pg.locator("body").inner_text())
            await pg.screenshot(path=f"/tmp/944-chain-{lang}.png")
            raise
        text = (await card.inner_text()).strip()
        assert want in text
        assert "任务卡住了" not in text
        assert "已停止" not in text
        assert "继续生成" not in text
        assert "Continue generating" not in text
        assert await card.locator("button").count() == 0
        other = EN if lang == "zh" else ZH
        assert other not in text
        assert len(r.paid_mcp()) == 1
        assert [name for name, _ in r.mcp] == ["generate_image", "wait_generation"]
        assert r.n == 2
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        await pg.locator(".ca-root").screenshot(path=str(SHOT_DIR / f"still-generating-{lang}-{theme}.png"))
        await browser.close()
