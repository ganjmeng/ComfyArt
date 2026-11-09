"""Safe ProviderAdmin save-fail fixture: opt-in, no network, drafts kept → provider.saveFailed."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = (ROOT / "src/providerAdmin.ts").read_text(encoding="utf-8")
UI = (ROOT / "src/ui/ProviderAdmin.tsx").read_text(encoding="utf-8")
ZH = (ROOT / "src/locales/zh.json").read_text(encoding="utf-8")
EN = (ROOT / "src/locales/en.json").read_text(encoding="utf-8")


def test_fixture_is_opt_in_query_or_localstorage():
    assert "providerSaveFail" in ADMIN
    assert "comfyart.provider.saveFailMock" in ADMIN
    assert "function providerSaveFailFixture" in ADMIN or "export function providerSaveFailFixture" in ADMIN
    # Default path still calls send when fixture is off.
    assert "providerSaveFailFixture() ? rejectSaveFixture()" in ADMIN
    assert "send(`/comfyart/provider-admin/tool/${id}`, 'PUT', body)" in ADMIN
    assert "send('/comfyart/provider-admin/tools/batch', 'PUT', body)" in ADMIN


def test_forced_failure_is_plain_error_not_provider_admin_error():
    """Plain Error so failText uses t('provider.saveFailed'), not e.message."""
    assert "new Error('provider-save-fail-fixture')" in ADMIN
    assert "rejectSaveFixture" in ADMIN
    # Must not throw ProviderAdminError from the fixture path.
    fixture_chunk = ADMIN[ADMIN.find("rejectSaveFixture") : ADMIN.find("rejectSaveFixture") + 200]
    assert "ProviderAdminError" not in fixture_chunk


def test_fail_text_maps_plain_error_to_save_failed_key():
    assert "return t('provider.saveFailed')" in UI
    assert '"provider.saveFailed": "保存失败，已保留未提交更改"' in ZH
    assert '"provider.saveFailed": "Save failed; unsaved changes kept"' in EN


def test_save_catch_keeps_drafts_no_absorb():
    idx = UI.find("const saveOne")
    assert idx > 0
    chunk = UI[idx : idx + 900]
    catch = chunk[chunk.find(".catch") : chunk.find(".finally")]
    assert "setError(failText(e))" in catch
    assert "absorb" not in catch


def test_fixture_does_not_gate_load_or_restore():
    """Load/restore stay real so the panel still seeds Live; only writes are forced to fail."""
    assert "export const loadProviderAdmin = () => send('/comfyart/provider-admin', 'GET')" in ADMIN
    assert "export const restoreTool = (id: string) => send(`/comfyart/provider-admin/tool/${id}/restore`, 'POST')" in ADMIN
    # LLM save not gated — gap 4 shot is tool save-failed.
    assert "export const saveLlmProvider" in ADMIN
    llm = ADMIN[ADMIN.find("export const saveLlmProvider") : ADMIN.find("export const saveLlmProvider") + 120]
    assert "providerSaveFailFixture" not in llm
