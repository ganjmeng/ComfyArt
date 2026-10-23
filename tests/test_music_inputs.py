"""#119: agent bpm/language/key reach the WaveSpeed inputs only for ACE-Step (src/music.ts under node)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    out = tmp_path_factory.mktemp("music") / "music.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "music_inputs.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_minimax_is_default_and_gets_no_ace_settings(result):
    assert result["models"][0] == "minimax/music-3.0"
    assert result["minimax"]["model"] == "minimax/music-3.0" and "music" not in result["minimax"]


def test_ace_step_gets_bpm_language_key(result):
    assert result["ace"]["music"] == {"bpm": 90, "language": "en", "key": "F minor"}
