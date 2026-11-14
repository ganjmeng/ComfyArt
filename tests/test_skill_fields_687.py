"""#687 unit — each Phase1 card's dialog field structure == the hard-coded Lovart spec (tests/lovart_fields_687.py).
Runs src/skills.ts through tests/js/fields_687.ts; $0, no network. Skips without node_modules (gate) — the e2e covers it there."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.lovart_fields_687 import MOTION_DESC, MOTION_FEATURED_806, MOTION_FEATURED_REMOVED, OURS_PH, PRODUCT_OPTIONAL_748, RAW_748, REF12, SPEC

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(
    not shutil.which("node") or not (ROOT / "node_modules/.bin/rolldown").exists(), reason="needs node + rolldown")


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("f687") / "fields_687.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "fields_687.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def rows(fields: list[dict]) -> list[tuple]:
    return [(f["key"], f["type"], f["required"], f["accept"], f["maxLength"], f["zh"], f["en"], f["phEn"]) for f in fields]


@needs_node
@pytest.mark.parametrize("sid", sorted(SPEC))
def test_dialog_fields_match_lovart_spec_687(got, sid):
    assert rows(got[sid]["fields"]) == SPEC[sid], sid


@needs_node
def test_multi_angle_upload_additional_optional_974(got):
    """#974 / #693: the raw 748 dump marks user_image + user_requirement required; applyRaw748 must
    keep the product-signed optional form. The guard names exactly the raw keys, so a raw key rename
    cannot silently re-block the dialog either."""
    raw_keys = {q["key"] for q in RAW_748["universal-multi-angle-grid"]["inputs"]}
    assert raw_keys == {"user_image", "user_requirement"}
    assert set(PRODUCT_OPTIONAL_748["universal-multi-angle-grid"]) == raw_keys
    fields = got["universal-multi-angle-grid"]["fields"]
    assert [f["key"] for f in fields] == ["user_image", "user_requirement"]
    assert not any(f["required"] for f in fields), fields


@needs_node
def test_motion_poster_templates_and_featured_806(got):
    m = got["motion-poster-generator"]
    # #806: 动态海报 keeps the two raw templates; featured is those stills, not the remake-era 580 drop.
    assert m["presets"] == 2
    assert m["presetFields"] == [
        {"zh": "海报动效", "keys": ["source_image", "motion_brief", "visual_direction"], "required": ["source_image"]},
        {"zh": "首尾帧动画", "keys": ["source_image", "start_frame", "motion_brief", "visual_direction"], "required": ["source_image"]},
    ]
    assert m["featured"] == MOTION_FEATURED_806
    assert not any(MOTION_FEATURED_REMOVED in u for u in m["featured"])


@needs_node
def test_ref12_zh_placeholder_exact_687(got):
    assert len(REF12) == 11  # #748 Final: 11 example cards (logo-material-explorer raw ready)
    for sid in REF12:  # #751 HOLD: our filled zh placeholder (COPY-REWRITE.md → copy-748.json), never a reference string
        q = RAW_748[sid]["inputs"][1]
        assert got[sid]["fields"][1]["phZh"] == OURS_PH(sid)[q["key"]]["zh"], sid


def test_typo_uploaded_file_are_uploaded_fixed_687():
    """No skill copy (src/skills.ts + every locale skills.* string) may contain the substring 'uploaded file'."""
    import json
    assert "uploaded file" not in (ROOT / "src/skills.ts").read_text().lower()
    for f in (ROOT / "src/locales").glob("*.json"):
        assert "uploaded file" not in json.dumps(json.loads(f.read_text()).get("skills", {}), ensure_ascii=False).lower(), f.name

def test_motion_title_desc_poster_806():
    import json
    from tests.lovart_fields_687 import MOTION_TITLE
    src = (ROOT / "src/skills.ts").read_text()
    assert "MOTION_REMAKE_INPUTS_687" not in src and "refVideo" not in src and "remakeBrief" not in src
    # #805 comment mentions a first-frame remake; ignore // and /* */ comments.
    import re as _re
    code = _re.sub(r"/\*[\s\S]*?\*/", "", src)
    code = _re.sub(r"//.*?$", "", code, flags=_re.M)
    assert "remake" not in code.lower() and "重制" not in code
    assert "source_image" in src and "start_frame" in src and "motion_brief" in src and "visual_direction" in src
    for lang in ("zh", "en"):
        loc = json.loads((ROOT / f"src/locales/{lang}.json").read_text())
        assert loc["skills.motionPoster"] == MOTION_TITLE[lang], lang
        desc = loc["skills.desc.motion-poster-generator"]
        assert desc == MOTION_DESC[lang], lang
        assert "remake" not in desc.lower() and "reference video" not in desc.lower() and "参考视频" not in desc
