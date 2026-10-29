"""#436 Arti page 「我学会的 › 记忆」 entry + chat opens same dialog without highlight."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTI = (ROOT / "src/home/Arti.tsx").read_text()
MEM = (ROOT / "src/home/ArtiMemory.tsx").read_text()
HOME = (ROOT / "src/home/HomeApp.tsx").read_text()
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
DLG = (ROOT / "src/ui/MemoryDialog.tsx").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())
CSS = (ROOT / "src/styles/home.css").read_text()


def test_learned_three_tabs_still_present() -> None:
    assert 'TabBtn id="memory"' in ARTI
    assert 'TabBtn id="skills"' in ARTI
    assert 'TabBtn id="evolution"' in ARTI
    assert ZH["arti.tabMemory"] == "记忆"
    assert ZH["arti.tabSkills"] == "自进化技能"
    assert ZH["arti.tabEvolution"] == "进化日志"


def test_intro_actions_tell_yourself_and_learn_past() -> None:
    assert 'data-testid="arti-intro-actions"' in ARTI
    assert 'data-testid="arti-tell-yourself"' in ARTI
    assert 'data-testid="arti-learn-past"' in ARTI
    assert "openMemoryDialog({ onboard: true })" in ARTI
    assert ZH["arti.tellYourself"] == "说说你自己"
    assert ZH["arti.learnPast"] == "学习过往项目"
    assert EN["arti.tellYourself"] == "Tell me about yourself"
    assert "ca-arti__actions" in CSS


def test_empty_memory_tab_shows_go_complete() -> None:
    assert 'data-testid="arti-memory-tab-empty"' in MEM
    assert 'data-testid="arti-memory-go-complete"' in MEM
    assert "arti.memory.tabEmpty" in MEM
    assert "arti.memory.goComplete" in MEM
    assert ZH["arti.memory.tabEmpty"] == "暂无记忆"
    assert ZH["arti.memory.goComplete"] == "去完善"
    assert EN["arti.memory.tabEmpty"] == "No memories yet"
    assert EN["arti.memory.goComplete"] == "Complete setup"
    # empty tab opens onboarding on the shared dialog
    assert "openMemoryDialog({ onboard: true })" in MEM
    # Oops empty stays for the dialog, not the Arti tab
    assert 'data-testid="arti-memory-empty-guide"' not in MEM


def test_home_mounts_same_memory_dialog() -> None:
    assert "MemoryDialog" in HOME
    assert "<MemoryDialog" in HOME
    assert "openMemoryDialog" in DLG
    assert "memoryOnboardAtom" in DLG


def test_chat_memory_updated_opens_without_highlight() -> None:
    assert "openMemoryDialog()" in CHAT
    assert "memoryFocusAtom.set({ id, undoable: true })" not in CHAT
    assert "memoryFocusAtom.set(null)" in DLG or "memoryFocusAtom.set(null)" in CHAT or "openMemoryDialog" in DLG
    # helper clears focus before open
    assert "memoryFocusAtom.set(null)" in DLG
    assert "useValue(memoryFocusAtom)" not in DLG


def test_project_menu_memory_entry_kept() -> None:
    # canvas App still mounts MemoryDialog; project header still has memory entry
    app = (ROOT / "src/App.tsx").read_text()
    header = (ROOT / "src/ui/ProjectHeader.tsx").read_text()
    assert "<MemoryDialog" in app
    assert "memoryOpenAtom" in header or "common.memory" in header


def test_level_copy_matches_measured() -> None:
    assert ZH["arti.levelStatus"] == "Arti"
    assert ZH["arti.levelHint"] == "从零开始。越用，越像你"
    assert "Starting from zero" in EN["arti.levelHint"]


def test_onboard_option_cards_skip_confirm() -> None:
    assert 'data-testid="memory-onboard-welcome"' in DLG
    assert 'data-testid="memory-onboard-skip"' in DLG
    assert 'data-testid="memory-onboard-confirm"' in DLG
    assert 'data-testid="memory-onboard-options"' in DLG
    assert "ca-memory-onboard__opt" in DLG
    assert ZH["memoryDialog.skip"] == "跳过"
    assert ZH["memoryDialog.confirm"] == "确认"
    assert ZH["memoryDialog.ready"] == "准备好了"
    assert ZH["memoryDialog.nickBoss"] == "Boss"
    assert EN["memoryDialog.skip"] == "Skip"
    assert EN["memoryDialog.confirm"] == "Confirm"
    # no product-brand string in onboard copy
    assert "Lovart" not in DLG
    assert "Lovart" not in ZH["memoryDialog.welcomeBody"]
    assert "Lovart" not in ZH["memoryDialog.whatKindOfCreativeWork"]
