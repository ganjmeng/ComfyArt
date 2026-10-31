"""#509: YuE2 joins the music models; the length slider follows each model's WaveSpeed schema; per-tab dialog state.

src/music.ts runs under node (same harness as test_music_inputs.py); AudioDialog's per-tab text is checked in source
because the dialog is a React component with no DOM harness here."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")
YUE2 = "wavespeed-ai/yue2-3b/text-to-music"


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    out = tmp_path_factory.mktemp("music509") / "music.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "music_509.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_yue2_is_a_third_built_in_model_and_custom_music_joins_the_picker(result):
    # port of upstream test_workflows.py: every music model takes lyrics + seed (YuE2 added to the accepted set)
    assert result["builtIn"] == ["minimax/music-3.0", "wavespeed-ai/ace-step-1.5", YUE2]
    assert result["picker"] == result["builtIn"] + ["custom:music"]


@needs_node
def test_slider_range_comes_from_the_schema(result):
    assert result["before"] is None  # no catalog yet: no invented 360/1000/900 limits
    assert result["range"]["ace"] == {"min": 5, "max": 240, "step": 1, "default": 60}
    assert result["range"]["custom"] == {"min": 10, "max": 600, "step": 10}
    assert result["clamp"] == {"aceHigh": 240, "aceLow": 5, "custom": 30, "yue2": 600}
    assert result["inputs"]["ace"]["duration"] == 240


@needs_node
def test_slider_hidden_for_yue2_and_minimax(result):
    assert result["range"]["yue2"] is None and result["range"]["minimax"] is None
    assert "duration" not in result["inputs"]["yue2"] and "duration" not in result["inputs"]["minimax"]


@needs_node
def test_yue2_field_mapping(result):
    y = result["inputs"]["yue2"]
    assert y == {"feature": "music", "model": YUE2, "prompt": "lofi", "lyrics": "[verse] 你好\n[chorus] 再见", "seed": 7}
    assert result["inputs"]["yue2Empty"]["lyrics"] == "[instrumental]"
    assert result["inputs"]["custom"]["custom"] == "music" and result["inputs"]["custom"]["duration"] == 600


def _dialog():
    return (ROOT / "src/ui/AudioDialog.tsx").read_text(encoding="utf-8")


def test_audio_dialog_slider_or_lyrics_note():
    src = _dialog()
    # slider bounds come from musicDuration(); no hard-coded upstream limits or fixed tiers
    assert re.search(r"type=\"range\" min=\{range\.min\} max=\{range\.max\} step=\{range\.step\}", src)
    assert "MUSIC_SECONDS" not in src and "maxSeconds" not in src
    assert re.search(r"range \? \(.*?type=\"range\".*?\) : \(.*?t\('audio\.durationByLyrics'\)", src, re.S)
    zh = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))
    assert zh["audio.durationByLyrics"] == "时长由歌词决定" and en["audio.durationByLyrics"] == "Length follows the lyrics"


def test_audio_dialog_keeps_text_per_tab_and_separate_sfx_length():
    src = _dialog()
    assert "useState<Record<Tab, string>>({ music: '', speech: '', sfx: '' })" in src
    assert "const prompt = prompts[tab]" in src
    assert "setPrompts({ ...prompts, [tab]: e.target.value })" in src
    assert "useState(8)" in src and "seconds: sfxSeconds" in src
    # switching tabs only switches the tab: no reset of text or length
    assert "onPick={setTab}" in src


# ---- #509 PR1 QA acceptance: what is actually handed to the WaveSpeed hook (wsBuilt -> withCustomModel) ----
@pytest.fixture(scope="module")
def sent(tmp_path_factory):
    out = tmp_path_factory.mktemp("music509p") / "payload.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "music_509_payload.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


ACE = "wavespeed-ai/ace-step-1.5"


@needs_node
def test_qa_ace_step_241_and_3_are_clamped_in_the_sent_inputs(sent):
    assert sent["ace241"] == {"feature": "music", "model": ACE, "prompt": "lofi", "lyrics": "[instrumental]", "duration": 240}
    assert sent["ace3"] == {"feature": "music", "model": ACE, "prompt": "lofi", "lyrics": "[instrumental]", "duration": 5}


@needs_node
def test_qa_minimax_and_yue2_send_no_duration(sent):
    for k in ("minimax", "yue2", "yue2NoLyrics"):
        assert "duration" not in sent[k] and "music_length_ms" not in sent[k], (k, sent[k])
    assert sent["minimax"] == {"feature": "music", "model": "minimax/music-3.0", "prompt": "pop", "lyrics": "[instrumental]"}


@needs_node
def test_qa_yue2_style_always_sent_and_empty_prompt_blocked_before_any_request(sent):
    assert sent["yue2"] == {"feature": "music", "model": YUE2, "prompt": "mandarin pop", "lyrics": "[verse] 你好"}
    # empty lyrics: upstream behaviour kept (product to confirm); flipping BLOCK_EMPTY_LYRICS in src/music.ts blocks instead
    assert sent["blockEmptyLyrics"] is False and sent["missing"] == {"empty": "prompt", "noLyrics": None}
    assert sent["yue2NoLyrics"]["lyrics"] == "[instrumental]" and sent["yue2NoLyrics"]["prompt"] == "mandarin pop"
    assert sent["yue2EmptyPrompt"] == sent["aceEmptyPrompt"] == "Describe the music style first"
    assert sent["fetchesDuringJobs"] == 0  # refused before any request (so before any charge)
    src = _dialog()
    assert "musicMissing({ prompt, lyrics })" in src and "disabled={tab === 'music' ? !!musicMissing({ prompt, lyrics })" in src
    assert "musicMissing({ prompt: String(args.prompt ?? ''), lyrics: String(args.lyrics ?? '') })" in (ROOT / "src/botCommands.ts").read_text(encoding="utf-8")
    assert "wsBuilt(musicJobInputs(spec))" in (ROOT / "src/assetGen.ts").read_text(encoding="utf-8")


@needs_node
def test_qa_custom_music_uses_main_custom_path_and_falls_back_without_it(sent):
    c = sent["custom"]
    assert c == {"feature": "music", "model": "acme/custom-music", "prompt": "lofi", "lyrics": "[verse] la", "duration": 30,
                 "custom": True, "fields": {"@lyrics": "lyrics"}, "params": {"seed": 3}}
    # a built-in model with a custom file assigned stays on the default WaveSpeed path (tag dropped, no fields)
    assert sent["builtInWithCustomAssigned"] == sent["ace241"]
    # custom picked but its file is gone: refused, not silently sent to a default
    assert "no longer" in sent["customGone"]


def test_qa_minimax_fixed_tiers_removed():
    for f in ("src/assetGen.ts", "src/music.ts", "src/ui/AudioDialog.tsx", "src/botCommands.ts"):
        assert "MUSIC_SECONDS" not in (ROOT / f).read_text(encoding="utf-8"), f


def test_qa_note_reuses_hint_class_in_a_fixed_height_shared_row():
    src = _dialog()
    row = re.search(r'<div className="ca-audio__length" data-testid="music-length-row">(.*?)\n          </div>', src, re.S)
    assert row and 'type="range"' in row.group(1) and 'data-testid="music-duration-note"' in row.group(1)
    assert '<span className="ca-chat__hint">{t(\'audio.durationByLyrics\')}</span>' in row.group(1)
    assert "ca-audio__note" not in src  # no new text style
    css = (ROOT / "src/styles/overlays.css").read_text(encoding="utf-8")
    assert re.search(r"\.ca-audio__length \{[^}]*min-height: 32px", css)
    assert ".ca-chat__hint { font-size: 12px; }" in (ROOT / "src/styles/shell.css").read_text(encoding="utf-8")


def test_music_length_ms_is_clamped_into_the_schema_range():
    # #509: models that take music_length_ms get the length clamped to the schema's range (ms), not seconds * 1000 raw
    from ComfyArt.api import wavespeed
    props = {"music_length_ms": {"type": "integer", "minimum": 5000, "maximum": 240000}}
    for seconds, want in ((1000, 240000), (2, 5000), (30, 30000)):
        payload: dict = {}
        wavespeed._av_fields(props, set(), {"duration": seconds}, payload)
        assert payload == {"music_length_ms": want}, (seconds, payload)


def test_custom_music_lyrics_marker_reaches_the_request():
    # #509: a custom music workflow maps @lyrics onto the user's model field, like @prompt
    import asyncio
    from ComfyArt.api import wavespeed
    assert "lyrics" in wavespeed.MARKER_INPUTS
    payload: dict = {}
    asyncio.run(wavespeed._custom_fields(None, {"prompt": "lofi", "lyrics": "[verse] hi", "fields": {"@prompt": "style", "@lyrics": "words"}}, payload))
    assert payload == {"style": "lofi", "words": "[verse] hi"}


def test_yue2_listed_for_the_agent_music_models():
    # #509: YuE2 sits in curated music "more" (the curated top list is capped at 5), so list_models still offers it
    from ComfyArt.api import wavespeed
    assert YUE2 in [m["id"] for m in wavespeed.load_config()["features"]["music"]["models"]]
