from ..bot import (
    ClaudeCodeProvider,
    CodexCodeProvider,
    DeepSeekHarnessProvider,
    LocalLlmProvider,
    QwenCodeProvider,
    register_provider,
)
from ._common import app_path
from .llm_key import llm_api_key
from .settings import get_setting


class AgentLlmProvider(LocalLlmProvider):
    """The unchanged Local LLM agent loop; only the key lookup also covers the WaveSpeed LLM default (#120)."""

    def _api_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        key = llm_api_key(self._base_url())
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers


register_provider(ClaudeCodeProvider(home_dir=app_path("bot-home")))
register_provider(CodexCodeProvider(home_dir=app_path("bot-home-codex")))
register_provider(QwenCodeProvider(home_dir=app_path("bot-home-qwen")))
register_provider(DeepSeekHarnessProvider(home_dir=app_path("bot-home-deepseek-harness")))
register_provider(AgentLlmProvider(base_url=lambda: str(get_setting("bot-local-llm-url"))))
