"""#944 HOLD: Full App zh/en screenshots of the still-generating card (no stuck card, no 继续生成).

Uses the real dist app and the backend's _summary_card. Mocked data only — no WaveSpeed submit.
Set CA_943_SHOTS=<dir> to write the review screenshots (always written to that dir when set;
defaults to tmp-943-shots under the repo).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from ComfyArt.bot.agent_loop import RunContext, _summary_card
from ComfyArt.bot.run_budget import BudgetLimits, ProgressTracker, RunBudget, Stop, StopReason, resolve_policy

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401,E402
from test_e2e_default_agent import fake_tools, _page  # noqa: F401,E402

ROOT = Path(__file__).resolve().parent.parent
SHOT_DIR = Path(os.environ.get("CA_943_SHOTS", str(ROOT / "tmp-943-shots")))
ZH = "图片还在生成，生成好后会自动出现在画布上，不会重复扣费。"
EN = "The image is still generating. It will appear on the canvas when it's ready, with no extra charge."


def still_generating_block() -> dict:
    policy = resolve_policy(env={})
    budget = RunBudget(BudgetLimits(tokens=10_000, credits=5, wall_s=900, hard_steps=300), clock=lambda: 0.0)
    ctx = RunContext(
        run_id="run-943-hold", store=None, lease_owner="t", policy=policy, budget=budget,
        tracker=ProgressTracker(), mode="interactive", goal="", lang="zh",
        owner_id="local", workspace_id="local", window=32_000, project_id="local",
    )
    card = _summary_card(ctx, Stop(StopReason.STUCK, "timeout", step=2))
    card["type"] = "run_stop"
    return card


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_full_app_still_generating_card(app_url, fake_tools, lang, theme):  # noqa: F811
    from ComfyArt.api import chat_store

    block = still_generating_block()
    want = ZH if lang == "zh" else EN
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, lang, theme)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"chromium/full app boot failed: {e}")
        user = await pg.evaluate("async()=>(await (await fetch('/api/comfyart/bot/status')).json()).user")
        proj = await pg.evaluate(
            "()=>{for (const e of performance.getEntriesByType('resource')){"
            "const m=e.name.match(/bot\\\\/chats\\\\?project=([^&]+)/); if(m) return decodeURIComponent(m[1])}"
            "return null}"
        )
        assert proj
        c = chat_store.create_chat(user=user, project=proj, provider="local-llm", title="still-gen-943")
        um = chat_store.create_message(chat_id=c["id"], role="user", blocks=[{"type": "text", "text": "画一张图"}])
        chat_store.create_message(chat_id=c["id"], role="assistant", parent_id=um["id"], blocks=[block])
        await pg.reload()
        await pg.locator(".ca-split__chev").first.click(timeout=8000)
        await pg.locator(".ca-history__item").first.click(timeout=8000)
        card = pg.locator("[data-testid=run-stop-still-generating]").first
        await card.wait_for(timeout=10000)
        text = (await card.inner_text()).strip()
        assert want in text
        assert "任务卡住了" not in text
        assert "已停止" not in text
        assert "继续生成" not in text
        assert "Continue generating" not in text
        assert await card.locator("button").count() == 0
        other = EN if lang == "zh" else ZH
        assert other not in text
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        await pg.locator(".ca-root").screenshot(path=str(SHOT_DIR / f"still-generating-{lang}-{theme}.png"))
        await browser.close()
