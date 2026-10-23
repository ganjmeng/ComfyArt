"""#95 TTS voice ruling (mock only, no real API calls): speech-2.8-turbo and eleven-v4 default to the
first preset voice their schema lists; minimax/voice-clone gets no default and stops with
"Please upload a voice sample first" (zh 请先上传样音) before any quote, confirm or charge."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from ComfyArt.api import wavespeed

ROOT = Path(__file__).resolve().parents[1]

# request schemas trimmed from the live WaveSpeed catalog (voice fields kept verbatim in shape)
SPEECH = {"required": ["text", "voice_id"], "properties": {"text": {"type": "string"}, "voice_id": {"type": "string",
          "description": "Desired voice ID. Use a voice ID you have trained (https://wavespeed.ai/models/minimax/voice-clone), or one of the following system voice IDs: Wise_Woman, Friendly_Person, Inspirational_girl, Deep_Voice_Man.",
          "x-suggestions": ["Wise_Woman", "Friendly_Person", "Inspirational_girl"]}}}
ELEVEN = {"required": ["text", "voice_id"], "properties": {"text": {"type": "string"}, "voice_id": {"type": "string", "default": "Alicia", "minLength": 1,
          "x-suggestions": ["Alicia", "Aria", "Roger"]}, "stability": {"type": "number"}}}
CLONE = {"required": ["audio", "custom_voice_id", "model"], "properties": {"audio": {"type": "string"}, "custom_voice_id": {"type": "string"}, "text": {"type": "string"},
         "model": {"type": "string", "enum": ["speech-02-hd", "speech-2.8-turbo"]}}}


def _payload(schema, inputs):
    return asyncio.run(wavespeed.build_payload(None, schema, inputs))


def test_speech_28_turbo_defaults_to_first_listed_voice():
    assert _payload(SPEECH, {"text": "你好"}) == {"text": "你好", "voice_id": "Wise_Woman"}
    # description-only schema (no x-suggestions) still yields the first listed system voice
    bare = {**SPEECH, "properties": {**SPEECH["properties"], "voice_id": {"type": "string", "description": SPEECH["properties"]["voice_id"]["description"]}}}
    assert _payload(bare, {"text": "hi"})["voice_id"] == "Wise_Woman"
    # the user's choice wins
    assert _payload(SPEECH, {"text": "hi", "voice": "Calm_Woman"})["voice_id"] == "Calm_Woman"


def test_eleven_v4_defaults_to_first_voice_and_user_can_change():
    assert _payload(ELEVEN, {"text": "hello"}) == {"text": "hello", "voice_id": "Alicia"}
    assert _payload(ELEVEN, {"text": "hello", "voice": "Roger"})["voice_id"] == "Roger"


def test_voice_clone_has_no_default_and_asks_for_sample_before_any_charge(monkeypatch):
    meta = {"model_id": "minimax/voice-clone", "base_price": 1.6, "api_schema": {"api_schemas": [{"request_schema": CLONE}]}}

    async def cat(refresh=False):
        return {"minimax/voice-clone": meta}

    async def no_quote(*a, **k):
        raise AssertionError("quoted before the sample check")

    monkeypatch.setattr(wavespeed, "catalog", cat)
    monkeypatch.setattr(wavespeed, "quote", no_quote)
    monkeypatch.setattr(wavespeed, "resolve_model", lambda feature, picked: "minimax/voice-clone")
    monkeypatch.setattr(wavespeed, "_check_limits", lambda: None)
    wavespeed._submits.clear()
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        asyncio.run(wavespeed.submit({"feature": "voice_clone", "model": "minimax/voice-clone", "text": "你好"}))
    assert e.value.status == 400 and str(e.value) == "Please upload a voice sample first"
    assert "needs" not in str(e.value) and wavespeed._submits == []  # not a parameter error, nothing submitted
    # no default voice is invented for voice-clone; with a sample it names the clone and picks a model
    assert wavespeed.needs_voice_sample("minimax/voice-clone", "voice_clone", CLONE, {"text": "x"})
    assert not wavespeed.needs_voice_sample("minimax/voice-clone", "voice_clone", CLONE, {"audio": "a.mp3"})
    out = asyncio.run(_with_audio(CLONE))
    assert "voice_id" not in out and out["custom_voice_id"].startswith("ComfyArt") and out["model"] == "speech-02-hd"


async def _with_audio(schema):
    payload = {"audio": "https://cdn.test/a.mp3"}
    wavespeed._av_fields(schema["properties"], set(schema["required"]), {}, payload)
    return payload


def test_voice_sample_message_is_localized():
    zh = json.loads((ROOT / "src/locales/zh.json").read_text())
    en = json.loads((ROOT / "src/locales/en.json").read_text())
    assert zh["jobs.needVoiceSample"] == "请先上传样音"
    assert en["jobs.needVoiceSample"] == "Please upload a voice sample first"
    assert "Please upload a voice sample first/.test(msg)) return t('jobs.needVoiceSample')" in (ROOT / "src/jobs.ts").read_text()
