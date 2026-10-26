"""#323: left-side think breath + shimmer sync (Icons.agent; no stream-light)."""
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
    assert "Icons.agent" in thought
    assert "stream-light" not in thought
    assert "ca-stream" not in thought


def test_agentpanel_thinking_has_thinkicon() -> None:
    assert 'className="ca-chat__thinking"' in PANEL
    # thinkicon precedes the thinking/working text inside the waiting bar
    block = PANEL.split('className="ca-chat__thinking"')[1].split("</div>")[0]
    assert 'className="ca-chat__thinkicon"' in block
    assert "Icons.agent" in block


def test_css_think_breath_and_reduced_motion() -> None:
    assert "ca-think-breath 1.8s" in OVERLAYS
    assert "@keyframes ca-think-breath" in OVERLAYS
    assert "prefers-reduced-motion: reduce" in OVERLAYS
    assert ".ca-chat__thinkicon::after { display: none; }" in OVERLAYS or ".ca-chat__thinkicon::after{display:none;}" in OVERLAYS.replace(" ", "")
    # no stream-light
    assert "stream-light" not in OVERLAYS
    assert "ca-stream-light" not in OVERLAYS


def test_thinking_shimmer_1_8s() -> None:
    rule = SHELL.split(".ca-chat__thinking {")[1].split("}")[0]
    assert "ca-shine 1.8s" in rule
    assert "1.6s" not in rule
