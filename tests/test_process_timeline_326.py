"""#326 process timeline v3.4: solid spine · Lucide icons · status card outside · shimmer on active only."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
OVERLAYS = (ROOT / "src/styles/overlays.css").read_text()
ICONS = (ROOT / "src/ui/icons.tsx").read_text()
EN = (ROOT / "src/locales/en.json").read_text()
HTML = (ROOT / "docs/design/326/process-timeline-326.html").read_text()


def test_design_lock_v34_present() -> None:
    assert "v3.4" in HTML
    assert "single spine" in HTML.lower() or "spine" in HTML
    assert 'data-icon="brain"' in HTML
    assert 'data-icon="scroll"' in HTML
    assert 'data-icon="globe"' in HTML
    assert "status-card" in HTML
    # solid spine, not dashed (issue body dashed is obsolete)
    assert "dashed" not in HTML.lower() or "border-style: dashed" not in HTML


def test_lucide_process_icons() -> None:
    assert "scrollText:" in ICONS
    assert "globe:" in ICONS
    assert "imageLine:" in ICONS
    assert "videoLine:" in ICONS
    assert "strokeWidth={2}" in ICONS
    # Brain stays on Icons.think (timeline + #325)
    block = ICONS.split("think:")[1].split(",\n")[0]
    assert 'd="M12 18V5"' in block
    scroll = ICONS.split("scrollText:")[1].split(",\n")[0]
    assert "M15 12h-5" in scroll
    globe = ICONS.split("globe:")[1].split(",\n")[0]
    assert 'r="10"' in globe


def test_process_timeline_component() -> None:
    assert "function ProcessTimeline" in CHAT
    assert "ca-process__spine" in CHAT
    assert "ca-process__status" in CHAT
    assert "ca-process__label--active" in CHAT
    assert "PROCESS_ICONS" in CHAT
    assert "Icons.scrollText" in CHAT
    assert "Icons.globe" in CHAT
    assert "Icons.sparkleImage" in CHAT  # #437/#442: model-name row icon (designer v5)
    assert "Icons.videoLine" in CHAT
    # no Vercel Trace spinner / check on timeline
    proc = CHAT.split("function ProcessTimeline")[1].split("\nfunction ")[0]
    assert "ca-spin" not in proc
    assert "Icons.check" not in proc
    assert "breath" not in proc.lower()


def test_assistant_blocks_rails_process_keeps_single_thought() -> None:
    ab = CHAT.split("export function AssistantBlocks")[1].split("\nexport function ")[0]
    assert "flushProc" in ab
    assert "ProcessTimeline" in ab
    # #325 single Thought preserved
    assert "onlyThought" in ab
    assert "<Thought" in ab


def test_css_spine_status_outside_shimmer() -> None:
    assert ".ca-process__spine" in OVERLAYS
    assert ".ca-process__status" in OVERLAYS
    assert ".ca-process__label--active" in OVERLAYS
    spine = OVERLAYS.split(".ca-process__spine")[1].split("}")[0]
    assert "1px" in spine
    assert "dashed" not in spine
    active = OVERLAYS.split(".ca-process__label--active")[1].split("}")[0]
    assert "ca-shine" in active
    # status is sibling (margin-left indent), not inside steps rail
    status = OVERLAYS.split(".ca-process__status")[1].split("}")[0]
    assert "margin-left" in status
    assert "border-radius: 12px" in status


def test_locale_process_labels() -> None:
    assert "Skill ready" in EN
    assert "Searching the web" in EN
    assert "Generating images" in EN
    assert "Generating Video" in EN
