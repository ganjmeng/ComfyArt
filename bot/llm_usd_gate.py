"""Fail-closed USD validation gate for the official direct DeepSeek chat route.

The gate sits on the physical HTTP boundary after provider body adaptation. It
does not price WaveSpeed, and it does not treat ``count_tokens`` as a billed-token
guarantee. Money is integer nano-USD (1 nano-USD = 1e-9 USD). $0.05 is exactly
50_000_000 nano-USD. Rates are the peak cache-miss input price and the peak output
price from the official pricing page retrieved 2026-11-18. Off-peak is half of
peak and depends on Chinese public holidays, so every reservation and every
reconciliation uses peak. Reservations assume a cache miss. A later usage object
may reconcile down only when every required usage field is present and consistent.

Official sources (retrieved 2026-11-18):

- https://api-docs.deepseek.com/quick_start/pricing
- https://api-docs.deepseek.com/api/create-chat-completion
- https://api-docs.deepseek.com/quick_start/token_usage
- https://api-docs.deepseek.com/guides/vision
- https://api-docs.deepseek.com/news/news260910

Pricing page, per 1M tokens, peak (the higher band):

- deepseek-flash cache-miss input $0.30, cache-hit input $0.006, output $1.20
- deepseek-v4-pro cache-miss input $1.32, cache-hit input $0.044, output $3.96

The 2026-09-10 news post says deepseek-v4-pro would route to V4.1-Flash at Flash
rates after 2026-09-14. The pricing page still lists Pro's own higher rates and
version DeepSeek-V4-Pro-0813. This snapshot keeps the higher published Pro rates.

Chat completions ``max_tokens`` must be from 1 to 384K, and the same page defines
384K as 393216, so K is 1024. When ``max_tokens`` is omitted the documented
default is 8K (8192) in non-thinking mode, 64K (65536) in thinking mode, and
128K (131072) when ``reasoning_effort`` is ``max``. The gate writes that default
onto the body when the field is absent. Ordinary, summary, and thinking
(including the memory-add boost) share those documented ceilings. It never
lowers an explicit cap to make the call fit a budget.

The default validation scope is $0.05. A separate cumulative $2 scope exists
only as explicit code support: it must be opened on its own ledger path and
then bound with ``use_authorized_scope`` before ``dispatch`` or the official
HTTP wrapper, which omits ``ledger_path``, will use it. Binding is in-process,
does not replace ``default_ledger_path``, does not absorb a prior balance, and
is not performed by ``install``. Opening a scope is not a live activation.

Reopening trusts the ledger file. ``ceiling_nano`` is clamped to that file's
authorization binding, and a default or legacy scope that already has non-$2
reservations cannot be raised by editing the ceiling. The authorization field
lives in the same file, so an empty or rewritten ledger can be recast as $2
by editing the file. ``open_authorized_scope`` itself will not upgrade or reset
an existing scope.

Billed input tokens are not a proven upper bound. The token-usage page gives
approximate character ratios and says the actual number is the usage the model
returns. The demo tokenizer zip is not a published ceiling on prompt tokens
after the server chat template, tool schemas, or images. Vision states 1024
tokens as an image cap, and the token-usage page says an image estimate can
vary slightly from billed usage. Tool schemas have no official token formula.
``count_tokens`` in ``local_llm`` is a character heuristic, not a guarantee.
Any of those gaps blocks the HTTP call. A functional reservation path still
exists for a caller that supplies a separate proven bound for a text-only body.
The current direct route does not have that bound, so it stays blocked.
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import urlparse

_log = logging.getLogger("comfyart.llm_usd_gate")

CEILING_NANO = 50_000_000  # $0.05 exactly. Default scope. No confirm path raises this.
TWO_DOLLAR_CEILING_NANO = 2_000_000_000  # $2 exactly. Only for an explicitly opened new scope.
AUTHORIZED_CEILINGS_NANO = frozenset({CEILING_NANO, TWO_DOLLAR_CEILING_NANO})
DEFAULT_AUTHORIZATION = "default-0.05"
TWO_DOLLAR_AUTHORIZATION = "explicit-2.00"
SNAPSHOT_ID = "deepseek-pricing-2026-11-18"
RETRIEVED = "2026-11-18"
PRICING_URL = "https://api-docs.deepseek.com/quick_start/pricing"
CHAT_URL = "https://api-docs.deepseek.com/api/create-chat-completion"
TOKEN_URL = "https://api-docs.deepseek.com/quick_start/token_usage"
VISION_URL = "https://api-docs.deepseek.com/guides/vision"
PRO_NEWS_URL = "https://api-docs.deepseek.com/news/news260910"
MAX_OUTPUT_SUPPORTED = 393_216  # 384K as parenthesized on the pricing / chat pages
NON_THINKING_DEFAULT = 8_192
THINKING_DEFAULT = 65_536
THINKING_MAX_EFFORT_DEFAULT = 131_072
ORDINARY_OUTPUT_DEFAULT = NON_THINKING_DEFAULT
SUMMARY_OUTPUT_DEFAULT = NON_THINKING_DEFAULT
MEMORY_BOOST_OUTPUT_DEFAULT = THINKING_DEFAULT
_LEDGER_NAME = "llm_usd_ledger.json"
_thread_lock = threading.Lock()
_bound_ledger_path = None

_SOURCES = (PRICING_URL, CHAT_URL, TOKEN_URL, VISION_URL, PRO_NEWS_URL)

# nano-USD per token. Computed as ceil(usd_per_million * 1000) from integer
# ratios so the stored rate does not pass through binary float.
# $0.30 = 3/10 → 300; $0.006 = 6/1000 → 6; $1.20 = 6/5 → 1200
# $1.32 = 132/100 → 1320; $0.044 = 44/1000 → 44; $3.96 = 396/100 → 3960
def _nano_per_token(numerator: int, denominator: int) -> int:
    num = numerator * 1000
    return (num + denominator - 1) // denominator


_FLASH = {
    "input_miss_peak_nano": _nano_per_token(3, 10),
    "input_hit_peak_nano": _nano_per_token(6, 1000),
    "output_peak_nano": _nano_per_token(6, 5),
    "list_model": "deepseek-flash",
    "version": "DeepSeek-V4.1-Flash-1017",
}
_PRO = {
    "input_miss_peak_nano": _nano_per_token(132, 100),
    "input_hit_peak_nano": _nano_per_token(44, 1000),
    "output_peak_nano": _nano_per_token(396, 100),
    "list_model": "deepseek-v4-pro",
    "version": "DeepSeek-V4-Pro-0813",
    "note": "higher of the pricing-page Pro rate and the 2026-09-10 news post",
}
PRICES: dict[str, dict[str, Any]] = {
    "deepseek-flash": _FLASH,
    "deepseek-v4-pro": _PRO,
}

_BODY_KEYS = frozenset({
    "messages", "model", "thinking", "reasoning_effort", "max_tokens",
    "response_format", "stop", "stream", "stream_options", "temperature",
    "top_p", "tools", "tool_choice", "safety_check", "title", "logprobs",
    "top_logprobs", "user_id", "frequency_penalty", "presence_penalty",
})
_TEXT_ROLES = frozenset({"system", "user", "assistant"})
_TEXT_MSG_KEYS = frozenset({"role", "content", "name"})
_WEB_TOOLS = frozenset({"deepseek_web_search", "deepseek_read_url"})
_EFFORT = {
    "none": "none", "low": "low", "high": "high", "max": "max",
    "minimal": "low", "medium": "high", "xhigh": "high",
}
_USAGE_KEYS = frozenset({
    "prompt_tokens", "prompt_tokens_details", "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens", "completion_tokens", "total_tokens",
    "completion_tokens_details", "server_tool_use",
})
_USAGE_REQUIRED = (
    "prompt_tokens", "prompt_tokens_details", "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens", "completion_tokens", "total_tokens",
)

_BLOCK_TEXT = {
    "unpriced": (
        "官方 DeepSeek 这次调用没有价目快照，已在联网前阻断。"
        " / No official DeepSeek price snapshot for this call. Blocked before HTTP."
    ),
    "unbounded_tools": (
        "工具序列化的计费 token 没有官方上界，已在联网前阻断。"
        " / Tool serialization has no official billed-token bound. Blocked before HTTP."
    ),
    "unbounded_multimodal": (
        "图像计费 token 不能证明为上界，已在联网前阻断。"
        " / Image billed tokens are not a proven upper bound. Blocked before HTTP."
    ),
    "unbounded_billed_input": (
        "计费输入 token 没有可证明的上界。字符计数不是保证。已在联网前阻断。"
        " / No provable billed-input token bound. The character-count heuristic is not a guarantee. Blocked before HTTP."
    ),
    "unpriced_tool_fee": (
        "官方网页搜索或抓取按次计费，次数没有上界，已在联网前阻断。"
        " / Official web search or fetch is billed per use with no count cap. Blocked before HTTP."
    ),
    "over_budget": (
        "同一校验范围的硬顶不够覆盖最坏输入加最大输出，已在联网前阻断。确认不能提高硬顶。"
        " / The shared validation ceiling cannot cover worst-case input plus maximum output. Blocked before HTTP. Confirmation cannot raise the cap."
    ),
    "unsupported_output_cap": (
        "最大输出 token 缺失或不在官方支持范围内，已在联网前阻断。"
        " / Maximum output tokens are missing or outside the supported range. Blocked before HTTP."
    ),
    "unsupported_stream": (
        "流式响应无法在发送前封顶对账，已在联网前阻断。"
        " / Streaming cannot be capped and reconciled before send. Blocked before HTTP."
    ),
    "unsupported_request_field": (
        "请求里有未列入官方计费模型的字段，已在联网前阻断。"
        " / The request has a field this billing snapshot does not cover. Blocked before HTTP."
    ),
    "route_mismatch": (
        "请求与锁定的官方路由不一致，已在联网前阻断。"
        " / The request does not match the locked official route. Blocked before HTTP."
    ),
    "ledger_unreadable": (
        "校验账本无法读取，为避免重置 $0.05 上限，已在联网前阻断。"
        " / The validation ledger cannot be read. Blocked before HTTP so the $0.05 ceiling is not reset."
    ),
}


class LlmScopeConflict(RuntimeError):
    """Raised when opening a scope would reset, upgrade, or replace an existing ledger."""


class LlmBudgetBlocked(RuntimeError):
    """Raised before any socket send. Not an HTTP error, so the retry loop must not catch it."""

    def __init__(self, code: str, detail: str = "", *, scope_id: str = "") -> None:
        self.code = code
        self.detail = detail
        self.scope_id = scope_id
        text = _BLOCK_TEXT.get(code, code)
        if detail:
            text = f"{text} [{detail}]"
        super().__init__(text)


class Bound:
    __slots__ = ("ok", "tokens", "code", "detail")

    def __init__(self, ok: bool, tokens: int = 0, code: str = "", detail: str = "") -> None:
        self.ok = ok
        self.tokens = tokens
        self.code = code
        self.detail = detail


def default_ledger_path() -> str:
    from ..api._common import app_path
    return app_path(_LEDGER_NAME)


def price_snapshot(model: str) -> Optional[dict]:
    """Immutable list-price snapshot for an official request model, or None when unpriced.

    WaveSpeed ids such as ``deepseek/deepseek-v4.1-flash-1017`` are not in this table.
    """
    row = PRICES.get(model)
    if row is None:
        return None
    return {
        "snapshot_id": SNAPSHOT_ID,
        "retrieved": RETRIEVED,
        "sources": list(_SOURCES),
        "model": model,
        "list_model": row["list_model"],
        "version": row["version"],
        "input_miss_peak_nano": row["input_miss_peak_nano"],
        "input_hit_peak_nano": row["input_hit_peak_nano"],
        "output_peak_nano": row["output_peak_nano"],
        "max_output_supported": MAX_OUTPUT_SUPPORTED,
        "context_length": 1_000_000,
        "peak_policy": "always_peak",
        "cache_policy": "reserve_cache_miss",
        "currency": "USD",
        "unit": "nano_usd_per_token",
    }


def worst_case_nano(snapshot: dict, input_tokens: int, max_output_tokens: int) -> int:
    """Peak cache-miss input plus peak output. Both factors are non-negative ints."""
    return (input_tokens * snapshot["input_miss_peak_nano"]
            + max_output_tokens * snapshot["output_peak_nano"])


def official_input_bound(body: dict, snapshot: dict) -> Bound:
    """Production bound. Text and images are unproven, so this never authorizes a send.

    Ordinary MCP function tools are not a structural block; they still do not
    invent a billed-input ceiling. The character-count heuristic is not consulted.
    """
    structural = structural_block(body)
    if structural:
        return Bound(False, 0, structural, _structural_detail(structural))
    return Bound(False, 0, "unbounded_billed_input", _structural_detail("unbounded_billed_input"))


def structural_block(body: dict) -> str:
    """Return a block code when the body shape itself has no proven billed-input accounting."""
    if not isinstance(body, dict):
        return "unbounded_billed_input"
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        return "unbounded_billed_input"
    if _web_tool_fee(body):
        return "unpriced_tool_fee"
    if _has_nonordinary_tools(body):
        return "unbounded_tools"
    if _has_multimodal(body):
        return "unbounded_multimodal"
    for msg in messages:
        if not isinstance(msg, dict):
            return "unbounded_billed_input"
        if _ordinary_mcp_message(msg):
            continue
        if set(msg) - _TEXT_MSG_KEYS:
            return "unbounded_billed_input"
        if msg.get("role") not in _TEXT_ROLES:
            return "unbounded_billed_input"
        if "name" in msg and type(msg.get("name")) is not str:
            return "unbounded_billed_input"
        if type(msg.get("content")) is not str:
            return "unbounded_billed_input"
    return ""


def _structural_detail(code: str) -> str:
    if code == "unbounded_tools":
        return f"tool schema tokens are not specified at {CHAT_URL}"
    if code == "unbounded_multimodal":
        return (
            f"vision cap is an estimate that can vary ({VISION_URL}; {TOKEN_URL}). "
            "1024 is not applied as a billed guarantee, and text overhead is still unproven"
        )
    if code == "unpriced_tool_fee":
        return f"web search and fetch are per-use at {PRICING_URL}"
    return (
        f"approximate ratios only; billed tokens are the returned usage ({TOKEN_URL}). "
        "The character-count heuristic is not a guarantee"
    )


def _web_tool_fee(body: dict) -> bool:
    tools = body.get("tools")
    if isinstance(tools, list):
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
            name = str(fn.get("name") or tool.get("name") or tool.get("type") or "")
            if name in _WEB_TOOLS:
                return True
    choice = body.get("tool_choice")
    if isinstance(choice, dict):
        fn = choice.get("function") if isinstance(choice.get("function"), dict) else {}
        name = fn.get("name") or choice.get("name")
        if name in _WEB_TOOLS:
            return True
    return False


_ORDINARY_TOOL_CHOICES = frozenset({None, "none", "auto", "required"})
_ORDINARY_TOOL_MSG_KEYS = frozenset({"role", "content", "name", "tool_call_id"})
_ORDINARY_ASSISTANT_TOOL_KEYS = frozenset({"role", "content", "name", "tool_calls"})


def _function_tool_name(tool: dict) -> str | None:
    """Return the function name when *tool* is an ordinary Chat Completions function tool."""
    if tool.get("type") != "function":
        return None
    fn = tool.get("function")
    if not isinstance(fn, dict):
        return None
    name = fn.get("name")
    return name if type(name) is str and name else None


def _ordinary_function_tools(tools) -> bool:
    """True when every declared tool is a non-web Chat Completions function tool (MCP style)."""
    if tools is None:
        return True
    if not isinstance(tools, list):
        return False
    for tool in tools:
        if not isinstance(tool, dict):
            return False
        name = _function_tool_name(tool)
        if name is None or name in _WEB_TOOLS:
            return False
    return True


def _ordinary_function_tool_call(call) -> bool:
    if not isinstance(call, dict):
        return False
    if call.get("type") not in (None, "function"):
        return False
    fn = call.get("function")
    if not isinstance(fn, dict):
        return False
    name = fn.get("name")
    return type(name) is str and bool(name) and name not in _WEB_TOOLS


def _ordinary_mcp_message(msg: dict) -> bool:
    """True for a client MCP tool result or an assistant function tool_calls message.

    These are not vendor built-in web tools. Image parts are rejected earlier as
    multimodal. Unknown keys or content shapes are not accepted here.
    """
    role = msg.get("role")
    if role in ("tool", "function"):
        if set(msg) - _ORDINARY_TOOL_MSG_KEYS:
            return False
        if "name" in msg and type(msg.get("name")) is not str:
            return False
        if "tool_call_id" in msg and type(msg.get("tool_call_id")) is not str:
            return False
        return type(msg.get("content")) is str
    if role != "assistant" or "tool_calls" not in msg:
        return False
    if "server_tool_calls" in msg:
        return False
    if set(msg) - _ORDINARY_ASSISTANT_TOOL_KEYS:
        return False
    if "name" in msg and type(msg.get("name")) is not str:
        return False
    if msg.get("content") is not None and type(msg.get("content")) is not str:
        return False
    calls = msg.get("tool_calls")
    if not isinstance(calls, list) or not calls:
        return False
    return all(_ordinary_function_tool_call(call) for call in calls)


def _has_tools(body: dict) -> bool:
    tools = body.get("tools")
    if isinstance(tools, list) and tools:
        return True
    if body.get("tool_choice") not in (None, "none"):
        return True
    for msg in body.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") in ("tool", "function") or msg.get("tool_calls") or msg.get("server_tool_calls"):
            return True
    return False


def _ordinary_tool_choice(value) -> bool:
    """True for standard Chat Completions function-tool control values.

    ``required`` and a named ``type: function`` choice are ordinary MCP controls,
    not a vendor web-search fee. Unknown shapes stay rejected.
    """
    if isinstance(value, dict):
        if set(value) - {"type", "function"}:
            return False
        if value.get("type") != "function":
            return False
        fn = value.get("function")
        if not isinstance(fn, dict) or set(fn) - {"name"}:
            return False
        name = fn.get("name")
        return type(name) is str and bool(name) and name not in _WEB_TOOLS
    return value in _ORDINARY_TOOL_CHOICES


def _has_nonordinary_tools(body: dict) -> bool:
    """True when tool machinery is present and is not ordinary MCP function calling.

    Ordinary MCP: ``type: function`` tools; ``tool_choice`` omitted / none / auto /
    required / a named function; and function ``tool_calls`` plus ``role: tool`` /
    ``function`` result messages. Vendor web tools are classified earlier as
    ``unpriced_tool_fee``. Unknown tool types and ``server_tool_calls`` stay blocked.
    """
    if not _has_tools(body):
        return False
    if not _ordinary_tool_choice(body.get("tool_choice")):
        return True
    if not _ordinary_function_tools(body.get("tools")):
        return True
    for msg in body.get("messages") or []:
        if not isinstance(msg, dict):
            return True
        if msg.get("server_tool_calls"):
            return True
        if msg.get("role") in ("tool", "function") or "tool_calls" in msg:
            if not _ordinary_mcp_message(msg):
                return True
    return False


def _has_multimodal(body: dict) -> bool:
    for msg in body.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    return True
                if part.get("type") in ("image_url", "image", "input_image", "file"):
                    return True
                if "image_url" in part or "file_id" in part or "file_data" in part:
                    return True
        elif isinstance(content, dict):
            return True
    return False


def _mode_default_max(body: dict) -> Optional[int]:
    effort = body.get("reasoning_effort", None)
    if effort is not None:
        if not isinstance(effort, str) or effort not in _EFFORT:
            return None
        effort = _EFFORT[effort]
    thinking = body.get("thinking", None)
    thinking_on: Optional[bool]
    if thinking is None:
        thinking_on = effort != "none"
    elif isinstance(thinking, dict):
        if set(thinking) - {"type"}:
            return None
        kind = thinking.get("type")
        if kind == "disabled":
            thinking_on = False
        elif kind == "enabled":
            thinking_on = True
        else:
            return None
    else:
        return None
    if not thinking_on:
        return NON_THINKING_DEFAULT
    if effort == "max":
        return THINKING_MAX_EFFORT_DEFAULT
    return THINKING_DEFAULT


def apply_output_cap(body: dict) -> tuple[Optional[int], str]:
    """Write the documented default when max_tokens is absent. Never shrink an explicit value."""
    if "max_tokens" not in body or body.get("max_tokens") is None:
        cap = _mode_default_max(body)
        if cap is None:
            return None, "unsupported_output_cap"
        body["max_tokens"] = cap
        return cap, ""
    raw = body.get("max_tokens")
    if type(raw) is not int or not (1 <= raw <= MAX_OUTPUT_SUPPORTED):
        return None, "unsupported_output_cap"
    return raw, ""


def route_requires_gate(method: str, url: str, route: Optional[dict]) -> bool:
    if not isinstance(route, dict) or route.get("passthrough"):
        return False
    if route.get("adapter") != "deepseek_official":
        return False
    if str(method or "").upper() != "POST":
        return False
    path = urlparse(str(url or "")).path.rstrip("/")
    return path.endswith("/chat/completions")


def _host(url: str) -> str:
    return (urlparse(str(url or "")).hostname or "").lower()


def _fail(code: str, detail: str = "") -> dict:
    return {"ok": False, "code": code, "detail": detail or _BLOCK_TEXT.get(code, code)}


def prepare(body: dict, route: dict, url: str, bound_fn: Optional[Callable[[dict, dict], Bound]] = None) -> dict:
    """Decide the reservation. May set ``max_tokens`` on ``body``. Does not touch the ledger or the network."""
    if not isinstance(body, dict) or not isinstance(route, dict):
        return _fail("route_mismatch")
    if _host(url) != _host(str(route.get("base_url") or "")) or not _host(url):
        return _fail("route_mismatch", "host")
    model = body.get("model")
    if type(model) is not str or model != route.get("model"):
        return _fail("route_mismatch", "model")
    unknown = sorted(set(body) - _BODY_KEYS)
    if unknown:
        return _fail("unsupported_request_field", ",".join(unknown))
    stream = body.get("stream", False)
    if stream not in (None, False):
        return _fail("unsupported_stream")
    snapshot = price_snapshot(model)
    if snapshot is None:
        return _fail("unpriced", model)
    structural = structural_block(body)
    if structural:
        return _fail(structural, _structural_detail(structural))
    cap, cap_code = apply_output_cap(body)
    if cap is None:
        return _fail(cap_code or "unsupported_output_cap")
    bound = (bound_fn or official_input_bound)(body, snapshot)
    if not isinstance(bound, Bound) or not bound.ok or type(bound.tokens) is not int or bound.tokens < 0:
        code = bound.code if isinstance(bound, Bound) and bound.code else "unbounded_billed_input"
        detail = bound.detail if isinstance(bound, Bound) else ""
        return _fail(code, detail)
    nano = worst_case_nano(snapshot, bound.tokens, cap)
    if type(nano) is not int or nano <= 0:
        return _fail("unbounded_billed_input", "non_positive_reservation")
    return {
        "ok": True,
        "code": "ready",
        "detail": "",
        "snapshot": snapshot,
        "input_tokens": bound.tokens,
        "max_output_tokens": cap,
        "reserved_nano": nano,
        "route": {
            "provider": str(route.get("provider") or ""),
            "model": model,
            "catalog_model": str(route.get("catalog_model") or ""),
            "base_url": str(route.get("base_url") or ""),
            "adapter": str(route.get("adapter") or ""),
            "quote": route.get("quote") if isinstance(route.get("quote"), str) else "unknown",
            "snapshot_id": snapshot["snapshot_id"],
        },
    }


def _fresh(*, ceiling_nano: int = CEILING_NANO, authorization: str = DEFAULT_AUTHORIZATION) -> dict:
    if ceiling_nano not in AUTHORIZED_CEILINGS_NANO:
        raise LlmScopeConflict("ceiling is not an authorized validation cap")
    if authorization == TWO_DOLLAR_AUTHORIZATION:
        if ceiling_nano != TWO_DOLLAR_CEILING_NANO:
            raise LlmScopeConflict("authorization does not match the authorized ceiling")
    elif authorization != DEFAULT_AUTHORIZATION or ceiling_nano != CEILING_NANO:
        raise LlmScopeConflict("authorization does not match the authorized ceiling")
    return {
        "version": 1,
        "scope_id": "usd-" + uuid.uuid4().hex,
        "authorization": authorization,
        "authorized_ceiling_nano": ceiling_nano,
        "ceiling_nano": ceiling_nano,
        "accounted_nano": 0,
        "reservations": {},
    }


def open_authorized_scope(path: str, ceiling_nano: int) -> dict:
    """Create a new independent validation scope with a durable authorized cap.

    An existing ledger is left unchanged: this will not upgrade, reset, merge a
    prior balance, or replace the default $0.05 path. It does not reserve or spend.
    """
    if type(ceiling_nano) is not int or ceiling_nano not in AUTHORIZED_CEILINGS_NANO:
        raise LlmScopeConflict("ceiling is not an authorized validation cap")
    authorization = (
        TWO_DOLLAR_AUTHORIZATION if ceiling_nano == TWO_DOLLAR_CEILING_NANO
        else DEFAULT_AUTHORIZATION
    )
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with _thread_lock:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            os.chmod(path, 0o600)
            with os.fdopen(fd, "r+", encoding="utf-8") as handle:
                fd = -1
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    raw = handle.read()
                    if raw.strip():
                        raise LlmScopeConflict("a validation scope already exists at this path")
                    data = _fresh(ceiling_nano=ceiling_nano, authorization=authorization)
                    json.dump(data, handle, ensure_ascii=True, separators=(",", ":"))
                    handle.flush()
                    os.fsync(handle.fileno())
                    return {
                        "ok": True,
                        "scope_id": data["scope_id"],
                        "authorization": authorization,
                        "authorized_ceiling_nano": ceiling_nano,
                        "ceiling_nano": ceiling_nano,
                        "accounted_nano": 0,
                    }
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            if fd >= 0:
                os.close(fd)


def clear_authorized_scope() -> None:
    """Drop the in-process bind. Does not change any ledger file or the default path."""
    global _bound_ledger_path
    with _thread_lock:
        _bound_ledger_path = None


def use_authorized_scope(path: str) -> dict:
    """Bind later dispatch calls that omit ledger_path to an already-opened scope.

    Does not open, upgrade, spend, or change ``default_ledger_path``. The official
    install wrapper omits ``ledger_path``, so this is how that transport can
    consume an explicit authorized ledger. Nothing in ``install`` binds a scope.
    """
    if type(path) is not str or not path or not os.path.isfile(path):
        raise LlmScopeConflict("no authorized scope exists at this path")
    try:
        fd = os.open(path, os.O_RDONLY)
        try:
            with os.fdopen(fd, "r", encoding="utf-8") as handle:
                fd = -1
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                try:
                    raw = handle.read()
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            if fd >= 0:
                os.close(fd)
    except OSError as exc:
        raise LlmScopeConflict("authorized scope is unreadable") from exc
    if not raw.strip():
        raise LlmScopeConflict("no authorized scope exists at this path")
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise LlmScopeConflict("authorized scope is unreadable") from exc
    data = _normalize(parsed)
    global _bound_ledger_path
    with _thread_lock:
        _bound_ledger_path = path
    return {
        "ok": True,
        "path": path,
        "scope_id": data["scope_id"],
        "authorization": data["authorization"],
        "authorized_ceiling_nano": data["authorized_ceiling_nano"],
        "ceiling_nano": data["ceiling_nano"],
        "accounted_nano": data["accounted_nano"],
    }


def resolved_ledger_path(ledger_path: Optional[str] = None) -> str:
    """Explicit path, else the in-process bind, else the default $0.05 ledger path."""
    if ledger_path:
        return ledger_path
    with _thread_lock:
        return _bound_ledger_path or default_ledger_path()


def _as_int(value: Any) -> Optional[int]:
    if type(value) is not int or value < 0:
        return None
    return value


def _row_hold(row: dict) -> Optional[int]:
    status = row.get("status")
    if status == "reconciled":
        return _as_int(row.get("actual_nano"))
    if status in ("reserved", "retained"):
        return _as_int(row.get("reserved_nano"))
    return None


def _scope_binding(data: dict) -> tuple[int, str]:
    """Return the authorized cap recorded in this ledger file.

    Only a scope marked ``explicit-2.00`` with no default or legacy reservations
    uses the $2 ceiling. Missing or default authorization stays at $0.05.
    This is not a seal against rewriting the same file's authorization field.
    """
    auth = data.get("authorization")
    if auth == TWO_DOLLAR_AUTHORIZATION:
        binding, sealed = TWO_DOLLAR_CEILING_NANO, TWO_DOLLAR_AUTHORIZATION
    else:
        binding, sealed = CEILING_NANO, DEFAULT_AUTHORIZATION
    rows = data.get("reservations")
    if isinstance(rows, dict):
        for row in rows.values():
            if not isinstance(row, dict):
                continue
            row_auth = row.get("authorization")
            row_ceil = _as_int(row.get("authorized_ceiling_nano"))
            if row_auth == TWO_DOLLAR_AUTHORIZATION and row_ceil == TWO_DOLLAR_CEILING_NANO:
                continue
            binding, sealed = CEILING_NANO, DEFAULT_AUTHORIZATION
            break
    return binding, sealed


def _normalize(data: Any) -> dict:
    if not isinstance(data, dict):
        raise LlmBudgetBlocked("ledger_unreadable", "shape")
    scope = data.get("scope_id")
    if not isinstance(scope, str) or not scope:
        raise LlmBudgetBlocked("ledger_unreadable", "scope")
    ceiling = _as_int(data.get("ceiling_nano"))
    accounted = _as_int(data.get("accounted_nano"))
    rows = data.get("reservations")
    if ceiling is None or accounted is None or not isinstance(rows, dict):
        raise LlmBudgetBlocked("ledger_unreadable", "totals")
    # Clamp ceiling_nano to the file's authorization binding and do not erase
    # spend. A default or legacy reservation still forces $0.05. Authorization
    # lives in this same file, so an empty or rewritten ledger can be recast.
    binding, authorization = _scope_binding(data)
    data["authorization"] = authorization
    data["authorized_ceiling_nano"] = binding
    data["ceiling_nano"] = min(ceiling, binding)
    held = 0
    for key, row in rows.items():
        if not isinstance(key, str) or not isinstance(row, dict):
            raise LlmBudgetBlocked("ledger_unreadable", "row")
        piece = _row_hold(row)
        if piece is None:
            raise LlmBudgetBlocked("ledger_unreadable", "row_nano")
        held += piece
    data["accounted_nano"] = max(accounted, held)
    return data


def _mutate(path: str, change: Callable[[dict], Any]) -> Any:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with _thread_lock:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            os.chmod(path, 0o600)
            with os.fdopen(fd, "r+", encoding="utf-8") as handle:
                fd = -1
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    raw = handle.read()
                    if not raw.strip():
                        data = _fresh()
                    else:
                        try:
                            parsed = json.loads(raw)
                        except ValueError as exc:
                            raise LlmBudgetBlocked("ledger_unreadable", "json") from exc
                        data = _normalize(parsed)
                    result = change(data)
                    handle.seek(0)
                    handle.truncate()
                    json.dump(data, handle, ensure_ascii=True, separators=(",", ":"))
                    handle.flush()
                    os.fsync(handle.fileno())
                    return result
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            if fd >= 0:
                os.close(fd)


def reserve_nano(path: str, *, nano: int, record: dict) -> dict:
    if type(nano) is not int or nano <= 0:
        raise LlmBudgetBlocked("over_budget", "reservation must be a positive integer nano-USD")
    if not isinstance(record, dict) or not isinstance(record.get("id"), str):
        raise LlmBudgetBlocked("ledger_unreadable", "record")

    def change(data: dict) -> dict:
        ceiling = data["ceiling_nano"]
        accounted = data["accounted_nano"]
        scope_id = data["scope_id"]
        if accounted + nano > ceiling:
            return {
                "ok": False, "code": "over_budget", "scope_id": scope_id,
                "accounted_nano": accounted, "ceiling_nano": ceiling, "need_nano": nano,
            }
        rid = record["id"]
        if rid in data["reservations"]:
            raise LlmBudgetBlocked("ledger_unreadable", "duplicate")
        row = dict(record)
        row["authorization"] = data["authorization"]
        row["authorized_ceiling_nano"] = data["authorized_ceiling_nano"]
        data["reservations"][rid] = row
        data["accounted_nano"] = accounted + nano
        return {
            "ok": True, "code": "reserved", "id": rid, "scope_id": scope_id,
            "accounted_nano": data["accounted_nano"], "ceiling_nano": ceiling,
            "reserved_nano": nano,
        }

    return _mutate(path, change)


def ledger_state(path: str) -> dict:
    def change(data: dict) -> dict:
        return {
            "scope_id": data["scope_id"],
            "authorization": data.get("authorization"),
            "authorized_ceiling_nano": data.get("authorized_ceiling_nano"),
            "ceiling_nano": data["ceiling_nano"],
            "accounted_nano": data["accounted_nano"],
            "reservations": {
                key: {
                    "status": row.get("status"),
                    "reserved_nano": row.get("reserved_nano"),
                    "actual_nano": row.get("actual_nano"),
                    "retain_reason": row.get("retain_reason") or "",
                    "max_output_tokens": row.get("max_output_tokens"),
                    "input_bound": row.get("input_bound"),
                    "snapshot_id": (row.get("snapshot") or {}).get("snapshot_id"),
                }
                for key, row in data["reservations"].items()
            },
        }
    return _mutate(path, change)


def _usage_nano(usage: Any, snapshot: dict, input_bound: int, max_output: int) -> dict:
    if not isinstance(usage, dict) or set(usage) - _USAGE_KEYS:
        return {"ok": False, "code": "missing_or_malformed_usage"}
    for key in _USAGE_REQUIRED:
        if key not in usage:
            return {"ok": False, "code": "missing_or_malformed_usage"}
    prompt = _as_int(usage.get("prompt_tokens"))
    completion = _as_int(usage.get("completion_tokens"))
    total = _as_int(usage.get("total_tokens"))
    hit = _as_int(usage.get("prompt_cache_hit_tokens"))
    miss = _as_int(usage.get("prompt_cache_miss_tokens"))
    details = usage.get("prompt_tokens_details")
    if None in (prompt, completion, total, hit, miss) or not isinstance(details, dict):
        return {"ok": False, "code": "missing_or_malformed_usage"}
    if set(details) - {"cached_tokens"}:
        return {"ok": False, "code": "missing_or_malformed_usage"}
    if "cached_tokens" in details and _as_int(details.get("cached_tokens")) != hit:
        return {"ok": False, "code": "missing_or_malformed_usage"}
    if hit + miss != prompt or prompt + completion != total:
        return {"ok": False, "code": "missing_or_malformed_usage"}
    if prompt > input_bound or completion > max_output:
        return {"ok": False, "code": "usage_exceeds_bound"}
    comp_details = usage.get("completion_tokens_details", None)
    if comp_details is not None:
        if not isinstance(comp_details, dict) or set(comp_details) - {"reasoning_tokens", "safety_tokens"}:
            return {"ok": False, "code": "missing_or_malformed_usage"}
        for key in ("reasoning_tokens", "safety_tokens"):
            if key in comp_details:
                n = _as_int(comp_details.get(key))
                if n is None or n > completion:
                    return {"ok": False, "code": "missing_or_malformed_usage"}
    server = usage.get("server_tool_use", None)
    if server is not None:
        if not isinstance(server, dict) or set(server) - {"tool_search", "tool_fetch", "tool_image_search"}:
            return {"ok": False, "code": "unpriced_tool_fee"}
        for key in ("tool_search", "tool_fetch", "tool_image_search"):
            if key in server:
                n = _as_int(server.get(key))
                if n is None or n > 0:
                    return {"ok": False, "code": "unpriced_tool_fee"}
    nano = (hit * snapshot["input_hit_peak_nano"]
            + miss * snapshot["input_miss_peak_nano"]
            + completion * snapshot["output_peak_nano"])
    return {"ok": True, "nano": nano}


def settle(path: str, reservation_id: str, usage: Any) -> dict:
    def change(data: dict) -> dict:
        row = data["reservations"].get(reservation_id)
        if not isinstance(row, dict) or row.get("status") != "reserved":
            return {"ok": False, "code": "missing_reservation", "accounted_nano": data.get("accounted_nano")}
        reserved = _as_int(row.get("reserved_nano"))
        snapshot = row.get("snapshot")
        input_bound = _as_int(row.get("input_bound"))
        max_output = _as_int(row.get("max_output_tokens"))
        if reserved is None or input_bound is None or max_output is None or not isinstance(snapshot, dict):
            row["status"] = "retained"
            row["retain_reason"] = "ledger_row"
            return {"ok": True, "code": "retained", "accounted_nano": data["accounted_nano"], "reason": "ledger_row"}
        decision = _usage_nano(usage, snapshot, input_bound, max_output)
        if not decision.get("ok"):
            row["status"] = "retained"
            row["retain_reason"] = decision.get("code") or "missing_or_malformed_usage"
            return {"ok": True, "code": "retained", "accounted_nano": data["accounted_nano"], "reason": row["retain_reason"]}
        actual = decision["nano"]
        if type(actual) is not int or actual > reserved:
            row["status"] = "retained"
            row["retain_reason"] = "usage_exceeds_reservation"
            return {"ok": True, "code": "retained", "accounted_nano": data["accounted_nano"], "reason": row["retain_reason"]}
        row["status"] = "reconciled"
        row["actual_nano"] = actual
        data["accounted_nano"] = data["accounted_nano"] - (reserved - actual)
        return {"ok": True, "code": "reconciled", "actual_nano": actual, "accounted_nano": data["accounted_nano"]}

    return _mutate(path, change)


def retain(path: str, reservation_id: str, reason: str) -> dict:
    def change(data: dict) -> dict:
        row = data["reservations"].get(reservation_id)
        if not isinstance(row, dict) or row.get("status") != "reserved":
            return {"ok": False, "code": "missing_reservation", "accounted_nano": data.get("accounted_nano")}
        row["status"] = "retained"
        row["retain_reason"] = reason or "unknown"
        return {"ok": True, "code": "retained", "accounted_nano": data["accounted_nano"], "reason": row["retain_reason"]}

    return _mutate(path, change)


async def dispatch(body: dict, *, route: dict, url: str, send: Callable[[], Awaitable[Any]],
                   ledger_path: Optional[str] = None,
                   bound_fn: Optional[Callable[[dict, dict], Bound]] = None) -> Any:
    """Reserve the worst case, then call ``send``. Unknown outcomes keep the reservation."""
    pre = prepare(body, route, url, bound_fn)
    if not pre["ok"]:
        raise LlmBudgetBlocked(pre["code"], pre["detail"])
    path = resolved_ledger_path(ledger_path)
    rid = uuid.uuid4().hex
    record = {
        "id": rid,
        "status": "reserved",
        "reserved_nano": pre["reserved_nano"],
        "actual_nano": None,
        "retain_reason": "",
        "input_bound": pre["input_tokens"],
        "max_output_tokens": pre["max_output_tokens"],
        "model": pre["route"]["model"],
        "route": pre["route"],
        "snapshot": pre["snapshot"],
        "created_at": int(time.time()),
    }
    reserved = reserve_nano(path, nano=pre["reserved_nano"], record=record)
    if not reserved["ok"]:
        raise LlmBudgetBlocked(
            "over_budget",
            f"scope={reserved.get('scope_id', '')} accounted={reserved.get('accounted_nano')} need={pre['reserved_nano']}",
            scope_id=str(reserved.get("scope_id") or ""),
        )
    try:
        result = await send()
    except BaseException as exc:
        try:
            retain(path, rid, "transport:" + type(exc).__name__)
        except Exception:
            _log.exception("llm usd gate could not mark a failed send; reservation stays")
        raise
    try:
        usage = result.get("usage") if isinstance(result, dict) else None
        settle(path, rid, usage)
    except Exception:
        _log.exception("llm usd gate could not reconcile; reservation stays")
    return result
