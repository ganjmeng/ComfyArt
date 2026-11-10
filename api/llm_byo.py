"""#877 v2: BYO conversation-model providers (settings page, not Auto/image routing)."""
from __future__ import annotations

from urllib.parse import urlparse

LLM_PROVIDERS: tuple[dict, ...] = (
    {"id": "wavespeed", "url": "https://llm.wavespeed.ai/v1", "hosts": ("llm.wavespeed.ai",)},
    {"id": "deepseek", "url": "https://api.deepseek.com/v1", "hosts": ("api.deepseek.com",)},
    {
        "id": "siliconflow",
        "url": "https://api.siliconflow.com/v1",
        "hosts": ("api.siliconflow.com", "api.siliconflow.cn"),
    },
    {"id": "openrouter", "url": "https://openrouter.ai/api/v1", "hosts": ("openrouter.ai",)},
    {"id": "openai", "url": "https://api.openai.com/v1", "hosts": ("api.openai.com",)},
    {"id": "ollama", "url": "http://localhost:11434/v1", "hosts": ()},
    {"id": "custom", "url": "", "hosts": ()},
)

LLM_PROVIDER_IDS = tuple(p["id"] for p in LLM_PROVIDERS)

# Recommended model ids are applied only when present in the fetched list.
RECOMMENDED_MODELS: dict[str, tuple[str, ...]] = {
    "wavespeed": ("deepseek/deepseek-v4.1-flash-1017",),
    "deepseek": ("deepseek-flash", "deepseek-chat"),
}


def _norm_url(url: str) -> str:
    return str(url or "").strip().rstrip("/")


def _host_port(url: str) -> tuple[str, int | None]:
    try:
        parsed = urlparse(str(url or "").strip())
    except ValueError:
        return "", None
    host = (parsed.hostname or "").lower()
    return host, parsed.port


def infer_llm_provider(url: str, stored: str = "") -> str:
    """Resolve a provider id from a stored enum, else from the URL hostname."""
    stored = str(stored or "").strip()
    if stored in LLM_PROVIDER_IDS:
        return stored
    host, port = _host_port(url)
    if host in ("localhost", "127.0.0.1") and port == 11434:
        return "ollama"
    for row in LLM_PROVIDERS:
        if host and host in row["hosts"]:
            return row["id"]
    return "custom" if _norm_url(url) else "wavespeed"


def provider_preset_url(provider_id: str) -> str:
    for row in LLM_PROVIDERS:
        if row["id"] == provider_id:
            return str(row["url"] or "")
    return ""


def recommended_model_ids(provider_id: str) -> tuple[str, ...]:
    return RECOMMENDED_MODELS.get(provider_id, ())


def public_models_payload(result: dict) -> dict:
    """Strip anything that could leak a key; keep the documented list-proxy shape."""
    models = []
    for item in result.get("models") or []:
        if isinstance(item, dict):
            mid = str(item.get("id") or "").strip()
        else:
            mid = str(item or "").strip()
        if mid:
            models.append({"id": mid})
    out = {
        "ok": bool(result.get("ok")),
        "code": str(result.get("code") or ("ok" if result.get("ok") else "unreachable")),
        "models": models,
    }
    if result.get("status") is not None:
        out["status"] = result["status"]
    if result.get("total") is not None:
        out["total"] = result["total"]
    if result.get("truncated"):
        out["truncated"] = True
    return out
