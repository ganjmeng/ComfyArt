"""#349: Home↔canvas Model / Image·Video same source + FieldSelect Model + DirectPills parity."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_agent_extras_model_is_fieldselect_shared_settings():
    src = (ROOT / "src/ui/AgentPicker.tsx").read_text()
    block = src.split("export function AgentExtras")[1]
    assert "FieldSelect" in block
    assert "bot-model-${providerId}" in block or "bot-model-${" in src
    assert "settingsAtom" in src
    assert "saveSettings({ [modelKey]" in src
    assert "<select" not in block
    # Default option still present via FieldSelect options (empty id)
    assert "common.default" in block


def test_home_and_composer_both_use_agent_extras_and_direct_pills():
    home = (ROOT / "src/home/Home.tsx").read_text()
    composer = (ROOT / "src/ui/Composer.tsx").read_text()
    assert "AgentExtras" in home and "AgentExtras" in composer
    assert "DirectPills" in home and "DirectPills" in composer
    assert "from '../ui/DirectPills'" in home or 'from "../ui/DirectPills"' in home
    assert "from './DirectPills'" in composer or 'from "./DirectPills"' in composer
    # shortLabel on closed Mode pill (both surfaces)
    assert "shortLabel" in home and "shortLabel" in composer


def test_home_and_composer_reload_settings_on_mode_open():
    """Same bot-model-* after open: both pull loadSettings with providers."""
    home = (ROOT / "src/home/Home.tsx").read_text()
    composer = (ROOT / "src/ui/Composer.tsx").read_text()
    assert "Promise.all([loadProviders(), loadSettings()])" in home
    assert "Promise.all([loadProviders(), loadSettings()])" in composer


def test_direct_pills_single_store():
    src = (ROOT / "src/ui/DirectPills.tsx").read_text()
    assert "modelPrefsAtom" in src
    assert "saveDirectSettings" in src
    assert "ModelPill" in src and "SettingsPill" in src


def test_no_native_select_on_key_surfaces():
    surfaces = [
        "src/ui/AgentPicker.tsx",
        "src/home/Home.tsx",
        "src/ui/Composer.tsx",
        "src/ui/AudioDialog.tsx",
        "src/ui/BotSettings.tsx",
        "src/ui/StyleToolbars.tsx",
        "src/ui/KitEditor.tsx",
        "src/ui/WorkflowsDialog.tsx",
        "src/ui/FieldSelect.tsx",
    ]
    for rel in surfaces:
        text = (ROOT / rel).read_text()
        assert "<select" not in text, rel


def test_no_lovart_empty_guide_on_canvas():
    """#349: empty canvas stays empty — no Lovart empty-state chrome introduced."""
    for rel in ["src/ui/Composer.tsx", "src/App.tsx", "src/ui/CanvasTools.tsx"]:
        text = (ROOT / rel).read_text().lower()
        assert "lovart" not in text, rel
        assert "empty-state" not in text and "emptystate" not in text, rel
