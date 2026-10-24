"""API key for the OpenAI-compatible agent endpoint (#120 / #30).

COMFYART_LOCAL_LLM_API_KEY wins, as before. When it is unset and the endpoint is WaveSpeed's own LLM
service (the default, https://llm.wavespeed.ai/v1), the WaveSpeed key already used for generation is
sent, so no second key is needed. Any other endpoint never receives the WaveSpeed key.
#219: a key typed in Agent settings (bot-local-llm-key) is used next, for any endpoint."""
from __future__ import annotations

import os
from urllib.parse import urlparse

from ..bot.local_llm import _API_KEY_ENV

WAVESPEED_LLM_HOST = "llm.wavespeed.ai"


def llm_api_key(base_url: str) -> str:
    key = os.environ.get(_API_KEY_ENV, "")
    if key:
        return key
    from .settings import get_setting

    saved = str(get_setting("bot-local-llm-key") or "").strip()  # #219: key typed in Agent settings
    if saved:
        return saved
    if is_wavespeed_url(base_url):
        from .wavespeed import key_source

        return key_source()[0]
    return ""


def is_wavespeed_url(base_url: str) -> bool:
    return (urlparse(base_url.strip()).hostname or "").lower() == WAVESPEED_LLM_HOST
