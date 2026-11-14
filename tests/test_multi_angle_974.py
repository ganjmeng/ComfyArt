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


def test_apply_generate_locks_every_call_to_1536x2048_count_one():
    # A model that tries one 1024 square call with count=4 is corrected to one 3:4 1536x2048 call.
    args = apply_generate({"skill": SID, "prompt": "front view", "width": 1024, "height": 1024,
                           "ratio": "1:1", "count": 4})
    assert (args["width"], args["height"], args["ratio"], args["count"]) == (1536, 2048, "3:4", 1)
    assert args["skill"] == SID and args["size_lock"] is True
    # Four calls are expected, so the single-image skip must never swallow calls 2-4.
    for generated in (1, 2, 3):
        assert single_image_skip("generate_image", SID, "zh", generated) is None


def test_run_hint_uses_the_multi_angle_wording_not_pose_fission():
    hint = run_hint("Multi-Angle Image Generator")
    assert "deliver exactly 4 separate images" in hint
    assert "width=1536 height=2048 ratio=3:4" in hint
    assert "one angle per call" in hint and "same uploaded subject shape id in refs" in hint
    assert "grid, collage or contact sheet" in hint and "Do not use 1024x1024" in hint
    assert "pose and angle only" not in hint and "not camera or shot size" not in hint


def test_instruction_states_four_separate_images_fixed_size_and_same_ref():
    text = _instr(SID)
    assert "exactly four separate images" in text
    assert "3:4 / 1536×2048" in text and "never one grid, collage or contact sheet" in text
    assert "generate_image exactly four times" in text and "count=1 each" in text
    assert "same uploaded subject shape id in refs" in text
    # #693 fallback path stays written down: no upload -> Additional subject or ask, never invent.
    assert "if none is uploaded, use the subject described in the Additional notes or ask for one" in text
    assert "pose and angle only" not in text and "not camera or shot size" not in text
