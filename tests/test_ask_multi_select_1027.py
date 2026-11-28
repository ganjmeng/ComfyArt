"""#1027 QA: a card question that says 可多选 must let the user pick several options.

The agent wrote "（可多选）" but no max_selections, so the card fell back to one choice and B
deselected A. Shared card code, no skill named: `multi_select: true` or a prompt that tells the
user to pick several makes the question allow every option, and the answer keeps them all.
"""
from __future__ import annotations

import pytest

from ComfyArt.api import bot_asks
from ComfyArt.api.mcp_tools.bot_tools import ASK_USER_SCHEMA  # noqa: F401  (schema import must stay valid)

OPTS = [{"id": k, "label": k} for k in "ABCDE"]


def _q(prompt, **extra):
    return {"questions": [{"id": "q1", "prompt": prompt, "options": OPTS, "page": 1, **extra}]}


@pytest.mark.parametrize("prompt", ["这次需要交付哪些品牌物料？（可多选）", "Which pieces do you need? Select all that apply.",
                                    "Pick one or more deliverables"])
def test_a_prompt_that_says_multi_select_allows_every_option(prompt):
    spec = bot_asks.validate_spec(_q(prompt))
    q = spec["questions"][0]
    assert q["max_selections"] == len(OPTS)
    answers = {"q1": {"selected": ["A", "B"]}}
    bot_asks.validate_answer(spec, [], "", answers)  # two picks are accepted, not trimmed


def test_explicit_flag_wins_both_ways():
    assert bot_asks.validate_spec(_q("哪些物料？", multi_select=True))["questions"][0]["max_selections"] == 5
    assert bot_asks.validate_spec(_q("哪些物料？（可多选）", multi_select=False))["questions"][0]["max_selections"] == 1


def test_a_single_choice_question_stays_single():
    spec = bot_asks.validate_spec(_q("色彩方向倾向哪一种？"))
    assert spec["questions"][0]["max_selections"] == 1
    with pytest.raises(ValueError):
        bot_asks.validate_answer(spec, [], "", {"q1": {"selected": ["A", "B"]}})


def test_an_explicit_max_is_kept():
    spec = bot_asks.validate_spec(_q("哪些物料？（可多选）", max_selections=3))
    assert spec["questions"][0]["max_selections"] == 3


def test_legacy_single_question_form_too():
    spec = bot_asks.validate_spec({"prompt": "Which ones? (multi-select)", "options": OPTS})
    assert spec["max_selections"] == len(OPTS)


def test_pick_one_of_many_is_not_multi():
    # 多选一 means "pick one of several"
    assert bot_asks.validate_spec(_q("风格多选一："))["questions"][0]["max_selections"] == 1
