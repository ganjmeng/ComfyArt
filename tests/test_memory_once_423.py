"""#423 one 记忆已更新 › row per turn; dedupe before write; saved note tells the model to answer now. $0, mocks only."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ComfyArt.api.bot_turns import _TurnState, _apply_event, memory_updated_block
from ComfyArt.bot.providers import BotEvent, TurnHandle

ROOT = Path(__file__).resolve().parent.parent


def _use(i):
    return {"type": "tool_use", "id": i, "name": "local__memory", "input": {"action": "add"}}


def _add(blocks, i, ids, texts, upd=()):
    blocks.append(_use(i))
    b = memory_updated_block(blocks, i, "local__memory", json.dumps({"saved": True, "memory_ids": ids, "texts": texts, "updated_ids": list(upd)}), "success")
    if b is not None and b not in blocks:
        blocks.append(b)
    return b


def test_three_adds_merge_into_one_block_with_count():
    blocks = []
    first = _add(blocks, "c1", ["m1"], ["A"])
    assert _add(blocks, "c2", ["m2"], ["B"]) is first
    assert _add(blocks, "c3", ["m3", "m2"], ["C", "B"]) is first
    rows = [b for b in blocks if b["type"] == "memory_updated"]
    assert len(rows) == 1
    assert rows[0]["memory_ids"] == ["m1", "m2", "m3"] and rows[0]["texts"] == ["A", "B", "C"]
    assert rows[0]["count"] == 3 and rows[0]["tool_ids"] == ["c1", "c2", "c3"]


def test_unchanged_only_or_failed_add_makes_no_row():
    blocks = [_use("c1")]
    assert memory_updated_block(blocks, "c1", "local__memory", json.dumps({"saved": True, "memory_ids": []}), "success") is None
    assert memory_updated_block(blocks, "c1", "local__memory", json.dumps({"memory_ids": ["x"]}), "error") is None


def test_apply_event_appends_once_and_payload_carries_merged_block():
    st = _TurnState(TurnHandle(), "c", "m")
    pays = []
    for i, mid in (("c1", "m1"), ("c2", "m2")):
        _apply_event(st, BotEvent(t="tool_use", name="local__memory", input={"action": "add"}, id=i))
        pays.append(_apply_event(st, BotEvent(t="tool_result", name="local__memory", id=i,
                                                     text=json.dumps({"saved": True, "memory_ids": [mid], "texts": [mid]}))))
    assert sum(b.get("type") == "memory_updated" for b in st.blocks) == 1
    assert pays[-1]["memory_updated"]["memory_ids"] == ["m1", "m2"] and pays[-1]["memory_updated"]["count"] == 2


def _src(p):
    return (ROOT / p).read_text()


def test_frontend_single_row_wiring():
    bl = _src("src/botLayout.ts")
    assert "upsertMemory(" in bl and "MEMORY_SAVED_NOTE" in bl and "saved: true" in bl
    assert re.search(r"MEMORY_SAVED_NOTE = '.*reply to the user now", _src("src/memory.ts"), re.I)
    bot = _src("src/bot.ts")
    assert "findIndex((b) => b.type === 'memory_updated')" in bot
    cm = _src("src/ui/ChatMessage.tsx")
    assert "b !== firstMem" in cm and "tool_ids" in cm and "memoryIds: b.type === 'memory_updated' ? memIdsAll" in cm


@pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node")
def test_upsert_dedupes_and_updates(tmp_path):
    out = tmp_path / "m.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "memory_safety.ts"})
    got = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True,
                                    env={**os.environ, "SETTINGS": json.dumps({"proactive-memory": True, "proactive-skills": True})}).stdout)["upsert_423"]
    assert got["added"] == ["品牌色：克莱因蓝"]
    assert got["updated"] == [["a", "常用画幅：16:9", "常用画幅：9:16"]]
    assert got["unchanged"] == ["b"]
    assert sorted(got["file"]) == sorted(["常用画幅：9:16", "偏好极简", "品牌色：克莱因蓝"])


def test_update_only_add_shows_row_and_counts():
    blocks = []
    b = _add(blocks, "c1", ["old1"], ["画幅：9:16"], upd=["old1"])
    assert b is not None and b["count"] == 1 and b["updated"] == 1 and b["added_count"] == 0


def test_mixed_counts_new_plus_updated():
    blocks = []
    b = _add(blocks, "c1", ["n1"], ["A"])
    _add(blocks, "c2", ["u1"], ["画幅：9:16"], upd=["u1"])
    _add(blocks, "c3", ["n1"], ["A：2"], upd=["n1"])  # added earlier this turn, then changed: still new
    assert (b["count"], b["added_count"], b["updated"], b["updated_ids"]) == (2, 1, 1, ["u1"])


def _run_harness(tmp_path):
    out = tmp_path / "m.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "memory_safety.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True,
                                     env={**os.environ, "SETTINGS": json.dumps({"proactive-memory": True, "proactive-skills": True})}).stdout)


def test_memory_add_tool_rows_always_hidden():
    cm = _src("src/ui/ChatMessage.tsx")
    assert "memCalls.has(b.id) || memAddIds.has(b.id))" in cm   # incl. no-op identical repeat


def test_block_carries_no_undo_payload():
    blocks = [_use("c1")]
    b = memory_updated_block(blocks, "c1", "local__memory", json.dumps({"memory_ids": ["u1"], "texts": ["画幅：4:3"], "updated_ids": ["u1"], "previous": {"u1": "画幅：16:9"}}), "success")
    assert "previous" not in b and b["updated_ids"] == ["u1"]


def _git_main(p):
    r = subprocess.run(["git", "show", f"origin/main:{p}"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def test_dialog_and_click_entry_identical_to_main():
    """#423 narrowed scope: the memory dialog, its click entry, locales and undo API are main's."""
    for p in ("src/ui/MemoryDialog.tsx",):
        m = _git_main(p)
        if m is None:
            pytest.skip("origin/main not available")
        assert _src(p) == m, p
    assert "memoryFocusAtom.set({ id, undoable: true })" in _src("src/ui/ChatMessage.tsx")
    mem = _src("src/memory.ts")
    assert "export interface MemoryFocus { id: string; undoable?: boolean }" in mem
    assert "export function undoMemoryUpdated(id: string): Promise<boolean> {\n  return removeMemory(id, 'memory-updated-undo')" in mem


def test_locales_only_add_memory_retrieved_430():
    """#430 A: locales differ from main only by the Memory retrieved key (+ #441 memoryUpdated without ›)."""
    for p, v in (("src/locales/zh.json", "记忆已读取"), ("src/locales/en.json", "Memory retrieved")):
        m = _git_main(p)
        if m is None:
            pytest.skip("origin/main not available")
        cur, base = json.loads(_src(p)), json.loads(m)
        assert cur.pop("chatMessage.memoryRetrieved") == v
        cur.pop("chatMessage.memoryUpdated"); base.pop("chatMessage.memoryUpdated")  # #441: › moved to an svg
        assert cur == base
    assert json.loads(_src("src/locales/zh.json"))["chatMessage.memoryUpdated"] == "记忆已更新"
    assert json.loads(_src("src/locales/en.json"))["chatMessage.memoryUpdated"] == "Memory updated"


def test_retrieved_row_before_updated_only_on_update_430():
    cm = _src("src/ui/ChatMessage.tsx")
    i = cm.index("kind: 'memory_retrieved'")
    assert i < cm.index("kind: kindResolved", i)  # pushed right before the 记忆已更新 › step
    assert "memBlocks.some((x) => (x.updated_ids ?? []).length > 0)" in cm
    assert "const isMemory = s.kind === 'memory_updated'" in cm  # only 记忆已更新 › is clickable
    assert "memory_retrieved: Icons.memoryHead" in cm and "memory_updated: Icons.memoryHead" in cm  # #435 in-house icon


def test_update_block_flags_retrieved_add_does_not_430():
    blocks = []
    b = _add(blocks, "c1", ["n1"], ["A"])
    assert b["updated_ids"] == []  # plain add -> no 记忆已读取
    _add(blocks, "c2", ["u1"], ["画幅：9:16"], upd=["u1"])
    assert b["updated_ids"] == ["u1"] and sum(x["type"] == "memory_updated" for x in blocks) == 1


def test_memory_row_measured_css_441() -> None:
    root = Path(__file__).resolve().parent.parent
    css = (root / "src/styles/overlays.css").read_text()
    for frag in ("--ca-memory-text: rgba(0,0,0,.55)", "--ca-memory-text: rgba(255,255,255,.55)",
                 ":last-child { height: 20px; margin: 0;",
                 "> .ca-process__row[data-kind^='memory_'] > .ca-process__spine { top: 20px; }",
                 "font-weight: 400; font-size: 14px; line-height: 20px; height: 20px; color: inherit; gap: 6px;",
                 "[data-kind^='memory_']:hover { color: var(--ca-text); }",
                 ".ca-process__memchev { width: 16px; height: 16px;"):
        assert frag in css, frag
    icons = (root / "src/ui/icons.tsx").read_text()
    line = next(l for l in icons.splitlines() if l.strip().startswith("memoryHead:"))
    assert "<Svg strokeWidth={1.5}>" in line and "fill" not in line  # #441 v7: thin outline, not solid
    cm = (root / "src/ui/ChatMessage.tsx").read_text()
    assert "{isMemory && <span className=\"ca-process__memchev ca-icon\"" in cm

    assert "memory_']:last-child) { margin-bottom" not in css  # #441 v5: no extra gap before the reply (main pitch)