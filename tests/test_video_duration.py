"""#128: a requested video duration the model doesn't take is rounded up to its next allowed value (capped at the
longest); the confirm dialog and the tool result state the actual duration in zh and en. Pure functions, no WaveSpeed."""
import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ComfyArt.api import wavespeed as ws

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")


@pytest.mark.parametrize("asked,actual", [(3, 5), (5, 5), (7, 10), (10, 10), (11, 15), (15, 15), (20, 15), ("3", 5)])
def test_backend_rounds_up_and_caps(asked, actual):
    assert ws.fit_duration([5, 10, 15], asked) == actual


def test_backend_payload_uses_rounded_duration():
    schema = {"properties": {"duration": {"type": "integer", "enum": [5, 10]}}}
    payload = asyncio.run(ws.build_payload(None, schema, {"duration": 7}))
    assert payload["duration"] == 10
    payload = asyncio.run(ws.build_payload(None, schema, {"duration": 30}))
    assert payload["duration"] == 10


@pytest.fixture(scope="module")
def js(tmp_path_factory):
    out = tmp_path_factory.mktemp("dur") / "dur.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "video_duration.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_frontend_rounds_up_and_caps(js):
    assert js["fit"] == [5, 5, 5, 5, 10, 10, 15, 15, 15]
    assert js["fitModel"] == [5, 5, 10, 10, 10]


@needs_node
def test_actual_duration_is_stated_zh_en(js):
    three, seven, twenty, exact = js["notes"]
    assert three["zh"].startswith("该模型最短 5 秒，将按 5 秒生成") and "3 秒" in three["zh"]
    assert "shortest video is 5s" in three["en"] and "3s" in three["en"]
    assert "不支持 7 秒，将按 10 秒生成" in seven["zh"] and "10s" in seven["en"]
    assert "最长 15 秒，将按 15 秒生成" in twenty["zh"] and "longest video is 15s" in twenty["en"]
    assert exact == {"zh": "", "en": ""} and js["none"] == ""


def test_wiring():
    bot = (ROOT / "src/botCommands.ts").read_text()
    assert "fitDuration(args.duration, lengths)" in bot and "duration_note: notes" in bot
    assert "DURATIONS.includes(args.duration)" not in bot  # no silent fallback to 5s
    assert "duration_note" in (ROOT / "src/generate.ts").read_text()
    assert "inputs.duration_note" in (ROOT / "src/comfy.ts").read_text()
