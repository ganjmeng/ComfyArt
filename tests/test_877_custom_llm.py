"""#877: after the official DeepSeek default, a saved custom LLM still works; admin wins first.

Mocks only, $0. Cases (a)–(e) from issue comment 6763096420.
"""
from __future__ import annotations

from conftest import write_admin_llm_passthrough, write_settings
from ComfyArt.api import provider_admin, settings
from ComfyArt.api.bot_turns import provider_model
from ComfyArt.bot import get_provider
from ComfyArt.bot.providers import TurnHandle, TurnRequest


CUSTOM_URL = "http://127.0.0.1:8081/v1"
CUSTOM_MODEL = "qwen3"
OFFICIAL = "https://api.deepseek.com"


def _collect():
    async def emit(_ev):
        return None
    return emit


def test_a_settings_custom_only_uses_saved_url_and_model():
    write_settings(**{"bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL})
    assert provider_admin.llm_source() == "settings"
    assert provider_admin.llm_route() is None
    assert provider_model("local-llm") == CUSTOM_MODEL
    assert settings.get_setting("bot-local-llm-url") == CUSTOM_URL


def test_b_nothing_configured_is_official_deepseek_flash():
    assert settings.get_setting("bot-local-llm-url") == settings.SETTINGS_SPEC["bot-local-llm-url"]
    assert provider_admin.llm_source() == "default"
    route = provider_admin.llm_route()
    assert route["catalog_model"] == "deepseek-flash" and route["base_url"] == OFFICIAL
    assert provider_model("local-llm") == route["model"]


def test_defaults_written_back_are_not_custom():
    # PUT writes SETTINGS_SPEC values back; that must not count as a custom endpoint.
    write_settings(**{
        "bot-local-llm-url": settings.SETTINGS_SPEC["bot-local-llm-url"],
        "bot-model-local-llm": settings.SETTINGS_SPEC["bot-model-local-llm"],
        "bot-local-llm-key": "",
    })
    assert provider_admin.llm_source() == "default"
    assert provider_model("local-llm") == provider_admin.llm_route()["model"]


def test_whitespace_and_trailing_slash_match_the_default():
    write_settings(**{
        "bot-local-llm-url": "  " + settings.SETTINGS_SPEC["bot-local-llm-url"] + "/  ",
        "bot-model-local-llm": "  " + settings.SETTINGS_SPEC["bot-model-local-llm"] + "  ",
    })
    assert provider_admin.llm_source() == "default"


def test_d_admin_section_wins_over_settings_custom():
    write_settings(**{"bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL})
    provider_admin._save_section("llm", {"provider": "deepseek", "model": "deepseek-flash"})
    assert provider_admin.llm_source() == "admin"
    route = provider_admin.llm_route()
    assert route["catalog_model"] == "deepseek-flash" and route["base_url"] == OFFICIAL
    assert provider_model("local-llm") == route["model"]


def test_d_admin_wavespeed_passthrough_leaves_settings_alone():
    write_settings(**{"bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL})
    write_admin_llm_passthrough()
    assert provider_admin.llm_source() == "admin"
    assert provider_admin.llm_route() is None
    assert provider_model("local-llm") == CUSTOM_MODEL


def test_old_config_without_admin_section_still_goes_to_custom():
    write_settings(**{"bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL})
    assert provider_admin.active_llm() is None
    assert provider_admin.llm_source() == "settings"
    assert provider_model("local-llm") == CUSTOM_MODEL


def test_e_switch_writes_defaults_clears_key_and_does_not_touch_admin():
    write_settings(**{
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
        "bot-local-llm-key": "sk-custom-877",
    })
    assert provider_admin.llm_source() == "settings"
    # Not yet clicked: custom values stay put.
    assert settings.get_setting("bot-local-llm-url") == CUSTOM_URL
    assert settings.get_setting("bot-local-llm-key") == "sk-custom-877"
    masked = provider_admin.restore_official_llm_settings()
    assert provider_admin.llm_source() == "default"
    assert settings.get_setting("bot-local-llm-url") == settings.SETTINGS_SPEC["bot-local-llm-url"]
    assert settings.get_setting("bot-model-local-llm") == settings.SETTINGS_SPEC["bot-model-local-llm"]
    assert settings.get_setting("bot-local-llm-key") == ""
    assert masked["bot-local-llm-key"] == ""
    assert provider_admin.active_llm() is None
    assert provider_model("local-llm") == provider_admin.llm_route()["model"]


def test_e_switch_does_not_touch_a_saved_admin_section():
    write_settings(**{"bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL, "bot-local-llm-key": "sk-custom-877"})
    provider_admin._save_section("llm", {"provider": "deepseek", "model": "deepseek-flash"})
    before = provider_admin.active_llm()
    provider_admin.restore_official_llm_settings()
    assert provider_admin.active_llm() == before
    assert provider_admin.llm_source() == "admin"
    assert settings.get_setting("bot-local-llm-key") == ""


async def test_a_request_goes_to_the_custom_url(monkeypatch):
    write_settings(**{"bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL, "bot-local-llm-key": "sk-custom-877"})
    monkeypatch.setattr("ComfyArt.api.wavespeed.key_source", lambda: ("ws-test-key", "settings"))
    p = get_provider("local-llm")
    hits = []

    async def fake(session, method, url, *, headers, json_body=None, timeout=120):
        hits.append({"url": url, "model": (json_body or {}).get("model"), "auth": (headers or {}).get("Authorization")})
        if str(url).endswith("/chat/completions"):
            return {"choices": [{"message": {"content": "ok", "tool_calls": []}}]}
        return {"data": []}

    monkeypatch.setattr(p, "_request_json", fake)
    res = await p.send(TurnRequest(chat_id="c", user_text="hi", model=provider_model("local-llm")), _collect(), TurnHandle())
    assert not res.error
    chat = [h for h in hits if str(h["url"]).endswith("/chat/completions")]
    assert chat and CUSTOM_URL.rstrip("/") in chat[0]["url"]
    assert chat[0]["model"] == CUSTOM_MODEL
    assert chat[0]["auth"] == "Bearer sk-custom-877"
    assert all(OFFICIAL not in str(h["url"]) for h in hits)
    assert all(h["auth"] != "Bearer ws-test-key" for h in hits)


async def test_c_custom_failure_never_hits_official_and_offers_switch(monkeypatch):
    write_settings(**{"bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL})
    p = get_provider("local-llm")
    hits = []

    async def fake(session, method, url, *, headers, json_body=None, timeout=120):
        hits.append(url)
        if OFFICIAL in str(url):
            raise AssertionError("must not hit the official DeepSeek endpoint")
        raise ConnectionError("Cannot connect to host 127.0.0.1:8081")

    monkeypatch.setattr(p, "_request_json", fake)
    res = await p.send(TurnRequest(chat_id="c", user_text="hi", model=CUSTOM_MODEL, lang="zh"), _collect(), TurnHandle())
    assert "你设置的模型服务连接失败" in res.error
    assert "主机连不上" in res.error
    assert res.action == "use_official_llm"
    assert all(OFFICIAL not in str(u) for u in hits)
    official_hits = [u for u in hits if OFFICIAL in str(u)]
    assert official_hits == []


async def test_e_status_and_restore_endpoint(bot_client):
    write_settings(**{"bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL, "bot-local-llm-key": "sk-custom-877"})
    status = await (await bot_client.get("/comfyart/bot/status")).json()
    assert status["llm"]["source"] == "settings"
    assert status["llm"]["host"] == "127.0.0.1"
    admin = await (await bot_client.get("/comfyart/provider-admin")).json()
    # provider-admin is admin-only; 403 is fine, otherwise source must match
    if admin.get("llm"):
        assert admin["llm"]["source"] == "settings"
    res = await bot_client.post("/comfyart/bot/local-llm/use-official-default", json={})
    assert res.status == 200, await res.text()
    body = await res.json()
    assert body["bot-local-llm-url"] == settings.SETTINGS_SPEC["bot-local-llm-url"]
    assert body["bot-model-local-llm"] == settings.SETTINGS_SPEC["bot-model-local-llm"]
    assert body["bot-local-llm-key"] in ("", settings.MASK)
    assert settings.get_setting("bot-local-llm-key") == ""
    status = await (await bot_client.get("/comfyart/bot/status")).json()
    assert status["llm"]["source"] == "default"
    assert status["llm"]["host"] == ""


def test_public_state_and_settings_share_llm_source():
    write_settings(**{"bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL})
    assert provider_admin._public_state()["llm"]["source"] == provider_admin.llm_source() == "settings"
    provider_admin.restore_official_llm_settings()
    assert provider_admin._public_state()["llm"]["source"] == provider_admin.llm_source() == "default"


def test_frontend_shows_source_and_switch_copy():
    from pathlib import Path
    import json
    root = Path(__file__).resolve().parent.parent
    settings_src = (root / "src/ui/BotSettings.tsx").read_text()
    assert "llm-source" in settings_src and "useOfficialLlmDefault" in settings_src
    assert "botSettings.llmSourceOfficial" in settings_src
    assert "botSettings.llmSourceCustom" in settings_src
    chat = (root / "src/ui/ChatMessage.tsx").read_text()
    assert "use_official_llm" in chat and "useOfficialLlmDefault" in chat
    for lang in ("zh", "en"):
        loc = json.loads((root / f"src/locales/{lang}.json").read_text())
        assert loc["botSettings.customLlmFailed"]
        assert loc["botSettings.useOfficialDefault"]
        assert loc["botSettings.customLlmFailHost"]
        assert loc["botSettings.customLlmFailAuth"]
        assert loc["botSettings.customLlmFailTimeout"]
    assert json.loads((root / "src/locales/zh.json").read_text())["botSettings.useOfficialDefault"] == "切回官方默认"
    assert json.loads((root / "src/locales/zh.json").read_text())["botSettings.customLlmFailed"] == "你设置的模型服务连接失败"
