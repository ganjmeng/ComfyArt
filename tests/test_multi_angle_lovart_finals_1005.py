"""Lovart 44b6ab37: finals follow the selected compositions and the card aspect.

The nine-cell line-art preview stays 1152×2048 9:16. No network.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from multi_angle_plan_fixture import HEADPHONES_PLAN, preview_url
from test_multi_angle_stages_911 import choose, confirm_quote, run, setup  # noqa: F401

from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api import multi_angle as ma
from ComfyArt.bot.skill_output import run_hint


ROOT = Path(__file__).resolve().parents[1]


def _instructions() -> str:
    text = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
    match = re.search(r"\{ id: 'universal-multi-angle-grid'.*?instructions: '(.*?)',\n", text, re.S)
    assert match
    return match.group(1)


def test_skill_prompt_drops_the_fixed_four_by_three_to_four_lock():
    text = _instructions()
    hint = run_hint("universal-multi-angle-grid")
    for body in (text, hint):
        assert "exactly four" not in body.lower()
        assert "exactly 4" not in body
        assert "1152" in body and "9:16" in body
        assert "2048" in body
    assert "one separate image for each composition the user selects" in text
    assert "1:1 is 2048×2048" in text and "3:4 is 1536×2048" in text
    assert "number of finals equals the number of selected compositions" in hint
    assert "1:1 is 2048x2048" in hint and "3:4 is 1536x2048" in hint


@pytest.mark.asyncio
@pytest.mark.parametrize("aspect,size,ids", [
    ("1:1", (2048, 2048), ("1", "2", "3")),
    ("3:4", (1536, 2048), ("1", "2", "3")),
    ("3:4", (1536, 2048), ("2",)),
])
async def test_finals_match_selected_compositions_and_card_aspect_preview_stays_9_16(run, aspect, size, ids):
    rows, sent = run
    setup(rows, aspect)
    confirm_quote(rows)
    relay = canvas._relay("generate_image")
    preview = await relay({
        "composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
        "multi_angle_stage": "preview", "ratio": aspect,
    })
    assert preview.get("submitted") is True
    assert (sent[0][1]["width"], sent[0][1]["height"], sent[0][1]["ratio"], sent[0][1]["count"]) == (1152, 2048, "9:16", 1)
    ma.record_wait({"results": [{
        "id": preview["ids"][0], "status": "done", "placed": True, "generation_succeeded": True,
        "shapes": ["preview-shape"], "urls": [preview_url()],
    }]})
    choose(rows, ids)
    for panel in ids:
        placed = await relay({"skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": panel,
                              "ratio": "16:9", "count": 4})
        assert placed.get("submitted") is True
    finals = [args for _action, args in sent[1:]]
    assert len(finals) == len(ids)
    assert [(a["width"], a["height"], a["ratio"], a["count"]) for a in finals] == [(*size, aspect, 1)] * len(ids)
