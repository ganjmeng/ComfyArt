"""#120: text-returning models (whisper transcribe M32, image captioner M33, OCR) read their text from
wherever WaveSpeed puts it, never report an empty success, and a WaveSpeed `timeout` status stops polling
with the charged amount. Mock WaveSpeed server only (no real calls)."""
from __future__ import annotations

import pytest

from ComfyArt.api import wavespeed
from tests.test_wavespeed import ws  # noqa: F401

AUDIO = "/api/view?filename=voice.webm&subfolder=&type=input"
PIC = "/api/view?filename=pic.png&subfolder=&type=input"


@pytest.fixture
def media(fresh_user_dir):
    d = fresh_user_dir / "input"
    d.mkdir(parents=True, exist_ok=True)
    (d / "voice.webm").write_bytes(b"audio")
    (d / "pic.png").write_bytes(b"png")


@pytest.mark.parametrize("out,text", [
    ("你好世界", "你好世界"),
    ({"text": "hello there"}, "hello there"),
    ({"segments": [{"text": "a"}, {"text": "b"}]}, "a b"),
    ('{"transcription": "json text"}', "json text"),
])
async def test_transcribe_reads_text_shapes(ws, bot_client, media, out, text):
    ws["outputs"] = [out]
    res = await bot_client.post("/comfyart/wavespeed/transcribe", json={"src": AUDIO})
    assert res.status == 200, await res.text()
    assert (await res.json())["text"] == text


async def test_caption_reads_object_output(ws, bot_client, media):
    ws["outputs"] = [{"caption": "a red bicycle"}]
    res = await bot_client.post("/comfyart/wavespeed/caption", json={"src": PIC})
    assert (await res.json())["text"] == "a red bicycle"


@pytest.mark.parametrize("route,src", [("transcribe", AUDIO), ("caption", PIC)])
async def test_completed_without_text_is_an_error(ws, bot_client, media, route, src):
    ws["outputs"] = [""]
    res = await bot_client.post(f"/comfyart/wavespeed/{route}", json={"src": src})
    assert res.status >= 400
    assert "without output" in (await res.text())


async def test_completed_with_blank_object_is_an_error(ws, bot_client, media):
    ws["outputs"] = [{"text": "  "}]
    res = await bot_client.post("/comfyart/wavespeed/transcribe", json={"src": AUDIO})
    assert res.status >= 400 and "without text" in (await res.text())


async def test_ocr_empty_outputs_raise(ws):
    ws["outputs"] = [""]
    with pytest.raises(wavespeed.WaveSpeedError, match="without output"):
        await wavespeed.run_raw({"feature": "ocr", "image": "https://cdn.test/a.png", "params": {"output_format": "json"}})


async def test_timeout_status_stops_with_charged_amount(ws, bot_client, media):
    ws["status"] = "timeout"
    ws["prices"]["wavespeed-ai/image-captioner"] = 0.001371
    res = await bot_client.post("/comfyart/wavespeed/caption", json={"src": PIC})
    assert res.status == 504
    assert "timed out, may have been charged about (quoted price) $0.001371" in await res.text()
    assert len(ws["submits"]) == 1 and ws["polls"] == 1  # terminal: no 900s polling, no resubmit


@pytest.mark.parametrize("status", ["cancelled", "deleted"])
async def test_other_terminal_statuses_stop_polling(ws, status):
    ws["status"] = status
    with pytest.raises(wavespeed.WaveSpeedError, match=status):
        await wavespeed.run_raw({"feature": "caption", "image": "https://cdn.test/a.png"}, timeout=5)
    assert ws["polls"] == 1


async def test_generate_job_timeout_status_reports_charge(ws):
    ws["prices"]["wavespeed-ai/image-captioner"] = 0.001371
    task = await wavespeed.submit({"feature": "caption", "image": "https://cdn.test/a.png"})
    ws["status"] = "timeout"
    h = (await wavespeed.poll(task))[f"ws:{task}"]
    assert h["status"]["status_str"] == "error"
    assert "may have been charged about (quoted price) $0.001371" in h["status"]["messages"][0][1]["exception_message"]


async def test_generate_job_text_only_output_is_not_an_empty_success(ws):
    task = await wavespeed.submit({"feature": "caption", "image": "https://cdn.test/a.png"})
    ws["outputs"] = ["just text"]
    h = (await wavespeed.poll(task))[f"ws:{task}"]
    assert h["status"]["status_str"] == "error"
