"""#974 — multi-angle default delivery is product-locked: four separate 3:4 1536x2048 images,
one angle per generate_image call, the same uploaded reference on every call.

No provider call. The TS/Python output tables, the skill instruction, the appended run hint and
the per-call size fill are checked here; the Full App mock e2e checks the four real calls and canvas.
"""
from __future__ import annotations

import re
from pathlib import Path

from ComfyArt.bot.skill_output import OUTPUTS, apply_generate, run_hint, single_image_skip

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
SID = "universal-multi-angle-grid"


def _instr(sid: str) -> str:
    m = re.search(rf"\{{ id: '{sid}'.*?instructions: '(.*?)',\n", SKILLS, re.S)
    assert m, sid
    return m.group(1)


def test_python_and_ts_output_tables_lock_four_1536x2048():
    row = OUTPUTS[SID]
    assert (row["width"], row["height"], row["ratio"], row["images"]) == (1536, 2048, "3:4", 4)
    assert SID in row["names"] and "多角度图像生成器" in row["names"] and "Multi-Angle Image Generator" in row["names"]
    block = re.search(r"export const SKILL_OUTPUT[\s\S]*?\n\}", SKILLS).group(0)
    assert "'universal-multi-angle-grid': { width: 1536, height: 2048, ratio: '3:4', images: 4 }" in block


def test_apply_generate_does_not_apply_the_flat_row_or_read_stage_flags():
    # The static 1536×2048 row stays in OUTPUTS. This fill does not consult
    # multi_angle_stage and does not replace a size the server snapshot wrote.
    # A second fill is the same spec. Caller flags are not a size source.
    resolved = {
        "skill": SID, "prompt": "lineart", "width": 1152, "height": 2048,
        "ratio": "9:16", "count": 4,
    }
    preview = apply_generate(dict(resolved))
    again = apply_generate(dict(preview), current_skill=SID)
    forged = apply_generate({**resolved, "multi_angle_stage": "final", "width": 1152, "height": 2048, "ratio": "9:16"})
    size = (1152, 2048, "9:16", 1)
    assert (preview["width"], preview["height"], preview["ratio"], preview["count"]) == size
    assert (again["width"], again["height"], again["ratio"], again["count"]) == size
    assert (forged["width"], forged["height"], forged["ratio"]) == size[:3]
    assert preview.get("width") != OUTPUTS[SID]["width"]
    for generated in (1, 2, 3):
        assert single_image_skip("generate_image", SID, "zh", generated) is None


def test_run_hint_uses_the_staged_preview_not_four_1536_images():
    hint = run_hint("Multi-Angle Image Generator")
    assert "1152x2048 (9:16)" in hint
    assert "not a locked set of four" in hint
    assert "1:1 is 2048x2048, 3:4 is 1536x2048" in hint
    assert "deliver exactly 4 separate images" not in hint
    assert "pose and angle only" not in hint


def test_instruction_states_four_separate_images_fixed_size_and_same_ref():
    text = _instr(SID)
    assert "exactly four separate images" in text
    assert "3:4 / 1536×2048" in text and "never one grid, collage or contact sheet" in text
    assert "generate_image exactly four times" in text and "count=1 each" in text
    assert "same uploaded subject shape id in refs" in text
    # #693 fallback path stays written down: no upload -> Additional subject or ask, never invent.
    assert "if none is uploaded, use the subject described in the Additional notes or ask for one" in text
    assert "pose and angle only" not in text and "not camera or shot size" not in text
