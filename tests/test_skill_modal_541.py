"""#541: skill modal to Lovart's measurements (no media wall). Real-data meta line via src/skills.ts + wiring greps."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()
BASE = (ROOT / "src/styles/base.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())
needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m541") / "skill_modal_541.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "skill_modal_541.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_meta_is_template_count_only(got):
    for sid, n in got["presets"].items():
        assert got["meta"][sid] == ({"templates": n} if n else None), sid
    assert got["meta"]["custom-workflow"] is None and got["old"] is None


def test_meta_copy_has_no_fake_usage():
    assert ZH["skillRun.templateCount"] == "{0} 个模板" and EN["skillRun.templateCount"] == "{0} templates"
    assert "已使用" not in DLG and "skillRun.used" not in DLG
    assert "skillMeta(skill)" in DLG and "skill-run-meta" in DLG


def test_lovart_sizes_and_theme_vars():
    assert "width: min(1112px, calc(100vw - 32px))" in CSS and "height: min(820px" in CSS
    assert "flex: 1 1 752px" in CSS and "flex: 0 0 360px" in CSS
    assert "background: var(--ca-skillrun-side)" in CSS and "#f5f5f5" not in CSS
    assert BASE.count("--ca-skillrun-side:") == 2 and BASE.count("--ca-skillrun-tile:") == 2  # light + dark
    assert "object-fit: contain" in CSS and "aspect-ratio: 160 / 120" in CSS  # 344×258 well
    assert "width: 22px; height: 22px" in CSS  # zoom
    assert "height: 86px" in CSS and "width: 36px; height: 36px" in CSS  # current card + thumb
    assert "1px dashed" in CSS and "height: 108px" in CSS  # upload
    assert "margin-top: auto" in CSS  # pinned submit
    assert ".ca-skillrun__preset[data-on]::after" in CSS  # ring wraps whole tile
    assert ".ca-skillrun__preset[data-on] .ca-skillrun__presetimg" not in CSS


def test_tiles_from_presets_and_zoom_is_sibling_button():
    assert "skill.presets" in DLG and not re.search(r"\.slice\(0,\s*6\)", DLG)
    assert 'data-testid="skill-run-zoom"' in DLG and 'data-testid="skill-run-zoomview"' in DLG
    tile = DLG[DLG.index('className="ca-skillrun__tile"'):DLG.index('data-testid="skill-run-zoom"')]
    assert tile.count("</button>") == 1  # zoom is not nested inside the radio button
    for k in ("skillRun.zoom", "skillRun.uploadHint", "skillRun.templateCount"):
        assert k in ZH and k in EN
