"""#493: known-model window table, shared by the built-in agent and external CLIs."""
from __future__ import annotations

from ComfyArt.bot import external_context, local_llm
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnRequest


def _stub(p, body):
    async def fake(session, method, url, *, headers, json_body=None, timeout=120):
        return body
    p._request_json = fake


async def test_493_deepseek_without_window_field_uses_1m():
    p = LocalLlmProvider(base_url=lambda: "http://x/v1")
    _stub(p, {"data": [{"id": "deepseek-chat"}]})
    window = await p._context_window(None, "deepseek-chat")
    assert window == 1_000_000
    assert local_llm.input_token_budget(window) == 700_000


async def test_493_deepseek_match_is_case_insensitive():
    p = LocalLlmProvider(base_url=lambda: "http://x/v1")
    _stub(p, {"data": [{"id": "DeepSeek-V3"}]})
    assert await p._context_window(None, "DeepSeek-V3") == 1_000_000


async def test_493_unknown_model_without_window_falls_back_to_32k():
    p = LocalLlmProvider(base_url=lambda: "http://x/v1")
    _stub(p, {"data": [{"id": "mystery-7b"}]})
    assert await p._context_window(None, "mystery-7b") == 32_000


async def test_493_endpoint_field_wins_over_table():
    p = LocalLlmProvider(base_url=lambda: "http://x/v1")
    _stub(p, {"data": [{"id": "deepseek-chat", "context_length": 64_000}]})
    assert await p._context_window(None, "deepseek-chat") == 64_000


def test_493_resolve_rule_order():
    assert local_llm.resolve_context_window("deepseek-chat", 64_000) == 64_000
    assert local_llm.resolve_context_window("deepseek-chat") == 1_000_000
    assert local_llm.resolve_context_window("mystery-7b") == 32_000
    assert local_llm.resolve_context_window("") == 32_000


def _long_history():
    # ~60k tokens: over 32k*70% (22.4k), well under 1M*70%.
    return [{"role": r, "content": "字" * 3_000}
            for _ in range(10) for r in ("user", "assistant")]


def test_493_external_context_uses_shared_window_for_deepseek():
    history = _long_history()
    wide = external_context.apply_cold_start(
        TurnRequest(chat_id="c", user_text="hi", history=history, model="deepseek-chat"))
    narrow = external_context.apply_cold_start(
        TurnRequest(chat_id="c", user_text="hi", history=history, model="mystery-7b"))
    # deepseek keeps every turn verbatim; the unknown model is cut to 32k*70%.
    assert wide.user_text.count("字" * 3_000) == len(history)
    assert narrow.user_text.count("字" * 3_000) < len(history)


def test_493_external_context_calls_resolve_context_window(monkeypatch):
    seen: list = []
    real = external_context.resolve_context_window

    def spy(model, declared=0):
        seen.append(model)
        return real(model, declared)
    monkeypatch.setattr(external_context, "resolve_context_window", spy)
    external_context.apply_cold_start(
        TurnRequest(chat_id="c", user_text="hi", history=[{"role": "user", "content": "a"}],
                    model="deepseek-chat"))
    assert seen == ["deepseek-chat"]
