"""#493: model window = endpoint field, else known-model table (prefix), else 270k.
Shared by the built-in agent and external CLIs; overflow guard resends once; summary cap
is 5% of the window clamped to [1000, 16000]. Mocks only, no real model call."""
from __future__ import annotations

import pytest

from ComfyArt.bot import external_context, local_llm
from ComfyArt.bot.local_llm import LlmHttpError, LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest
from test_agent_budget_391 import store  # noqa: F401  (sqlite run-store fixture)

BASE = "http://x/v1"
URL = f"{BASE}/chat/completions"
OK = {"choices": [{"message": {"content": "ok", "tool_calls": []}}]}
OVERFLOW_8K = ("This model's maximum context length is 8192 tokens. However, your messages "
               "resulted in 9000 tokens. Please reduce the length of the messages.")
OVERFLOW_NO_NUMBER = "context_length_exceeded: the prompt is too long for this model"


def _stub(p, body):
    async def fake(session, method, url, *, headers, json_body=None, timeout=120):
        return body
    p._request_json = fake


# ------------------------------------------------------------- window resolution

async def test_493_endpoint_field_wins_over_table():
    p = LocalLlmProvider(base_url=lambda: BASE)
    _stub(p, {"data": [{"id": "deepseek-flash", "context_length": 64_000}]})
    assert await p._context_window(None, "deepseek-flash") == 64_000


@pytest.mark.parametrize("model", ["deepseek-flash", "deepseek-v4-pro", "DeepSeek-V4-Flash",
                                   "deepseek/deepseek-v4.1-flash-1017",
                                   "openrouter/deepseek/deepseek-v4-pro"])
async def test_493_table_prefix_hit_gives_1m(model):
    p = LocalLlmProvider(base_url=lambda: BASE)
    _stub(p, {"data": [{"id": model}]})
    window = await p._context_window(None, model)
    assert window == 1_000_000
    assert local_llm.input_token_budget(window) == 700_000


@pytest.mark.parametrize("model", ["deepseek-chat", "deepseek-reasoner", "mystery-7b"])
async def test_493_retired_or_unknown_model_falls_back_to_270k(model):
    p = LocalLlmProvider(base_url=lambda: BASE)
    _stub(p, {"data": [{"id": model}]})
    assert await p._context_window(None, model) == 270_000
    assert local_llm.input_token_budget(270_000) == 189_000


def test_493_local_distill_does_not_hit_table():
    # prefix, not substring: a local distill that merely contains the name is not 1M
    assert local_llm.known_model_window("my-deepseek-distill") == 0
    assert local_llm.known_model_window("my-deepseek-v4-pro-q4") == 0
    assert local_llm.resolve_context_window("my-deepseek-distill") == 270_000


def test_493_resolve_rule_order():
    assert local_llm.resolve_context_window("deepseek-flash", 64_000) == 64_000
    assert local_llm.resolve_context_window("deepseek-flash") == 1_000_000
    assert local_llm.resolve_context_window("mystery-7b") == 270_000
    assert local_llm.resolve_context_window("") == 270_000


def test_493_non_table_fallback_paths_are_270k():
    assert local_llm.context_window_tokens(None) == 270_000
    assert local_llm.input_token_budget(None) == 189_000


# ------------------------------------------------------------- external_context

def _long_history():
    # ~250k tokens: over 270k*70% (189k), well under 1M*70%.
    return [{"role": r, "content": "字" * 12_500}
            for _ in range(10) for r in ("user", "assistant")]


def test_493_external_context_uses_shared_window():
    history = _long_history()
    wide = external_context.apply_cold_start(
        TurnRequest(chat_id="c", user_text="hi", history=history, model="deepseek-flash"))
    narrow = external_context.apply_cold_start(
        TurnRequest(chat_id="c", user_text="hi", history=history, model="mystery-7b"))
    assert wide.user_text.count("字" * 12_500) == len(history)
    assert narrow.user_text.count("字" * 12_500) < len(history)


def test_493_external_context_empty_model_gets_270k(monkeypatch):
    seen: list = []
    real = external_context.resolve_context_window

    def spy(model, declared=0):
        out = real(model, declared)
        seen.append((model, out))
        return out
    monkeypatch.setattr(external_context, "resolve_context_window", spy)
    external_context.apply_cold_start(
        TurnRequest(chat_id="c", user_text="hi", history=[{"role": "user", "content": "a"}]))
    assert seen == [("", 270_000)]


# ------------------------------------------------------------- summary cap

@pytest.mark.parametrize("window, cap", [
    (32_000, 1_600), (1_000_000, 16_000), (10_000, 1_000), (270_000, 13_500), (None, 13_500),
], ids=["32k", "1m-ceiling", "10k-floor", "270k-fallback", "unknown"])
def test_493_summary_token_cap_is_5pct_clamped(window, cap):
    assert local_llm.summary_token_cap(window) == cap


def test_493_fit_history_summary_uses_window_cap():
    history = [{"role": "user", "text": "z" * 400_000},
               *[{"role": "user", "text": f"RECENT{i}"} for i in range(6)]]
    msgs = local_llm.fit_history(history, context_window=100_000)
    assert local_llm.count_tokens(msgs[0]["content"]) <= local_llm.summary_token_cap(100_000)


# ------------------------------------------------------------- overflow guard

class _Seq:
    """Scripted /chat/completions answers; records the messages of every request."""

    def __init__(self, p, answers):
        self.answers, self.sent = list(answers), []

        async def fake(session, method, url, *, headers, json_body=None, timeout=120):
            self.sent.append(json_body)
            a = self.answers.pop(0)
            if isinstance(a, BaseException):
                raise a
            return a
        p._request_json = fake


async def _noop(_ev):
    return None


def _big_messages(n=40, size=4_000):
    return [{"role": "system", "content": "sys"},
            *[{"role": "user" if i % 2 == 0 else "assistant", "content": f"M{i} " + "y" * size}
              for i in range(n)],
            {"role": "user", "content": "LAST"}]


def _refit(m, w):
    return local_llm.refit_messages(m, w)


async def test_493_overflow_with_number_resends_once_and_caches():
    p = LocalLlmProvider(base_url=lambda: BASE)
    seq = _Seq(p, [LlmHttpError(400, OVERFLOW_8K), OK])
    body = {"model": "m", "messages": _big_messages()}
    data, used = await p._llm_request_fit(None, URL, body, _noop, TurnHandle(),
                                          model="m", window=270_000, refit=_refit)
    assert data == OK
    assert used == 8_192
    assert len(seq.sent) == 2
    resent = seq.sent[1]["messages"]
    assert local_llm._message_tokens(resent) <= local_llm.input_token_budget(8_192)
    assert resent[0]["role"] == "system" and resent[-1]["content"] == "LAST"
    assert p._model_windows[(BASE, "m")] == 8_192


async def test_493_next_call_uses_cached_window_without_error():
    p = LocalLlmProvider(base_url=lambda: BASE)
    _Seq(p, [LlmHttpError(400, OVERFLOW_8K), OK])
    await p._llm_request_fit(None, URL, {"model": "m", "messages": _big_messages()}, _noop,
                             TurnHandle(), model="m", window=270_000, refit=_refit)
    models_calls: list = []

    async def models(session, method, url, *, headers, json_body=None, timeout=120):
        models_calls.append(url)
        return {"data": [{"id": "m"}]}
    p._request_json = models
    assert await p._context_window(None, "m") == 8_192
    assert models_calls == []  # answered from the cache, no refetch, no error


async def test_493_overflow_without_number_shrinks_by_half():
    p = LocalLlmProvider(base_url=lambda: BASE)
    seq = _Seq(p, [LlmHttpError(400, OVERFLOW_NO_NUMBER), OK])
    _, used = await p._llm_request_fit(None, URL, {"model": "m", "messages": _big_messages()},
                                       _noop, TurnHandle(), model="m", window=100_000, refit=_refit)
    assert local_llm.OVERFLOW_SHRINK == 0.5
    assert used == 50_000
    assert p._model_windows[(BASE, "m")] == 50_000
    assert len(seq.sent) == 2


async def test_493_overflow_without_number_floor_32k():
    p = LocalLlmProvider(base_url=lambda: BASE)
    seq = _Seq(p, [LlmHttpError(400, OVERFLOW_NO_NUMBER), OK])
    _, used = await p._llm_request_fit(None, URL, {"model": "m", "messages": _big_messages()},
                                       _noop, TurnHandle(), model="m", window=40_000, refit=_refit)
    assert used == 32_000                      # max(32_000, 40_000 * 0.5)
    assert p._model_windows[(BASE, "m")] == 32_000
    assert len(seq.sent) == 2


async def test_493_second_overflow_raises_no_loop():
    p = LocalLlmProvider(base_url=lambda: BASE)
    seq = _Seq(p, [LlmHttpError(400, OVERFLOW_8K), LlmHttpError(400, OVERFLOW_8K), OK])
    with pytest.raises(LlmHttpError):
        await p._llm_request_fit(None, URL, {"model": "m", "messages": _big_messages()}, _noop,
                                 TurnHandle(), model="m", window=270_000, refit=_refit)
    assert len(seq.sent) == 2


async def test_493_non_overflow_400_is_not_resent():
    p = LocalLlmProvider(base_url=lambda: BASE)
    seq = _Seq(p, [LlmHttpError(400, "invalid tool schema"), OK])
    with pytest.raises(LlmHttpError):
        await p._llm_request_fit(None, URL, {"model": "m", "messages": []}, _noop, TurnHandle(),
                                 model="m", window=270_000, refit=_refit)
    assert len(seq.sent) == 1


def test_493_parse_overflow_window():
    assert local_llm.parse_overflow_window(OVERFLOW_8K) == 8_192
    assert local_llm.parse_overflow_window("context window of 131,072 tokens exceeded") == 131_072
    assert local_llm.parse_overflow_window(OVERFLOW_NO_NUMBER) == 0


# ------------------------------------------------------------- loop guard + billing (agent loop)

async def test_493_resend_is_not_a_duplicate_or_extra_charge(monkeypatch, store):
    """Same run with and without one overflow: same stop (done, not stuck/repeat), same tokens
    charged, same steps. The failed request is neither a step nor a charge."""
    from test_agent_budget_391 import Rig, calls, reply, stop_of
    usage = {"prompt_tokens": 500, "completion_tokens": 5}
    ok = {**reply("好了"), "usage": usage}
    tool = {**calls(("add_text", {"text": "a"})), "usage": usage}

    base_rig = Rig(monkeypatch, [tool, ok], store=store)
    base_res, _ = await base_rig.send("加一行字")
    over_rig = Rig(monkeypatch, [tool, LlmHttpError(400, OVERFLOW_8K), ok], store=store)
    over_res, _ = await over_rig.send("加一行字")

    assert stop_of(over_res)["reason"] == "done" and over_res.error == ""
    assert over_rig.n == base_rig.n + 1          # exactly one extra (resent) HTTP request
    assert over_res.run["log"]["tokens"] == base_res.run["log"]["tokens"]
    assert over_res.run["log"]["steps"] == base_res.run["log"]["steps"]
    assert over_rig.mcp == base_rig.mcp          # tool calls not repeated


# ------------------------------------------------------------- QA /models dump (provider prefix, max_input)

@pytest.mark.parametrize("model", ["deepseek/deepseek-v4.1-flash-1017", "openrouter/deepseek/deepseek-v4-pro",
                                   "deepseek/deepseek-flash"])
def test_493_provider_prefixed_ids_hit_table(model):
    assert local_llm.known_model_window(model) == 1_000_000
    assert local_llm.resolve_context_window(model) == 1_000_000


def test_493_prefix_strip_still_misses_distill():
    assert local_llm.known_model_window("someone/my-deepseek-distill") == 0


QA_DUMP = {"data": [{"id": "deepseek/deepseek-v4.1-flash-1017",
                     "max_context_tokens": 1_048_576, "max_input_tokens": 655_360}]}


async def test_493_max_context_tokens_is_window_and_max_input_caps_budget():
    p = LocalLlmProvider(base_url=lambda: BASE)
    _stub(p, QA_DUMP)
    model = "deepseek/deepseek-v4.1-flash-1017"
    window = await p._context_window(None, model)
    assert window == 1_048_576
    assert local_llm.input_token_budget(window) == 734_003       # 70% alone
    assert p._input_budget(model, window) == 655_360             # min(70%, max_input_tokens)


def test_493_input_budget_min_rule():
    assert local_llm.input_token_budget(1_048_576, 655_360) == 655_360
    assert local_llm.input_token_budget(100_000, 655_360) == 70_000
    assert local_llm.input_token_budget(100_000, 0) == 70_000


def test_493_history_fit_uses_max_input_cap():
    # ~700k tokens of history: under 70% of 1048576 (734k) but over max_input_tokens (655k)
    history = [{"role": r, "text": "字" * 35_000} for _ in range(10) for r in ("user", "assistant")]
    wide = local_llm.fit_history(history, context_window=1_048_576)
    capped = local_llm.fit_history(history, context_window=1_048_576, max_input_tokens=655_360)
    assert wide[0]["role"] != "system"
    assert capped[0]["role"] == "system"
    assert local_llm._message_tokens(capped) <= 655_360


async def test_493_default_config_models_request_carries_auth(monkeypatch):
    """Default config (WaveSpeed endpoint, no LLM key env, WaveSpeed key in settings): /models is sent
    with the same key as the chat request, so the endpoint's 1048576 window is read, not the table's 1M."""
    from ComfyArt.api import settings, wavespeed
    from ComfyArt.api.providers import AgentLlmProvider
    monkeypatch.delenv("COMFYART_LOCAL_LLM_API_KEY", raising=False)
    monkeypatch.setattr(settings, "read_json", lambda *_a, **_k: {})
    monkeypatch.setattr(wavespeed, "key_source", lambda: ("ws-test-key", "settings"))
    base = settings.get_setting("bot-local-llm-url")
    assert base == "https://llm.wavespeed.ai/v1"
    p = AgentLlmProvider(base_url=lambda: base)
    seen: list = []

    async def models(session, method, url, *, headers, json_body=None, timeout=120):
        seen.append(headers.get("Authorization"))
        if headers.get("Authorization") != "Bearer ws-test-key":
            raise LlmHttpError(401, "missing auth")
        return QA_DUMP
    p._request_json = models
    window = await p._context_window(None, "deepseek/deepseek-v4.1-flash-1017")
    assert seen == ["Bearer ws-test-key"]
    assert seen[0] == p._api_headers()["Authorization"]   # same key as the chat request
    assert window == 1_048_576
