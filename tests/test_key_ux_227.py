"""#227: Key UX fixes from the bb9d6c5 walk (mock, $0)."""
import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
node = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
                          reason="needs node + npm install")
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())


# 1. no-Key error follows the UI language
def test_no_key_error_follows_lang():
    from ComfyArt.api.providers import no_key_error
    en, zh = no_key_error("en"), no_key_error("zh")
    assert en == "No WaveSpeed key yet: set one in WaveSpeed key settings."
    assert not any("\u4e00" <= c <= "\u9fff" for c in en)
    assert zh.startswith("还没有设置 WaveSpeed Key") and "No WaveSpeed" not in zh
    assert "/" in no_key_error("")  # unknown language keeps both


def test_send_uses_turn_lang(monkeypatch):
    import ComfyArt.api.providers as prov
    from ComfyArt.bot.providers import TurnRequest
    p = prov.AgentLlmProvider(base_url=lambda: "https://llm.wavespeed.ai/v1")
    monkeypatch.setattr(prov, "llm_api_key", lambda base: "")
    for lang in ("en", "zh"):
        r = asyncio.run(p.send(TurnRequest(chat_id="c", user_text="hi", lang=lang), lambda e: None, None))
        assert r.error == prov.NO_KEY_ERROR[lang]


# 2. Key dialog copy + auto-close
def test_key_dialog_copy():
    assert ZH["wsKey.placeholder"] == "粘贴 WaveSpeed Key"
    assert EN["wsKey.placeholder"] == "Paste your WaveSpeed key"
    assert ZH["wsKey.confirmUsd"].replace("{0}", "X") == "单次费用达到 $X 时先确认（0 = 每次都确认）"
    assert EN["wsKey.confirmUsd"].replace("{0}", "X") == "Ask before jobs costing $X or more (0 = always)"
    src = (ROOT / "src/ui/KeySettings.tsx").read_text()
    assert 'placeholder="ws-' not in src and "t('wsKey.placeholder')" in src
    assert "setDraft(''); close()" in src  # closes only in the success branch of saveKey


# 3. cancelled tool row
def test_cancelled_copy():
    assert ZH["chatMessage.cancelled"] == "已取消" and EN["chatMessage.cancelled"] == "Cancelled"
    for f in ("src/ui/ChatMessage.tsx", "src/ui/TaskDetails.tsx"):
        assert "t('chatMessage.cancelled')" in (ROOT / f).read_text()


@node
def test_step_state(tmp_path):
    out = tmp_path / "s.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "step_state.ts"})
    got = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    assert got == ["running", "done", "error", "cancelled", "cancelled", "cancelled"]


# 4. failed turn does not name the chat / board
def test_failed_turn_does_not_set_title():
    src = (ROOT / "api/bot_turns.py").read_text()
    assert 'if status == "done" and not (chat.get("title") or "").strip():' in src
