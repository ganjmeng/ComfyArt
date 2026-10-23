"""#130: edit_video cuts canvas videos into one new video on the local ComfyUI (ComfyArtTimeline). Direct mock tests:
the MCP tool only relays to the page, it is not a paid tool, it never reaches WaveSpeed, and the frontend graph is a
single local timeline node. Mocks only, no model call, no charge."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from conftest import node_ready

from ComfyArt.api import paid_guard, wavespeed
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot.guide import PAID_TOOLS

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not node_ready(), reason="COMFYART_SKIP_NODE_TESTS=1 and no node_modules")
ARGS = {
    "clips": [{"id": "shape:a", "start": 1, "end": 4}, {"id": "shape:b", "start": 0, "end": 4, "speed": 2, "volume": 0.5}],
    "transitions": [{"type": "fade", "duration": 0.5}],
    "music": {"id": "shape:song", "start": 10, "volume": 0.3},
    "captions": [{"text": "Hello", "start": 0, "end": 2}],
}


@pytest.fixture
def no_wavespeed(monkeypatch):
    """Any WaveSpeed submit/run or charge accounting fails the test."""
    def boom(*_a, **_k):
        raise AssertionError("edit_video must not call WaveSpeed")
    for name in ("submit", "run_raw", "run_text"):
        monkeypatch.setattr(wavespeed, name, boom)
    monkeypatch.setattr(paid_guard, "charged", boom)


def test_edit_video_is_not_a_paid_tool():
    assert "edit_video" in canvas.TOOLS
    assert "edit_video" not in PAID_TOOLS
    assert canvas.TOOLS["edit_video"]["inputSchema"]["required"] == ["clips"]


async def test_edit_video_relays_args_to_page_unchanged(monkeypatch, no_wavespeed):
    sent, asked = [], []

    async def fake_submit(action, args, project, timeout, chat=None):
        sent.append((action, json.loads(json.dumps(args)), timeout))
        return {"ids": ["shape:out"]}

    async def fake_approval(label):
        asked.append(label)
        return None

    monkeypatch.setattr(canvas, "submit_command", fake_submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", fake_approval)
    out = await canvas.TOOLS["edit_video"]["handler"](dict(ARGS))
    assert out == {"ids": ["shape:out"]}
    assert sent == [("edit_video", ARGS, 20.0)]
    assert asked == ["剪辑视频"]


async def test_edit_video_declined_never_reaches_page(monkeypatch, no_wavespeed):
    async def fake_submit(*_a, **_k):
        raise AssertionError("declined edit must not be sent")

    async def decline(_label):
        return {"declined": True}

    monkeypatch.setattr(canvas, "submit_command", fake_submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", decline)
    assert await canvas.TOOLS["edit_video"]["handler"](dict(ARGS)) == {"declined": True}


def test_frontend_wiring_runs_locally():
    actions = (ROOT / "src/actions.ts").read_text()
    line = next(l for l in actions.splitlines() if l.startswith("export const editVideo"))
    body = actions.split(line, 1)[1].split("\n\n", 1)[0]
    assert "timelineGraph(edit" in body and "runOn: 'local'" in body
    assert "wsBuilt" not in body and "cloud(" not in body
    assert "actions.editVideo(" in (ROOT / "src/botCommands.ts").read_text()


@pytest.fixture(scope="module")
def js(tmp_path_factory):
    out = tmp_path_factory.mktemp("ev") / "ev.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "edit_video.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_timeline_graph_is_one_local_node(js):
    for key in ("built", "hard"):
        graph = js[key]["graph"]
        assert list(graph) == ["r"] and js[key]["result"] == "r"
        assert graph["r"]["class_type"] == "ComfyArtTimeline"
        assert "wavespeed" not in json.dumps(graph).lower()
    assert js["calls"] == [] and js["net"] == []  # nothing uploaded, queued or fetched while building


@needs_node
def test_timeline_cuts_fades_and_music(js):
    tl = json.loads(js["built"]["graph"]["r"]["inputs"]["timeline"])
    assert (tl["width"], tl["height"], tl["fps"], tl["format"]) == (1280, 720, 24, "mp4")
    a, b = tl["video"]
    assert (a["src"], a["offset"], a["fadeOut"]) == ("a.mp4 [input]", 1, 0.25)
    assert (b["speed"], b["volume"], b["fadeIn"], b["transition"]) == (2, 0.5, 0.25, {"type": "fade", "duration": 0.5})
    assert tl["duration"] == 4.5  # 3 s + 2 s at 2x, minus the 0.5 s fade overlap
    assert tl["audio"] == [{"src": "song.mp3 [input]", "start": 0, "duration": 4.5, "offset": 10, "speed": 1, "volume": 0.3}]
    hard = json.loads(js["hard"]["graph"]["r"]["inputs"]["timeline"])
    assert hard["duration"] == 5 and hard["audio"] == [] and all(v["fadeIn"] == v["fadeOut"] == 0 for v in hard["video"])
