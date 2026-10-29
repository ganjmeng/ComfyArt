"""#433 memory dialog in the reference layout: four vertical groups (measured order), title + body
cards, bottom 「通过对话修改记忆」 pill, measured empty state; opening from 「记忆已更新 ›」 highlights
nothing and offers no undo — removal is delete + confirm only."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLG = (ROOT / "src/ui/MemoryDialog.tsx").read_text()
MEM = (ROOT / "src/home/ArtiMemory.tsx").read_text()
CSS = (ROOT / "src/styles/overlays.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())


def test_measured_group_order_shared() -> None:
    assert "export const GROUP_ORDER: CatId[] = ['taste', 'about', 'work', 'assets']" in MEM
    assert "GROUP_ORDER.map" in DLG and "GROUP_ORDER.map" in MEM
    assert 'data-testid={`memory-dialog-group-${cat}`}' in DLG


def test_categories_are_groups_not_tabs() -> None:
    # category chips are gone; log + abilities stay as their own views
    assert "MEMORY_CATEGORIES.map(([id, label]) =>" not in DLG
    assert "setTab('log')" in DLG and "setTab('abilities')" in DLG and "<AbilitiesPanel" in DLG
    # no per-category count
    assert ".length || ''" not in DLG


def test_title_body_cards_and_empty_group_rows() -> None:
    assert 'data-testid="memory-dialog-card"' in DLG
    assert 'className="ca-memory__title"' in DLG and "m.label" in DLG
    assert 'ca-arti-mem__text' in DLG
    assert ".ca-memory__title { font: 600" in CSS
    assert "memory-dialog-add-${cat}" in DLG
    for cat in ("taste", "about", "work", "assets"):
        assert ZH[f"memoryDialog.addYour.{cat}"].startswith("添加你的")
        assert EN[f"memoryDialog.addYour.{cat}"].startswith("Add your")
    assert ZH["memoryDialog.addYour.assets"] == "添加你的资产"


def test_bottom_chat_pill() -> None:
    assert 'data-testid="memory-dialog-chat-open"' in DLG
    assert "t('arti.memory.chatCta')" in DLG and "<ChatComposer" in DLG
    assert ZH["arti.memory.chatCta"] == "通过对话修改记忆"
    assert "export function ChatComposer(" in MEM


def test_measured_empty_state() -> None:
    assert "export function MemoryEmpty()" in MEM
    assert "Oops." in MEM
    assert "<MemoryEmpty />" in DLG and "<MemoryEmpty />" in MEM
    assert ZH["memoryDialog.emptyTitle"] == "Arti 还不认识你"
    assert ZH["memoryDialog.emptyDesc"] == "在对话中告诉 Arti 你的偏好，它就会记住来"
    assert EN["memoryDialog.emptyTitle"] == "Arti doesn't know you yet"


def test_dialog_width_measured() -> None:
    assert ".ca-memory { width: min(720px," in CSS


def test_no_focus_highlight_and_no_undo() -> None:
    # product ruling: opened from 「记忆已更新 ›」 → no highlighted entry, no 撤销
    assert "undoMemoryUpdated" not in DLG
    assert "memory-updated-undo" not in DLG
    assert "focus.undoable" not in DLG
    assert "useValue(memoryFocusAtom)" not in DLG
    assert "data-focus" not in DLG and "memory-focus-row" not in DLG
    assert "scrollIntoView" not in DLG


def test_delete_goes_through_confirm_only() -> None:
    btn = re.search(r'data-testid="memory-dialog-delete" onClick=\{\(\) => (\w+)\.set\(', DLG)
    assert btn and btn.group(1) == "confirmAtom"
    assert "danger: true" in DLG and "t('arti.memory.deleteTitle')" in DLG
    # removeMemory is only reachable from inside the confirm's run()
    assert DLG.count("removeMemory(") == 1
    assert "run: () => { void removeMemory(" in DLG


def test_existing_features_kept() -> None:
    for s in ("setOnboarding(true)", "importFiles", "updateMemory(", "remember(", "loadMemory()", "memory-dialog-error"):
        assert s in DLG
