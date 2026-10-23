"""#174: a WaveSpeed timeout carries error kind 'timeout' (+ the quoted amount when known) so the card shows zh/en copy.
Mocks only, $0. #173's strict xfail (test_170_task_timeout_has_readable_kind) is now a normal test."""
from __future__ import annotations

import pytest

from ComfyArt.api import wavespeed
from test_wavespeed import ws  # noqa: F401  (mocked WaveSpeed API)


def _info(hist: dict, task: str) -> dict:
    return hist[f"ws:{task}"]["status"]["messages"][0][1]


async def test_local_timeout_has_kind_and_amount(ws, monkeypatch):  # noqa: F811
    ws["status"] = "processing"
    ws["prices"]["wavespeed-ai/minimax-h3/text-to-video"] = 0.32
    task = await wavespeed.submit({"feature": "text_to_video", "model": "wavespeed-ai/minimax-h3/text-to-video", "prompt": "x", "duration": 5})
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 0.0)
    info = _info(await wavespeed.poll(task), task)
    assert "timed out" in info["exception_message"]
    assert info["ws_kind"] == "timeout" and info["ws_charged"] == pytest.approx(0.32)
    assert len(ws["submits"]) == 1  # no auto-retry


async def test_wavespeed_reported_timeout_has_kind(ws):  # noqa: F811
    ws["status"] = "timeout"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x", "confirmed": True})
    info = _info(await wavespeed.poll(task), task)
    assert info["ws_kind"] == "timeout"
    assert len(ws["submits"]) == 1


async def test_timeout_without_price_has_no_amount(ws, monkeypatch):  # noqa: F811
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x", "confirmed": True})
    wavespeed._jobs[task].pop("model", None)  # nothing to quote
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 0.0)
    info = _info(await wavespeed.poll(task), task)
    assert info["ws_kind"] == "timeout" and "ws_charged" not in info


async def test_run_raw_timeout_route_body(ws, monkeypatch):  # noqa: F811
    ws["status"] = "processing"
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.run_raw({"feature": "text_to_image", "prompt": "x", "confirmed": True}, timeout=0.0)
    assert e.value.kind == "timeout"
    body = wavespeed._respond_error(e.value)
    import json
    err = json.loads(body.body)["error"]
    assert err["kind"] == "timeout" and ("charged_usd" in err) == (e.value.charged is not None)
