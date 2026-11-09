"""Fixture: generate_image API row must draft to WaveSpeed, not gif_default Flare."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "src/ui/ProviderAdmin.tsx").read_text(encoding="utf-8")


def test_live_baseline_generate_image_ignores_gif_default_in_source():
    m = re.search(r"function liveBaseline\(tool: ToolRow\): ToolRoute \{(.*?)\n\}", SRC, re.S)
    assert m
    body = m.group(1)
    assert "tool.id === 'to_gif'" in body or 'tool.id === "to_gif"' in body
    assert re.search(r"if\s*\(\s*tool\.gif_default\s*\)", body) is None


def test_draft_route_prefers_live_baseline_when_no_saved_route():
    m = re.search(r"function draftRoute\(tool: ToolRow\): ToolRoute \{(.*?)\n\}", SRC, re.S)
    assert m
    body = m.group(1)
    assert "liveBaseline(tool)" in body
    assert "gif_default" not in body
