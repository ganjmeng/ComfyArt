"""#974 assertions superseded by #911 actual Lovart run (2026-11-16).

Keep the original four contract-test categories, now checking removal of the
false fixed 4 x 3:4 lock. Executable stage/order/mock relay coverage lives in
 test_multi_angle_stages_911.py. No paid API or browser.
"""
from __future__ import annotations

import re
from pathlib import Path

from ComfyArt.bot.skill_output import OUTPUTS, accepted_image_counts, apply_generate, resolve, run_hint, single_image_skip

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
SID = "universal-multi-angle-grid"


def _instr(sid: str) -> str:
    m = re.search(rf"\{{ id: '{sid}'.*?instructions: '(.*?)',\n", SKILLS, re.S)
    assert m, sid
    return m.group(1)


def test_python_and_ts_output_tables_no_longer_lock_four_1536x2048():
    assert SID not in OUTPUTS  # count/size belong to answered stages, not a flat row
    assert all(resolve(name) == SID for name in (SID, "多角度图像生成器", "Multi-Angle Image Generator"))
    block = re.search(r"export const SKILL_OUTPUT[\s\S]*?\n\}", SKILLS).group(0)
    assert f"'{SID}':" not in block
    assert accepted_image_counts(SID) is None


def test_apply_generate_defers_stage_pixels_but_keeps_one_per_call():
    args = apply_generate({"skill": SID, "ratio": "1:1", "count": 4, "multi_angle_stage": "final", "composition_id": "2"})
    assert args["count"] == 1 and args["ratio"] == "1:1"
    assert args["multi_angle_stage"] == "final" and args["composition_id"] == "2"
    assert "width" not in args and "height" not in args
    for generated in range(1, 10):
        assert single_image_skip("generate_image", SID, "zh", generated) is None


def test_run_hint_uses_numbered_preview_then_answered_selected_finals():
    hint = run_hint("Multi-Angle Image Generator")
    assert "ONE numbered nine-panel lineart preview" in hint
    assert "ask_user" in hint and "composition_id" in hint and "WAIT for the answer" in hint
    assert "No fixed output count" in hint and "chosen final aspect" in hint
    assert "exactly 4" not in hint and "Never merge the angles" not in hint


def test_instruction_describes_stages_reference_retention_and_no_old_lock():
    text = _instr(SID)
    assert "nine-panel lineart preview" in text
    assert "nine-grid at 1152×2048 / 9:16" in text
    assert "panels:[{id,name,description,geometry,appearance,content} x9]" in text
    assert "English prompt prose is not a composition_plan" in text
    assert 'multi_angle_stage="preview"' in text and 'multi_angle_stage="final"' in text
    assert "Do not generate final images before that answer" in text
    assert "Preserve reference, user description and selected final aspect" in text
    assert "Reuse an attached reference" in text
    assert "If none is uploaded, use the subject described in the Additional notes or ask for one" in text
    assert "exactly four" not in text and "1536×2048" not in text
    assert "Then generate selected finals only" in text


def test_built_skill_read_is_nine_grid_not_four_3x4_images():
    """skill action=read returns the bundled instructions. A stale dist must not ship the old copy."""
    blobs = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "dist/assets").glob("*.js"))
    match = re.search(
        r"id:`universal-multi-angle-grid`,name:[^,]+,instructions:`(.*?)`,category:",
        blobs,
        re.S,
    )
    assert match, "shipped bundle has no universal-multi-angle-grid instructions"
    text = match.group(1)
    assert "exactly four separate images" not in text
    assert "exactly four" not in text and "1536×2048" not in text
    assert "nine-grid at 1152×2048 / 9:16" in text
    assert "composition_plan" in text and "content" in text
    assert "selected finals" in text
