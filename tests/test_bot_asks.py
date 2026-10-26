"""#328/#330 Question-card protocol: validate_spec / validate_answer."""
from __future__ import annotations

import pytest

from ComfyArt.api import bot_asks


OPTS = [
    {"id": "a", "label": "A"},
    {"id": "b", "label": "B"},
    {"id": "c", "label": "C"},
]


def test_validate_spec_defaults_kind_question_and_allow_skip():
    spec = bot_asks.validate_spec({"prompt": "ratio?", "options": OPTS})
    assert spec["kind"] == bot_asks.QUESTION_KIND
    assert spec["allow_skip"] is True
    assert spec["min_selections"] == 1
    assert spec["max_selections"] == 1
    assert "defaults" not in spec


def test_validate_spec_recommended_and_defaults_and_page():
    opts = [
        {"id": "a", "label": "A", "recommended": True},
        {"id": "b", "label": "B"},
        {"id": "c", "label": "C", "description": "wide"},
    ]
    spec = bot_asks.validate_spec({
        "prompt": "style?",
        "options": opts,
        "max_selections": 2,
        "page": 1,
        "page_count": 2,
    })
    assert spec["defaults"] == ["a"]
    assert spec["options"][0]["recommended"] is True
    assert spec["options"][2]["description"] == "wide"
    assert spec["page"] == 1 and spec["page_count"] == 2

    spec2 = bot_asks.validate_spec({
        "prompt": "style?",
        "options": opts,
        "defaults": ["b", "c"],
        "max_selections": 2,
    })
    assert spec2["defaults"] == ["b", "c"]


def test_validate_spec_rejects_bad_defaults_and_page():
    with pytest.raises(ValueError, match="unknown default"):
        bot_asks.validate_spec({
            "prompt": "q", "options": OPTS, "defaults": ["z"],
        })
    with pytest.raises(ValueError, match="defaults exceed"):
        bot_asks.validate_spec({
            "prompt": "q", "options": OPTS, "defaults": ["a", "b"],
            "max_selections": 1,
        })
    with pytest.raises(ValueError, match="page cannot exceed"):
        bot_asks.validate_spec({
            "prompt": "q", "options": OPTS, "page": 3, "page_count": 2,
        })


def test_validate_answer_skip_empty_selected():
    spec = bot_asks.validate_spec({"prompt": "q", "options": OPTS})
    bot_asks.validate_answer(spec, [], "")  # allow_skip default
    with pytest.raises(ValueError, match="at least"):
        bot_asks.validate_answer({**spec, "allow_skip": False}, [], "")


def test_validate_answer_multi_and_other():
    spec = bot_asks.validate_spec({
        "prompt": "q",
        "options": OPTS,
        "min_selections": 1,
        "max_selections": 2,
        "allow_other": True,
        "allow_skip": False,
    })
    bot_asks.validate_answer(spec, ["a", "b"], "")
    bot_asks.validate_answer(spec, [], "free text")
    with pytest.raises(ValueError, match="at most"):
        bot_asks.validate_answer(spec, ["a", "b", "c"], "")
    with pytest.raises(ValueError, match="unknown"):
        bot_asks.validate_answer(spec, ["z"], "")
    with pytest.raises(ValueError, match="free-text"):
        bot_asks.validate_answer({**spec, "allow_other": False}, [], "nope")


def test_skip_note_text():
    note = bot_asks.skip_note()
    assert "skipped" in note
    assert "do not re-ask" in note


def test_allow_skip_false_explicit():
    spec = bot_asks.validate_spec({
        "prompt": "q", "options": OPTS, "allow_skip": False,
    })
    assert spec["allow_skip"] is False
