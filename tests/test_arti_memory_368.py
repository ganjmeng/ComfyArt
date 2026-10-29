"""#368 Arti P0-2 memory center — four groups + inline edit + chat CTA + assets (mock)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTI = (ROOT / "src/home/Arti.tsx").read_text()
MEM = (ROOT / "src/home/ArtiMemory.tsx").read_text()
MEMORY_TS = (ROOT / "src/memory.ts").read_text()
HOME_CSS = (ROOT / "src/styles/home.css").read_text()
EN = (ROOT / "src/locales/en.json").read_text()
ZH = (ROOT / "src/locales/zh.json").read_text()
HOME_APP = (ROOT / "src/home/HomeApp.tsx").read_text()


def test_arti_wires_memory_center_not_placeholder() -> None:
    assert "ArtiMemory" in ARTI
    assert "from './ArtiMemory'" in ARTI or 'from "./ArtiMemory"' in ARTI
    assert "arti-memory-placeholder" not in ARTI
    assert "<ArtiMemory" in ARTI


def test_four_memory_groups() -> None:
    assert 'data-testid="arti-memory-center"' in MEM
    assert 'data-testid="arti-memory-groups"' in MEM
    for cat in ("about", "work", "taste", "assets"):
        assert f"arti-memory-group-${{cat}}" in MEM or f'arti-memory-group-{cat}' in MEM
    assert "'about'" in MEM and "'work'" in MEM and "'taste'" in MEM and "'assets'" in MEM
    # labels align with MEMORY_CATEGORIES / CN groups
    assert "MEMORY_CATEGORIES" in MEM
    assert "基础信息" in ZH or '"memory.basics"' in ZH
    assert "协作方式" in ZH
    assert "审美偏好" in ZH
    assert "常用资产" in ZH


def test_inline_edit_crud_ui() -> None:
    assert "testid = 'arti-memory-row'" in MEM and 'data-testid={testid}' in MEM
    assert 'data-testid="arti-memory-edit-btn"' in MEM
    assert 'data-testid="arti-memory-menu-btn"' in MEM
    assert 'data-testid="arti-memory-row-menu"' in MEM
    assert "memoryDialog.correctMemory" in MEM
    assert "common.delete" in MEM
    assert 'data-testid="arti-memory-edit-row"' in MEM
    assert 'data-testid="arti-memory-edit-input"' in MEM
    assert 'data-testid="arti-memory-edit-plus"' in MEM
    assert 'data-testid="arti-memory-edit-cancel"' in MEM
    assert 'data-testid="arti-memory-edit-save"' in MEM
    # save disabled when unchanged
    assert "disabled={!dirty" in MEM or "disabled={!dirty ||" in MEM
    # delete needs confirm (not silent)
    assert "confirmAtom" in MEM
    assert "arti.memory.deleteTitle" in MEM
    assert "removeMemory" in MEM


def test_chat_to_edit_cta_and_composer() -> None:
    assert 'data-testid="arti-memory-chat-cta"' in MEM
    assert 'data-testid="arti-memory-chat-open"' in MEM
    assert "arti.memory.chatCta" in MEM
    assert 'data-testid="arti-memory-composer"' in MEM
    assert 'data-testid="arti-memory-composer-input"' in MEM
    assert 'data-testid="arti-memory-composer-plus"' in MEM
    assert 'data-testid="arti-memory-composer-plus-menu"' in MEM
    assert 'data-testid="arti-memory-upload-local"' in MEM
    assert 'data-testid="arti-memory-pick-library"' in MEM
    assert "arti.memory.uploadLocal" in MEM
    assert "arti.memory.pickLibrary" in MEM
    # #385: chat path uses intent parser (add/correct/forget), not hardcoded taste remember
    assert "runChatMemoryEdit" in MEM or "remember(" in MEM
    assert "arti.memory.sourceChat" in MEM


def test_assets_empty_add_flow() -> None:
    assert 'data-testid="arti-memory-assets-empty"' in MEM
    assert "arti.memory.addAssets" in MEM
    assert 'data-testid="arti-memory-assets-add"' in MEM
    assert 'data-testid="arti-memory-assets-purpose"' in MEM
    assert "memoryDialog.explainHowTheseAssetsShould" in MEM
    assert 'data-testid="arti-memory-assets-submit"' in MEM
    assert 'data-testid="arti-memory-assets-cancel"' in MEM


def test_persists_via_memory_apis_without_demo_seed() -> None:
    # #381: demo seeding is gone; empty store shows guidance only (behavior: tests/test_memory_safety_381.py)
    assert "ensureArtiDemoMemories" not in MEMORY_TS
    assert "updateMemory" in MEMORY_TS
    assert "removeMemory" in MEMORY_TS
    assert "memoryStore()" in MEMORY_TS  # #381: one store interface (server only, src/memoryStore.ts)
    assert "saveMemory" not in MEMORY_TS  # #381: removed — it resent stale state after a conflict
    # ArtiMemory loads + seeds through real APIs
    assert "loadMemory" in MEM
    assert "ensureArtiDemoMemories" not in MEM
    assert "updateMemory" in MEM
    assert "removeMemory" in MEM


def test_not_merged_with_brand_kit_or_canvas_only() -> None:
    assert "Brand Kit" not in MEM
    assert "brandKit" not in MEM.lower() or "Brand" not in MEM
    assert "AgentPanel" not in MEM
    assert "CanvasChat" not in MEM
    # account-level entry remains HomeApp rail → /arti
    assert "openView('arti')" in HOME_APP
    assert 'data-testid="arti-memory-center"' in MEM


def test_locales_zh_en_memory_center() -> None:
    for key in (
        "arti.memory.chatCta",
        "arti.memory.chatPlaceholder",
        "arti.memory.chatHelper",
        "arti.memory.addAssets",
        "arti.memory.uploadLocal",
        "arti.memory.pickLibrary",
        "arti.memory.deleteTitle",
    ):
        assert f'"{key}"' in ZH
        assert f'"{key}"' in EN
    assert "通过对话修改记忆" in ZH
    assert "+ 添加常用资产" in ZH or "添加常用资产" in ZH
    assert "从本地上传" in ZH
    assert "从资产库选择" in ZH


def test_css_memory_center_present() -> None:
    assert ".ca-arti-mem" in HOME_CSS
    assert ".ca-arti-mem__cta" in HOME_CSS
    assert ".ca-arti-mem__sticky" in HOME_CSS
    assert ".ca-arti-mem__edit" in HOME_CSS
    assert ".ca-arti-mem__addasset" in HOME_CSS


def test_out_of_scope_not_touched() -> None:
    """P0-1 shell stays; no P1 mascot / paid / schedules CRUD."""
    assert 'data-testid="arti-level-card"' in ARTI
    assert 'data-testid="arti-capabilities"' in ARTI
    assert "Schedules" not in MEM
    assert "mascot" not in MEM.lower()
    assert "trial" not in MEM.lower()
