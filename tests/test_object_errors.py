"""P1: object-shaped `{error: {...}}` bodies showed "[object Object]" (Edit Elements OCR, projects, bot, LLM).
All four fetch sites now go through wsBodyError and show localized zh/en text. Mock only, no network, $0."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")
SITES = ("elements", "projects", "bot", "llm")
OBJECT_BODIES = ("tagged", "untagged", "nested")
WS_FAILED = {"zh": "WaveSpeed 没能完成这次任务，请检查输入后再试。", "en": "WaveSpeed could not finish this job. Check the inputs and try again."}
FALLBACK = {
    "elements": WS_FAILED,
    "projects": {"zh": "请求失败（500），请稍后再试。", "en": "Request failed (500). Please try again."},
    "bot": {"zh": "请求失败（500），请稍后再试。", "en": "Request failed (500). Please try again."},
    "llm": {"zh": "Agent 调用失败：500", "en": "Agent call failed: 500"},
}


@pytest.fixture(scope="module")
def js(tmp_path_factory):
    out = tmp_path_factory.mktemp("objerr") / "objerr.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.objerr.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out)})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("site", SITES)
def test_object_error_never_shows_object_object(js, lang, site):
    for body in OBJECT_BODIES:
        msg = js[lang][site][body]
        assert "[object Object]" not in msg and "{" not in msg and msg.strip()
        assert "Internal Error xyz" not in msg  # raw WaveSpeed text stays hidden


@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("site", SITES)
def test_localized_message(js, lang, site):
    assert js[lang][site]["tagged"] == WS_FAILED[lang]  # tagged WaveSpeed failure -> wsErr copy
    assert js[lang][site]["untagged"] == FALLBACK[site][lang]  # untagged object -> localized fallback
    assert js[lang][site]["nested"] == FALLBACK[site][lang]  # non-string message is not stringified
    assert js[lang][site]["plain"] == "project not found"  # ComfyArt's own string errors pass through
