"""#219: the built-in ComfyArt Agent is the default and works with only a WaveSpeed key; external CLIs are
optional; the custom-endpoint key is masked and never mixed with the WaveSpeed key. Mocks only, $0."""
from __future__ import annotations

import logging

import pytest

from conftest import write_settings
from ComfyArt.api import llm_key, providers as api_providers, settings, wavespeed
from ComfyArt.bot import get_provider, list_providers
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import ProviderStatus

WS_URL = "https://llm.wavespeed.ai/v1"
CUSTOM = "https://llm.example-cloud.com/v1"


@pytest.fixture()
def no_env_keys(monkeypatch):
    monkeypatch.delenv("COMFYART_LOCAL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)


def test_fresh_install_defaults(monkeypatch):
    monkeypatch.setattr(settings, "read_json", lambda *_a, **_k: {})
    assert settings.get_setting("bot-provider") == "local-llm"
    assert settings.mcp_enabled() and settings.bot_enabled()  # no switches to turn on first
    assert settings.get_setting("bot-local-llm-key") == ""


def test_builtin_is_first_and_renamed():
    first = list_providers()[0]
    assert first.id == "local-llm" and first.label == "ComfyArt Agent (built-in)"
    assert [p.id for p in list_providers()][1:5] == ["claude-code", "codex", "qwen-code", "deepseek-harness"]


def _available(self):
    async def probe():
        return ProviderStatus(available=True, version="1.0", logged_in=True)
    return probe


async def test_status_lists_builtin_first_even_with_claude_and_codex_detected(bot_client, monkeypatch, no_env_keys):
    for pid in ("claude-code", "codex"):
        monkeypatch.setattr(get_provider(pid), "probe", _available(None))
    for pid in ("qwen-code", "deepseek-harness"):
        async def gone():
            return ProviderStatus(available=False, detail="not found")
        monkeypatch.setattr(get_provider(pid), "probe", gone)
    monkeypatch.setattr(wavespeed, "key_source", lambda: ("ws-test-key", "settings"))

    async def models(self):
        return ProviderStatus(available=True, version="m", logged_in=True)
    monkeypatch.setattr(LocalLlmProvider, "probe", models)
    status = await (await bot_client.get("/comfyart/bot/status")).json()
    ids = [p["id"] for p in status["providers"]]
    assert status["enabled"] and ids[0] == "local-llm"
    by = {p["id"]: p for p in status["providers"]}
    assert by["claude-code"]["available"] and by["codex"]["available"]
    assert not by["qwen-code"]["available"] and not by["deepseek-harness"]["available"]  # greyed in the UI
    assert (await (await bot_client.get("/comfyart/settings")).json())["bot-provider"] == "local-llm"


async def test_no_wavespeed_key_gives_a_clear_status_not_a_401(no_env_keys, monkeypatch):
    monkeypatch.setattr(wavespeed, "key_source", lambda: ("", "none"))
    monkeypatch.setattr(settings, "read_json", lambda *_a, **_k: {})
    called = []

    async def boom(self):
        called.append(1)
        raise AssertionError("must not hit the endpoint without a key")
    monkeypatch.setattr(LocalLlmProvider, "probe", boom)
    st = await get_provider("local-llm").probe()
    assert not st.available and st.detail == api_providers.NO_KEY_DETAIL and not called
    res = await get_provider("local-llm").send(None, None, None)
    assert "WaveSpeed Key" in res.error and "401" not in res.error


def test_custom_url_key_used_and_wavespeed_key_never_sent_there(no_env_keys, monkeypatch):
    monkeypatch.setattr(wavespeed, "key_source", lambda: ("ws-test-key", "settings"))
    saved = {"bot-local-llm-url": CUSTOM}
    monkeypatch.setattr(settings, "read_json", lambda *_a, **_k: saved)
    p = api_providers.AgentLlmProvider(base_url=lambda: CUSTOM)
    assert llm_key.llm_api_key(CUSTOM) == "" and "Authorization" not in p._api_headers()
    saved["bot-local-llm-key"] = "custom-key"
    assert p._api_headers()["Authorization"] == "Bearer custom-key"
    saved["bot-local-llm-key"] = ""
    assert llm_key.llm_api_key(WS_URL) == "ws-test-key"  # empty box: only WaveSpeed URLs reuse the WaveSpeed key


async def test_key_is_masked_and_mask_round_trip_keeps_it(bot_client, caplog):
    caplog.set_level(logging.DEBUG)
    saved = await (await bot_client.put("/comfyart/settings", json={"bot-local-llm-key": "sk-secret-219"})).json()
    assert saved["bot-local-llm-key"] == settings.MASK
    got = await (await bot_client.get("/comfyart/settings")).json()
    assert got["bot-local-llm-key"] == settings.MASK and "sk-secret-219" not in str(got)
    await bot_client.put("/comfyart/settings", json={"bot-local-llm-key": settings.MASK, "bot-model-local-llm": "m2"})
    assert settings.get_setting("bot-local-llm-key") == "sk-secret-219"
    assert settings.get_setting("bot-model-local-llm") == "m2"  # model name is editable
    assert "sk-secret-219" not in caplog.text


async def test_saved_model_name_is_used_when_models_endpoint_fails(no_env_keys, monkeypatch):
    monkeypatch.setattr(wavespeed, "key_source", lambda: ("ws-test-key", "settings"))
    monkeypatch.setattr(settings, "read_json", lambda *_a, **_k: {"bot-model-local-llm": "my/model"})

    async def down(self):
        return ProviderStatus(available=False, detail="HTTP 500")

    async def empty(self):
        return []
    monkeypatch.setattr(LocalLlmProvider, "probe", down)
    monkeypatch.setattr(LocalLlmProvider, "list_models", empty)
    p = get_provider("local-llm")
    st = await p.probe()
    assert st.available and st.version == "my/model"
    assert await p.list_models() == ["my/model"]


def test_frontend_default_and_copy():
    from pathlib import Path
    import json
    root = Path(__file__).resolve().parent.parent
    bot = (root / "src/bot.ts").read_text()
    assert "p.id === BUILTIN_AGENT" in bot.split("export function defaultProvider")[1].split("}\n")[0]
    for lang, name, nd in (("zh", "ComfyArt Agent（内置）", "未检测到"), ("en", "ComfyArt Agent (built-in)", "Not detected")):
        loc = json.loads((root / f"src/locales/{lang}.json").read_text())
        assert loc["agentPicker.builtinAgent"] == name and loc["agentPicker.notDetected"] == nd
        assert "127.0.0.1" not in loc["botSettings.localLlmUrlHint"] and "llm.wavespeed.ai" in loc["botSettings.localLlmUrlHint"]
        for k in ("agentPanel.noWavespeedKey", "agentPanel.setWavespeedKey", "botSettings.localLlmModel", "botSettings.localLlmKey", "agentPicker.fellBackToBuiltin"):
            assert loc[k]
    assert "'password'" in (root / "src/ui/BotSettings.tsx").read_text()
