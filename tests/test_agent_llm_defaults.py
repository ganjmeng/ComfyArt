"""#120 / #30: the agent defaults to DeepSeek 4.1 flash on WaveSpeed's OpenAI-compatible endpoint with the
WaveSpeed key; a custom endpoint still works and never receives the WaveSpeed key. Mocks only."""
from __future__ import annotations

from ComfyArt.api import llm_key, settings, wavespeed
from ComfyArt.api.bot_turns import provider_model
from ComfyArt.api.providers import AgentLlmProvider
from ComfyArt.bot import get_provider
from ComfyArt.bot.local_llm import LocalLlmProvider

DEFAULT_URL = "https://llm.wavespeed.ai/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash-1017"


def test_defaults_resolve_to_wavespeed_deepseek(monkeypatch):
    monkeypatch.setattr(settings, "read_json", lambda *_a, **_k: {})
    assert settings.get_setting("bot-local-llm-url") == DEFAULT_URL
    assert provider_model("local-llm") == DEFAULT_MODEL


def test_saved_custom_endpoint_and_model_still_win(monkeypatch):
    monkeypatch.setattr(settings, "read_json", lambda *_a, **_k: {"bot-local-llm-url": "http://127.0.0.1:8081/v1", "bot-model-local-llm": "qwen3"})
    assert settings.get_setting("bot-local-llm-url") == "http://127.0.0.1:8081/v1"
    assert provider_model("local-llm") == "qwen3"


def test_registered_provider_keeps_the_original_agent_loop():
    # #219: probe/send/list_models only add the no-key status and the saved-model fallback, then call the original
    p = get_provider("local-llm")
    assert isinstance(p, AgentLlmProvider) and isinstance(p, LocalLlmProvider)
    for name in ("_history_messages", "_build_tools", "_mcp_list_tools", "_request_json"):
        assert getattr(AgentLlmProvider, name) is getattr(LocalLlmProvider, name)


def test_wavespeed_endpoint_uses_the_wavespeed_key(monkeypatch):
    monkeypatch.delenv("COMFYART_LOCAL_LLM_API_KEY", raising=False)
    monkeypatch.setattr(wavespeed, "key_source", lambda: ("ws-test-key", "settings"))
    assert llm_key.llm_api_key(DEFAULT_URL) == "ws-test-key"
    p = AgentLlmProvider(base_url=lambda: DEFAULT_URL)
    assert p._api_headers()["Authorization"] == "Bearer ws-test-key"


def test_custom_endpoint_never_gets_the_wavespeed_key(monkeypatch):
    monkeypatch.delenv("COMFYART_LOCAL_LLM_API_KEY", raising=False)
    monkeypatch.setattr(wavespeed, "key_source", lambda: ("ws-test-key", "settings"))
    assert llm_key.llm_api_key("http://127.0.0.1:8081/v1") == ""
    assert "Authorization" not in AgentLlmProvider(base_url=lambda: "http://127.0.0.1:8081/v1")._api_headers()


def test_explicit_llm_key_env_still_wins(monkeypatch):
    monkeypatch.setenv("COMFYART_LOCAL_LLM_API_KEY", "own-key")
    monkeypatch.setattr(wavespeed, "key_source", lambda: ("ws-test-key", "settings"))
    assert llm_key.llm_api_key(DEFAULT_URL) == "own-key"
