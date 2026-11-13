"""WaveSpeed timeout behaviour. Mocks only, $0.

A job already submitted to WaveSpeed is never judged failed at our local poll cap.
The history route stays on processing until WaveSpeed completes (image lands) or
WaveSpeed itself reports failed/timeout. WaveSpeed-reported timeout still carries
kind 'timeout' (+ the quoted amount when known) so the card can show zh/en copy.
"""
from __future__ import annotations

import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ComfyArt.api import gen_ledger, wavespeed
from test_wavespeed import ws  # noqa: F401  (mocked WaveSpeed API)


def _info(hist: dict, task: str) -> dict:
    return hist[f"ws:{task}"]["status"]["messages"][0][1]


def _entry(hist: dict, task: str) -> dict:
    return hist[f"ws:{task}"]


async def test_local_cap_keeps_processing_no_resubmit(ws, monkeypatch):  # noqa: F811
    """Our poll cap must not fail a submitted, still-running job or submit again."""
    ws["status"] = "processing"
    ws["prices"]["wavespeed-ai/minimax-h3/text-to-video"] = 0.32
    task = await wavespeed.submit({"feature": "text_to_video", "model": "wavespeed-ai/minimax-h3/text-to-video", "prompt": "x", "duration": 5})
    monkeypatch.setattr(wavespeed, "IMAGE_JOB_TIMEOUT", 0.0)
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 0.0)
    st = _entry(await wavespeed.poll(task), task)["status"]
    assert st["completed"] is False and st["status_str"] == "processing" and not st["messages"]
    assert wavespeed._jobs[task]["fallback_blocked"] is True
    assert len(ws["submits"]) == 1  # no auto-retry / no second charge
    assert not [f for f in gen_ledger.failures() if f["task_id"] == task]


async def test_wavespeed_reported_timeout_has_kind(ws):  # noqa: F811
    ws["status"] = "timeout"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x", "confirmed": True})
    info = _info(await wavespeed.poll(task), task)
    assert info["ws_kind"] == "timeout"
    assert len(ws["submits"]) == 1


async def test_local_cap_without_price_still_processing(ws, monkeypatch):  # noqa: F811
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x", "confirmed": True})
    wavespeed._jobs[task].pop("model", None)  # nothing to quote
    monkeypatch.setattr(wavespeed, "IMAGE_JOB_TIMEOUT", 0.0)
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 0.0)
    st = _entry(await wavespeed.poll(task), task)["status"]
    assert st["completed"] is False and st["status_str"] == "processing" and not st["messages"]
    assert "ws_kind" not in (st["messages"][0][1] if st["messages"] else {})


async def test_run_raw_timeout_route_body(ws, monkeypatch):  # noqa: F811
    ws["status"] = "processing"
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.run_raw({"feature": "text_to_image", "prompt": "x", "confirmed": True}, timeout=0.0)
    assert e.value.kind == "timeout"
    body = wavespeed._respond_error(e.value)
    err = json.loads(body.body)["error"]
    assert err["kind"] == "timeout" and ("charged_usd" in err) == (e.value.charged is not None)


async def test_image_job_completes_at_933s_delivers_without_resubmit(ws, monkeypatch):  # noqa: F811
    """Simulated 933s completion (the ad43d7b8 case): past the old 600s cap, image is delivered, no resubmit."""
    from ComfyArt.api import gen_ledger as ledger

    assert wavespeed.IMAGE_JOB_TIMEOUT >= 933
    clock = {"now": 1_000.0}
    monkeypatch.setattr(wavespeed.time, "time", lambda: clock["now"])
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x", "confirmed": True})
    started = wavespeed._jobs[task]["started"]
    quoted = wavespeed._jobs[task].get("quoted")

    # Old 10 min cap: must stay processing, never an execution_error.
    clock["now"] = started + 600
    wavespeed._jobs[task]["next_poll"] = 0
    hist = await wavespeed.poll(task)
    st = _entry(hist, task)["status"]
    assert st["completed"] is False and st["status_str"] == "processing" and not st["messages"]
    assert len(ws["submits"]) == 1

    # WaveSpeed finishes at 933s on the same prediction id.
    ws["status"] = "completed"
    clock["now"] = started + 933
    wavespeed._jobs[task]["next_poll"] = 0
    hist = await wavespeed.poll(task)
    entry = _entry(hist, task)
    assert entry["generation_succeeded"] is True
    assert entry["status"]["status_str"] == "completed"
    assert entry["outputs"]["ws"]["images"]
    assert len(ws["submits"]) == 1
    row = ledger.run(task)
    assert row and row["status"] == "completed"
    assert not [f for f in ledger.failures() if f["task_id"] == task]
    # Quoted cost is recorded once on submit; success does not invent a second charge.
    if quoted is not None:
        assert row.get("quoted_usd") == quoted


async def test_image_job_delivers_after_30min_cap(ws, monkeypatch):  # noqa: F811
    """Past the 30 min cap the backend keeps fetching; a later completion still lands, no resubmit."""
    clock = {"now": 1_000.0}
    monkeypatch.setattr(wavespeed.time, "time", lambda: clock["now"])
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x", "confirmed": True})
    started = wavespeed._jobs[task]["started"]

    clock["now"] = started + 30 * 60 + 1
    wavespeed._jobs[task]["next_poll"] = 0
    st = _entry(await wavespeed.poll(task), task)["status"]
    assert st["completed"] is False and st["status_str"] == "processing" and not st["messages"]
    assert wavespeed._jobs[task]["fallback_blocked"] is True
    assert len(ws["submits"]) == 1

    ws["status"] = "completed"
    clock["now"] = started + 30 * 60 + 20
    wavespeed._jobs[task]["next_poll"] = 0
    entry = _entry(await wavespeed.poll(task), task)
    assert entry["generation_succeeded"] is True
    assert entry["outputs"]["ws"]["images"]
    assert len(ws["submits"]) == 1


async def test_history_route_backfills_completed_image(ws, monkeypatch):  # noqa: F811
    """GET /comfyart/wavespeed/history/<id> is the canvas poll path: processing then completed images."""
    import server

    clock = {"now": 1_000.0}
    monkeypatch.setattr(wavespeed.time, "time", lambda: clock["now"])
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x", "confirmed": True})
    started = wavespeed._jobs[task]["started"]

    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        clock["now"] = started + 933
        wavespeed._jobs[task]["next_poll"] = 0
        res = await client.get(f"/comfyart/wavespeed/history/{task}")
        assert res.status == 200
        body = await res.json()
        assert body[f"ws:{task}"]["status"]["status_str"] == "processing"

        ws["status"] = "completed"
        wavespeed._jobs[task]["next_poll"] = 0
        res = await client.get(f"/comfyart/wavespeed/history/{task}")
        assert res.status == 200
        entry = (await res.json())[f"ws:{task}"]
        assert entry["generation_succeeded"] is True
        assert entry["outputs"]["ws"]["images"]
        assert len(ws["submits"]) == 1
    finally:
        await client.close()


async def test_wavespeed_failed_still_reports_failure(ws):  # noqa: F811
    """Only WaveSpeed's own failed status is a user-facing failure."""
    ws["status"] = "failed"
    ws["error"] = "provider rejected the prompt"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x", "confirmed": True})
    entry = _entry(await wavespeed.poll(task), task)
    assert entry["status"]["completed"] is True
    assert entry["status"]["status_str"] == "error"
    assert entry["status"]["messages"][0][0] == "execution_error"
    assert len(ws["submits"]) == 1
