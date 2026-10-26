"""#312: mode dropdown checkmark ~16–20px; Model label/select closer to agent-row scale."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PICKER = (REPO / "src/ui/AgentPicker.tsx").read_text()
SHELL = (REPO / "src/styles/shell.css").read_text()


def test_selected_check_wrapped_in_ca_icon() -> None:
    # Raw Icons.check inside .ca-agentpick__check stretches to the 52px column.
    assert "ca-agentpick__check" in PICKER
    assert 'className="ca-icon">{Icons.check}' in PICKER or "className=\"ca-icon\">{Icons.check}" in PICKER
    # Must not dump bare Icons.check as the only child of the check column.
    bare = 'ca-agentpick__check">{current && p.id === providerId && Icons.check}'
    assert bare not in PICKER


def test_check_sized_under_agentpick() -> None:
    assert ".ca-agentpick__check > .ca-icon" in SHELL
    assert "18px" in SHELL[SHELL.index(".ca-agentpick__check > .ca-icon") : SHELL.index(".ca-agentpick__check > .ca-icon") + 200]


def test_model_section_scaled_under_agentpick() -> None:
    assert ".ca-agentpick .ca-gen__title" in SHELL
    chunk = SHELL[SHELL.index(".ca-agentpick .ca-gen__title") : SHELL.index(".ca-agentpick .ca-gen__title") + 280]
    assert "13px" in chunk
    assert ".ca-agentpick select.ca-panel__input" in SHELL
    sel = SHELL[SHELL.index(".ca-agentpick select.ca-panel__input") : SHELL.index(".ca-agentpick select.ca-panel__input") + 160]
    assert "32px" in sel
    assert "13px" in sel
