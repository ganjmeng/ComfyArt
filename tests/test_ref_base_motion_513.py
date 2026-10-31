"""#513 step1 / #528: custom generate refs/base + motion + lipsync — tag, swap, markers.

Mocks only ($0). Mutations must go red if tags, @base/@strength, or motion/lipsync actions are removed."""
import json
import os
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
    out = tmp_path_factory.mktemp("r513") / "tags.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "ref_base_motion_513.ts"},
    )
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@pytest.fixture(scope="module")
def sent(tmp_path_factory):
    out = tmp_path_factory.mktemp("r513p") / "payload.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "ref_base_motion_513_payload.ts"},
    )
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_step1_inputs_always_tag_custom_action(result):
    assert result["motion"]["custom"] == "motion" and result["motion"]["feature"] == "motion_control"
    assert result["lipsync"]["custom"] == "lipsync" and result["lipsync"]["feature"] == "lip_sync"
    assert result["generatePlain"]["custom"] == "generate" and result["generatePlain"]["model"] == "custom:generate"
    assert result["generateRefs"]["image"] and result["generateRefs"]["image2"]
    assert result["generateBase"]["base"] and result["generateBase"]["strength"] == 0.65
    assert result["hasMotion"] and result["hasLipsync"]
    for m in ("image", "image2", "base", "strength"):
        assert m in result["generateOptional"]
    for m in ("base", "strength"):
        assert m in result["markerIds"]


@needs_node
def test_qa_no_custom_drops_tag_and_keeps_builtin_path(sent):
    assert sent["motion"] == {
        "feature": "motion_control", "image": "c.png [input]", "video": "m.mp4 [input]", "prompt": "move",
    }
    assert sent["lipsync"]["feature"] == "lip_sync" and "custom" not in sent["lipsync"]
    assert "no longer" in (sent["generateGone"] or "").lower() or "不在" in (sent["generateGone"] or "")


@needs_node
def test_qa_custom_motion_lipsync_generate_swap(sent):
    m = sent["customMotion"]
    assert m["model"] == "acme/custom-motion" and m["custom"] is True
    assert m["feature"] == "motion_control" and m["fields"]["@video"] == "video"
    lip = sent["customLipsync"]
    assert lip["model"] == "acme/custom-lipsync" and lip["custom"] is True and lip["feature"] == "lip_sync"
    g = sent["customGenerate"]
    assert g["model"] == "acme/custom-gen" and g["custom"] is True and g["image"] == "a.png [input]"
    gb = sent["customGenerateBase"]
    assert gb["base"] == "b.png [input]" and gb["strength"] == 0.5 and gb["fields"]["@base"] == "image"
    assert "needs" in sent["needsVideo"].lower() or "需要" in sent["needsVideo"]
    assert "needs" in sent["needsAudio"].lower() or "需要" in sent["needsAudio"]
    assert "needs" in sent["needsImage"].lower() or "需要" in sent["needsImage"]
    assert "@base" in sent["unusedBase"] or "base" in sent["unusedBase"].lower()


def _markers():
    return (ROOT / "src/customMarkers.ts").read_text(encoding="utf-8")


def _generate():
    return (ROOT / "src/generate.ts").read_text(encoding="utf-8")


def _models():
    return (ROOT / "src/models.ts").read_text(encoding="utf-8")


def _ref_modes():
    return (ROOT / "src/refModes.ts").read_text(encoding="utf-8")


def _panel():
    return (ROOT / "src/ui/GenPanel.tsx").read_text(encoding="utf-8")


def _wavespeed():
    return (ROOT / "api/wavespeed.py").read_text(encoding="utf-8")


def test_mutation_markers_include_base_strength_motion_lipsync():
    text = _markers()
    assert "id: 'motion'" in text and "id: 'lipsync'" in text
    assert "'base'" in text and "'strength'" in text
    assert "feature: 'motion_control'" in text and "feature: 'lip_sync'" in text


def test_mutation_generate_tags_motion_lipsync_and_passes_refs_base():
    text = _generate()
    assert "custom: 'motion'" in text and "custom: 'lipsync'" in text
    assert "base: start ? annotated(start.src)" in text
    assert "strength: start ? start.strength / 100" in text
    assert "model.id !== CUSTOM_GENERATE" in text  # palette skip


def test_mutation_custom_model_refs_cap_two_first_mode_only():
    assert "refs: 'custom'" in _models()
    rm = _ref_modes()
    assert "CUSTOM_IMAGES = 2" in rm
    assert "model.refs === 'custom'" in rm
    assert "REF_MODES.slice(0, 1)" in rm


def test_mutation_gen_panel_allows_base_for_custom_generate():
    panel = _panel()
    assert "CUSTOM_GENERATE" not in panel or "model.id !== CUSTOM_GENERATE" not in panel
    assert "genPanel.baseImage" in panel


def test_mutation_backend_accepts_base_strength_markers():
    text = _wavespeed()
    assert '"base"' in text and '"strength"' in text
    assert 'inputs.get("base")' in text and 'inputs.get("strength")' in text
