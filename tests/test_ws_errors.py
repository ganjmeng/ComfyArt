"""#155: WaveSpeed failures show readable zh/en messages: insufficient balance names the top-up link and says nothing
was charged; 1200 / 429 / other errors never show the raw WaveSpeed text. Mock only, no WaveSpeed calls."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")
TOP_UP = "https://wavespeed.ai/top-up"


@pytest.fixture(scope="module")
def js(tmp_path_factory):
    out = tmp_path_factory.mktemp("wserr") / "wserr.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "ws_errors.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_insufficient_credit_zh_en(js):
    zh, en = js["zh"]["kinds"]["insufficientCredit"], js["en"]["kinds"]["insufficientCredit"]
    assert "余额不足" in zh and "本次未扣费" in zh and TOP_UP in zh
    assert "balance is too low" in en and "Nothing was charged" in en and TOP_UP in en


@pytest.mark.parametrize("kind", ["moderation", "rateLimit", "invalidKey", "network", "failed"])
def test_other_kinds_readable(js, kind):
    zh, en = js["zh"]["kinds"][kind], js["en"]["kinds"][kind]
    assert zh and en and zh != en and "wsErr." not in zh + en
    assert not any(c in zh + en for c in ("{", "(", "1200", "429", "500"))


def test_raw_text_never_shown(js):
    for lang in ("zh", "en"):
        assert "Internal Error xyz" not in js[lang]["raw"] and js[lang]["raw"] == js[lang]["kinds"]["failed"]
        assert js[lang]["untagged"] == "mask file not found"  # ComfyArt's own validation messages pass through
        assert js[lang]["plain"] == "src must be a /api/view URL"
        assert js[lang]["unknown"] is None


def test_old_comfyui_copy_cleaned():
    # #30: Local LLM and LM Studio stay; only the "before starting ComfyUI" leftover goes
    for f, old in (("en.json", "before starting ComfyUI"), ("zh.json", "在启动 ComfyUI 前")):
        text = json.loads((ROOT / "src/locales" / f).read_text())["botSettings.claudeCodeCodexQwenCode"]
        assert old not in text and "Local LLM" in text and "COMFYART_LOCAL_LLM_API_KEY" in text


def test_agent_relays_our_copy_verbatim(js):
    # follow-up: the agent's tool result carries our zh/en copy as user_message plus a do-not-paraphrase note
    for lang in ("zh", "en"):
        copy = js[lang]["kinds"]["insufficientCredit"]
        a = js[lang]["agent"]
        assert a["user_message"] == a["error"] == copy and "paraphrase" in a["note"] and "word for word" in a["note"]
        assert js[lang]["agentThrown"].startswith(copy) and "do not paraphrase" in js[lang]["agentThrown"]


def test_bot_commands_use_agent_error():
    src = (ROOT / "src/botCommands.ts").read_text()
    assert "...agentError(r.error)" in src and src.count("agentErrorText(err)") == 2
