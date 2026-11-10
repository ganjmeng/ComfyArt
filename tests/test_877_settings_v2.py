"""#877 settings v2: BYO providers, list proxy, copy, and no pin/Auto changes.

Mocks only, $0. Does not reopen the closed issue; covers ACs 1–18 and 20 (AC19 is screenshot).
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest
from conftest import write_settings
from ComfyArt.api import llm_byo, settings
from ComfyArt.api.provider_admin import CUSTOM_LLM_NOT_SETUP, CUSTOM_LLM_NOT_SETUP_MODEL, OFFICIAL_LLM_NOT_READY

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_SOURCE = ("官方默认", "官方模型", "切回官方默认", "Official default", "official model")


def _locales():
    return (
        json.loads((ROOT / "src/locales/zh.json").read_text()),
        json.loads((ROOT / "src/locales/en.json").read_text()),
    )


def test_ac18_pins_and_auto_untouched():
    import subprocess

    def git(*args, **kw):
        return subprocess.check_output(["git", *args], cwd=ROOT, **kw)

    # Compare to origin/main (or the merge-base), not HEAD. A pin/Auto
    # change committed on this branch must still fail this test.
    try:
        base = git("merge-base", "HEAD", "origin/main", text=True).strip()
    except subprocess.CalledProcessError:
        base = git("rev-parse", "origin/main", text=True).strip()
    assert base
    for path in ("api/auto_models.json", "src/skills.ts"):
        current = (ROOT / path).read_bytes()
        origin = git("show", f"{base}:{path}")
        assert current == origin, path


def test_infer_llm_provider_from_host_and_stored():
    assert llm_byo.infer_llm_provider("https://llm.wavespeed.ai/v1") == "wavespeed"
    assert llm_byo.infer_llm_provider("https://api.deepseek.com/v1") == "deepseek"
    assert llm_byo.infer_llm_provider("https://api.siliconflow.cn/v1") == "siliconflow"
    assert llm_byo.infer_llm_provider("https://api.siliconflow.com/v1") == "siliconflow"
    assert llm_byo.infer_llm_provider("https://openrouter.ai/api/v1") == "openrouter"
    assert llm_byo.infer_llm_provider("https://api.openai.com/v1") == "openai"
    assert llm_byo.infer_llm_provider("http://localhost:11434/v1") == "ollama"
    assert llm_byo.infer_llm_provider("http://127.0.0.1:11434/v1") == "ollama"
    assert llm_byo.infer_llm_provider("https://example.com/v1") == "custom"
    assert llm_byo.infer_llm_provider("https://example.com/v1", "deepseek") == "deepseek"
    assert llm_byo.recommended_model_ids("wavespeed") == ("deepseek/deepseek-v4.1-flash-1017",)
    assert llm_byo.recommended_model_ids("deepseek") == ("deepseek-flash", "deepseek-chat")
    assert llm_byo.recommended_model_ids("openrouter") == ()


def test_llm_provider_setting_enum_and_empty_ok():
    assert settings.SETTINGS_SPEC["llm_provider"] == ""
    assert "wavespeed" in settings.CHOICES["llm_provider"]
    assert "custom" in settings.CHOICES["llm_provider"]


async def test_official_llm_ready_is_readonly(bot_client, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    got = await (await bot_client.get("/comfyart/settings")).json()
    assert got["official_llm_ready"] is False
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-mock-ready")
    got = await (await bot_client.get("/comfyart/settings")).json()
    assert got["official_llm_ready"] is True
    res = await bot_client.put("/comfyart/settings", json={"official_llm_ready": False, "ocr-engine": "local"})
    assert res.status == 200
    body = await res.json()
    assert body["official_llm_ready"] is True
    status = await (await bot_client.get("/comfyart/bot/status")).json()
    assert status["llm"]["official_ready"] is True
    assert "sk-mock-ready" not in json.dumps(body)
    assert "sk-mock-ready" not in json.dumps(status)


async def test_put_llm_provider_and_infer_on_read(bot_client):
    res = await bot_client.put("/comfyart/settings", json={"llm_provider": "not-a-provider"})
    assert res.status == 400
    res = await bot_client.put("/comfyart/settings", json={
        "llm_mode": "custom",
        "llm_provider": "openrouter",
        "bot-local-llm-url": "https://openrouter.ai/api/v1",
        "bot-model-local-llm": "openai/gpt-4o",
    })
    assert res.status == 200, await res.text()
    body = await res.json()
    assert body["llm_provider"] == "openrouter"
    status = await (await bot_client.get("/comfyart/bot/status")).json()
    assert status["llm"]["provider"] == "openrouter"


async def test_models_proxy_success_and_never_returns_key(bot_client):
    from aiohttp import web
    from aiohttp.test_utils import TestServer

    app = web.Application()
    seen = {}

    async def models(request):
        seen["auth"] = request.headers.get("Authorization")
        # upstream must not be reachable from the browser; this is the mock third party
        return web.json_response({
            "data": [{"id": "alpha"}, {"id": "beta"}, {"id": "gamma"}],
            "key": "should-not-leak",
        })

    app.router.add_get("/v1/models", models)
    server = TestServer(app)
    await server.start_server()
    try:
        base = str(server.make_url("/v1"))
        write_settings(**{"bot-local-llm-url": "http://old/v1", "bot-local-llm-key": "saved-secret"})
        res = await bot_client.post("/comfyart/bot/local-llm/models",
                                    json={"url": base, "key": "draft-secret"})
        assert res.status == 200
        body = await res.json()
        assert body["ok"] is True and body["code"] == "ok"
        assert [m["id"] for m in body["models"]] == ["alpha", "beta", "gamma"]
        assert body["total"] == 3
        blob = json.dumps(body)
        assert "draft-secret" not in blob and "saved-secret" not in blob
        assert "should-not-leak" not in blob
        assert "key" not in body and "api_key" not in body
        assert seen["auth"] == "Bearer draft-secret"
    finally:
        await server.close()


async def test_models_proxy_auth_timeout_codes(bot_client):
    from aiohttp import web
    from aiohttp.test_utils import TestServer

    app = web.Application()

    async def models(_request):
        return web.Response(status=401, text="no")

    app.router.add_get("/v1/models", models)
    server = TestServer(app)
    await server.start_server()
    try:
        base = str(server.make_url("/v1"))
        res = await bot_client.post("/comfyart/bot/local-llm/models",
                                    json={"url": base, "key": "bad"})
        body = await res.json()
        assert body["ok"] is False and body["code"] == "auth_failed" and body["status"] == 401
        assert "bad" not in json.dumps(body)
    finally:
        await server.close()

    res = await bot_client.post("/comfyart/bot/local-llm/models", json={"url": "", "key": "x"})
    assert (await res.json())["code"] == "no_url"


async def test_models_proxy_reuses_wavespeed_image_key_only_on_ws_host(bot_client, monkeypatch):
    from aiohttp import web
    from aiohttp.test_utils import TestServer
    from ComfyArt.api import wavespeed

    app = web.Application()
    seen = []

    async def models(request):
        seen.append((str(request.url), request.headers.get("Authorization")))
        host = request.host
        return web.json_response({"data": [{"id": "deepseek/deepseek-v4.1-flash-1017"}]})

    app.router.add_get("/v1/models", models)
    server = TestServer(app)
    await server.start_server()
    try:
        base = str(server.make_url("/v1"))
        monkeypatch.setattr(wavespeed, "key_source", lambda: ("ws-image-key", "settings"))
        # Pretend the mock server is WaveSpeed by patching is_wavespeed_url
        from ComfyArt.api import llm_key
        monkeypatch.setattr(llm_key, "is_wavespeed_url", lambda url: urlparse(url).hostname == urlparse(base).hostname)
        res = await bot_client.post("/comfyart/bot/local-llm/models",
                                    json={"url": base, "key": ""})
        body = await res.json()
        assert body["ok"] is True
        assert seen[-1][1] == "Bearer ws-image-key"
        assert "ws-image-key" not in json.dumps(body)

        # After leaving a WaveSpeed host, the image key must not be sent.
        monkeypatch.setattr(llm_key, "is_wavespeed_url", lambda url: False)
        seen.clear()
        res = await bot_client.post("/comfyart/bot/local-llm/models",
                                    json={"url": base, "key": ""})
        body = await res.json()
        assert seen[-1][1] is None
        assert "ws-image-key" not in json.dumps(body)
    finally:
        await server.close()


async def test_models_and_test_do_not_call_chat_completions(bot_client):
    from aiohttp import web
    from aiohttp.test_utils import TestServer

    app = web.Application()
    hits = []

    async def models(request):
        hits.append(str(request.rel_url))
        return web.json_response({"data": [{"id": "m1"}]})

    async def chat(_request):
        raise AssertionError("must not send chat completions for list or test")

    app.router.add_get("/v1/models", models)
    app.router.add_post("/v1/chat/completions", chat)
    server = TestServer(app)
    await server.start_server()
    try:
        base = str(server.make_url("/v1"))
        assert (await (await bot_client.post("/comfyart/bot/local-llm/models",
                                             json={"url": base, "key": "k"})).json())["ok"]
        assert (await (await bot_client.post("/comfyart/bot/local-llm/test",
                                             json={"url": base, "key": "k", "model": "m1"})).json())["ok"]
        assert hits == ["/v1/models", "/v1/models"]
    finally:
        await server.close()


def test_ac1_ac2_frontend_copy_and_cards():
    settings_src = (ROOT / "src/ui/BotSettings.tsx").read_text()
    zh, en = _locales()
    assert "ca-botsettings__sourcecard" in settings_src
    assert "llmModeOfficial" in settings_src and "llmModeCustom" in settings_src
    assert "Icons.agent" in settings_src and "Icons.key" in settings_src
    assert "official_llm_display_name" in settings_src
    assert "DeepSeek V4.1 Flash" not in settings_src
    assert "t('botSettings.llmOfficialNotice', officialDisplayName)" in settings_src
    assert "codex.svg" not in settings_src
    assert zh["botSettings.llmModeOfficial"] == "Loomi 内置模型"
    assert zh["botSettings.llmModeCustom"] == "使用我自己的 API Key"
    assert "（" not in zh["botSettings.llmModeOfficial"] and "(" not in zh["botSettings.llmModeOfficial"]
    for loc in (zh, en):
        for key in (
            "botSettings.llmModeOfficial", "botSettings.llmModeCustom",
            "botSettings.useOfficialDefault", "botSettings.llmOfficialNotice",
            "botSettings.llmManagedByAdmin", "botSettings.llmSourceOfficial",
            "botSettings.llmSourceCustom", "botSettings.llmSourceAdmin",
            "botSettings.builtinAgentHint", "botSettings.customLlmNotSetup",
            "botSettings.customLlmNotSetupModel",
        ):
            text = loc[key]
            assert "官方默认" not in text and "切回官方默认" not in text
            assert "Official default" not in text
            if key != "botSettings.builtinAgentHint":
                # section hint may mention 自定义工作流? it doesn't. "自定义" as source name is banned.
                if key in ("botSettings.llmModeCustom", "botSettings.customLlmNotSetup", "botSettings.llmCustomKept"):
                    continue
            assert "官方模型" not in text
    # source names themselves
    assert zh["botSettings.useOfficialDefault"] == "改用 Loomi 内置模型"
    assert "自定义" not in zh["botSettings.llmModeOfficial"]
    assert zh["botSettings.llmOfficialNotReady"] == OFFICIAL_LLM_NOT_READY["zh"]
    assert en["botSettings.llmOfficialNotReady"] == OFFICIAL_LLM_NOT_READY["en"]
    assert zh["botSettings.customLlmNotSetup"] == CUSTOM_LLM_NOT_SETUP["zh"]
    assert en["botSettings.customLlmNotSetup"] == CUSTOM_LLM_NOT_SETUP["en"]
    assert zh["botSettings.customLlmNotSetupModel"] == "还没配好：请选择模型。"
    assert en["botSettings.customLlmNotSetupModel"] == "Your model isn't set up yet. Please choose a model."
    assert zh["botSettings.customLlmNotSetupModel"] == CUSTOM_LLM_NOT_SETUP_MODEL["zh"]
    assert en["botSettings.customLlmNotSetupModel"] == CUSTOM_LLM_NOT_SETUP_MODEL["en"]
    assert "botSettings.customLlmNotSetupModel" in settings_src
    assert "notSetupCopy" in settings_src
    assert zh["botSettings.chooseModelFirst"] == "请先选择模型"
    assert en["botSettings.chooseModelFirst"] == "Choose a model first"
    # Open model list must stack above the settings dialog (modal is z-index 2000).
    assert ".ca-pop:has(.ca-llm-model__menu)" in (ROOT / "src/styles/base.css").read_text()
    assert "z-index: 2200" in (ROOT / "src/styles/base.css").read_text()
    assert "listLocalLlmModels" in settings_src
    assert "disabled={testing || !modelReady}" in settings_src
    assert "botSettings.chooseModelFirst" in settings_src
    assert "llm-official-not-ready" in settings_src
    assert "use-official-llm" in settings_src
    assert "testFailed && !incomplete" in settings_src
    assert "value={llmSource.model || ''}" in settings_src
    assert "/comfyart/bot/local-llm/models" in (ROOT / "src/bot.ts").read_text()
    # frontend never calls a third-party /models URL
    assert "llm.wavespeed.ai/models" not in settings_src
    assert "api.deepseek.com" in (ROOT / "src/ui/llmProviders.ts").read_text()
    # AC / product: list-fail reason and "couldn't fetch list" must not run together on one line
    assert "${failCopyOf(code, r.status)}\\n${t('botSettings.fetchModelsFailed')}" in settings_src
    assert "white-space: pre-line" in (ROOT / "src/styles/shell.css").read_text()


def test_frontend_providers_and_model_cap():
    prov = (ROOT / "src/ui/llmProviders.ts").read_text()
    for url in (
        "https://llm.wavespeed.ai/v1",
        "https://api.deepseek.com/v1",
        "https://api.siliconflow.com/v1",
        "https://openrouter.ai/api/v1",
        "https://api.openai.com/v1",
        "http://localhost:11434/v1",
    ):
        assert url in prov
    select = (ROOT / "src/ui/LlmModelSelect.tsx").read_text()
    assert "VISIBLE_CAP = 100" in select
    assert "flip={false}" in select
    assert "models.length > 10" in select
    assert "pickDefaultModel" in prov
    assert "openrouter" in prov and "recommended: []" in prov


def test_chat_source_labels_wired():
    picker = (ROOT / "src/ui/AgentPicker.tsx").read_text()
    assert "llmSourceLabel" in picker and "llm-source-label" in picker
    zh, en = _locales()
    assert zh["botSettings.llmSourceOfficial"] == "Loomi 内置 · {0}"
    assert zh["botSettings.llmSourceCustom"] == "自己的 Key · {0}"
    assert zh["botSettings.llmSourceAdmin"] == "由管理员统一配置"
    assert "官方默认" not in zh["botSettings.llmSourceOfficial"]
    assert "自定义" not in zh["botSettings.llmSourceCustom"]


def test_ac12_switching_source_keeps_unsaved_byo_draft():
    """AC12: 「改用 Loomi 内置模型」 only changes the draft source.

    Unsaved URL / provider / model / Key stay when switching to built-in and
    back to 「使用我自己的 API Key」. Save is when the built-in source takes
    effect. Cancel discards unsaved source and field edits; the next open
    shows the previously saved settings.
    """
    settings_src = (ROOT / "src/ui/BotSettings.tsx").read_text()
    # Regression: hydrating on modeOverride rebuilt the draft from saved
    # settings (WaveSpeed defaults) and dropped unsaved example.com values.
    assert "}, [settings, modeOverride])" not in settings_src
    assert "}, [open, settings])" in settings_src
    # Source switch (card click or 「改用 Loomi 内置模型」) only writes llm_mode.
    assert "setDraft({ ...draft, llm_mode: id })" in settings_src
    assert "setModeOverride(id)" in settings_src
    # Hydrate still copies saved settings when the dialog opens or settings change.
    assert "if (!open) return" in settings_src
    assert "const next = { ...settings } as Settings" in settings_src
    # Save materializes the draft source; close / cancel drops the override.
    assert "llm_mode: modeOf({ ...draft, llm_mode: modeOverride ?? draft.llm_mode })" in settings_src
    assert "const close = () => { setModeOverride(null); botSettingsOpenAtom.set(false) }" in settings_src
    assert "if (!open) {\n      setModeOverride(null)" in settings_src
