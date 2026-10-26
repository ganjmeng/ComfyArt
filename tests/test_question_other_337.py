"""#337 product lock: keep other text on A–D pick; empty placeholder ≠ answered."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()


def _question_block() -> str:
    return CHAT.split("function QuestionBlock")[1].split("\nfunction ")[0]


def _q_filled() -> str:
    return CHAT.split("function qFilled")[1].split("\nfunction ")[0]


def test_single_select_pick_keeps_other_text() -> None:
    """(1) Click A–D must keep other text — only moves soft-select."""
    block = _question_block()
    toggle = block.split("const toggle =")[1].split("const onOther")[0]
    # Product lock comment + spread that preserves `other`
    assert "keeps other text" in toggle or "do NOT clear other" in toggle
    assert re.search(r"onChange\(\{\s*\.\.\.st,\s*selected:\s*\[id\]\s*\}\)", toggle)
    # Must NOT clear other on letter pick
    assert not re.search(r"other:\s*['\"]['\"]", toggle)
    assert "other: ''" not in toggle
    assert 'other: ""' not in toggle


def test_empty_other_placeholder_not_answered() -> None:
    """(2) Empty / placeholder other does not count as filled / enable primary alone."""
    filled = _q_filled()
    # trim required — whitespace/placeholder empty string fails
    assert "st.other.trim().length > 0" in filled or "st.other.trim()" in filled
    # text-only path also requires trim
    assert "st.other.trim().length > 0" in filled
    # allow_other alone is not enough without trim check
    assert re.search(
        r"q\.allow_other\s*&&\s*st\.other\.trim\(\)",
        filled,
    )


def test_behavior_sim_keep_text_and_empty_other() -> None:
    """Pure sim of QuestionBlock single-select contract (mirrors tip ChatMessage)."""

    def toggle(st: dict, id_: str, multi: bool = False) -> dict:
        # tip: if (!multi) onChange({ ...st, selected: [id] })
        if not multi:
            return {**st, "selected": [id_]}
        selected = (
            [x for x in st["selected"] if x != id_]
            if id_ in st["selected"]
            else st["selected"] + [id_]
        )
        return {**st, "selected": selected}

    def on_other(st: dict, value: str, multi: bool = False) -> dict:
        if not multi and value.strip():
            return {**st, "selected": [], "other": value}
        return {**st, "other": value}

    def q_filled(st: dict, allow_other: bool = True, options: bool = True) -> bool:
        if not options and allow_other:
            return len(st["other"].strip()) > 0
        if st["selected"]:
            return True
        return bool(allow_other and st["other"].strip())

    def other_on(st: dict, multi: bool = False) -> bool:
        return bool(st["other"].strip()) and (multi or len(st["selected"]) == 0)

    # fill other → soft-on other, A–D cleared
    st = {"selected": ["b"], "other": ""}
    st = on_other(st, "包装袋")
    assert st == {"selected": [], "other": "包装袋"}
    assert other_on(st) is True
    assert q_filled(st) is True

    # pick A → keeps other text; soft moves to A; other not soft-on
    st = toggle(st, "a")
    assert st["other"] == "包装袋"
    assert st["selected"] == ["a"]
    assert other_on(st) is False
    assert q_filled(st) is True

    # empty other alone does not fill / enable primary
    empty = {"selected": [], "other": ""}
    assert q_filled(empty) is False
    assert other_on(empty) is False
    spaces = {"selected": [], "other": "   "}
    assert q_filled(spaces) is False
    assert other_on(spaces) is False
