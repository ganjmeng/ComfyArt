"""Source contract: ProviderAdmin draft/live radios follow Live; gif_default only for to_gif."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "src/ui/ProviderAdmin.tsx").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    m = re.search(rf"function {name}\(tool: ToolRow\): ToolRoute \{{(.*?)\n\}}", SRC, re.S)
    assert m, f"missing {name}"
    return m.group(1)


def test_live_baseline_gif_default_only_for_to_gif():
    body = _fn("liveBaseline")
    assert "gif_default" in body
    assert "tool.id === 'to_gif'" in body or 'tool.id === "to_gif"' in body
    # Bare `if (tool.gif_default)` (no to_gif on the same statement) is the mutation QA used.
    assert re.search(r"if\s*\(\s*tool\.gif_default\s*\)", body) is None
    assert re.search(r"tool\.id\s*===\s*['\"]to_gif['\"]\s*&&\s*tool\.gif_default", body)


def test_draft_route_delegates_to_live_baseline():
    body = _fn("draftRoute")
    assert "liveBaseline(tool)" in body


def test_unedited_primary_reads_draft_route_not_blank():
    """Opening Providers must not fall back to blank() WaveSpeed for Still→GIF, nor keep stale edits."""
    assert "drafts[current.id] ?? draftRoute(current)" in SRC or 'drafts[current.id] ?? draftRoute(current)' in SRC
    assert "drafts[current.id] || blank()" not in SRC
    assert "setDrafts({})" in SRC


def test_gap4_save_error_does_not_call_absorb():
    """On save failure, in-session drafts stay: catch only setError(failText), absorb stays in then()."""
    # saveOne: then → absorb; catch → setError(failText) without absorb.
    assert "function failText" in SRC or "failText(e" in SRC
    idx_save = SRC.find("const saveOne")
    assert idx_save > 0
    chunk = SRC[idx_save:idx_save + 900]
    assert "absorb(next)" in chunk
    assert "setError(failText(e))" in chunk
    # catch block must not call absorb
    catch = chunk[chunk.find(".catch"):chunk.find(".finally")]
    assert "absorb" not in catch

