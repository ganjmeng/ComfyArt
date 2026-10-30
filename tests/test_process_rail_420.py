"""#420: canvas tools (get_canvas / create_frame / add_text) stay on the process rail;
failed rows read 「工具名 · 失败」 on-rail (no off-rail ca-chat__tool Step)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
ZH = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
EN = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))


def _process_kind_of_fn() -> str:
    # Stop before the next top-level function (liveThoughtLabel), not mid-comment exports
    return CHAT.split("function processKindOf", 1)[1].split("\nfunction liveThoughtLabel", 1)[0]


def test_process_kind_falls_through_to_tool() -> None:
    """Any tool_use that is not a known process family joins as kind 'tool' (never null for tool_use)."""
    body = _process_kind_of_fn()
    assert "return 'tool'" in body
    # only non-tool_use still returns null
    assert "if (b.type !== 'tool_use') return null" in body
    assert body.rstrip().endswith("return 'tool'\n}") or "return 'tool'\n}" in body
    assert "'tool'" in CHAT.split("type ProcessKind", 1)[1].split("const VIDEO_TOOLS", 1)[0]


def test_failed_tool_label_includes_tool_kind() -> None:
    ab = CHAT.split("export function AssistantBlocks", 1)[1].split("\nexport function ", 1)[0]
    assert "kindResolved === 'tool'" in ab
    assert "chatMessage.failed" in ab
    assert "process-row-failed" in CHAT


def test_failed_locale_strings() -> None:
    assert ZH["chatMessage.failed"] == "失败"
    assert EN["chatMessage.failed"] == "Failed"


def test_canvas_tool_labels_exist() -> None:
    for key in ("bot.viewCanvas", "bot.addText", "bot.createArtboard"):
        assert key in ZH and ZH[key]
        assert key in EN and EN[key]
