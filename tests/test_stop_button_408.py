"""#408 first slice: generator-card stop button adapted to WaveSpeed cancel + 「已停止」 fee line."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ComfyArt.api import wavespeed
from ComfyArt.bot.run_budget import ui_credits
from tests.test_wavespeed import T2I, ws  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def test_stop_ui_and_locales_present():
    gen = (ROOT / "src/shapes/GeneratorShape.tsx").read_text()
    assert "stopJob" in gen and "ca-gen-card__stop" in gen and "jobs.stop" in gen
    assert "Icons.stop" in gen
    jobs = (ROOT / "src/jobs.ts").read_text()
    assert "export async function stopJob" in jobs
    assert "dropped" in jobs and "stoppedCharged" in jobs
    assert "jobs.stoppedCharged" in jobs and "jobs.stopped" in jobs
    comfy = (ROOT / "src/comfy.ts").read_text()
    assert "CancelResult" in comfy and "charged_usd" in comfy
    assert "dropped: true" in comfy  # WaveSpeed cancel always drops the waiter
    css = (ROOT / "src/styles/canvas.css").read_text()
    assert ".ca-gen-card__stop" in css
    icons = (ROOT / "src/ui/icons.tsx").read_text()
    assert "stop:" in icons
    zh = json.loads((ROOT / "src/locales/zh.json").read_text())
    en = json.loads((ROOT / "src/locales/en.json").read_text())
    assert zh["jobs.stop"] == "停止生成"
    assert zh["jobs.stopped"] == "已停止"
    assert "积分" in zh["jobs.stoppedCharged"] and "{0}" in zh["jobs.stoppedCharged"]
    assert en["jobs.stop"] == "Stop generating"
    assert en["jobs.stopped"] == "Stopped"
    assert "credits" in en["jobs.stoppedCharged"] and "{0}" in en["jobs.stoppedCharged"]
    # New stop path must not invent a second payment / charge API
    assert "/comfyart/wavespeed/cancel/" in (ROOT / "src/comfy.ts").read_text()


def test_localize_stopped_patterns_map_to_credits():
    """Source contract: stopped + quoted USD becomes jobs.stoppedCharged via uiCredits."""
    jobs = (ROOT / "src/jobs.ts").read_text()
    assert "WaveSpeed task stopped, may have been charged about (quoted price)" in jobs
    assert "uiCredits(Number(stoppedCharged[1]))" in jobs or "uiCredits(Number(stoppedCharged" in jobs
    assert "uiCredits(charged)" in jobs
    # $0.04 -> 4 credits matches the review mock banner
    assert ui_credits(0.04) == 4


@pytest.mark.asyncio
async def test_cancel_sets_interrupted_history_with_quoted_fee(ws):
    """Cancel frees the slot, writes interrupted history, and returns charged_usd from the quote."""
    ws["prices"][T2I] = 0.04
    # Keep the job "running" so cancel has something to interrupt
    ws["status"] = "processing"
    task = await wavespeed.submit({
        "feature": "text_to_image", "model": T2I, "prompt": "stop me",
        "width": 1024, "height": 1024, "confirmed": True,
    })
    assert task in wavespeed._jobs and not wavespeed._jobs[task].get("result")

    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        res = await client.post(f"/comfyart/wavespeed/cancel/{task}")
        body = await res.json()
        assert res.status == 200
        assert body.get("charged_usd") == pytest.approx(0.04)
        job = wavespeed._jobs[task]
        assert job.get("done") is True
        hist = job["result"][f"ws:{task}"]
        msgs = hist["status"]["messages"]
        assert msgs and msgs[0][0] == "execution_interrupted"
        assert msgs[0][1]["ws_charged"] == pytest.approx(0.04)
        assert "may have been charged" in msgs[0][1]["exception_message"]
        # Poll returns the cached interrupted result — waiter can settle without hanging
        again = await wavespeed.poll(task)
        assert again[f"ws:{task}"]["status"]["messages"][0][0] == "execution_interrupted"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_cancel_without_quote_still_interrupts(ws):
    """When price is unknown, cancel still settles as stopped (no charged_usd)."""
    ws["status"] = "processing"
    # No prices[T2I] → price API 400 → catalog estimate may still apply for default tier.
    # Force unpriced by clearing model on the job after submit.
    task = await wavespeed.submit({
        "feature": "text_to_image", "model": T2I, "prompt": "x",
        "width": 512, "height": 512, "confirmed": True,
    })
    wavespeed._jobs[task]["model"] = None  # no quote path
    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        res = await client.post(f"/comfyart/wavespeed/cancel/{task}")
        body = await res.json()
        assert res.status == 200
        assert "charged_usd" not in body
        msgs = wavespeed._jobs[task]["result"][f"ws:{task}"]["status"]["messages"]
        assert msgs[0][0] == "execution_interrupted"
        assert msgs[0][1]["exception_message"] == "WaveSpeed task stopped"
        assert "ws_charged" not in msgs[0][1]
    finally:
        await client.close()


def test_finish_suppresses_toast_on_user_stop():
    src = (ROOT / "src/jobs.ts").read_text()
    # User stop must not call onError (card banner only)
    finish = src.split("async function finish")[1].split("export async function stopJob")[0]
    assert "if (holder && !stopped) onError(msg)" in finish
    assert "stopped" in finish
