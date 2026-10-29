"""#413: low reasoning on the one LLM call that directly follows a successful memory add.

The memory_updated row is followed by a real thought only when the model returns reasoning. To make
that dependable without faking anything, the single request right after a step whose tool results
include a successful memory add (the one that becomes memory_updated) asks the provider for low
reasoning with its own setting. Every other request is unchanged. A model without reasoning just
replies; no thought is synthesized. If the endpoint rejects the setting (HTTP 400), the same
request is sent once more without it.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

ANTHROPIC_THINKING_BUDGET = 1024


def wrote_memory(blocks: list[dict]) -> bool:
    """True when these step blocks hold a successful memory add that returned memory ids
    (the same condition that produces the memory_updated block in api/bot_turns.py)."""
    uses = {b.get("id"): b for b in blocks if b.get("type") == "tool_use"}
    for b in blocks:
        if b.get("type") != "tool_result" or b.get("status") != "success":
            continue
        if str(b.get("name") or "").split("__")[-1] != "memory":
            continue
        use = uses.get(b.get("id")) or {}
        if str((use.get("input") or {}).get("action") or "") != "add":
            continue
        text = str(b.get("text") or "")
        try:
            data = json.loads(text)
        except ValueError:
            m = re.search(r"\{.*\}", text, re.S)
            try:
                data = json.loads(m.group(0)) if m else {}
            except ValueError:
                data = {}
        if isinstance(data, dict) and any(data.get("memory_ids") or []):
            return True
    return False


def reasoning_params(base_url: str, model: str) -> dict:
    """The provider's own low-reasoning setting for one chat/completions request.

    - Anthropic (OpenAI-compatible endpoint): thinking with a ~1024 token budget.
    - OpenRouter: the unified reasoning object, effort low.
    - DeepSeek's own API: reasoning_effort low plus thinking enabled (its OpenAI-format toggle).
    - Everything else, including the default WaveSpeed LLM endpoint (llm.wavespeed.ai/v1, whose
      DeepSeek v4.1 flash models list reasoning_effort as a supported parameter) and OpenAI:
      top-level reasoning_effort low.
    """
    host = (urlparse(base_url or "").hostname or "").lower()
    if host.endswith("anthropic.com") or str(model or "").lower().startswith("claude"):
        return {"thinking": {"type": "enabled", "budget_tokens": ANTHROPIC_THINKING_BUDGET}}
    if host.endswith("openrouter.ai"):
        return {"reasoning": {"effort": "low"}}
    if host.endswith("deepseek.com"):
        return {"reasoning_effort": "low", "thinking": {"type": "enabled"}}
    return {"reasoning_effort": "low"}
