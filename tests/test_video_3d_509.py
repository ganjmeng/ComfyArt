"""#509 PR3: custom extend / videoUpscale / videoCutout / model3d — tag, swap, @video, toolbar 3rd item.

Mocks only ($0). Mutations must go red if the tag, nearest-up target_resolution, or 3D custom item is removed."""
import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    out = tmp_path_factory.mktemp("v3d509") / "tags.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "video_3d_509.ts"},
    )
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@pytest.fixture(scope="module")
def sent(tmp_path_factory):
    out = tmp_path_factory.mktemp("v3d509p") / "payload.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "video_3d_509_payload.ts"},
    )
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_video_3d_inputs_always_tag_custom_action(result):
    assert result["extend"] == {
        "feature": "extend_video", "custom": "extend", "video": "clip.mp4 [input]",
        "prompt": "Continue the shot naturally.", "duration": 5,
    }
    assert result["videoUpscale"]["custom"] == "videoUpscale"
    assert result["videoUpscale"]["feature"] == "upscale_video"
    assert result["videoUpscale"]["params"]["target_resolution"] == "2k"
    assert result["videoCutout"] == {
        "feature": "remove_video_background", "custom": "videoCutout", "video": "clip.mp4 [input]",
    }
    assert result["model3dBuiltIn"] == {"feature": "image_to_3d", "image": "a.png [input]"}
    assert result["model3dCustom"]["custom"] == "model3d" and result["model3dCustom"]["model"] == "custom:model3d"
    assert result["customModel3dId"] == "custom:model3d"
    assert result["target1080"] == "1080p" and result["target2k"] == "2k" and result["target4k"] == "4k"
    assert result["targetBelow1080"] == "1080p"  # nearest-up floor


@needs_node
def test_qa_no_custom_drops_tag_and_keeps_builtin_path(sent):
    assert sent["extend"] == {
        "feature": "extend_video", "video": "clip.mp4 [input]", "prompt": "go on", "duration": 5,
    }
    assert sent["videoUpscale"]["feature"] == "upscale_video" and "custom" not in sent["videoUpscale"]
    assert sent["videoUpscale"]["params"]["target_resolution"] == "2k"
    assert sent["videoCutout"] == {"feature": "remove_video_background", "video": "clip.mp4 [input]"}
    assert sent["model3dBuiltIn"] == {"feature": "image_to_3d", "image": "a.png [input]"}
    assert "no longer" in sent["model3dGone"] or "不在" in sent["model3dGone"]


@needs_node
def test_qa_custom_extend_upscale_cutout_model3d_swap(sent):
    e = sent["customExtend"]
    assert e["model"] == "acme/custom-extend" and e["custom"] is True
    assert e["fields"] == {"@video": "video", "@prompt": "prompt"}
    assert e["feature"] == "extend_video"
    u = sent["customUpscale"]
    assert u["model"] == "acme/custom-vup" and u["custom"] is True
    assert u["params"]["target_resolution"] == "2k" and u["params"]["seed"] == 1
    assert sent["customCutout"]["model"] == "acme/custom-vcut" and sent["customCutout"]["custom"] is True
    m = sent["customModel3d"]
    assert m["model"] == "acme/custom-3d" and m["custom"] is True and m["feature"] == "image_to_3d"
    assert "needs" in sent["needsVideo"].lower() or "需要" in sent["needsVideo"]


def _actions():
    return (ROOT / "src/actions.ts").read_text(encoding="utf-8")


def _markers():
    return (ROOT / "src/customMarkers.ts").read_text(encoding="utf-8")


def _toolbar():
    return (ROOT / "src/ui/ImageToolbar.tsx").read_text(encoding="utf-8")


def _asset():
    return (ROOT / "src/assetGen.ts").read_text(encoding="utf-8")


def test_actions_always_tag_extend_upscale_cutout():
    src = _actions()
    assert "custom: 'extend'" in src or 'custom: "extend"' in src
    assert "custom: 'videoUpscale'" in src or 'custom: "videoUpscale"' in src
    assert "custom: 'videoCutout'" in src or 'custom: "videoCutout"' in src
    assert "videoTargetResolution" in src
    assert "resizeVideoTo" not in src  # ruling 5: no exact post-scale


def test_markers_video_and_model3d_actions():
    src = _markers()
    assert "id: 'extend'" in src and "id: 'videoUpscale'" in src and "id: 'videoCutout'" in src
    assert "id: 'model3d'" in src and "group: 'model'" in src
    assert "id: 'video'" in src  # @video marker
    assert "does not stitch" in src or "does not stitch or concatenate" in src
    assert "nearest-up target_resolution" in src


def test_image_toolbar_third_3d_item_filename_keeps_trellis_pixal_labels():
    src = _toolbar()
    assert 'label="TRELLIS.2"' in src and 'label="Pixal3D"' in src
    assert "CUSTOM_MODEL3D" in src and "custom3d" in src
    assert "custom3d.replace" in src


def test_asset_gen_custom_model3d_tags_only_when_custom():
    src = _asset()
    assert "CUSTOM_MODEL3D" in src
    assert "custom: 'model3d'" in src or 'custom: "model3d"' in src
    assert "model === CUSTOM_MODEL3D" in src


def test_workflows_dialog_has_model_group():
    src = (ROOT / "src/ui/WorkflowsDialog.tsx").read_text(encoding="utf-8")
    assert "'model'" in src and "GROUPS" in src


def test_bot_commands_image_to_3d_accepts_custom():
    src = (ROOT / "src/botCommands.ts").read_text(encoding="utf-8")
    assert "args.model === 'custom'" in src and "CUSTOM_MODEL3D" in src


def test_wavespeed_backend_accepts_video_marker():
    src = (ROOT / "api/wavespeed.py").read_text(encoding="utf-8")
    assert '"video"' in src.split("MARKER_INPUTS", 1)[1].split("\n", 1)[0] or '"video"' in re.search(r"MARKER_INPUTS = \{[^}]+\}", src).group(0)
    assert re.search(r'MEDIA_MARKERS = \{[^}]*"video"', src)
    assert '"video": inputs.get("video")' in src or "'video': inputs.get('video')" in src


def test_mutation_remove_extend_tag_would_break():
    """Guard: actions must keep custom:'extend' so assigned workflows swap."""
    assert "custom: 'extend'" in _actions() or 'custom: "extend"' in _actions()


def test_mutation_remove_video_marker_would_break():
    assert " | 'video' |" in _markers() or "'video' |" in _markers() or "id: 'video'" in _markers()
