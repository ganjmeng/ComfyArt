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

Ledger updates use a stable sibling ``.lock`` (not the replaced ledger inode),
a same-directory temporary file, ``fsync`` of that file, ``os.replace``, and
``fsync`` of the parent directory. Persist order is ledger first, then the
``.activated`` marker. A crash after a successful ledger replace and before the
marker is recovered by treating a valid ledger as already activated and
completing the marker on the next update or bind, not on a read. A later
missing or empty activated ledger fails closed and is never rebuilt with
``_fresh()``. A valid ledger without a marker (legacy or crashed mid-activation)
must not be reset. This does not claim recovery when both the marker and the
ledger have been maliciously deleted or rewritten, and it does not prove
power-loss durability on every filesystem. ``ledger_state`` is a read under the
stable lock and must not write the ledger or the marker. ``settle`` and
``retain`` never initialize a scope. First use of a missing unactivated path
through ``reserve_nano`` or ``dispatch`` may still ``_fresh()`` a default
scope; ``open_authorized_scope`` is the explicit trusted initializer for a
chosen cap. If parent-directory ``fsync`` fails after ``replace``, the new
reservation is already visible on this filesystem and the error is propagated
so ``dispatch`` does not call transport (conservative hold). Process-level
``os._exit`` at a persist stage skips Python ``finally`` cleanup; the kernel
releases the lock fd.

An explicit, unactivated ``context_contract=True`` profile validates supported
images/full function tools and reserves documented C=1048576 as input PLUS the
actual output cap, with images already included in C. It sends frozen validated
bytes without redirects and requires an existing controlled $2 scope in the same
reservation transaction. Strict default behavior and install remain unchanged;
this engineering context interpretation is not charged-error proof or activation.

Optional controlled scopes require an explicit ``max_posts`` (1..6, or 1..12
only after ``extend_post_limit`` writes a matching ``limit_extension`` record),
retain the existing amount authority, and allow one outstanding POST at a time.
``open_authorized_scope(...,
max_posts=N)`` creates this profile; ``constrain_authorized_scope`` explicitly
migrates existing history without resetting it. Omitting the parameter keeps the
legacy amount-only API; it is NOT a controlled profile or a live activation.
Limits are immutable through these APIs and copied into the durable marker.
There is no circuit-reset API. Unknown legacy results migrate to a stopped scope.
A reservation durably consumes an attempt before transport, including an attempt
whose process dies before the socket opens; preflight/budget/inflight rejections
do not consume attempts. Every physical official POST is one attempt regardless
of main/summary/retry/overflow/boost call site. MCP calls consume no model attempt.
First uncertain/failed controlled outcome latches a persistent breaker and keeps
its full reservation. Only trusted normal success releases inflight and excess
money, never an attempt. If storage persistently fails, no software can guarantee
a new breaker record reaches disk. A durable pre-outcome journal retains the
last outstanding hold if outcome persistence fails, even after a visible replace;
a leftover journal blocks all later mutation and needs manual review. These
local controls do not bound an undocumented supplier bill.

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

import errno
import fcntl
import json
import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
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
# Test-only crash hook: called with a persist stage name. Production leaves this None.
_write_fault = None

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
_TEXT_MSG_KEYS = frozenset({"role", "content", "name", "reasoning_content"})
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


class LlmScopeStopped(LlmBudgetBlocked):
    """A controlled POST outcome stopped the scope; never a retryable HTTP error.

    The original transport exception is retained as __cause__. Cancellation and
    other BaseException subclasses retain their original type instead.
    """


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
        "context_length": 1_048_576 if model == "deepseek-flash" else 1_000_000,
        "peak_policy": "always_peak",
        "cache_policy": "reserve_cache_miss",
        "currency": "USD",
        "unit": "nano_usd_per_token",
    }


def worst_case_nano(snapshot: dict, input_tokens: int, max_output_tokens: int) -> int:
    """Peak cache-miss input plus peak output. Both factors are non-negative ints."""
    return (input_tokens * snapshot["input_miss_peak_nano"]
            + max_output_tokens * snapshot["output_peak_nano"])


class BoundEvidence(Bound):
    """Explicit, non-strict context-contract interpretation; never live activation."""
    __slots__ = ("envelope",)

    def __init__(self, envelope) -> None:
        from .llm_input_envelope import CONTEXT_TOKENS
        super().__init__(True, CONTEXT_TOKENS, "", "documented context contract; charged-error coverage not proven")
        self.envelope = envelope


def official_input_bound(body: dict, snapshot: dict, *, context_contract: bool = False,
                         frozen_images=None) -> Bound:
    """Strict default denies unproven input; explicit context mode is non-strict.

    Context mode validates full images/tools and reserves the documented whole
    window, not a tokenizer/character estimate or an absolute supplier bill cap.
    It is unactivated by default and cannot upgrade or open scope authority.
    """
    if context_contract:
        from .llm_input_envelope import EnvelopeInvalid, validate_envelope
        if snapshot.get("model") != "deepseek-flash" or snapshot.get("version") != "DeepSeek-V4.1-Flash-1017":
            return Bound(False, 0, "route_mismatch", "context-contract model pin")
        try:
            return BoundEvidence(validate_envelope(body, frozen_images=frozen_images))
        except EnvelopeInvalid as exc:
            return Bound(False, 0, exc.code, exc.field)
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
        if "reasoning_content" in msg and type(msg.get("reasoning_content")) is not str:
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
_ORDINARY_ASSISTANT_TOOL_KEYS = frozenset({"role", "content", "name", "tool_calls", "reasoning_content"})


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
    if "reasoning_content" in msg and type(msg.get("reasoning_content")) is not str:
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


def prepare(body: dict, route: dict, url: str, bound_fn: Optional[Callable[[dict, dict], Bound]] = None,
            *, context_contract: bool = False, frozen_images=None) -> dict:
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
    if type(context_contract) is not bool:
        return _fail("invalid_input_profile")
    if context_contract:
        if bound_fn is not None:
            return _fail("conflicting_input_bound")
        if (url not in ("https://api.deepseek.com/chat/completions", "https://api.deepseek.com/v1/chat/completions")
                or route.get("adapter") != "deepseek_official" or route.get("passthrough")
                or route.get("base_url") not in ("https://api.deepseek.com", "https://api.deepseek.com/v1")):
            return _fail("route_mismatch", "context-contract official route")
    else:
        structural = structural_block(body)
        if structural:
            return _fail(structural, _structural_detail(structural))
    cap, cap_code = apply_output_cap(body)
    if cap is None:
        return _fail(cap_code or "unsupported_output_cap")
    bound = (official_input_bound(body, snapshot, context_contract=True, frozen_images=frozen_images)
             if context_contract else (bound_fn or official_input_bound)(body, snapshot))
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
        **({"input_evidence": bound.envelope.evidence(), "body_bytes": bound.envelope.frozen.encoded}
           if isinstance(bound, BoundEvidence) else {}),
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


# Versioned local validation profile from billing-bound-evidence-plan.md §5.
# The caller MUST specify max_posts. Six is the limit a scope can be opened
# with. Twelve is the hard cap, and only extend_post_limit may cross six, by
# writing a matching limit_extension record in the same ledger update.
CONTROLLED_POSTS_LIMIT = 6
CONTROLLED_POSTS_HARD_CAP = 12


def _validate_max_posts(max_posts: int) -> None:
    if type(max_posts) is not int or not 1 <= max_posts <= CONTROLLED_POSTS_HARD_CAP:
        raise LlmScopeConflict("max_posts must be an explicit integer between 1 and 12")


def _extension_matches(data: dict, posts: int) -> bool:
    """True when limit_extension is a contiguous chain that ends at *posts*."""
    rows = data.get("limit_extension")
    if type(rows) is not list or not rows or type(posts) is not int:
        return False
    previous = None
    for row in rows:
        if type(row) is not dict:
            return False
        old, new = row.get("old"), row.get("new")
        if (type(old) is not int or type(new) is not int or not 1 <= old < new <= CONTROLLED_POSTS_HARD_CAP
                or type(row.get("operator")) is not str or not row["operator"].strip()
                or type(row.get("reason")) is not str or not row["reason"].strip()
                or type(row.get("at")) is not int or row["at"] <= 0):
            return False
        if previous is None:
            if old > CONTROLLED_POSTS_LIMIT:
                return False
        elif old != previous:
            return False
        previous = new
    return previous == posts


def _controlled(data: dict) -> bool:
    return "control_limits" in data


def _trip(data: dict, reason: str, reservation_id: str = "") -> None:
    if _controlled(data):
        state = data["control_state"]
        if not state["circuit_open"]:
            state.update(circuit_open=True, circuit_reason=reason, first_anomaly_id=reservation_id)


def _install_controls(data: dict, max_posts: int) -> None:
    _validate_max_posts(max_posts)
    if max_posts > CONTROLLED_POSTS_LIMIT:
        raise LlmScopeConflict("posts above 6 require limit_extension")
    limits = {"version": 1, "amount_nano": data["ceiling_nano"],
              "max_posts": max_posts, "max_inflight": 1}
    if _controlled(data):
        if data["control_limits"] != limits:
            raise LlmScopeConflict("controlled scope limits are immutable")
        return
    data["control_limits"] = limits
    data["control_state"] = {"attempts_total": len(data["reservations"]),
                             "circuit_open": False, "circuit_reason": "", "first_anomaly_id": ""}
    # Migration never discards spend, attempts, or an ambiguous legacy outcome.
    if any(row["status"] != "reconciled" for row in data["reservations"].values()):
        _trip(data, "legacy_unknown_outcome")
    elif len(data["reservations"]) > max_posts:
        _trip(data, "legacy_attempts_exceed_limit")


def _control_view(data: dict) -> dict:
    if not _controlled(data):
        return {}
    external = data.get("external_spend") if type(data.get("external_spend")) is dict else {}
    return {"control_limits": dict(data["control_limits"]),
            "control_state": dict(data["control_state"]),
            "inflight": sum(row["status"] == "reserved" for row in data["reservations"].values()),
            "external_inflight": sum(type(row) is dict and row.get("status") == "reserved" for row in external.values())}


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


def _ledger_lock_path(path: str) -> str:
    return path + ".lock"


def _ledger_marker_path(path: str) -> str:
    return path + ".activated"


def _fault(stage: str) -> None:
    hook = _write_fault
    if hook is not None:
        hook(stage)


def _fsync_dir(directory: str, *, stage: str = "dir_fsync") -> None:
    _fault(stage)
    fd = os.open(directory or ".", os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _marker_present(path: str) -> bool:
    return os.path.lexists(_ledger_marker_path(path))


def _read_raw(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=True, separators=(",", ":"))


def _write_all(fd: int, payload: bytes) -> None:
    """Finish every byte before a temporary ledger or marker can be published.

    A successful os.write may still be short. A zero (or invalid negative)
    result cannot make progress and is a hard persistence failure, not success.
    Other write errors propagate without reaching fsync/replace/transport.
    """
    remaining = memoryview(payload)
    while remaining:
        written = os.write(fd, remaining)
        if written <= 0:
            raise OSError(errno.EIO, "atomic write made no progress")
        remaining = remaining[written:]


def _atomic_write(path: str, payload: str, *, stage_prefix: str = "") -> None:
    """Write *payload* to *path* via a same-directory temp file, fsync, and replace.

    A crash before ``os.replace`` leaves the previous file (if any) in place. A
    crash after replace but before the parent-directory fsync may still lose the
    directory entry on some mounts after power loss; that case is not claimed as
    proven here. Marker writes use stage names prefixed with ``marker_``.
    """
    parent = os.path.dirname(path) or "."
    tmp = path + ".tmp"
    encoded = payload.encode("utf-8")
    _fault(stage_prefix + "before_temp")
    if os.path.lexists(tmp):
        os.unlink(tmp)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _write_all(fd, encoded)
        _fault(stage_prefix + "after_temp_write")
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(tmp, 0o600)
    _fault(stage_prefix + "after_temp_fsync")
    _fault(stage_prefix + "before_replace")
    os.replace(tmp, path)
    _fault(stage_prefix + "after_replace")
    _fsync_dir(parent, stage=stage_prefix + "dir_fsync")
    _fault(stage_prefix + "after_dir_fsync")


def _write_activation_marker(path: str, data: dict) -> None:
    marker = {
        "scope_id": data["scope_id"],
        "authorization": data["authorization"],
        "authorized_ceiling_nano": data["authorized_ceiling_nano"],
    }
    if _controlled(data):
        marker["control_limits"] = dict(data["control_limits"])
    if "runtime_activation" in data:
        marker["runtime_activation"] = data["runtime_activation"]
    _atomic_write(_ledger_marker_path(path), _dump(marker), stage_prefix="marker_")


def _read_marker(path: str) -> dict:
    try:
        marker = json.loads(_read_raw(_ledger_marker_path(path)))
    except ValueError as exc:
        raise LlmBudgetBlocked("ledger_unreadable", "activation_marker") from exc
    if not isinstance(marker, dict):
        raise LlmBudgetBlocked("ledger_unreadable", "activation_marker")
    return marker


def _check_control_marker(path: str, data: dict) -> None:
    if _marker_present(path):
        marker = _read_marker(path)
        if "control_limits" in marker and (
                marker["control_limits"] != data.get("control_limits") or
                marker.get("scope_id") != data["scope_id"]):
            raise LlmBudgetBlocked("ledger_unreadable", "controlled_limits_changed")
        if "runtime_activation" in marker and marker["runtime_activation"] != data.get("runtime_activation"):
            raise LlmBudgetBlocked("ledger_unreadable", "runtime_activation_changed")


def _persist_ledger(path: str, data: dict, *, write_marker: bool) -> None:
    # Persist the ledger first, then the activation marker. A crash after the
    # ledger write but before the marker is recovered by treating a valid
    # ledger as already activated and completing the marker on the next
    # update or bind. ledger_state must not perform that write.
    _atomic_write(path, _dump(data))
    if write_marker and (not _marker_present(path) or (
            _controlled(data) and "control_limits" not in _read_marker(path)) or (
            "runtime_activation" in data and "runtime_activation" not in _read_marker(path))):
        _write_activation_marker(path, data)


@contextmanager
def _with_ledger_lock(path: str):
    """Hold a process-shared exclusive lock on a sibling file that is never replaced."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    lock_path = _ledger_lock_path(path)
    with _thread_lock:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            os.chmod(lock_path, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def open_authorized_scope(path: str, ceiling_nano: int, *, max_posts: Optional[int] = None) -> dict:
    """Create a new independent validation scope with a durable authorized cap.

    An existing ledger is left unchanged: this will not upgrade, reset, merge a
    prior balance, or replace the default $0.05 path. It does not reserve or spend.
    Explicit max_posts opts into immutable amount/count/one-inflight controls and
    first-anomaly stop. Omission preserves the legacy amount-only API, NOT an
    authorization to use a controlled profile. Production input proof is unchanged.
    """
    if type(ceiling_nano) is not int or ceiling_nano not in AUTHORIZED_CEILINGS_NANO:
        raise LlmScopeConflict("ceiling is not an authorized validation cap")
    if max_posts is not None:
        _validate_max_posts(max_posts)
    authorization = (
        TWO_DOLLAR_AUTHORIZATION if ceiling_nano == TWO_DOLLAR_CEILING_NANO
        else DEFAULT_AUTHORIZATION
    )
    with _with_ledger_lock(path):
        if _marker_present(path) or os.path.lexists(_outcome_pending_path(path)) or _read_raw(path).strip():
            raise LlmScopeConflict("a validation scope already exists at this path")
        data = _fresh(ceiling_nano=ceiling_nano, authorization=authorization)
        if max_posts is not None:
            _install_controls(data, max_posts)
        _persist_ledger(path, data, write_marker=True)
        return {
            "ok": True,
            "scope_id": data["scope_id"],
            "authorization": authorization,
            "authorized_ceiling_nano": ceiling_nano,
            "ceiling_nano": ceiling_nano,
            "accounted_nano": 0,
            **_control_view(data),
        }


def constrain_authorized_scope(path: str, *, max_posts: int) -> dict:
    """Explicit conservative migration; cannot raise amount or reset history.

    Unknown legacy outcomes open the circuit permanently. There is no automatic
    migration at send/bind/read time and no circuit-reset API. All legacy rows
    conservatively count as POST attempts, even if a socket was never opened.
    """
    _validate_max_posts(max_posts)

    def change(data: dict) -> dict:
        _install_controls(data, max_posts)
        return {"ok": True, "scope_id": data["scope_id"], **_control_view(data)}

    return _mutate(path, change, create=False)


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
    if type(path) is not str or not path:
        raise LlmScopeConflict("no authorized scope exists at this path")
    try:
        with _with_ledger_lock(path):
            raw = _read_raw(path)
            if not raw.strip():
                if _marker_present(path):
                    raise LlmBudgetBlocked("ledger_unreadable", "activated_missing_or_empty")
                raise LlmScopeConflict("no authorized scope exists at this path")
            try:
                parsed = json.loads(raw)
            except ValueError as exc:
                raise LlmScopeConflict("authorized scope is unreadable") from exc
            data = _normalize(parsed)
            _check_control_marker(path, data)
            data = _apply_pending_outcome(path, data)
            if not _marker_present(path) or (_controlled(data) and "control_limits" not in _read_marker(path)):
                _write_activation_marker(path, data)
    except LlmBudgetBlocked:
        raise
    except OSError as exc:
        raise LlmScopeConflict("authorized scope is unreadable") from exc
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
        **_control_view(data),
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
    if status == "resolved_as_spent":
        # Booked at the full reserve. A different actual is unreadable, not a release.
        actual = _as_int(row.get("actual_nano"))
        reserved = _as_int(row.get("reserved_nano"))
        return actual if actual is not None and actual == reserved else None
    if status in ("reserved", "retained"):
        reserved = _as_int(row.get("reserved_nano"))
        if "observed_nano" in row:
            observed = _as_int(row["observed_nano"])
            return max(reserved, observed) if reserved is not None and observed is not None else None
        return reserved
    return None


def _external_rows(data: dict) -> dict:
    """External rows are optional. A ledger written before them has no key."""
    if "external_spend" not in data:
        return {}
    rows = data.get("external_spend")
    if type(rows) is not dict:
        raise LlmBudgetBlocked("ledger_unreadable", "external_spend")
    return rows


def _external_hold(row: dict) -> Optional[int]:
    if type(row) is not dict:
        return None
    quote = _as_int(row.get("quote_nano"))
    status = row.get("status")
    if quote is None:
        return None
    if status in ("reserved", "retained"):
        return quote if row.get("actual_nano") is None else None
    if status == "resolved_as_spent":
        actual = _as_int(row.get("actual_nano"))
        return actual if actual is not None and actual == quote else None
    if status == "reconciled":
        return _as_int(row.get("actual_nano"))
    return None


def _external_row_readable(row: dict) -> bool:
    if _external_hold(row) is None:
        return False
    return all(type(row.get(key)) is str for key in ("provider", "task_ref", "task_id", "operator", "retain_reason"))


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
    # Absent on every ledger that predates external spend. Do not insert the key.
    for key, row in _external_rows(data).items():
        if not isinstance(key, str) or not _external_row_readable(row):
            raise LlmBudgetBlocked("ledger_unreadable", "external_row")
        held += _external_hold(row)
    data["accounted_nano"] = max(accounted, held)
    if _controlled(data) or "control_state" in data:
        limits, state = data.get("control_limits"), data.get("control_state")
        if not isinstance(limits, dict) or not isinstance(state, dict):
            raise LlmBudgetBlocked("ledger_unreadable", "controlled_shape")
        if (set(limits) != {"version", "amount_nano", "max_posts", "max_inflight"}
                or type(limits.get("version")) is not int or limits["version"] != 1
                or type(limits.get("max_inflight")) is not int or limits["max_inflight"] != 1
                or type(limits.get("amount_nano")) is not int or limits["amount_nano"] != data["ceiling_nano"]
                or type(limits.get("max_posts")) is not int or not 1 <= limits["max_posts"] <= CONTROLLED_POSTS_HARD_CAP
                or (limits["max_posts"] > CONTROLLED_POSTS_LIMIT and not _extension_matches(data, limits["max_posts"]))):
            raise LlmBudgetBlocked("ledger_unreadable", "controlled_limits")
        if (set(state) != {"attempts_total", "circuit_open", "circuit_reason", "first_anomaly_id"}
                or _as_int(state.get("attempts_total")) is None
                or type(state.get("circuit_open")) is not bool
                or type(state.get("circuit_reason")) is not str
                or type(state.get("first_anomaly_id")) is not str
                or state["circuit_open"] != bool(state["circuit_reason"])):
            raise LlmBudgetBlocked("ledger_unreadable", "controlled_state")
        state["attempts_total"] = max(state["attempts_total"], len(rows))
        # A legacy retained result or partial historical migration cannot turn
        # an uncertainty into permission for another POST.
        if any(row["status"] == "retained" for row in rows.values()):
            _trip(data, "historical_unknown_outcome")
        if any(row.get("status") == "retained" for row in _external_rows(data).values()):
            _trip(data, "historical_unknown_outcome")
    return data


def _load_ledger(path: str, *, create: bool) -> tuple[dict, bool, bool]:
    """Read and normalize a ledger under an already-held lock. Never writes.

    Returns ``(data, initializing, activated)``. First initialization happens
    only when *create* is true and the path has no activation marker and no
    ledger content. An activated missing or empty ledger never calls
    ``_fresh()``. A valid ledger is not reset, with or without a marker.
    """
    raw = _read_raw(path)
    activated = _marker_present(path)
    if not raw.strip():
        if activated or os.path.lexists(_outcome_pending_path(path)) or not create:
            raise LlmBudgetBlocked(
                "ledger_unreadable",
                "activated_missing_or_empty" if activated else "missing",
            )
        return _fresh(), True, False
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise LlmBudgetBlocked("ledger_unreadable", "json") from exc
    data = _normalize(parsed)
    _check_control_marker(path, data)
    return _apply_pending_outcome(path, data), False, activated


def _outcome_pending_path(path: str) -> str:
    return path + ".outcome_pending"


def _apply_pending_outcome(path: str, data: dict) -> dict:
    if not os.path.lexists(_outcome_pending_path(path)):
        return data
    try:
        pending = _normalize(json.loads(_read_raw(_outcome_pending_path(path))))
    except (ValueError, LlmBudgetBlocked) as exc:
        raise LlmBudgetBlocked("ledger_unreadable", "pending_outcome") from exc
    if (not _controlled(pending) or pending["scope_id"] != data["scope_id"]
            or pending["control_limits"] != data.get("control_limits")):
        raise LlmBudgetBlocked("ledger_unreadable", "pending_scope_mismatch")
    # The journal is the last confirmed outstanding hold. A possibly visible
    # success replace whose fsync failed cannot free that hold after restart.
    for rid, row in data["reservations"].items():
        if "observed_nano" in row and rid in pending["reservations"]:
            for key in ("observed_nano", "reservation_violation", "budget_violation"):
                pending["reservations"][rid][key] = row[key]
    pending["accounted_nano"] = max(pending["accounted_nano"], data["accounted_nano"])
    pending["control_state"]["attempts_total"] = max(
        pending["control_state"]["attempts_total"], data["control_state"]["attempts_total"])
    current = data["control_state"]
    _trip(pending, current["circuit_reason"] or "outcome_persistence_failed", current["first_anomaly_id"])
    return _normalize(pending)


def _mutate(path: str, change: Callable[[dict], Any], *, create: bool = True,
            preserve_on_failure: bool = False) -> Any:
    """Apply *change* under the stable ledger lock and persist atomically if needed.

    First initialization happens only when *create* is true and the path has no
    activation marker and no ledger content. An activated missing or empty
    ledger never calls ``_fresh()``.
    """
    with _with_ledger_lock(path):
        data, initializing, activated = _load_ledger(path, create=create)
        if os.path.lexists(_outcome_pending_path(path)):
            raise LlmScopeStopped("scope_circuit_open", "outcome persistence needs manual review", scope_id=data["scope_id"])
        before = _dump(data)
        result = change(data)
        after = _dump(data)
        if initializing or after != before:
            journaled = preserve_on_failure and _controlled(data)
            if journaled:
                # Persist the old outstanding reservation BEFORE any outcome
                # replace. A leftover journal is a persistent stop, never auto-
                # cleared or replayed on restart. Uses the same write-all path.
                _atomic_write(_outcome_pending_path(path), before, stage_prefix="outcome_")
            try:
                _persist_ledger(path, data, write_marker=initializing or not activated or _controlled(data))
            except Exception:
                if preserve_on_failure and _controlled(data):
                    # Keep the stable lock while latching a persistence failure.
                    # Restore the pre-settlement holds, not a possibly visible
                    # reconciled state. If storage cannot persist anything, the
                    # preceding reserved ledger is the conservative fallback.
                    fallback = json.loads(before)
                    for rid, row in data["reservations"].items():
                        if "observed_nano" in row and rid in fallback["reservations"]:
                            for key in ("observed_nano", "reservation_violation", "budget_violation"):
                                fallback["reservations"][rid][key] = row[key]
                    fallback["accounted_nano"] = max(fallback["accounted_nano"], data["accounted_nano"])
                    current = data["control_state"]
                    _trip(fallback, current["circuit_reason"] or "outcome_persistence_failed", current["first_anomaly_id"])
                    try:
                        _persist_ledger(path, fallback, write_marker=True)
                    except Exception:
                        _log.exception("could not durably latch controlled outcome persistence failure")
                raise
            if journaled:
                # The ledger outcome is now durably committed. If cleanup fails
                # before unlink, the journal remains a conservative stop. A dir
                # fsync failure AFTER unlink can only resurrect a stop after a
                # power loss; it cannot lose the already-fsynced ledger hold.
                os.unlink(_outcome_pending_path(path))
                try:
                    _fsync_dir(os.path.dirname(path), stage="outcome_cleanup_dir_fsync")
                except OSError:
                    _log.warning("outcome journal cleanup was not directory-fsynced; durable ledger retained")
        elif not activated:
            _write_activation_marker(path, data)
        return result


def reserve_nano(path: str, *, nano: int, record: dict, runtime_binding=None) -> dict:
    if type(nano) is not int or nano <= 0:
        raise LlmBudgetBlocked("over_budget", "reservation must be a positive integer nano-USD")
    if (not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]
            or record.get("status") != "reserved" or _as_int(record.get("reserved_nano")) != nano
            or record.get("actual_nano") is not None):
        raise LlmBudgetBlocked("ledger_unreadable", "record")
    evidence = record.get("input_evidence")
    if evidence is not None and type(evidence) is not dict:
        raise LlmBudgetBlocked("ledger_unreadable", "input_evidence")
    needs_controlled_scope = (evidence or {}).get("mode") == "documented_context_contract"

    def change(data: dict) -> dict:
        if "runtime_activation" in data or runtime_binding is not None:
            if (runtime_binding is None or data.get("runtime_activation") != runtime_binding
                    or not _marker_present(path)
                    or _read_marker(path).get("runtime_activation") != runtime_binding):
                raise LlmBudgetBlocked("activation_binding_required", "ledger/runtime/marker")
        ceiling = data["ceiling_nano"]
        accounted = data["accounted_nano"]
        scope_id = data["scope_id"]
        if needs_controlled_scope:
            # Same atomic transaction as amount/count/inflight. An offline
            # policy parameter cannot create/upgrade authority or omit controls.
            if (not _controlled(data) or data["authorization"] != TWO_DOLLAR_AUTHORIZATION
                    or data["ceiling_nano"] != TWO_DOLLAR_CEILING_NANO):
                return {"ok": False, "code": "controlled_scope_required", "scope_id": scope_id,
                        "accounted_nano": accounted, "ceiling_nano": ceiling}
        if _controlled(data):
            limits, state = data["control_limits"], data["control_state"]
            code = ("scope_circuit_open" if state["circuit_open"] else
                    "scope_posts_exhausted" if state["attempts_total"] >= limits["max_posts"] else
                    "scope_inflight" if any(r["status"] == "reserved" for r in data["reservations"].values()) else "")
            if code:
                return {"ok": False, "code": code, "scope_id": scope_id,
                        "accounted_nano": accounted, "ceiling_nano": ceiling}
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
        if _controlled(data):
            data["control_state"]["attempts_total"] += 1
        return {
            "ok": True, "code": "reserved", "id": rid, "scope_id": scope_id,
            "accounted_nano": data["accounted_nano"], "ceiling_nano": ceiling,
            "reserved_nano": nano,
            "controlled": _controlled(data),
        }

    return _mutate(path, change, create=not needs_controlled_scope)


def ledger_state(path: str) -> dict:
    """Return a view of the ledger. Read-only: does not write the ledger or marker."""
    with _with_ledger_lock(path):
        data, _, _ = _load_ledger(path, create=False)
        return {
            "scope_id": data["scope_id"],
            "authorization": data.get("authorization"),
            "authorization": data["authorization"],
            "authorized_ceiling_nano": data.get("authorized_ceiling_nano"),
            "ceiling_nano": data["ceiling_nano"],
            "accounted_nano": data["accounted_nano"],
            **_control_view(data),
            "reservations": {
                key: {
                    "status": row.get("status"),
                    "reserved_nano": row.get("reserved_nano"),
                    "actual_nano": row.get("actual_nano"),
                    "retain_reason": row.get("retain_reason") or "",
                    "max_output_tokens": row.get("max_output_tokens"),
                    "input_bound": row.get("input_bound"),
                    "snapshot_id": (row.get("snapshot") or {}).get("snapshot_id"),
                    **({"observed_nano": row["observed_nano"],
                        "reservation_violation": row.get("reservation_violation", False),
                        "budget_violation": row.get("budget_violation", False)} if "observed_nano" in row else {}),
                }
                for key, row in data["reservations"].items()
            },
        }


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
    if prompt > input_bound or completion > max_output:
        return {"ok": False, "code": "usage_exceeds_bound", "observed_nano": nano}
    return {"ok": True, "nano": nano}


def _observe_violation(data: dict, row: dict, observed: int, reserved: int) -> None:
    if _controlled(data):
        row["observed_nano"] = observed
        row["reservation_violation"] = observed > reserved
        data["accounted_nano"] += max(0, observed - reserved)
        row["budget_violation"] = data["accounted_nano"] > data["ceiling_nano"]


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
            _trip(data, "ledger_row", reservation_id)
            return {"ok": True, "code": "retained", "accounted_nano": data["accounted_nano"], "reason": "ledger_row"}
        decision = _usage_nano(usage, snapshot, input_bound, max_output)
        if not decision.get("ok"):
            row["status"] = "retained"
            row["retain_reason"] = decision.get("code") or "missing_or_malformed_usage"
            _trip(data, row["retain_reason"], reservation_id)
            if "observed_nano" in decision:
                _observe_violation(data, row, decision["observed_nano"], reserved)
            return {"ok": True, "code": "retained", "accounted_nano": data["accounted_nano"], "reason": row["retain_reason"]}
        actual = decision["nano"]
        if type(actual) is not int or actual > reserved:
            row["status"] = "retained"
            row["retain_reason"] = "usage_exceeds_reservation"
            _trip(data, row["retain_reason"], reservation_id)
            if type(actual) is int and actual >= 0:
                _observe_violation(data, row, actual, reserved)
            return {"ok": True, "code": "retained", "accounted_nano": data["accounted_nano"], "reason": row["retain_reason"]}
        row["status"] = "reconciled"
        row["actual_nano"] = actual
        data["accounted_nano"] = data["accounted_nano"] - (reserved - actual)
        return {"ok": True, "code": "reconciled", "actual_nano": actual, "accounted_nano": data["accounted_nano"]}

    return _mutate(path, change, create=False, preserve_on_failure=True)


def reserve_external_spend(path: str, provider: str = "wavespeed", *, quote_nano: int, task_ref: str, operator: str) -> dict:
    """Hold one provider quote against this ledger's USD ceiling.

    The hold does not consume a DeepSeek POST and is not LLM inflight. A second
    external hold is refused until the first is settled or retained. Over the
    ceiling, an open breaker, or a pending outcome journal writes nothing.
    """
    if type(provider) is not str or not provider.strip():
        raise LlmBudgetBlocked("external_refused", "provider")
    if type(quote_nano) is not int or quote_nano <= 0:
        raise LlmBudgetBlocked("external_refused", "quote")
    if type(task_ref) is not str or not task_ref.strip() or type(operator) is not str or not operator.strip():
        raise LlmBudgetBlocked("external_refused", "audit")

    def change(data: dict) -> dict:
        if data.get("control_state", {}).get("circuit_open") is True:
            raise LlmBudgetBlocked("external_refused", "breaker")
        external = _external_rows(data)
        if any(type(row) is dict and row.get("status") == "reserved" for row in external.values()):
            raise LlmBudgetBlocked("external_refused", "inflight")
        accounted = data.get("accounted_nano")
        ceiling = data.get("ceiling_nano")
        if type(accounted) is not int or type(ceiling) is not int or accounted + quote_nano > ceiling:
            raise LlmBudgetBlocked("external_refused", "ceiling")
        attempts = data["control_state"]["attempts_total"] if _controlled(data) else None
        reservation_id = uuid.uuid4().hex
        data.setdefault("external_spend", {})[reservation_id] = {
            "provider": provider, "status": "reserved", "quote_nano": quote_nano, "actual_nano": None,
            "task_ref": task_ref, "task_id": "", "operator": operator, "retain_reason": "",
        }
        data["accounted_nano"] = accounted + quote_nano
        if _controlled(data) and data["control_state"]["attempts_total"] != attempts:
            raise LlmBudgetBlocked("external_refused", "post_count")
        return {"ok": True, "reservation_id": reservation_id, "quote_nano": quote_nano,
                "accounted_nano": data["accounted_nano"], "attempts_total": attempts}

    return _mutate(path, change, create=False)


def settle_external_spend(path: str, reservation_id: str, task_id: str, actual_nano: int | None, operator: str) -> dict:
    """Record a provider task id and actual amount, or retain an unknown at the quote.

    An actual above the quote is stored and opens the breaker. None keeps the
    row retained and counted at the full quote. The same outcome again does not write.
    """
    if type(reservation_id) is not str or not reservation_id:
        raise LlmBudgetBlocked("external_refused", "id")
    if type(task_id) is not str or type(operator) is not str or not operator.strip():
        raise LlmBudgetBlocked("external_refused", "audit")
    if actual_nano is not None and (type(actual_nano) is not int or actual_nano < 0):
        raise LlmBudgetBlocked("external_refused", "actual")
    if actual_nano is not None and not task_id.strip():
        raise LlmBudgetBlocked("external_refused", "task_id")

    def change(data: dict) -> dict:
        external = data.get("external_spend") if type(data.get("external_spend")) is dict else {}
        row = external.get(reservation_id)
        if type(row) is not dict:
            raise LlmBudgetBlocked("external_refused", "id")
        quote = row.get("quote_nano")
        if type(quote) is not int or quote < 0:
            raise LlmBudgetBlocked("external_refused", "quote")
        attempts = data["control_state"]["attempts_total"] if _controlled(data) else None
        accounted = data.get("accounted_nano")
        circuit = data.get("control_state", {}).get("circuit_open") is True
        if row.get("status") == "reconciled" and row.get("task_id") == task_id and row.get("actual_nano") == actual_nano:
            return {"ok": True, "idempotent": True, "reservation_id": reservation_id, "status": "reconciled",
                    "task_id": task_id, "actual_nano": actual_nano, "quote_nano": quote, "accounted_nano": accounted,
                    "attempts_total": attempts, "circuit_open": circuit}
        if row.get("status") == "retained" and actual_nano is None and row.get("task_id") == task_id:
            return {"ok": True, "idempotent": True, "reservation_id": reservation_id, "status": "retained",
                    "task_id": task_id, "actual_nano": None, "quote_nano": quote, "accounted_nano": accounted,
                    "attempts_total": attempts, "circuit_open": circuit}
        if row.get("status") != "reserved":
            raise LlmBudgetBlocked("external_refused", "id")
        row["task_id"] = task_id
        row["operator"] = operator
        if actual_nano is None:
            row["status"] = "retained"
            row["retain_reason"] = "external_unknown"
            _trip(data, "external_unknown", reservation_id)
            status = "retained"
        else:
            row["status"] = "reconciled"
            row["actual_nano"] = actual_nano
            row["retain_reason"] = ""
            data["accounted_nano"] = accounted + (actual_nano - quote)
            if actual_nano > quote:
                _trip(data, "external_over_quote", reservation_id)
            status = "reconciled"
        if _controlled(data) and data["control_state"]["attempts_total"] != attempts:
            raise LlmBudgetBlocked("external_refused", "post_count")
        return {"ok": True, "idempotent": False, "reservation_id": reservation_id, "status": status,
                "task_id": task_id, "actual_nano": actual_nano, "quote_nano": quote,
                "accounted_nano": data["accounted_nano"], "attempts_total": attempts,
                "circuit_open": data.get("control_state", {}).get("circuit_open") is True}

    return _mutate(path, change, create=False)


def retain(path: str, reservation_id: str, reason: str, *, usage: Any = None) -> dict:
    def change(data: dict) -> dict:
        row = data["reservations"].get(reservation_id)
        if not isinstance(row, dict) or row.get("status") != "reserved":
            return {"ok": False, "code": "missing_reservation", "accounted_nano": data.get("accounted_nano")}
        row["status"] = "retained"
        row["retain_reason"] = reason or "unknown"
        _trip(data, row["retain_reason"], reservation_id)
        # A failed/refused HTTP200 can still carry billed usage. Keep the full
        # hold, but never hide a trustworthy observed amount above it.
        if _controlled(data) and isinstance(row.get("snapshot"), dict):
            input_bound = _as_int(row.get("input_bound"))
            output_cap = _as_int(row.get("max_output_tokens"))
            reserved = _as_int(row.get("reserved_nano"))
            if input_bound is not None and output_cap is not None and reserved is not None:
                observation = _usage_nano(usage, row["snapshot"], input_bound, output_cap)
                observed = observation.get("nano") if observation.get("ok") else observation.get("observed_nano")
                if type(observed) is int and observed >= 0:
                    _observe_violation(data, row, observed, reserved)
        return {"ok": True, "code": "retained", "accounted_nano": data["accounted_nano"], "reason": row["retain_reason"]}

    return _mutate(path, change, create=False, preserve_on_failure=True)


def resolve_unknown_as_spent(path: str, reservation_id: str, operator: str, reason: str) -> dict:
    """Book one retained row as spent at its full reserve. Never releases.

    The hold is already inside accounted_nano, so accounted, the POST count,
    the ceiling, and the inflight limit stay unchanged. A retained row in
    ``reservations`` or ``external_spend`` becomes ``resolved_as_spent`` and
    its actual becomes the full reserve or quote. The breaker closes only when
    this row is first_anomaly_id, no other row is retained in either map, and
    nothing is reserved in either map. operator, reason, and time are appended
    to resolution_audit. A second call returns the same result and does not
    write. Any other state raises and writes nothing.
    """
    if type(reservation_id) is not str or not reservation_id:
        raise LlmBudgetBlocked("resolve_refused", "id")
    if type(operator) is not str or not operator.strip() or type(reason) is not str or not reason.strip():
        raise LlmBudgetBlocked("resolve_refused", "audit")

    def change(data: dict) -> dict:
        limits = data.get("control_limits")
        state = data.get("control_state")
        posts = limits.get("max_posts") if type(limits) is dict else None
        activation = data.get("runtime_activation")
        bound = None
        if type(activation) is dict and type(activation.get("manifest")) is dict:
            scope_limits = activation["manifest"].get("scope_limits")
            if type(scope_limits) is dict:
                bound = scope_limits.get("max_posts")
        if type(bound) is not int:
            bound = posts
        if (type(limits) is not dict or limits.get("amount_nano") != TWO_DOLLAR_CEILING_NANO
                or type(posts) is not int or type(bound) is not int
                or not 1 <= posts <= bound <= CONTROLLED_POSTS_HARD_CAP
                or limits.get("max_inflight") != 1
                or (posts > CONTROLLED_POSTS_LIMIT and not _extension_matches(data, posts))
                or type(state) is not dict):
            raise LlmBudgetBlocked("resolve_refused", "limits")
        rows = data.get("reservations") if type(data.get("reservations")) is dict else {}
        external = data.get("external_spend") if type(data.get("external_spend")) is dict else {}
        row = rows.get(reservation_id)
        ext = external.get(reservation_id)
        if type(row) is dict and type(ext) is dict:
            raise LlmBudgetBlocked("resolve_refused", "id")
        if type(ext) is dict:
            quote = ext.get("quote_nano")
            if type(quote) is not int or quote < 0:
                raise LlmBudgetBlocked("resolve_refused", "reserve")
            accounted = data.get("accounted_nano")
            attempts = state.get("attempts_total")
            if ext.get("status") == "resolved_as_spent" and ext.get("actual_nano") == quote:
                return {"ok": True, "idempotent": True, "reservation_id": reservation_id,
                        "status": "resolved_as_spent", "actual_nano": quote,
                        "accounted_nano": accounted, "attempts_total": attempts,
                        "circuit_open": state.get("circuit_open") is True}
            if ext.get("status") != "retained":
                raise LlmBudgetBlocked("resolve_refused", "id")
            if any(type(other) is dict and other.get("status") == "retained" for other in rows.values()):
                raise LlmBudgetBlocked("resolve_refused", "other_retained")
            if any(type(other) is dict and other.get("status") == "retained" for rid, other in external.items() if rid != reservation_id):
                raise LlmBudgetBlocked("resolve_refused", "other_retained")
            if any(type(other) is dict and other.get("status") == "reserved" for other in (*rows.values(), *external.values())):
                raise LlmBudgetBlocked("resolve_refused", "inflight")
            if state.get("circuit_open") is not True or state.get("first_anomaly_id") != reservation_id:
                raise LlmBudgetBlocked("resolve_refused", "breaker")
            ext["status"] = "resolved_as_spent"
            ext["actual_nano"] = quote
            data.setdefault("resolution_audit", []).append({
                "reservation_id": reservation_id, "operator": operator, "reason": reason, "at": int(time.time()),
            })
            state["circuit_open"] = False
            state["circuit_reason"] = ""
            state["first_anomaly_id"] = ""
            if (data.get("accounted_nano") != accounted or state.get("attempts_total") != attempts
                    or data.get("control_limits") != limits or data.get("ceiling_nano") != TWO_DOLLAR_CEILING_NANO):
                raise LlmBudgetBlocked("resolve_refused", "spend_changed")
            return {"ok": True, "idempotent": False, "reservation_id": reservation_id,
                    "status": "resolved_as_spent", "actual_nano": quote,
                    "accounted_nano": accounted, "attempts_total": attempts, "circuit_open": False}
        if type(row) is not dict:
            raise LlmBudgetBlocked("resolve_refused", "id")
        reserved = row.get("reserved_nano")
        if type(reserved) is not int or reserved < 0:
            raise LlmBudgetBlocked("resolve_refused", "reserve")
        accounted = data.get("accounted_nano")
        attempts = state.get("attempts_total")
        if row.get("status") == "resolved_as_spent" and row.get("actual_nano") == reserved:
            return {"ok": True, "idempotent": True, "reservation_id": reservation_id,
                    "status": "resolved_as_spent", "actual_nano": reserved,
                    "accounted_nano": accounted, "attempts_total": attempts,
                    "circuit_open": state.get("circuit_open") is True}
        if row.get("status") != "retained":
            raise LlmBudgetBlocked("resolve_refused", "id")
        if any(type(other) is dict and other.get("status") == "retained" for rid, other in rows.items() if rid != reservation_id):
            raise LlmBudgetBlocked("resolve_refused", "other_retained")
        if any(type(other) is dict and other.get("status") == "reserved" for other in rows.values()):
            raise LlmBudgetBlocked("resolve_refused", "inflight")
        external = data.get("external_spend")
        if type(external) is dict and any(type(other) is dict and other.get("status") == "retained" for other in external.values()):
            raise LlmBudgetBlocked("resolve_refused", "other_retained")
        if type(external) is dict and any(type(other) is dict and other.get("status") == "reserved" for other in external.values()):
            raise LlmBudgetBlocked("resolve_refused", "external_inflight")
        if state.get("circuit_open") is not True or state.get("first_anomaly_id") != reservation_id:
            raise LlmBudgetBlocked("resolve_refused", "breaker")
        row["status"] = "resolved_as_spent"
        row["actual_nano"] = reserved
        data.setdefault("resolution_audit", []).append({
            "reservation_id": reservation_id, "operator": operator, "reason": reason, "at": int(time.time()),
        })
        state["circuit_open"] = False
        state["circuit_reason"] = ""
        state["first_anomaly_id"] = ""
        if (data.get("accounted_nano") != accounted or state.get("attempts_total") != attempts
                or data.get("control_limits") != limits or data.get("ceiling_nano") != TWO_DOLLAR_CEILING_NANO):
            raise LlmBudgetBlocked("resolve_refused", "spend_changed")
        return {"ok": True, "idempotent": False, "reservation_id": reservation_id,
                "status": "resolved_as_spent", "actual_nano": reserved,
                "accounted_nano": accounted, "attempts_total": attempts, "circuit_open": False}

    return _mutate(path, change, create=False)


def _response_anomaly(result: Any) -> str:
    if not isinstance(result, dict):
        return "malformed_response"
    if result.get("error") is not None:
        return "response_error"
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices:
        return "malformed_response"
    for choice in choices:
        if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
            return "malformed_response"
        if choice.get("finish_reason") in ("error", "aborted", "insufficient_system_resource") or choice.get("error") is not None:
            return "response_error"
        if choice.get("finish_reason") == "content_filter" or choice["message"].get("refusal"):
            return "response_refusal"
    return ""


async def dispatch(body: dict, *, route: dict, url: str, send: Callable[[], Awaitable[Any]],
                   ledger_path: Optional[str] = None,
                   bound_fn: Optional[Callable[[dict, dict], Bound]] = None,
                   context_contract: bool = False, frozen_images=None, activation_runtime=None,
                   send_frozen: Optional[Callable[[bytes], Awaitable[Any]]] = None) -> Any:
    """Reserve then send. Explicit context profile is unactivated by default.

    No manifest receipt is a send permit; activation/worker binding is separate.
    Context mode uses the documented-window interpretation, NOT strict proof.
    """
    pre = prepare(body, route, url, bound_fn, context_contract=context_contract, frozen_images=frozen_images)
    if not pre["ok"]:
        raise LlmBudgetBlocked(pre["code"], pre["detail"])
    if context_contract and send_frozen is None:
        raise LlmBudgetBlocked("frozen_transport_required", "no immutable-byte transport")
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
        **({"input_evidence": pre["input_evidence"], "body_sha256": pre["input_evidence"]["body_sha256"]}
           if context_contract else {}),
    }
    if activation_runtime is not None:
        from .llm_scope_activation import reserve_for_runtime
        tools = [(t.get("function") or {}).get("name") for t in json.loads(pre["body_bytes"]).get("tools", [])]
        reserved = reserve_for_runtime(activation_runtime, path=path, nano=pre["reserved_nano"],
                                       record=record, url=url, tools=tools)
    else:
        reserved = reserve_nano(path, nano=pre["reserved_nano"], record=record)
    if not reserved["ok"]:
        raise LlmBudgetBlocked(
            reserved.get("code") or "over_budget",
            f"scope={reserved.get('scope_id', '')} accounted={reserved.get('accounted_nano')} need={pre['reserved_nano']}",
            scope_id=str(reserved.get("scope_id") or ""),
        )
    controlled = reserved.get("controlled", False)
    try:
        result = await send_frozen(pre["body_bytes"]) if context_contract else await send()
    except BaseException as exc:
        try:
            retain(path, rid, "transport:" + type(exc).__name__)
        except Exception:
            _log.exception("llm usd gate could not mark a failed send; reservation stays")
        if controlled and isinstance(exc, Exception):
            raise LlmScopeStopped("scope_circuit_open", "transport outcome uncertain", scope_id=reserved["scope_id"]) from exc
        raise
    if controlled:
        anomaly = _response_anomaly(result)
        if anomaly:
            try:
                retain(path, rid, anomaly, usage=result.get("usage") if isinstance(result, dict) else None)
            except Exception as exc:
                raise LlmScopeStopped("scope_persistence_failed", "response outcome not durably recorded",
                                      scope_id=reserved["scope_id"]) from exc
            raise LlmScopeStopped("scope_circuit_open", anomaly, scope_id=reserved["scope_id"])
    try:
        usage = result.get("usage") if isinstance(result, dict) else None
        decision = settle(path, rid, usage)
    except Exception as exc:
        if controlled:
            raise LlmScopeStopped("scope_persistence_failed", "settlement not durably recorded",
                                  scope_id=reserved["scope_id"]) from exc
        _log.exception("llm usd gate could not reconcile; reservation stays")
    else:
        if controlled and decision.get("code") != "reconciled":
            raise LlmScopeStopped("scope_circuit_open", decision.get("reason") or decision.get("code") or "unknown",
                                  scope_id=reserved["scope_id"])
    return result
