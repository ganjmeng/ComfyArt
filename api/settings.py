import ipaddress
from urllib.parse import urlparse

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
    "bot-model-hermes": "",
    "bot-hermes-ssh-host": "",
    "bot-hermes-profile": "comfyart",
    # #120 / #30: default agent LLM is DeepSeek 4.1 flash on WaveSpeed's OpenAI-compatible endpoint (same
    # WaveSpeed key); any other OpenAI-compatible endpoint / model can still be set in Agent settings
    "bot-local-llm-url": "https://llm.wavespeed.ai/v1",
    "bot-model-local-llm": "deepseek/deepseek-v4.1-flash-1017",
    # #219: key for a custom endpoint; empty = WaveSpeed key, but only on WaveSpeed URLs. Never returned in clear.
    "bot-local-llm-key": "",
    # #877: official | custom; empty = not chosen yet (inferred on read, written only on Save)
    "llm_mode": "",
    # #877 v2: optional BYO provider id; empty = infer from hostname on read
    "llm_provider": "",
    # #232/#391: hard step cap of one agent run (clamped to 1..500); budgets + progress stop runs first
    "bot-max-steps": 300,
    # #391: budget + progress loop (off = legacy fixed-step loop); per-run wall time and credit quote
    "agent-budget-loop": True,
    "agent-wall-time-min": 15,
    "agent-credits-usd": 5.0,
    "agent-token-window-multiple": 40,
    "bot-enable-comfy-mcp": False,
    "bot-comfy-mcp-command": "",
    "ocr-engine": "local",
    "memory-enabled": True,
    # #364: Agent「审核」— post-image review thought on Done (default ON = Lovart)
    "bot-enable-review": True,
    "proactive-memory": False,
    "proactive-skills": False,
    "proactive-review": False,
    "proactive-daily": 5,
}

SECRET_KEYS = ("bot-local-llm-key",)
MASK = "********"

CHOICES: dict[str, tuple[str, ...]] = {
    "ocr-engine": ("local", "agent"),
    "llm_mode": ("official", "custom"),
    "llm_provider": ("wavespeed", "deepseek", "siliconflow", "openrouter", "openai", "ollama", "custom"),
}

# Official built-in LLM default (catalog/request id + user-facing display name).
# Not writable; GET/PUT /comfyart/settings include these as read-only fields.
OFFICIAL_LLM_MODEL = "deepseek-flash"
OFFICIAL_LLM_DISPLAY_NAME = "DeepSeek V4.1 Flash"
_READ_ONLY_SETTINGS = frozenset({"official_llm_model", "official_llm_display_name", "official_llm_ready"})

# #937 (port of upstream 54b6a377): settings that decide what the agent runs on this machine. Only a request
# from the machine running ComfyUI (loopback peer) may change them; LAN clients get 403 for a changed value.
LOCAL_ONLY = ("enable-mcp", "enable-bot", "bot-enable-comfy-mcp", "bot-comfy-mcp-command", "bot-hermes-ssh-host")


def request_is_local(request: web.Request) -> bool:
    """True when the TCP peer is a loopback address. Uses the socket peer only, never X-Forwarded-For."""
    try:
        addr = ipaddress.ip_address(str(request.remote or "").strip().split("%", 1)[0])
    except ValueError:
        return False
    mapped = getattr(addr, "ipv4_mapped", None)
    return bool(addr.is_loopback or (mapped is not None and mapped.is_loopback))


def _norm_llm_setting(value) -> str:
    return str(value or "").strip().rstrip("/")


def llm_values_are_custom(values: dict | None = None) -> bool:
    """True when the saved URL or model differs from the SETTINGS_SPEC default (strip + trailing /)."""
    values = values if values is not None else all_settings()
    url = _norm_llm_setting(values.get("bot-local-llm-url"))
    model = _norm_llm_setting(values.get("bot-model-local-llm"))
    def_url = _norm_llm_setting(SETTINGS_SPEC["bot-local-llm-url"])
    def_model = _norm_llm_setting(SETTINGS_SPEC["bot-model-local-llm"])
    return url != def_url or model != def_model


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


def official_llm_ready() -> bool:
    """True when the built-in official route has a server-side DEEPSEEK_API_KEY."""
    import os
    return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


def public_settings(values: dict | None = None) -> dict:
    """Masked settings plus the official LLM default (id + display name). Display name is not writable."""
    out = _masked(values if values is not None else all_settings())
    out["official_llm_model"] = OFFICIAL_LLM_MODEL
    out["official_llm_display_name"] = OFFICIAL_LLM_DISPLAY_NAME
    out["official_llm_ready"] = official_llm_ready()
    return out


@routes.get("/comfyart/settings")
async def get_settings(_request: web.Request) -> web.Response:
    return web.json_response(public_settings())


def _host(url: str) -> str:
    return (urlparse(str(url or "").strip()).hostname or "").lower()


def _masked(values: dict) -> dict:
    return {k: (MASK if k in SECRET_KEYS and v else v) for k, v in values.items()}


@routes.put("/comfyart/settings")
async def put_settings(request: web.Request) -> web.Response:
    body = await json_body(request)
    unknown = [k for k in body if k not in SETTINGS_SPEC and k not in _READ_ONLY_SETTINGS]
    if unknown:
        return error(f"unknown settings: {', '.join(unknown)}", 400)
    writable = {k: v for k, v in body.items() if k not in _READ_ONLY_SETTINGS}
    for key, value in writable.items():
        expected = type(SETTINGS_SPEC[key])
        # JSON has no 5.0 vs 5: the browser sends an int for a whole-number float (e.g. agent-credits-usd).
        # Accept int/float and store float; bool is an int subclass and must still be rejected.
        if expected is float and isinstance(value, (int, float)) and not isinstance(value, bool):
            writable[key] = float(value)
        elif type(value) is not expected:
            return error(f"{key} must be a {expected.__name__}", 400)
        # The SETTINGS_SPEC default remains valid even when it is not in CHOICES (llm_mode="" = not chosen yet).
        if key in CHOICES and writable[key] not in CHOICES[key] and writable[key] != SETTINGS_SPEC[key]:
            return error(f"{key} must be one of {', '.join(CHOICES[key])}", 400)
    current = all_settings()
    if not request_is_local(request):
        blocked = [k for k in LOCAL_ONLY if k in writable and writable[k] != current[k]]
        if blocked:
            return error(f"{', '.join(blocked)} can only be changed from the machine running ComfyUI", 403)
    old_host = _host(current["bot-local-llm-url"])
    # the UI echoes the mask back for an untouched key: keep the stored value
    current.update({k: v for k, v in writable.items() if not (k in SECRET_KEYS and v == MASK)})
    # #219: a stored custom key belongs to its host; a new hostname clears it unless a new key came with it.
    # Back on a WaveSpeed host the key is cleared too and the WaveSpeed key is used as usual.
    new_key = body.get("bot-local-llm-key")
    if _host(current["bot-local-llm-url"]) != old_host and (new_key is None or new_key == MASK):
        current["bot-local-llm-key"] = ""
    # #877: first Save of an unchosen mode persists the inferred official/custom value. Never write back on read.
    if str(current.get("llm_mode") or "").strip() not in CHOICES["llm_mode"]:
        current["llm_mode"] = "custom" if llm_values_are_custom(current) else "official"
    write_json(_file(), current, mode=0o600)  # holds the custom endpoint key
    return web.json_response(public_settings(current))
