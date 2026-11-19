"""Local request profile for the documented Flash context-contract interpretation.

Format/bytes/image limits are local engineering limits from the reviewed
billing-bound-evidence-plan, NOT token estimates or a supplier bill guarantee.
External HTTP(S) image URLs require already-materialized bytes from a caller;
this module never fetches, resolves DNS, loads credentials, or drops images.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import math
import re
import threading
import warnings
from dataclasses import dataclass
from urllib.parse import urlsplit

from PIL import Image

CONTEXT_TOKENS = 1_048_576
TOKENS_PER_IMAGE = 1_024
MAX_MESSAGES = 256
MAX_TOOLS = 128
MAX_SCHEMA_BYTES = 256 * 1024
MAX_SINGLE_SCHEMA_BYTES = 64 * 1024
MAX_TEXT_BYTES = 512 * 1024
MAX_IMAGES = 16
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_ALL_IMAGE_BYTES = 24 * 1024 * 1024
MAX_BODY_BYTES = 40 * 1024 * 1024
MAX_SIDE = 4096
MAX_PIXELS = 16_777_216
MAX_PROFILE_OUTPUT = 65_536
MODE = "documented_context_contract"
_DECODE_LOCK = threading.Lock()  # At most one bounded image decode per process.
_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif", "WEBP": "image/webp"}
_NAME = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
EVIDENCE = (
    ("https://api-docs.deepseek.com/api/create-chat-completion",
     "The total length of input tokens and generated tokens is limited by the model's context length."),
    ("https://api-docs.deepseek.com/quick_start/agent_integrations/codex.md", '"context_window": 1048576'),
    ("https://api-docs.deepseek.com/guides/vision", "As a result, there is an upper bound of 1024 tokens per image"),
)


class EnvelopeInvalid(ValueError):
    def __init__(self, code: str, field: str):
        self.code, self.field = code, field
        super().__init__(f"{code}: {field}")  # No candidate values / image data.


def _need(ok: bool, field: str, code: str = "invalid_request_envelope") -> None:
    if not ok:
        raise EnvelopeInvalid(code, field)


def _encode(value) -> bytes:
    try:
        # Exactly the default aiohttp JSON serializer's spacing/ASCII escaping,
        # with non-finite numbers rejected. These exact bytes are sent as data.
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")  # Reject lone surrogates.
        return json.dumps(value, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise EnvelopeInvalid("invalid_request_envelope", "json") from exc


@dataclass(frozen=True)
class FrozenJsonBody:
    encoded: bytes

    def as_dict(self) -> dict:
        return json.loads(self.encoded)


@dataclass(frozen=True)
class Envelope:
    frozen: FrozenJsonBody
    body_sha256: str
    image_count: int
    image_bytes: int
    text_bytes: int
    tool_schema_bytes: int

    def evidence(self) -> dict:
        return {"mode": MODE, "strictly_proven": False, "context_tokens": CONTEXT_TOKENS,
                "image_count": self.image_count, "image_tokens_upper": self.image_count * TOKENS_PER_IMAGE,
                "images_included_in_context": True, "context_includes_output": True,
                "reservation_policy": "full_context_input_plus_explicit_output",
                "charged_error_contract_proven": False, "body_sha256": self.body_sha256,
                "body_bytes": len(self.frozen.encoded), "image_bytes": self.image_bytes,
                "text_bytes": self.text_bytes, "tool_schema_bytes": self.tool_schema_bytes,
                "sources": [{"url": url, "quoted_statement_sha256": hashlib.sha256(text.encode()).hexdigest()}
                            for url, text in EVIDENCE]}


def _image(url: str, frozen_images, field: str) -> tuple[str, int]:
    _need(type(url) is str and bool(url), field)
    declared = None
    if url.startswith("data:"):
        match = re.fullmatch(r"data:(image/(?:jpeg|png|gif|webp));base64,([A-Za-z0-9+/]*={0,2})", url)
        _need(match is not None, field, "invalid_image")
        declared, encoded = match.groups()
        _need(len(encoded) <= 4 * ((MAX_IMAGE_BYTES + 2) // 3), field, "image_limit")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise EnvelopeInvalid("invalid_image", field) from exc
    else:
        _need(len(url) <= 8192 and not any(ord(c) <= 32 or ord(c) == 127 for c in url), field, "invalid_image_url")
        try:
            parsed = urlsplit(url)
            valid = (parsed.scheme in ("http", "https") and bool(parsed.hostname)
                     and not parsed.username and not parsed.password and not parsed.fragment)
            parsed.port  # Reject malformed port syntax. No network/DNS operation.
        except ValueError as exc:
            raise EnvelopeInvalid("invalid_image_url", field) from exc
        _need(valid, field, "invalid_image_url")
        raw = frozen_images.get(url) if frozen_images is not None else None
        _need(type(raw) is bytes, field, "image_url_not_frozen")
    _need(0 < len(raw) <= MAX_IMAGE_BYTES, field, "image_limit")
    try:
        with _DECODE_LOCK, warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                kind = image.format
                _need(kind in _MIME and (declared is None or declared == _MIME[kind]), field, "invalid_image")
                _need(getattr(image, "n_frames", 1) == 1, field, "animated_image_unsupported")
                width, height = image.size
                _need(0 < width <= MAX_SIDE and 0 < height <= MAX_SIDE and width * height <= MAX_PIXELS,
                      field, "image_limit")
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
    except EnvelopeInvalid:
        raise
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise EnvelopeInvalid("invalid_image", field) from exc
    # Preserve validated inline URL exactly. Freeze remote images to those same
    # verified bytes, so the supplier never fetches mutable content or a URL.
    return (url if declared else f"data:{_MIME[kind]};base64," + base64.b64encode(raw).decode()), len(raw)


def validate_envelope(body: dict, *, frozen_images=None) -> Envelope:
    """Private JSON snapshot; preserve canonical reasoning, tools and image parts.

    Caller applies the mode's real output cap first. No input token estimation:
    the entire context (already including images) is reserved as input, PLUS the
    explicit output cap. This deliberately over-reserves versus C-output, rather
    than adding image tokens again or assuming output is part of input billing.
    """
    _need(type(body) is dict, "body")
    encoded = _encode(body)
    _need(len(encoded) <= MAX_BODY_BYTES, "body", "body_limit")
    b = json.loads(encoded)
    allowed = {"messages", "model", "thinking", "reasoning_effort", "max_tokens",
               "response_format", "stop", "stream", "stream_options", "temperature", "top_p",
               "tools", "tool_choice", "safety_check", "title", "logprobs", "top_logprobs",
               "user_id", "frequency_penalty", "presence_penalty"}
    _need(not set(b) - allowed, "body.fields")
    _need(frozen_images is None or hasattr(frozen_images, "get"), "frozen_images")
    _need(b.get("model") == "deepseek-flash", "model")
    _need(b.get("stream") is None or b.get("stream") is False, "stream", "unsupported_stream")
    _need(b.get("stream_options") is None, "stream_options", "unsupported_stream")
    thinking = b.get("thinking")
    if thinking is not None:
        _need(type(thinking) is dict and set(thinking) == {"type"}
              and thinking["type"] in ("enabled", "disabled"), "thinking")
    _need(b.get("reasoning_effort") is None or b["reasoning_effort"] in
          ("none", "low", "high", "max", "minimal", "medium", "xhigh"), "reasoning_effort")
    cap = b.get("max_tokens")
    _need(type(cap) is int and 1 <= cap <= MAX_PROFILE_OUTPUT, "max_tokens", "profile_output_cap")
    tools = b.get("tools") if b.get("tools") is not None else []
    _need(type(tools) is list and len(tools) <= MAX_TOOLS, "tools", "tool_schema_limit")
    names, schema_bytes = set(), 0
    for i, tool in enumerate(tools):
        field = f"tools[{i}]"
        _need(type(tool) is dict and set(tool) == {"type", "function"}, field)
        _need(tool["type"] == "function", field, "unpriced_tool_fee")
        fn = tool["function"]
        _need(type(fn) is dict and not set(fn) - {"name", "description", "parameters", "strict"}, field)
        name = fn.get("name")
        _need(type(name) is str and bool(_NAME.fullmatch(name)) and name not in names, field)
        _need(name not in ("deepseek_web_search", "deepseek_read_url"), field, "unpriced_tool_fee")
        names.add(name)
        _need("parameters" not in fn or (type(fn["parameters"]) is dict
              and fn["parameters"].get("type", "object") == "object"), field)
        _need("description" not in fn or type(fn["description"]) is str, field)
        _need("strict" not in fn or type(fn["strict"]) is bool, field)
        size = len(_encode(tool)); schema_bytes += size
        _need(size <= MAX_SINGLE_SCHEMA_BYTES and schema_bytes <= MAX_SCHEMA_BYTES, field, "tool_schema_limit")
    choice = b.get("tool_choice")
    if type(choice) is dict:
        _need(set(choice) == {"type", "function"} and choice["type"] == "function"
              and type(choice["function"]) is dict and set(choice["function"]) == {"name"}, "tool_choice")
        _need(type(choice["function"]["name"]) is str and choice["function"]["name"] in names, "tool_choice")
    else:
        _need(choice in (None, "none", "auto", "required"), "tool_choice")
        _need(choice not in ("auto", "required") or bool(names), "tool_choice")
    messages = b.get("messages")
    _need(type(messages) is list and 1 <= len(messages) <= MAX_MESSAGES, "messages", "message_limit")
    pending, seen = {}, set()
    images, image_bytes = 0, 0
    for i, message in enumerate(messages):
        field = f"messages[{i}]"
        _need(type(message) is dict, field)
        role = message.get("role")
        _need(role in ("system", "user", "assistant", "tool", "latest_reminder"), field + ".role")
        allowed = {"role", "content", "name"}
        if role == "assistant":
            allowed |= {"tool_calls", "reasoning_content"}
        if role == "tool":
            allowed |= {"tool_call_id"}
        _need(not set(message) - allowed and "content" in message, field)
        _need("name" not in message or type(message["name"]) is str, field + ".name")
        if "reasoning_content" in message:
            _need(message["reasoning_content"] is None or type(message["reasoning_content"]) is str,
                  field + ".reasoning_content")
        if role == "assistant":
            _need(not pending, field + ".tool_calls", "tool_pairing")
            calls = message.get("tool_calls", [])
            _need(type(calls) is list, field + ".tool_calls")
            for call in calls:
                _need(type(call) is dict and set(call) == {"id", "type", "function"}, field + ".tool_calls")
                cid, fn = call["id"], call["function"]
                _need(type(cid) is str and bool(cid) and cid not in seen and call["type"] == "function",
                      field + ".tool_calls", "tool_pairing")
                _need(type(fn) is dict and set(fn) == {"name", "arguments"}
                      and type(fn["name"]) is str and fn["name"] in names
                      and type(fn["arguments"]) is str, field + ".tool_calls")
                try:
                    args = json.loads(fn["arguments"], parse_constant=lambda _v: (_ for _ in ()).throw(ValueError()))
                except (ValueError, RecursionError) as exc:
                    raise EnvelopeInvalid("invalid_request_envelope", field + ".arguments") from exc
                _need(type(args) is dict, field + ".arguments")
                pending[cid] = fn["name"]; seen.add(cid)
        if role == "tool":
            cid = message.get("tool_call_id")
            _need(type(cid) is str and cid in pending, field + ".tool_call_id", "tool_pairing")
            del pending[cid]
        if role == "latest_reminder":
            _need(i + 1 < len(messages) and type(messages[i + 1]) is dict
                  and messages[i + 1].get("role") == "user", field, "reminder_position")
        content = message["content"]
        if content is None:
            _need(role == "assistant", field + ".content")
        elif type(content) is list:
            _need(role in ("system", "user", "tool") and bool(content), field + ".content")
            for j, part in enumerate(content):
                pf = field + f".content[{j}]"
                _need(type(part) is dict, pf)
                if part.get("type") == "text":
                    _need(set(part) == {"type", "text"} and type(part["text"]) is str, pf)
                else:
                    _need(set(part) == {"type", "image_url"} and part.get("type") == "image_url", pf)
                    image = part["image_url"]
                    _need(type(image) is dict and "url" in image and not set(image) - {"url", "detail"}, pf)
                    _need("detail" not in image or image["detail"] in ("low", "high", "original", "auto"), pf)
                    images += 1
                    _need(images <= MAX_IMAGES, pf, "image_limit")
                    image["url"], size = _image(image["url"], frozen_images, pf + ".image_url.url")
                    image_bytes += size
                    _need(image_bytes <= MAX_ALL_IMAGE_BYTES, pf, "image_limit")
        else:
            _need(type(content) is str, field + ".content")
    _need(not pending, "messages.tool_calls", "tool_pairing")
    # Count every string outside tool schemas and image binary representations.
    def text_bytes(value, key=""):
        if type(value) is str:
            return 0 if key == "url" and value.startswith("data:image/") else len(value.encode("utf-8"))
        if type(value) is list:
            return sum(text_bytes(v) for v in value)
        if type(value) is dict:
            return sum(len(k.encode()) + text_bytes(v, k) for k, v in value.items() if k != "tools")
        return 0
    text = text_bytes(b)
    _need(text <= MAX_TEXT_BYTES, "text", "text_limit")
    for key, low, high in (("temperature", 0, 2), ("top_p", 0, 1), ("frequency_penalty", -2, 2), ("presence_penalty", -2, 2)):
        value = b.get(key)
        if value is not None:
            _need(type(value) in (int, float) and math.isfinite(value) and low <= value <= high
                  and (key != "top_p" or value > 0), key)
    if b.get("response_format") is not None:
        value = b["response_format"]
        _need(type(value) is dict and set(value) == {"type"} and value["type"] in ("text", "json_object"), "response_format")
    if b.get("stop") is not None:
        stops = [b["stop"]] if type(b["stop"]) is str else b["stop"]
        _need(type(stops) is list and 1 <= len(stops) <= 16
              and all(type(v) is str and 0 < len(v.encode()) <= 512 for v in stops), "stop")
    for key in ("logprobs",):
        _need(b.get(key) is None or type(b[key]) is bool, key)
    if b.get("top_logprobs") is not None:
        _need(type(b["top_logprobs"]) is int and 0 <= b["top_logprobs"] <= 20 and b.get("logprobs") is True, "top_logprobs")
    if b.get("safety_check") is not None:
        value = b["safety_check"]
        _need(type(value) is dict and set(value) == {"level"} and value["level"] in ("low", "high"), "safety_check")
    if b.get("title") is not None:
        value = b["title"]
        _need(type(value) is dict and set(value) == {"enabled"} and type(value["enabled"]) is bool, "title")
    if b.get("user_id") is not None:
        _need(type(b["user_id"]) is str and len(b["user_id"].encode()) <= 512, "user_id")
    encoded = _encode(b)
    _need(len(encoded) <= MAX_BODY_BYTES, "body", "body_limit")
    return Envelope(FrozenJsonBody(encoded), hashlib.sha256(encoded).hexdigest(), images, image_bytes, text, schema_bytes)
