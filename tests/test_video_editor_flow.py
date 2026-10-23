"""#167: video editor mock flow (upstream 1.0.1 editor). The editor's own TS edit functions build a multi-clip edit
(add, trim, split, reorder, remove, music track with beat snap); the export graph is rendered by the local
ComfyArtTimeline node on generated clips, and the file is checked with ffprobe. No model call, no charge."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import node_ready

from ComfyArt.api import paid_guard, wavespeed
from ComfyArt.timeline import Timeline
from test_timeline import frames_at, make_clip
from test_timeline_music_export import write_song

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not node_ready(), reason="COMFYART_SKIP_NODE_TESTS=1 and no node_modules")
needs_ffprobe = pytest.mark.skipif(not shutil.which("ffprobe"), reason="ffprobe not installed")


@pytest.fixture
def no_wavespeed(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("the video editor must not call WaveSpeed")
    for name in ("submit", "run_raw", "run_text"):
        monkeypatch.setattr(wavespeed, name, boom)
    monkeypatch.setattr(paid_guard, "charged", boom)


@pytest.fixture(scope="module")
def js(tmp_path_factory):
    out = tmp_path_factory.mktemp("vef") / "vef.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "video_editor_flow.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def ffprobe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


@needs_node
def test_edit_operations(js):
    assert js["added"] == {"n": 3, "total": 6}
    assert js["trimmed"] == {"len": 1, "total": 5}
    assert [s.split("=")[1].split("&")[0] for s in js["order"]] == ["blue.mp4", "red.mp4", "green.mp4"]
    assert js["outOfRange"] is True
    assert js["splitN"] == 4 and js["noSplitEdge"] is True
    assert js["snapped"] == 1.0 and js["unsnapped"] == 1.3
    assert js["total"] == 4


@needs_node
def test_export_graph_is_local_and_matches_edit(js):
    assert js["calls"] == [] and js["net"] == []
    graph = js["built"]["graph"]
    assert list(graph) == ["r"] and graph["r"]["class_type"] == "ComfyArtTimeline"
    t = json.loads(graph["r"]["inputs"]["timeline"])
    assert t["duration"] == 4 and t["fps"] == 24 and t["format"] == "mp4"
    assert [(c["src"], c["start"], c["duration"], c["offset"]) for c in t["video"]] == [
        ("blue.mp4 [input]", 0, 2, 0), ("red.mp4 [input]", 2, 1, 0), ("green.mp4 [input]", 3, 1, 0.5)]
    assert t["audio"] == [{"src": "song.wav [input]", "start": 0, "duration": 4, "offset": 1, "speed": 1, "volume": 0.8}]


@needs_node
@needs_ffprobe
def test_export_renders_valid_video_matching_timeline(js, fresh_user_dir, no_wavespeed):
    inp = fresh_user_dir / "input"
    for name, color in (("red", (255, 0, 0)), ("green", (0, 255, 0)), ("blue", (0, 0, 255))):
        make_clip(inp / f"{name}.mp4", color)
    write_song(inp / "song.wav", seconds=6)
    node = js["built"]["graph"]["r"]["inputs"]
    ui = Timeline().render(node["timeline"], node["filename_prefix"])["ui"]
    ref = ui["images"][0]
    out = fresh_user_dir / "output" / ref["subfolder"] / ref["filename"]
    probe = ffprobe(out)
    kinds = {s["codec_type"]: s for s in probe["streams"]}
    assert set(kinds) == {"video", "audio"}
    assert kinds["video"]["codec_name"] == "h264" and (kinds["video"]["width"], kinds["video"]["height"]) == (64, 48)
    assert kinds["video"]["avg_frame_rate"] == "24/1"
    assert abs(float(probe["format"]["duration"]) - 4) < 0.2
    blue, red, green = frames_at(out, [1.0, 2.5, 3.5])
    assert blue[2] > 200 and red[0] > 200 and green[1] > 200


def test_export_missing_clip_fails_without_output(fresh_user_dir, no_wavespeed):
    spec = {"width": 64, "height": 48, "fps": 24, "format": "mp4", "duration": 1,
            "video": [{"src": "gone.mp4 [input]", "start": 0, "duration": 1, "offset": 0}], "audio": [], "overlays": []}
    with pytest.raises(FileNotFoundError):
        Timeline().render(json.dumps(spec), "comfyart/edit")
    assert not list(fresh_user_dir.rglob("edit*.mp4"))
