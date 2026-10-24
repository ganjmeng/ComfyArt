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
    assert settings.bot_enabled()  # the Agent works without turning anything on first
    assert not settings.mcp_enabled()  # but external MCP access stays off by default
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
    zh = json.loads((root / "src/locales/zh.json").read_text())["agentPicker.enableMcpConfirm"]
    en = json.loads((root / "src/locales/en.json").read_text())["agentPicker.enableMcpConfirm"]
    assert zh == "外部 Agent 需要开启 MCP，开启后本机的 MCP 客户端可以读写当前画布。开启？"
    assert en == "External agents need MCP. Once on, MCP clients on this computer can read and edit your canvas. Turn on?"


def _rpc(method):
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": {}}


async def test_external_mcp_refused_while_off_but_builtin_agent_works(bot_client):
    import aiohttp
    write_settings(**{"enable-mcp": False, "enable-bot": True})
    # an outside MCP client (or an external tool) is refused while the switch is off
    resp = await bot_client.post("/comfyart/mcp", json=_rpc("tools/list"))
    assert resp.status == 403
    forged = await bot_client.post("/comfyart/mcp", json=_rpc("tools/list"), headers={"X-ComfyArt-Internal": "guess"})
    assert forged.status == 403
    # the built-in agent still gets its canvas tools through the internal channel
    agent = get_provider("local-llm")
    async with aiohttp.ClientSession() as session:
        tools = await agent._mcp_list_tools(session, str(bot_client.make_url("/comfyart/mcp")))
    assert tools and all(t.get("name") for t in tools)
    status = await (await bot_client.get("/comfyart/bot/status")).json()
    assert status["enabled"] is True


async def test_external_tool_send_refused_while_mcp_off(bot_client):
    write_settings(**{"enable-mcp": False, "enable-bot": True})
    chat = (await (await bot_client.post("/comfyart/bot/chats", json={"project": "p", "provider": "codex"})).json())["chat"]
    resp = await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send", json={"text": "hi"})
    assert resp.status == 403
    assert "MCP" in (await resp.json())["error"]


def test_internal_token_not_in_settings_or_logs(caplog):
    from ComfyArt.api import mcp
    assert mcp.INTERNAL_TOKEN not in repr(settings.all_settings())
    assert mcp.INTERNAL_TOKEN not in caplog.text


async def test_settings_file_is_private(bot_client):
    import os
    import stat
    resp = await bot_client.put("/comfyart/settings", json={"bot-local-llm-key": "sk-custom-secret"})
    assert resp.status == 200
    mode = stat.S_IMODE(os.stat(settings._file()).st_mode)
    assert mode == 0o600, oct(mode)


async def _put(client, body):
    resp = await client.put("/comfyart/settings", json=body)
    assert resp.status == 200
    return await resp.json()


async def test_hostname_change_clears_custom_key(bot_client):
    await _put(bot_client, {"bot-local-llm-url": CUSTOM, "bot-local-llm-key": "sk-custom-secret"})
    # same host, other path: the key stays
    out = await _put(bot_client, {"bot-local-llm-url": CUSTOM + "/beta", "bot-local-llm-key": settings.MASK})
    assert out["bot-local-llm-key"] == settings.MASK and settings.get_setting("bot-local-llm-key") == "sk-custom-secret"
    # a new hostname: the stored key is cleared, the user must re-enter it
    out = await _put(bot_client, {"bot-local-llm-url": "https://other-llm.example.org/v1", "bot-local-llm-key": settings.MASK})
    assert out["bot-local-llm-key"] == "" and settings.get_setting("bot-local-llm-key") == ""
    # a new key sent together with the new URL is kept
    await _put(bot_client, {"bot-local-llm-url": CUSTOM, "bot-local-llm-key": "sk-new"})
    assert settings.get_setting("bot-local-llm-key") == "sk-new"


async def test_back_to_wavespeed_host_clears_key_and_uses_wavespeed_key(bot_client, no_env_keys, monkeypatch):
    await _put(bot_client, {"bot-local-llm-url": CUSTOM, "bot-local-llm-key": "sk-custom-secret"})
    await _put(bot_client, {"bot-local-llm-url": WS_URL})
    assert settings.get_setting("bot-local-llm-key") == ""
    monkeypatch.setenv("WAVESPEED_API_KEY", "ws-mock-key")
    assert llm_key.llm_api_key(WS_URL) == "ws-mock-key"


def test_url_change_helper_copy():
    from pathlib import Path
    import json
    root = Path(__file__).resolve().parent.parent
    zh = json.loads((root / "src/locales/zh.json").read_text())["botSettings.urlChangedReenterKey"]
    en = json.loads((root / "src/locales/en.json").read_text())["botSettings.urlChangedReenterKey"]
    assert zh == "地址已更改，请重新填写 Key" and en == "URL changed. Please re-enter the key."
    ui = (root / "src/ui/BotSettings.tsx").read_text()
    assert 'className="ca-menu__key">{t(\'botSettings.urlChangedReenterKey\')}' in ui  # same grey style as "Not detected"
