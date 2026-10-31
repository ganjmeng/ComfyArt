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


@needs_node
def test_product_has_six_presets(got):
    assert got["presets"]["product"] == 6 and got["meta"]["product"] == {"templates": 6}
    assert got["productIds"] == ["white", "lifestyle", "detail", "electronics", "food", "beauty"]
    assert all("/688a702a1f322082cde4e5ed46200c3593db9c43/541/wash/product/product__" in u for u in got["productNew"])


R541 = "https://raw.githubusercontent.com/ganjmeng/ComfyArt/{}/541/wash/{}/{}__{}.webp"


@needs_node
def test_rev2_cells_pinned(got):
    """AC rev 2 (6546010130): product 6 (detail @2422dc5), brand 6 @f204502, packaging 5 @1014ef2 (no mockup)."""
    p, b, k = got["imgs"]["product"], got["imgs"]["brand"], got["imgs"]["packaging"]
    for pid in ("white", "lifestyle", "electronics", "food", "beauty"):
        assert p[pid] == R541.format("688a702a1f322082cde4e5ed46200c3593db9c43", "product", "product", pid)
    assert p["detail"] == R541.format("2422dc53d37b8f4437a7f9f7986440d2ea79bbf1", "product", "product", "detail")
    assert list(b) == ["geometric", "handmade", "tech", "beauty", "foodbev", "pet"]
    assert all(u == R541.format("f2045022727c73e24bd6d5ebcb3815bedb7b8797", "brand", "brand", i) for i, u in b.items())
    assert list(k) == ["eco", "gold", "playful", "panels", "shelf"] and "mockup" not in k
    assert all(u == R541.format("1014ef25ad2a8b49cae0c438c673a0b7f9e7797f", "packaging", "packaging", i) for i, u in k.items())
    assert got["presets"]["motion"] == 3 and got["presets"]["poster"] == 3


@needs_node
def test_examples_carousel_is_data_driven(got):
    assert all(n == 0 for n in got["examples"].values())  # design hasn't delivered; no section renders yet
    assert got["exNone"] == ["", ""]
    html = got["exMock"]
    assert 'data-testid="skill-run-examples"' in html and 'data-count="5"' in html
    assert html.count('data-testid="skill-run-example-thumb"') == 5 and html.count('aria-selected="true"') == 1
    assert 'data-testid="skill-run-example-stage"><img src="https://x.test/e1.webp"' in html
    assert "skill-run-example-thumb" not in got["exOne"] and "skill-run-example-stage" in got["exOne"]
    assert ZH["skillRun.examples"] == "效果示例" and EN["skillRun.examples"] == "Examples"
    assert ".ca-skillrun__stage" in CSS and "aspect-ratio: 704 / 526" in CSS and "object-fit: contain" in CSS
    assert "<SkillExamples examples={skill.examples} />" in DLG and "from './SkillExamples'" in DLG
