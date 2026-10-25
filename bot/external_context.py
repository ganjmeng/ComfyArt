"""#238: P1 context rules for external agents (Claude Code, Codex, Qwen Code, DeepSeek Harness).

A cold start (no resume token) fits prior chat history into 70% of a 32k window — these CLIs
do not report a context window, so the #234 fallback applies. The last 6 turns stay verbatim
and older turns become one summary of at most 2000 tokens. A resumed session is left as the
CLI stored it.

Screenshot data URLs inside that fitted text keep the latest 2; older ones become the same
placeholder the built-in agent uses. The user's own attachments are not part of this text.

DeepSeek Harness has nowhere else to put AGENT_GUIDE, so a new session carries it. Claude
Code, Codex and Qwen Code already load the guide on every launch.

An external CLI process is not retried. It may already have called a paid tool; the P1 HTTP
retry stays on the built-in agent's model request.
"""
from __future__ import annotations

from dataclasses import replace

from .guide import AGENT_GUIDE
from .local_llm import (
    KEEP_SCREENSHOTS,
    _DATA_URL_RE,
    _FALLBACK_CONTEXT_WINDOW,
    count_tokens,
    fit_history,
)
from .providers import TurnRequest

_LABEL_RESERVE = 200  # "User:" / "Assistant:" lines added when the fitted turns are flattened
SCREENSHOT_OMITTED = "[older screenshot omitted]"


def prune_screenshot_urls(text: str, keep: int = KEEP_SCREENSHOTS) -> str:
    """Keep the latest `keep` screenshot data URLs; replace every older one with one text line."""
    found = list(_DATA_URL_RE.finditer(text or ""))
    if keep < 0 or len(found) <= keep:
        return text or ""
    drop = found[: len(found) - keep] if keep else found
    pieces: list[str] = []
    last = 0
    for match in drop:
        pieces.append(text[last:match.start()])
        pieces.append(SCREENSHOT_OMITTED)
        last = match.end()
    pieces.append(text[last:])
    return "".join(pieces)


def _fitted_preamble(history, *, reserved_tokens: int) -> str:
    messages = fit_history(
        history,
        context_window=_FALLBACK_CONTEXT_WINDOW,
        reserved_tokens=reserved_tokens,
    )
    chunks: list[str] = []
    for msg in messages:
        content = str(msg.get("content") or "")
        role = msg.get("role")
        if role == "user":
            content = "User: " + content
        elif role == "assistant":
            content = "Assistant: " + content
        if content:
            chunks.append(content)
    return prune_screenshot_urls("\n\n".join(chunks))


def apply_cold_start(turn: TurnRequest, *, prepend_guide: bool = False) -> TurnRequest:
    """Fit history into the prompt only when the CLI is not resuming a session.

    `prepend_guide` is for DeepSeek Harness, which does not load AGENT_GUIDE on its own.
    The guide is still reserved for the other CLIs, because they attach it as a system prompt.
    """
    if turn.resume_token:
        return turn
    guide = AGENT_GUIDE if prepend_guide else ""
    reserved = count_tokens(AGENT_GUIDE) + count_tokens(turn.user_text or "") + _LABEL_RESERVE
    preamble = _fitted_preamble(turn.history, reserved_tokens=reserved)
    parts = [part for part in (guide, preamble, turn.user_text or "") if part]
    text = "\n\n".join(parts)
    if text == (turn.user_text or ""):
        return turn
    return replace(turn, user_text=text)


def clip_image_blocks(blocks: list[dict], *, already_sent: int,
                      keep: int = KEEP_SCREENSHOTS) -> tuple[list[dict], int]:
    """Cap screenshot image blocks.

    `already_sent` is how many screenshot images this turn has already returned to the CLI.
    Those cannot be pulled back, so once `keep` have been sent, later images become the
    placeholder. Inside the response that still has room, the latest images are the ones kept.
    """
    indexes = [
        i for i, block in enumerate(blocks)
        if isinstance(block, dict) and block.get("type") == "image" and block.get("data")
    ]
    room = max(0, keep - max(0, already_sent))
    keep_at = set(indexes[-room:]) if room else set()
    out: list[dict] = []
    sent = max(0, already_sent)
    for i, block in enumerate(blocks):
        is_image = isinstance(block, dict) and block.get("type") == "image"
        if not is_image:
            out.append(block)
            continue
        if i in keep_at:
            sent += 1
            out.append(block)
        else:
            out.append({"type": "text", "text": SCREENSHOT_OMITTED})
    return out, sent
