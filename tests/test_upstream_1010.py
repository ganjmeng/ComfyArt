"""#1010: font-name quoting and library read-modify-write. No network, no provider."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
ROLLDOWN = ROOT / "node_modules" / ".bin" / "rolldown"


@pytest.mark.skipif(not NODE, reason="needs node")
def test_font_names_quote_digits_and_strip_commas():
    got = subprocess.run(
        [NODE, "--experimental-strip-types", "tests/js/font_name_1010.ts"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    body = json.loads(got.stdout)
    assert body["family"]["2Banner"] == '"2Banner"'
    assert body["family"]["Comic Sans MS, cursive"] == '"Comic Sans MS", cursive'
    assert body["family"]["sans-serif"] == "sans-serif"
    assert body["filename"]["Han,SC.ttf"] == "Han SC"
    assert body["filename"]["2Banner.otf"] == "2Banner"
    text = (ROOT / "src/shapes/TextShape.tsx").read_text()
    assert "cssFamily(p.font)" in text
    assert "fontFamily: p.font" not in text
    kit = (ROOT / "src/ui/KitEditor.tsx").read_text()
    assert "fontFamilyFromFilename" in kit
    read = (ROOT / "src/comfy.ts").read_text().split("export async function readUserText", 1)[1].split("export async function readUserJson", 1)[0]
    assert "cache: 'no-store'" in read


@pytest.mark.skipif(not NODE or not ROLLDOWN.is_file(), reason="needs node_modules rolldown")
def test_library_update_keeps_the_other_tabs_save(tmp_path):
    out = tmp_path / "library1010.mjs"
    env = {**os.environ, "ENTRY": "library1010/main.ts", "OUT": str(out)}
    subprocess.run(
        [str(ROLLDOWN), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True, text=True, env=env,
    )
    got = subprocess.run([NODE, str(out)], cwd=ROOT, check=True, capture_output=True, text=True)
    body = json.loads(got.stdout)
    assert body == {"merged": ["Alpha", "Beta"], "draftKept": ["Alpha edited", "Beta"], "broadcasts": 2}


def test_version_stays_on_our_line():
    """Upstream v1.3.1 is not our release line. package.json stayed at 1.0.1 after the 1.0.1 port."""
    assert json.loads((ROOT / "package.json").read_text())["version"] == "1.0.1"
    assert 'version = "1.0.1"' in (ROOT / "pyproject.toml").read_text()
