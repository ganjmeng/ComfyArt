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
    assert 'testid="memory-dialog-card"' in DLG
    assert "<MemoryRow key={m.id} item={m}" in DLG and "item.label" in MEM and "ca-arti-mem__text" in MEM
    assert ".ca-memory .ca-arti-mem__row .ca-arti-mem__label" in CSS and "--ca-mem-title-weight: 500" in CSS
    assert "memory-dialog-add-${cat}" in DLG
    for cat in ("taste", "about", "work", "assets"):
        assert ZH[f"memoryDialog.addYour.{cat}"].startswith("添加你的")
        assert EN[f"memoryDialog.addYour.{cat}"].startswith("Add ")
    assert ZH["memoryDialog.addYour.assets"] == "添加你的资产"


def test_bottom_chat_pill() -> None:
    assert 'data-testid="memory-dialog-chat-open"' in DLG
    assert "t('memoryDialog.chatCta')" in DLG and "<ChatComposer" in DLG
    assert ZH["memoryDialog.chatCta"] == "通过对话修改记忆" and EN["memoryDialog.chatCta"] == "Chat with Arti to edit memory"
    assert [EN[f"memoryDialog.group.{c}"] for c in ("taste", "about", "work", "assets")] == ["Visual taste", "About you", "How we work", "Reused assets"]
    assert "export function ChatComposer(" in MEM


def test_measured_empty_state() -> None:
    assert "export function MemoryEmpty()" in MEM
    assert "Oops." in MEM
    assert "<MemoryEmpty />" in DLG  # #436: Arti tab uses 暂无记忆+去完善; dialog keeps Oops
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
    # #434: dialog reuses the hover row; 删除 lives in the ··· menu and only opens the confirm
    assert "removeMemory(" not in DLG
    row = MEM[MEM.index("export function MemoryRow("):MEM.index("export function EditRow(")]
    assert row.count("removeMemory(") == 1 and "run: () => { void removeMemory(" in row
    assert "danger: true" in row and "t('arti.memory.deleteTitle')" in row
    assert "onClick={askDelete}" in row and "data-danger" in row


def test_hover_edit_and_delete_kept_434() -> None:
    row = MEM[MEM.index("export function MemoryRow("):MEM.index("export function EditRow(")]
    assert "t('memoryDialog.correctMemory')" in row and "arti-memory-menu-btn" in row
    edit = MEM[MEM.index("export function EditRow("):]
    assert "updateMemory(" in edit and "disabled={!dirty" in edit
    assert "<EditRow key={m.id}" in DLG and "onEdit={setEditing}" in DLG
    assert ".ca-memory .ca-arti-mem__row:hover .ca-arti-mem__actions" in CSS
    assert ZH["memoryDialog.correctMemory"] == "更正记忆"


def test_header_info_and_updated() -> None:
    assert 'data-testid="memory-dialog-info"' in DLG and 'data-testid="memory-dialog-updated"' in DLG
    assert ZH["memoryDialog.updatedAt"] == "更新于{0}" and ZH["memoryDialog.justNow"] == "此刻"


def test_existing_features_kept() -> None:
    for s in ("setOnboarding(true)", "importFiles", "<EditRow", "remember(", "loadMemory()", "memory-dialog-error"):
        assert s in DLG


def test_skeleton_and_saving_state() -> None:
    assert 'data-testid="memory-dialog-skeleton"' in DLG and "useValue(memoryLoadingAtom)" in DLG
    assert 'data-testid="memory-dialog-saving"' in DLG and "t('memoryDialog.saving')" in DLG
    assert ZH["memoryDialog.saving"] == "记忆更新中"
    src = (ROOT / "src/memory.ts").read_text()
    assert "memorySavingAtom.set({ id, text })" in src and "saving(id, correct(" in src and "saving(id, forget(" in src
