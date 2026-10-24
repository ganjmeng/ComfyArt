from aiohttp import web

from ._common import app_path, error, json_body, read_json, routes, write_json

SETTINGS_SPEC: dict[str, object] = {
    # #219: the built-in agent works out of the box (only a WaveSpeed key is needed)
    "enable-mcp": False,
    "enable-bot": True,
    "bot-provider": "local-llm",
    "bot-model-claude-code": "",
    "bot-model-codex": "",
    "bot-model-qwen-code": "",
    "bot-model-deepseek-harness": "",
    # #120 / #30: default agent LLM is DeepSeek 4.1 flash on WaveSpeed's OpenAI-compatible endpoint (same
    # WaveSpeed key); any other OpenAI-compatible endpoint / model can still be set in Agent settings
    "bot-local-llm-url": "https://llm.wavespeed.ai/v1",
    "bot-model-local-llm": "deepseek/deepseek-v4.1-flash-1017",
    # #219: key for a custom endpoint; empty = WaveSpeed key, but only on WaveSpeed URLs. Never returned in clear.
    "bot-local-llm-key": "",
    "bot-enable-comfy-mcp": False,
    "bot-comfy-mcp-command": "",
    "ocr-engine": "local",
    "memory-enabled": True,
    "proactive-memory": False,
    "proactive-skills": False,
    "proactive-review": False,
    "proactive-daily": 5,
}

SECRET_KEYS = ("bot-local-llm-key",)
MASK = "********"

CHOICES: dict[str, tuple[str, ...]] = {"ocr-engine": ("local", "agent")}


def _file() -> str:
    return app_path("settings.json")


def all_settings() -> dict:
    saved = read_json(_file(), {})
    return {k: saved.get(k, default) for k, default in SETTINGS_SPEC.items()}


def get_setting(key: str):
    return all_settings()[key]


def mcp_enabled() -> bool:
    return bool(get_setting("enable-mcp"))


def bot_enabled() -> bool:
    # #219: the built-in agent reaches the canvas through an internal-only MCP channel, so the Agent no
    # longer depends on the external MCP switch; external tools are gated separately (bot_send / mcp_post)
    return bool(get_setting("enable-bot"))


def bot_disabled() -> web.Response:
    return error("the ComfyArt Agent is off: turn it on in Agent settings", 403)


@routes.get("/comfyart/settings")
async def get_settings(_request: web.Request) -> web.Response:
    return web.json_response(_masked(all_settings()))


def _masked(values: dict) -> dict:
    return {k: (MASK if k in SECRET_KEYS and v else v) for k, v in values.items()}


@routes.put("/comfyart/settings")
async def put_settings(request: web.Request) -> web.Response:
    body = await json_body(request)
    unknown = [k for k in body if k not in SETTINGS_SPEC]
    if unknown:
        return error(f"unknown settings: {', '.join(unknown)}", 400)
    for key, value in body.items():
        if type(value) is not type(SETTINGS_SPEC[key]):
            return error(f"{key} must be a {type(SETTINGS_SPEC[key]).__name__}", 400)
        if key in CHOICES and value not in CHOICES[key]:
            return error(f"{key} must be one of {', '.join(CHOICES[key])}", 400)
    current = all_settings()
    # the UI echoes the mask back for an untouched key: keep the stored value
    current.update({k: v for k, v in body.items() if not (k in SECRET_KEYS and v == MASK)})
    write_json(_file(), current)
    return web.json_response(_masked(current))
