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
