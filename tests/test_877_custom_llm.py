"""#877: llm_mode official/custom, admin first, custom config is never cleared.

Mocks only, $0. Final tech spec for PR #884.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import write_admin_llm_passthrough, write_settings
from ComfyArt.api import provider_admin, settings
from ComfyArt.api.bot_turns import provider_model
from ComfyArt.bot import get_provider
from ComfyArt.bot.local_llm import LlmHttpError
from ComfyArt.bot.providers import TurnHandle, TurnRequest


CUSTOM_URL = "http://127.0.0.1:8081/v1"
CUSTOM_MODEL = "qwen3"
CUSTOM_KEY = "sk-custom-877"
OFFICIAL = "https://api.deepseek.com"
ROOT = Path(__file__).resolve().parent.parent


def _collect():
    async def emit(_ev):
        return None
    return emit


async def _send(monkeypatch, *, expect_error=False):
    """Send one turn and return (result, hits) where each hit is the actual request."""
    p = get_provider("local-llm")
    hits = []

    async def fake(session, method, url, *, headers, json_body=None, timeout=120):
        hits.append({"url": str(url), "headers": dict(headers or {}), "body": json_body})
        if str(url).endswith("/chat/completions"):
            return {"choices": [{"message": {"content": "ok", "tool_calls": []}}]}
        return {"data": []}

    monkeypatch.setattr(p, "_request_json", fake)
    res = await p.send(
        TurnRequest(chat_id="c", user_text="hi", model=provider_model("local-llm"), lang="zh"),
        _collect(),
        TurnHandle(),
    )
    if not expect_error:
        assert not res.error, res.error
    return res, hits


def test_settings_spec_has_llm_mode():
    assert settings.SETTINGS_SPEC["llm_mode"] == ""
    assert settings.CHOICES["llm_mode"] == ("official", "custom")


def test_a_settings_custom_only_uses_saved_url_and_model():
    write_settings(**{"bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL})
    assert provider_admin.llm_source() == "settings"
    assert provider_admin.llm_route() is None
    assert provider_model("local-llm") == CUSTOM_MODEL
    assert settings.get_setting("bot-local-llm-url") == CUSTOM_URL


def test_b_nothing_configured_is_official_deepseek_flash():
    assert settings.get_setting("bot-local-llm-url") == settings.SETTINGS_SPEC["bot-local-llm-url"]
    assert settings.get_setting("llm_mode") == ""
    assert provider_admin.llm_source() == "default"
    route = provider_admin.llm_route()
    assert route["catalog_model"] == "deepseek-flash" and route["base_url"] == OFFICIAL
    assert provider_model("local-llm") == route["model"]


def test_defaults_written_back_are_not_custom_when_mode_empty():
    write_settings(**{
        "bot-local-llm-url": settings.SETTINGS_SPEC["bot-local-llm-url"],
        "bot-model-local-llm": settings.SETTINGS_SPEC["bot-model-local-llm"],
        "bot-local-llm-key": "",
        "llm_mode": "",
    })
    assert provider_admin.llm_source() == "default"
    assert provider_model("local-llm") == provider_admin.llm_route()["model"]


def test_whitespace_and_trailing_slash_match_the_default():
    write_settings(**{
        "bot-local-llm-url": "  " + settings.SETTINGS_SPEC["bot-local-llm-url"] + "/  ",
        "bot-model-local-llm": "  " + settings.SETTINGS_SPEC["bot-model-local-llm"] + "  ",
        "llm_mode": "",
    })
    assert provider_admin.llm_source() == "default"


def test_custom_mode_with_default_url_and_model_is_valid():
    write_settings(**{
        "llm_mode": "custom",
        "bot-local-llm-url": settings.SETTINGS_SPEC["bot-local-llm-url"],
        "bot-model-local-llm": settings.SETTINGS_SPEC["bot-model-local-llm"],
    })
    assert provider_admin.llm_source() == "settings"
    assert not provider_admin.settings_llm_incomplete()
    assert provider_admin.llm_route() is None
    assert provider_model("local-llm") == settings.SETTINGS_SPEC["bot-model-local-llm"]


@pytest.mark.parametrize("mode", ["official", "custom", ""])
def test_d_admin_section_wins_whatever_llm_mode_is(mode):
    write_settings(**{
        "llm_mode": mode,
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
    })
    provider_admin._save_section("llm", {"provider": "deepseek", "model": "deepseek-flash"})
    assert provider_admin.llm_source() == "admin"
    route = provider_admin.llm_route()
    assert route["catalog_model"] == "deepseek-flash" and route["base_url"] == OFFICIAL
    assert provider_model("local-llm") == route["model"]


def test_d_admin_wavespeed_passthrough_leaves_settings_alone():
    write_settings(**{"llm_mode": "custom", "bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL})
    write_admin_llm_passthrough()
    assert provider_admin.llm_source() == "admin"
    assert provider_admin.llm_route() is None
    assert provider_model("local-llm") == CUSTOM_MODEL


def test_old_config_without_llm_mode_still_goes_to_custom():
    write_settings(**{"bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL, "llm_mode": ""})
    assert provider_admin.active_llm() is None
    assert settings.get_setting("llm_mode") == ""
    assert provider_admin.llm_source() == "settings"
    assert provider_model("local-llm") == CUSTOM_MODEL


async def test_empty_mode_inferred_and_first_save_writes_custom(bot_client, monkeypatch):
    write_settings(**{
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
        "bot-local-llm-key": CUSTOM_KEY,
        "llm_mode": "",
    })
    assert settings.get_setting("llm_mode") == ""
    assert provider_admin.llm_source() == "settings"
    res, hits = await _send(monkeypatch)
    chat = [h for h in hits if h["url"].endswith("/chat/completions")]
    assert chat and CUSTOM_URL.rstrip("/") in chat[0]["url"]
    assert chat[0]["body"]["model"] == CUSTOM_MODEL
    # First Save (any PUT) persists the inferred mode; URL/model/key stay put.
    resp = await bot_client.put("/comfyart/settings", json={"enable-bot": True})
    assert resp.status == 200, await resp.text()
    assert settings.get_setting("llm_mode") == "custom"
    assert settings.get_setting("bot-local-llm-url") == CUSTOM_URL
    assert settings.get_setting("bot-model-local-llm") == CUSTOM_MODEL
    assert settings.get_setting("bot-local-llm-key") == CUSTOM_KEY


async def test_save_official_then_custom_keeps_url_model_key(bot_client, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-official-877")
    put = await bot_client.put("/comfyart/settings", json={
        "llm_mode": "custom",
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
        "bot-local-llm-key": CUSTOM_KEY,
    })
    assert put.status == 200, await put.text()
    assert settings.get_setting("llm_mode") == "custom"

    official = await bot_client.put("/comfyart/settings", json={
        "llm_mode": "official",
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
        "bot-local-llm-key": settings.MASK,
    })
    assert official.status == 200, await official.text()
    assert settings.get_setting("llm_mode") == "official"
    assert settings.get_setting("bot-local-llm-url") == CUSTOM_URL
    assert settings.get_setting("bot-model-local-llm") == CUSTOM_MODEL
    assert settings.get_setting("bot-local-llm-key") == CUSTOM_KEY
    assert provider_admin.llm_source() == "default"

    res, hits = await _send(monkeypatch)
    assert all(OFFICIAL in h["url"] or not h["url"].endswith("/chat/completions") or OFFICIAL in h["url"] for h in hits)
    chat = [h for h in hits if h["url"].endswith("/chat/completions")]
    assert chat and all(OFFICIAL in h["url"] for h in chat)
    assert all(CUSTOM_URL.rstrip("/") not in h["url"] for h in hits)
    assert all(CUSTOM_KEY not in json.dumps(h, ensure_ascii=False) for h in hits)

    custom = await bot_client.put("/comfyart/settings", json={
        "llm_mode": "custom",
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
        "bot-local-llm-key": settings.MASK,
    })
    assert custom.status == 200, await custom.text()
    assert settings.get_setting("llm_mode") == "custom"
    assert settings.get_setting("bot-local-llm-url") == CUSTOM_URL
    assert settings.get_setting("bot-model-local-llm") == CUSTOM_MODEL
    assert settings.get_setting("bot-local-llm-key") == CUSTOM_KEY
    assert provider_admin.llm_source() == "settings"

    res, hits = await _send(monkeypatch)
    chat = [h for h in hits if h["url"].endswith("/chat/completions")]
    assert chat and CUSTOM_URL.rstrip("/") in chat[0]["url"]
    assert chat[0]["body"]["model"] == CUSTOM_MODEL
    assert chat[0]["headers"].get("Authorization") == f"Bearer {CUSTOM_KEY}"
    assert all(OFFICIAL not in h["url"] for h in hits)


async def test_requests_only_reach_official_while_mode_is_official(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-official-877")
    write_settings(**{
        "llm_mode": "official",
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
        "bot-local-llm-key": CUSTOM_KEY,
    })
    assert provider_admin.llm_source() == "default"
    res, hits = await _send(monkeypatch)
    chat = [h for h in hits if h["url"].endswith("/chat/completions")]
    assert chat and all(OFFICIAL in h["url"] for h in chat)
    assert all(CUSTOM_URL.rstrip("/") not in h["url"] for h in hits)

    write_settings(**{
        "llm_mode": "custom",
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
        "bot-local-llm-key": CUSTOM_KEY,
    })
    assert provider_admin.llm_source() == "settings"
    res, hits = await _send(monkeypatch)
    chat = [h for h in hits if h["url"].endswith("/chat/completions")]
    assert chat and CUSTOM_URL.rstrip("/") in chat[0]["url"]
    assert all(OFFICIAL not in h["url"] for h in hits)


async def test_switching_llm_mode_does_not_clear_the_219_key(bot_client):
    """Switching mode does not change the URL, so the #219 host-change key-clear rule is not triggered."""
    await bot_client.put("/comfyart/settings", json={
        "llm_mode": "custom",
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
        "bot-local-llm-key": CUSTOM_KEY,
    })
    await bot_client.put("/comfyart/settings", json={
        "llm_mode": "official",
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
        "bot-local-llm-key": settings.MASK,
    })
    assert settings.get_setting("bot-local-llm-url") == CUSTOM_URL
    assert settings.get_setting("bot-local-llm-key") == CUSTOM_KEY
    await bot_client.put("/comfyart/settings", json={
        "llm_mode": "custom",
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
        "bot-local-llm-key": settings.MASK,
    })
    assert settings.get_setting("bot-local-llm-url") == CUSTOM_URL
    assert settings.get_setting("bot-local-llm-key") == CUSTOM_KEY
    # Host change still clears the key (#219).
    out = await (await bot_client.put("/comfyart/settings", json={
        "bot-local-llm-url": "https://other-llm.example.org/v1",
        "bot-local-llm-key": settings.MASK,
    })).json()
    assert out["bot-local-llm-key"] == "" and settings.get_setting("bot-local-llm-key") == ""


async def test_a_request_goes_to_the_custom_url(monkeypatch):
    write_settings(**{
        "llm_mode": "custom",
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
        "bot-local-llm-key": CUSTOM_KEY,
    })
    monkeypatch.setattr("ComfyArt.api.wavespeed.key_source", lambda: ("ws-test-key", "settings"))
    res, hits = await _send(monkeypatch)
    chat = [h for h in hits if h["url"].endswith("/chat/completions")]
    assert chat and CUSTOM_URL.rstrip("/") in chat[0]["url"]
    assert chat[0]["body"]["model"] == CUSTOM_MODEL
    assert chat[0]["headers"].get("Authorization") == f"Bearer {CUSTOM_KEY}"
    assert all(OFFICIAL not in h["url"] for h in hits)
    assert all("ws-test-key" not in json.dumps(h, ensure_ascii=False) for h in hits)


async def test_c_custom_failure_never_hits_official_and_offers_switch(monkeypatch):
    write_settings(**{"llm_mode": "custom", "bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL})
    p = get_provider("local-llm")
    hits = []

    async def fake(session, method, url, *, headers, json_body=None, timeout=120):
        hits.append(str(url))
        if OFFICIAL in str(url):
            raise AssertionError("must not hit the official DeepSeek endpoint")
        raise ConnectionError("Cannot connect to host 127.0.0.1:8081")

    monkeypatch.setattr(p, "_request_json", fake)
    res = await p.send(TurnRequest(chat_id="c", user_text="hi", model=CUSTOM_MODEL, lang="zh"), _collect(), TurnHandle())
    assert res.error == "你设置的模型服务连接失败：连不上该地址，请检查地址是否正确、服务是否已启动"
    assert res.action == "use_official_llm"
    assert all(OFFICIAL not in u for u in hits)
    assert [u for u in hits if OFFICIAL in u] == []


async def test_empty_custom_key_does_not_leak_wavespeed_or_official_keys(monkeypatch):
    """A custom endpoint (e.g. local Ollama) with an empty key must not receive the WaveSpeed
    or official DeepSeek key, in Authorization or anywhere else, and must not call official."""
    ollama = "http://localhost:11434/v1"
    ws_key = "ws-secret-877-noleak"
    ds_key = "sk-deepseek-877-noleak"
    write_settings(**{
        "llm_mode": "custom",
        "bot-local-llm-url": ollama,
        "bot-model-local-llm": CUSTOM_MODEL,
        "bot-local-llm-key": "",
    })
    monkeypatch.delenv("COMFYART_LOCAL_LLM_API_KEY", raising=False)
    monkeypatch.setenv("WAVESPEED_API_KEY", ws_key)
    monkeypatch.setenv("DEEPSEEK_API_KEY", ds_key)
    monkeypatch.setattr("ComfyArt.api.wavespeed.key_source", lambda: (ws_key, "env"))
    assert provider_admin.llm_source() == "settings"
    res, hits = await _send(monkeypatch)
    assert hits and all(OFFICIAL not in h["url"] for h in hits)
    assert any(ollama.rstrip("/") in h["url"] for h in hits)
    for h in hits:
        blob = json.dumps(h, ensure_ascii=False)
        assert ws_key not in blob and ds_key not in blob
        assert ws_key not in (h["headers"] or {}) and ds_key not in str(h["headers"])


@pytest.mark.parametrize("patch, expected", [
    ({"bot-local-llm-url": "", "bot-model-local-llm": CUSTOM_MODEL}, "还没配好：请选择服务商并填写 API Key，再选择模型"),
    ({"bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": ""}, "还没配好：请选择模型。"),
])
async def test_custom_mode_blank_url_or_model_is_flagged(monkeypatch, patch, expected):
    write_settings(**{"llm_mode": "custom", **patch})
    assert provider_admin.settings_llm_incomplete()
    p = get_provider("local-llm")
    hits = []

    async def fake(session, method, url, *, headers, json_body=None, timeout=120):
        hits.append(str(url))
        raise AssertionError("custom mode that isn't set up must not send any request")

    monkeypatch.setattr(p, "_request_json", fake)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-official-877")
    res = await p.send(TurnRequest(chat_id="c", user_text="hi", model="x", lang="zh"), _collect(), TurnHandle())
    assert res.error == expected
    assert not res.action
    assert hits == []
    assert all(OFFICIAL not in u for u in hits)


async def test_custom_mode_with_default_values_sends_to_wavespeed(monkeypatch):
    write_settings(**{
        "llm_mode": "custom",
        "bot-local-llm-url": settings.SETTINGS_SPEC["bot-local-llm-url"],
        "bot-model-local-llm": settings.SETTINGS_SPEC["bot-model-local-llm"],
        "bot-local-llm-key": "",
    })
    monkeypatch.delenv("COMFYART_LOCAL_LLM_API_KEY", raising=False)
    monkeypatch.setattr("ComfyArt.api.wavespeed.key_source", lambda: ("ws-flash-key", "env"))
    res, hits = await _send(monkeypatch)
    chat = [h for h in hits if h["url"].endswith("/chat/completions")]
    ws = str(settings.SETTINGS_SPEC["bot-local-llm-url"]).rstrip("/")
    assert chat and ws in chat[0]["url"]
    assert chat[0]["body"]["model"] == settings.SETTINGS_SPEC["bot-model-local-llm"]
    assert all(OFFICIAL not in h["url"] for h in hits)



def _http_copy(n, lang):
    if lang == "zh":
        return f"你设置的模型服务返回了错误（HTTP {n}），请检查模型名是否正确，或稍后再试"
    return f"Your model service returned an error (HTTP {n}). Check the model name, or try again later."


def _client_connector_error():
    from aiohttp import ClientConnectorError
    from aiohttp.client_reqrep import ConnectionKey
    key = ConnectionKey("api.x.com", 443, True, True, None, None, None)
    return ClientConnectorError(key, ConnectionRefusedError(111, "Connection refused"))


def _timeout_error():
    import asyncio
    return asyncio.TimeoutError()


@pytest.mark.parametrize("err,want,code", [
    ("Cannot connect to host api.x.com:443 ssl:default [Connection refused]", "host", None),
    (_client_connector_error(), "host", None),
    ("Cannot connect to host 127.0.0.1:5000 ssl:default [Connection refused] for http://127.0.0.1:5000/v1", "host", None),
    ("Read timed out (port 443)", "timeout", None),
    (_timeout_error(), "timeout", None),
    ("HTTP 404", "http", 404),
    ("status=429", "http", 429),
    ("HTTP/1.1 503", "http", 503),
    ("status_code: 401", "auth", 401),
    ("HTTP 403", "auth", 403),
])
def test_error_classification_exact_cases(err, want, code):
    """Host/timeout must not treat a port (443, 5000) as an HTTP status; http copy n is the real code."""
    assert provider_admin._settings_fail_reason(err) == want
    copy_zh = provider_admin.settings_llm_fail_copy(err, "zh")
    copy_en = provider_admin.settings_llm_fail_copy(err, "en")
    if want == "http":
        assert provider_admin._settings_fail_http_status(err) == code
        assert copy_zh == _http_copy(code, "zh")
        assert copy_en == _http_copy(code, "en")
        assert f"HTTP {code}" in copy_zh and f"HTTP {code}" in copy_en
    elif want == "auth":
        assert provider_admin._settings_fail_http_status(err) == code
        assert copy_zh == provider_admin._SETTINGS_FAIL["zh"]["auth"]
        assert copy_en == provider_admin._SETTINGS_FAIL["en"]["auth"]
    else:
        assert provider_admin._settings_fail_http_status(err) is None
        assert copy_zh == provider_admin._SETTINGS_FAIL["zh"][want]
        assert copy_en == provider_admin._SETTINGS_FAIL["en"][want]
        assert "HTTP 443" not in (copy_zh or "") and "HTTP 500" not in (copy_zh or "")
        assert "HTTP 443" not in (copy_en or "") and "HTTP 500" not in (copy_en or "")


def test_structured_status_wins_over_the_error_string():
    assert provider_admin._settings_fail_reason("upstream failed", status=429) == "http"
    assert provider_admin.settings_llm_fail_copy("upstream failed", "zh", status=404) == _http_copy(404, "zh")
    class _Err(Exception):
        def __init__(self):
            super().__init__("no number in this message")
            self.status_code = 500
    assert provider_admin._settings_fail_reason(_Err()) == "http"
    assert provider_admin.settings_llm_fail_copy(_Err(), "zh") == _http_copy(500, "zh")


def test_http_429_and_5xx_are_not_host_unreachable():
    assert provider_admin._settings_fail_reason("just http  and nothing") != "host"
    assert provider_admin._settings_fail_reason("upstream 5xx") != "host"
    assert provider_admin._settings_fail_reason("got a 429") is None
    assert provider_admin.settings_llm_fail_copy("got a 429", "zh") is None


@pytest.mark.parametrize("factory,want_zh", [
    (lambda: LlmHttpError(404, "model not found"), "HTTP 404"),
    (lambda: LlmHttpError(429, "too many requests"), "HTTP 429"),
    (lambda: LlmHttpError(503, "unavailable"), "HTTP 503"),
    (lambda: LlmHttpError(401, "unauthorized"), "你设置的模型服务拒绝了访问"),
    (lambda: LlmHttpError(403, "forbidden"), "你设置的模型服务拒绝了访问"),
    (lambda: ConnectionError("Cannot connect to host api.x.com:443 ssl:default [Connection refused]"), "连不上该地址，请检查地址是否正确、服务是否已启动"),
    (lambda: TimeoutError("Read timed out (port 443)"), "你设置的模型服务响应超时"),
])
async def test_error_mapping_on_the_actual_request(monkeypatch, factory, want_zh):
    write_settings(**{"llm_mode": "custom", "bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL})
    p = get_provider("local-llm")
    hits = []
    exc = factory()

    async def fake(session, method, url, *, headers, json_body=None, timeout=120):
        hits.append(str(url))
        if OFFICIAL in str(url):
            raise AssertionError("must not hit official")
        raise exc

    monkeypatch.setattr(p, "_request_json", fake)
    res = await p.send(TurnRequest(chat_id="c", user_text="hi", model=CUSTOM_MODEL, lang="zh"), _collect(), TurnHandle())
    assert want_zh in (res.error or ""), res.error
    assert res.action == "use_official_llm"
    assert all(OFFICIAL not in u for u in hits)


async def test_invalid_llm_mode_is_rejected_empty_is_inferred(bot_client):
    bad = await bot_client.put("/comfyart/settings", json={"llm_mode": "foo"})
    assert bad.status == 400
    write_settings(**{
        "bot-local-llm-url": CUSTOM_URL,
        "bot-model-local-llm": CUSTOM_MODEL,
        "llm_mode": "",
    })
    ok = await bot_client.put("/comfyart/settings", json={"llm_mode": ""})
    assert ok.status == 200, await ok.text()
    assert settings.get_setting("llm_mode") == "custom"


async def test_status_reflects_source_and_does_not_restore(bot_client):
    write_settings(**{"llm_mode": "custom", "bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL, "bot-local-llm-key": CUSTOM_KEY})
    status = await (await bot_client.get("/comfyart/bot/status")).json()
    assert status["llm"]["source"] == "settings"
    assert status["llm"]["host"] == "127.0.0.1"
    assert status["llm"]["official_model"] == settings.OFFICIAL_LLM_MODEL == "deepseek-flash"
    assert status["llm"]["official_display_name"] == settings.OFFICIAL_LLM_DISPLAY_NAME
    # The restore endpoint is gone; nothing is cleared.
    res = await bot_client.post("/comfyart/bot/local-llm/use-official-default", json={})
    assert res.status == 404
    assert settings.get_setting("bot-local-llm-url") == CUSTOM_URL
    assert settings.get_setting("bot-local-llm-key") == CUSTOM_KEY
    assert settings.get_setting("llm_mode") == "custom"


async def test_official_display_name_comes_from_config(bot_client):
    """The official-mode line is '使用官方 {display}'; the name comes from settings config, not the frontend."""
    assert settings.OFFICIAL_LLM_DISPLAY_NAME == "DeepSeek V4.1 Flash"
    assert settings.OFFICIAL_LLM_MODEL == "deepseek-flash"
    got = await (await bot_client.get("/comfyart/settings")).json()
    assert got["official_llm_display_name"] == settings.OFFICIAL_LLM_DISPLAY_NAME
    assert got["official_llm_model"] == settings.OFFICIAL_LLM_MODEL
    # Echoing the read-only fields on Save must not write them or change the config value.
    res = await bot_client.put("/comfyart/settings", json={"official_llm_display_name": "hacked", "ocr-engine": "local"})
    assert res.status == 200, await res.text()
    body = await res.json()
    assert body["official_llm_display_name"] == settings.OFFICIAL_LLM_DISPLAY_NAME
    again = await (await bot_client.get("/comfyart/settings")).json()
    assert again["official_llm_display_name"] == settings.OFFICIAL_LLM_DISPLAY_NAME
    status = await (await bot_client.get("/comfyart/bot/status")).json()
    assert status["llm"]["official_display_name"] == settings.OFFICIAL_LLM_DISPLAY_NAME
    assert status["llm"]["official_model"] == settings.OFFICIAL_LLM_MODEL


def test_public_state_and_settings_share_llm_source():
    write_settings(**{"llm_mode": "custom", "bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL})
    assert provider_admin._public_state()["llm"]["source"] == provider_admin.llm_source() == "settings"
    write_settings(**{"llm_mode": "official", "bot-local-llm-url": CUSTOM_URL, "bot-model-local-llm": CUSTOM_MODEL})
    assert provider_admin._public_state()["llm"]["source"] == provider_admin.llm_source() == "default"
    assert settings.get_setting("bot-local-llm-url") == CUSTOM_URL


def test_frontend_shows_mode_switch_and_copy():
    settings_src = (ROOT / "src/ui/BotSettings.tsx").read_text()
    assert "llm_mode" in settings_src
    assert 'data-testid="llm-mode"' in settings_src
    assert "botSettings.llmManagedByAdmin" in settings_src
    assert "ca-botsettings__adminnotice" in settings_src
    assert "ca-botsettings__officialnotice" in settings_src
    assert "botSettings.llmOfficialNotice" in settings_src
    assert "botSettings.llmCustomKept" in settings_src
    assert "mode === 'custom'" in settings_src and "ProviderSelect" in settings_src
    assert "mode === 'official'" in settings_src
    assert "botSettings.llmKeyProvidedByAdmin" in settings_src
    assert "common.close" in settings_src
    assert "data-err={(id === 'custom' && testFailed) || undefined}" in settings_src
    assert 'data-testid="use-official-llm"' in settings_src
    assert "setMode('official')" in settings_src
    assert "botSettings.customLlmNotSetup" in settings_src
    assert "pendingLlmModeAtom" in settings_src
    assert "useOfficialLlmDefault" not in settings_src
    assert "use-official-default" not in settings_src
    assert "onClick={close}>{t('common.cancel')}" in settings_src
    assert "onClick={save}>{t('common.save')}" in settings_src
    assert "const close = () => { setModeOverride(null); botSettingsOpenAtom.set(false) }" in settings_src
    # Not-set-up (5th) has no switch-back button: the button is only for a test failure, not incomplete.
    not_setup_idx = settings_src.find('data-testid="llm-custom-not-setup"')
    switch_idx = settings_src.find('data-testid="use-official-llm"')
    assert not_setup_idx > 0 and switch_idx > 0
    assert "testFailed && !incomplete" in settings_src
    bot = (ROOT / "src/bot.ts").read_text()
    assert "use-official-default" not in bot
    assert "useOfficialLlmDefault" not in bot
    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text()
    assert "use_official_llm" in chat
    assert "openBotSettingsWithLlmMode('official')" in chat
    assert "action === 'use_official_llm'" in chat
    picker = (ROOT / "src/ui/AgentPicker.tsx").read_text()
    assert "pendingLlmModeAtom" in picker and "openBotSettingsWithLlmMode" in picker
    zh = json.loads((ROOT / "src/locales/zh.json").read_text())
    en = json.loads((ROOT / "src/locales/en.json").read_text())
    assert zh["botSettings.useOfficialDefault"] == "改用 Loomi 内置模型"
    assert zh["botSettings.llmManagedByAdmin"] == "由管理员统一配置的对话模型"
    assert en["botSettings.llmManagedByAdmin"] == "Conversation model configured by your admin"
    assert zh["botSettings.llmModeCustom"] == "使用我自己的 API Key"
    assert zh["botSettings.llmOfficialNotice"] == "无需填写你的 API Key。当前使用 {0}。"
    assert en["botSettings.llmOfficialNotice"] == "No API key needed. Currently using {0}."
    assert zh["botSettings.llmOfficialNotice"].format(settings.OFFICIAL_LLM_DISPLAY_NAME) == "无需填写你的 API Key。当前使用 DeepSeek V4.1 Flash。"
    assert en["botSettings.llmOfficialNotice"].format(settings.OFFICIAL_LLM_DISPLAY_NAME) == "No API key needed. Currently using DeepSeek V4.1 Flash."
    assert zh["botSettings.llmCustomKept"] == "不会使用你已保存的 API Key 和模型。改回「使用我自己的 API Key」即可恢复。"
    assert "Use my own API key" in en["botSettings.llmCustomKept"] and "Official default" not in en["botSettings.llmCustomKept"]
    assert zh["botSettings.llmKeyProvidedByAdmin"] == "由管理员提供"
    assert en["botSettings.llmKeyProvidedByAdmin"] == "Provided by your admin"
    assert "Loomi 内置模型" in zh["botSettings.builtinAgentHint"] and "官方模型" not in zh["botSettings.builtinAgentHint"]
    assert "Loomi built-in model" in en["botSettings.builtinAgentHint"] and "official model" not in en["botSettings.builtinAgentHint"]
    assert zh["botSettings.customLlmFailHttp"] == "你设置的模型服务返回了错误（HTTP {0}），请检查模型名是否正确，或稍后再试"
    assert en["botSettings.customLlmFailHttp"] == "Your model service returned an error (HTTP {0}). Check the model name, or try again later."
    assert zh["botSettings.customLlmNotSetup"] == "还没配好：请选择服务商并填写 API Key，再选择模型"
    assert en["botSettings.customLlmNotSetup"] == "Your model isn't set up yet. Choose a provider, enter your API key, then pick a model."
    assert zh["botSettings.customLlmNotSetup"] == provider_admin.CUSTOM_LLM_NOT_SETUP["zh"]
    assert en["botSettings.customLlmNotSetup"] == provider_admin.CUSTOM_LLM_NOT_SETUP["en"]
    assert zh["botSettings.customLlmNotSetupModel"] == "还没配好：请选择模型。"
    assert en["botSettings.customLlmNotSetupModel"] == "Your model isn't set up yet. Please choose a model."
    assert zh["botSettings.customLlmNotSetupModel"] == provider_admin.CUSTOM_LLM_NOT_SETUP_MODEL["zh"]
    assert en["botSettings.customLlmNotSetupModel"] == provider_admin.CUSTOM_LLM_NOT_SETUP_MODEL["en"]
    assert "notSetupCopy" in settings_src
    assert "botSettings.customLlmNotSetupModel" in settings_src
    assert zh["botSettings.chooseModelFirst"] == "请先选择模型"
    for key, loc_key in (("host", "customLlmFailHost"), ("auth", "customLlmFailAuth"), ("timeout", "customLlmFailTimeout")):
        assert zh[f"botSettings.{loc_key}"] == provider_admin._SETTINGS_FAIL["zh"][key]
        assert en[f"botSettings.{loc_key}"] == provider_admin._SETTINGS_FAIL["en"][key]
    assert "customLlmFailed')}：${reason}" not in settings_src
    assert "failCopyOf" in settings_src
    assert provider_admin.OFFICIAL_LLM_MODEL == settings.OFFICIAL_LLM_MODEL == "deepseek-flash"
    assert provider_admin.OFFICIAL_LLM_DISPLAY_NAME == settings.OFFICIAL_LLM_DISPLAY_NAME == "DeepSeek V4.1 Flash"
    api_bot = (ROOT / "api/bot.py").read_text()
    assert "use-official-default" not in api_bot
    assert "official_model" in api_bot
    assert "official_display_name" in api_bot
    assert "restore_official_llm_settings" not in (ROOT / "api/provider_admin.py").read_text()
    # Official-mode summary uses the settings-API display name, not a hard-coded id.
    assert "official_llm_display_name" in settings_src
    assert "DeepSeek V4.1 Flash" not in settings_src
    assert "officialModel || 'deepseek-flash'" not in settings_src
    assert "t('botSettings.llmOfficialNotice', officialDisplayName)" in settings_src
    # Admin read-only model field still shows the raw model value.
    assert "value={llmSource.model || ''}" in settings_src
