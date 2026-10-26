"""#323 v3: live ca-spin spinner + check when done; title shimmer only (no breath/halo/agent smile)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
PANEL = (ROOT / "src/ui/AgentPanel.tsx").read_text()
OVERLAYS = (ROOT / "src/styles/overlays.css").read_text()
SHELL = (ROOT / "src/styles/shell.css").read_text()


def test_thought_live_spinner_done_check() -> None:
    assert "function Thought" in CHAT
    thought = CHAT.split("function Thought")[1].split("\nfunction ")[0]
    assert "data-live={live || undefined}" in thought
    assert 'className="ca-chat__thinkspin"' in thought
    assert "Icons.check" in thought
    assert "Icons.agent" not in thought
    assert 'className="ca-chat__thinklabel"' in thought
    assert "stream-light" not in thought
    assert "ca-stream" not in thought


def test_agentpanel_thinking_has_spinner() -> None:
    assert 'className="ca-chat__thinking"' in PANEL
    block = PANEL.split('className="ca-chat__thinking"')[1].split("</div>")[0]
    assert 'className="ca-chat__thinkspin"' in block
    assert 'className="ca-chat__thinklabel"' in block
    assert "Icons.agent" not in block


def test_css_no_breath_halo() -> None:
    assert "ca-think-breath" not in OVERLAYS
    assert "@keyframes ca-think-breath" not in OVERLAYS
    assert ".ca-chat__thinkicon::after" not in OVERLAYS
    assert "stream-light" not in OVERLAYS


def test_thinkspin_uses_ca_spin() -> None:
    assert ".ca-chat__thinkspin" in OVERLAYS
    block = OVERLAYS.split(".ca-chat__thinkspin")[1].split("}")[0]
    assert "ca-spin 1s" in block
    assert "border-radius: 50%" in block


def test_live_label_shimmer_not_icon() -> None:
    assert ".ca-chat__thought[data-live] .ca-chat__thinklabel" in OVERLAYS
    assert ".ca-chat__thinking .ca-chat__thinklabel" in OVERLAYS
    block = OVERLAYS.split(".ca-chat__thinking .ca-chat__thinklabel")[1].split("}")[0]
    assert "ca-shine 1.8s" in block
    assert "background-clip: text" in block or "-webkit-background-clip: text" in block
    # parent waiting bar must NOT carry shimmer (icon would clip)
    shell_rule = SHELL.split(".ca-chat__thinking {")[1].split("}")[0]
    assert "ca-shine" not in shell_rule
    assert "color: transparent" not in shell_rule
