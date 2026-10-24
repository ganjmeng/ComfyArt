from ..bot.providers import ProviderStatus
from ..bot import (
    ClaudeCodeProvider,
    CodexCodeProvider,
    DeepSeekHarnessProvider,
    LocalLlmProvider,
    QwenCodeProvider,
    register_provider,
)
from ._common import app_path
from .llm_key import is_wavespeed_url, llm_api_key
from .settings import get_setting


# #219: shown to the frontend, which turns it into the "set your WaveSpeed key" notice
NO_KEY_DETAIL = "no-wavespeed-key"


class AgentLlmProvider(LocalLlmProvider):
    """The unchanged agent loop (built-in ComfyArt Agent); the key lookup also covers the WaveSpeed LLM
    default (#120). #219: no WaveSpeed key -> a clear status instead of a raw 401, and a saved model name
    keeps the agent usable when the endpoint's /models fails or is empty."""

    id = "local-llm"
    label = "ComfyArt Agent (built-in)"

    @staticmethod
    def _mcp_headers() -> dict:
        # #219: the in-process secret lets the built-in agent use the canvas tools while external MCP is off
        from .mcp import INTERNAL_HEADER, INTERNAL_TOKEN
        return {**LocalLlmProvider._mcp_headers(), INTERNAL_HEADER: INTERNAL_TOKEN}

    async def probe(self) -> ProviderStatus:
        base = self._base_url()
        if base and is_wavespeed_url(base) and not llm_api_key(base):
            return ProviderStatus(available=False, detail=NO_KEY_DETAIL)
        status = await super().probe()
        model = str(get_setting("bot-model-local-llm") or "").strip()
        if not status.available and base and model and status.detail != NO_KEY_DETAIL:
            return ProviderStatus(available=True, version=model, logged_in=True,
                                  detail=f"/models unavailable, using {model}")
        return status

    async def send(self, turn, emit, handle):
        base = self._base_url()
        if base and is_wavespeed_url(base) and not llm_api_key(base):
            from ..bot.providers import TurnResult

            return TurnResult(error="还没有设置 WaveSpeed Key，请先在 WaveSpeed Key 设置里填写。"
                                    " / No WaveSpeed key yet: set one in WaveSpeed key settings.")
        return await super().send(turn, emit, handle)

    async def list_models(self) -> list[str]:
        models = await super().list_models()
        model = str(get_setting("bot-model-local-llm") or "").strip()
        return models or ([model] if model else [])

    def _api_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        key = llm_api_key(self._base_url())
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers


# #219: the built-in agent is listed first; external CLIs follow
register_provider(AgentLlmProvider(base_url=lambda: str(get_setting("bot-local-llm-url"))))
register_provider(ClaudeCodeProvider(home_dir=app_path("bot-home")))
register_provider(CodexCodeProvider(home_dir=app_path("bot-home-codex")))
register_provider(QwenCodeProvider(home_dir=app_path("bot-home-qwen")))
register_provider(DeepSeekHarnessProvider(home_dir=app_path("bot-home-deepseek-harness")))
