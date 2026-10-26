"""#315: Home and canvas Mode→Model read the same bot-model-* settings (no spurious Default)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_home_loads_settings_with_providers():
    home = (ROOT / "src/home/Home.tsx").read_text()
    assert "loadSettings" in home
    assert "loadProviders" in home
    # mount and menu-open both pull settings so AgentExtras sees bot-model-*
    assert "Promise.all([loadProviders(), loadSettings()])" in home
    assert home.count("Promise.all([loadProviders(), loadSettings()])") >= 2


def test_agent_extras_model_key_from_shared_settings():
    src = (ROOT / "src/ui/AgentPicker.tsx").read_text()
    assert "export function AgentExtras" in src
    block = src.split("export function AgentExtras")[1].split("export ")[0] if "export function AgentExtras" in src else src
    # shared settings key; empty string is the Default option only after settings loaded
    assert "bot-model-${providerId}" in block or "bot-model-${" in src
    assert "settingsAtom" in src
    assert "saveSettings({ [modelKey]" in src


def test_settings_spec_default_local_llm_model():
    """Server default for built-in agent is the 1017 flash model — Home must load it, not show Default."""
    spec = (ROOT / "api/settings.py").read_text()
    assert '"bot-model-local-llm": "deepseek/deepseek-v4.1-flash-1017"' in spec
