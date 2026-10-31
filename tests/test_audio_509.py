"""#509 PR2: custom speech / clone / sfx workflows — tag, swap, @audio/@prompt mapping, dialog voice list.

Mocks only ($0). Mutations must go red if the tag, voice drop, or @audio mapping is removed."""
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
    out = tmp_path_factory.mktemp("audio509") / "audio.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "audio_509.ts"},
    )
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@pytest.fixture(scope="module")
def sent(tmp_path_factory):
    out = tmp_path_factory.mktemp("audio509p") / "payload.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "audio_509_payload.ts"},
    )
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_audio_inputs_always_tag_custom_action(result):
    assert result["speechBuiltIn"] == {
        "feature": "text_to_speech", "custom": "speech", "text": "你好", "prompt": "你好", "voice": "Serena",
    }
    assert result["speechCustom"] == {
        "feature": "text_to_speech", "custom": "speech", "text": "你好", "prompt": "你好",
    }
    assert "voice" not in result["speechCustom"]
    assert result["clone"]["custom"] == "clone" and result["clone"]["feature"] == "voice_clone"
    assert result["clone"]["text"] == "克隆一句" and result["clone"]["prompt"] == "克隆一句"
    assert "[input]" in result["clone"]["audio"]
    assert result["sfx"] == {"feature": "sound_effect", "custom": "sfx", "prompt": "whoosh", "duration": 8}
    assert result["customSpeechId"] == "custom:speech"


@needs_node
def test_qa_no_custom_drops_tag_and_keeps_builtin_path(sent):
    assert sent["speech"] == {"feature": "text_to_speech", "text": "hello", "prompt": "hello", "voice": "Serena"}
    assert sent["clone"]["feature"] == "voice_clone" and "custom" not in sent["clone"]
    assert sent["sfx"] == {"feature": "sound_effect", "prompt": "boom", "duration": 5}
    assert "no longer" in sent["speechGone"] or "不在" in sent["speechGone"]


@needs_node
def test_qa_custom_speech_clone_sfx_swap_model(sent):
    assert sent["customSpeech"] == {
        "feature": "text_to_speech", "model": "acme/custom-tts", "text": "hello", "prompt": "hello",
        "custom": True, "fields": {"@prompt": "text"}, "params": {"voice": "Alloy"},
    }
    assert "voice" not in sent["customSpeech"]
    c = sent["customClone"]
    assert c["model"] == "acme/custom-clone" and c["custom"] is True
    assert c["fields"] == {"@audio": "audio", "@prompt": "text"}
    assert c["text"] == "hi" and c["prompt"] == "hi"
    assert sent["customSfx"] == {
        "feature": "sound_effect", "model": "acme/custom-sfx", "prompt": "boom", "duration": 5,
        "custom": True, "fields": {"@prompt": "prompt"}, "params": {"seed": 1},
    }
    assert sent["speechTaggedWithCustomAssigned"]["model"] == "acme/custom-tts"
    assert sent["speechTaggedWithCustomAssigned"]["custom"] is True


def _dialog():
    return (ROOT / "src/ui/AudioDialog.tsx").read_text(encoding="utf-8")


def test_audio_dialog_custom_speech_replaces_voice_list():
    src = _dialog()
    assert "CUSTOM_SPEECH" in src and "workflowConfigAtom" in src
    assert "speechFile" in src and "speechCustom" in src
    assert re.search(r"speechCustom\s*\?\s*\[\s*\{\s*id:\s*CUSTOM_SPEECH", src)
    assert "list.map((v) => ({ id: v, label: v, title: v }))" in src


def test_audio_dialog_clone_option_still_first_when_recording_selected():
    src = _dialog()
    assert "audio.cloneSelected" in src
    assert "reference ? [{ id: CLONE" in src
    assert "voice === CLONE && reference" in src


def test_custom_markers_list_speech_clone_sfx_and_audio():
    src = (ROOT / "src/customMarkers.ts").read_text(encoding="utf-8")
    assert "id: 'speech'" in src and "id: 'clone'" in src and "id: 'sfx'" in src
    assert "id: 'audio'" in src
    assert "feature: 'text_to_speech'" in src
    assert "feature: 'voice_clone'" in src
    assert "feature: 'sound_effect'" in src
    # PR2 only — no video/3d actions in this PR
    assert "videoUpscale" not in src and "model3d" not in src and "id: 'extend'" not in src


def test_builtin_sfx_default_stays_mirelo():
    # product ruling #4: do NOT switch built-in sfx default to elevenlabs
    cfg = json.loads((ROOT / "api/wavespeed_models.json").read_text(encoding="utf-8"))
    feat = cfg["features"]["sound_effect"]
    default = feat.get("default") or feat["models"][0]["id"]
    assert "mirelo" in default
    assert "elevenlabs" not in default


def test_audio_marker_and_prompt_auto_text_in_wavespeed():
    from ComfyArt.api import wavespeed
    assert "audio" in wavespeed.MARKER_INPUTS
    assert "audio" in wavespeed.MEDIA_MARKERS
    assert "text" in wavespeed.AUTO_FIELDS
    # @prompt fills from text when prompt key absent (speech/clone)
    payload: dict = {}
    asyncio.run(wavespeed._custom_fields(
        None,
        {"text": "朗读这句", "audio": "https://example.com/a.wav", "fields": {"@prompt": "text", "@audio": "audio"}},
        payload,
    ))
    assert payload["text"] == "朗读这句"
    assert payload["audio"] == "https://example.com/a.wav"


def test_check_custom_auto_detects_audio_and_text_as_prompt():
    from ComfyArt.api import wavespeed
    # synthetic: model that takes text + audio (+ duration) should auto-require prompt+audio and optional seconds
    meta = {
        "acme/tts-audio": {
            "api_schema": {
                "api_schemas": {
                    "https://api.wavespeed.ai/api/v3/acme/tts-audio": {
                        "request_schema": {
                            "properties": {
                                "text": {"type": "string"},
                                "audio": {"type": "string", "format": "uri"},
                                "duration": {"type": "number"},
                            },
                            "required": ["text", "audio"],
                        }
                    }
                }
            }
        }
    }
    # use internal helper if exposed; else inspect auto via check path
    # wavespeed has logic in check that builds auto — call the same block via inspect of source invariants
    src = (ROOT / "api/wavespeed.py").read_text(encoding="utf-8")
    assert '"audio": "audio" in props' in src
    assert '{"prompt", "tags", "style", "text"}' in src or "{'prompt', 'tags', 'style', 'text'}" in src


def test_locale_keys_for_speech_clone_sfx():
    for lang, speech, clone, sfx in (
        ("en", "Voiceover", "Voice clone", "Sound effect"),
        ("zh", "配音", "声音克隆", "音效"),
    ):
        data = json.loads((ROOT / f"src/locales/{lang}.json").read_text(encoding="utf-8"))
        assert data["customWorkflows.action.speech"] == speech
        assert data["customWorkflows.action.clone"] == clone
        assert data["customWorkflows.action.sfx"] == sfx
        assert "speechGone" in data["customWorkflows.speechGone"] or "不在" in data["customWorkflows.speechGone"] or "no longer" in data["customWorkflows.speechGone"]


# ---- must-red mutations ----
def test_mutation_removing_custom_tag_goes_red():
    src = (ROOT / "src/assetGen.ts").read_text(encoding="utf-8")
    assert "custom: 'speech'" in src and "custom: 'clone'" in src and "custom: 'sfx'" in src


def test_mutation_custom_speech_must_omit_voice():
    src = (ROOT / "src/assetGen.ts").read_text(encoding="utf-8")
    assert "customSpeech ? {} : { voice: spec.voice }" in src
    # body must keep text+prompt for speech/clone so @prompt auto-fill and explicit fields both work
    assert "text: spec.text, prompt: spec.text" in src


def test_mutation_audio_in_marker_inputs():
    from ComfyArt.api import wavespeed
    assert "audio" in wavespeed.MARKER_INPUTS and "audio" in wavespeed.MEDIA_MARKERS


def test_mutation_js_harness_mirrors_assetgen_audio_inputs():
    # harness copies audioInputs to avoid EmbedShapes dynamic-import chunks; must stay aligned
    src = (ROOT / "src/assetGen.ts").read_text(encoding="utf-8")
    for f in ("tests/js/audio_509.ts", "tests/js/audio_509_payload.ts"):
        h = (ROOT / f).read_text(encoding="utf-8")
        assert "custom: 'sfx'" in h and "custom: 'speech'" in h and "custom: 'clone'" in h
        assert "customSpeech ? {} : { voice: spec.voice }" in h
    assert "export function audioInputs" in src


def test_workflows_dialog_shows_assigned_filename_not_builtin():
    """#525 design HOLD: after assign/upload, FieldSelect value is config[id] (filename), not empty→内置."""
    src = (ROOT / "src/ui/WorkflowsDialog.tsx").read_text(encoding="utf-8")
    assert "value={config[id] ?? ''}" in src
    assert "setFiles((prev)" in src  # optimistic files refresh on upload
