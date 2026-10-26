"""#323 v2: static think icon + live Thought title shimmer (no breath/halo)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
PANEL = (ROOT / "src/ui/AgentPanel.tsx").read_text()
OVERLAYS = (ROOT / "src/styles/overlays.css").read_text()
SHELL = (ROOT / "src/styles/shell.css").read_text()


def test_thought_data_live_and_thinkicon() -> None:
    assert "function Thought" in CHAT
    thought = CHAT.split("function Thought")[1].split("\nfunction ")[0]
    assert "data-live={live || undefined}" in thought
    assert 'className="ca-chat__thinkicon"' in thought
    assert 'className="ca-chat__thinklabel"' in thought
    assert "Icons.agent" in thought
    assert "stream-light" not in thought
    assert "ca-stream" not in thought


def test_agentpanel_thinking_has_thinkicon() -> None:
    assert 'className="ca-chat__thinking"' in PANEL
    block = PANEL.split('className="ca-chat__thinking"')[1].split("</div>")[0]
    assert 'className="ca-chat__thinkicon"' in block
    assert "Icons.agent" in block


def test_css_no_breath_halo_static_icon() -> None:
    assert "ca-think-breath" not in OVERLAYS
    assert "@keyframes ca-think-breath" not in OVERLAYS
    assert ".ca-chat__thinkicon::after" not in OVERLAYS
    assert "radial-gradient" not in OVERLAYS.split("#323")[1].split(".ca-chat__thoughttext")[0]
    assert ".ca-chat__thinkicon {" in OVERLAYS
    assert ".ca-chat__thinking > .ca-chat__thinkicon { color: var(--ca-muted); }" in OVERLAYS
    assert "stream-light" not in OVERLAYS
    assert "ca-stream-light" not in OVERLAYS


def test_live_thought_label_shimmer() -> None:
    assert ".ca-chat__thought[data-live] .ca-chat__thinklabel" in OVERLAYS
    block = OVERLAYS.split(".ca-chat__thought[data-live] .ca-chat__thinklabel")[1].split("}")[0]
    assert "ca-shine 1.8s" in block
    assert "background-clip: text" in block or "-webkit-background-clip: text" in block
    assert "var(--ca-muted)" in block and "var(--ca-text)" in block


def test_thinking_shimmer_1_8s() -> None:
    rule = SHELL.split(".ca-chat__thinking {")[1].split("}")[0]
    assert "ca-shine 1.8s" in rule
    assert "1.6s" not in rule
