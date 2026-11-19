"""Canonical assistant history shared by the budget and legacy loops.

No provider or loop imports: this module must remain safe for either caller.
"""
from __future__ import annotations


def assistant_history_message(message: dict, content, tool_calls=None) -> dict:
    """Assistant message appended to history for the next official request.

    Canonical ``reasoning_content`` is preserved when the server sent it. Official
    thinking+tools requires that field to be echoed; this does not disable thinking.
    """
    row = {"role": "assistant", "content": content or (None if tool_calls else "")}
    if tool_calls:
        row["tool_calls"] = tool_calls
    if isinstance(message, dict) and "reasoning_content" in message:
        rc = message.get("reasoning_content")
        if type(rc) is str:
            row["reasoning_content"] = rc
    return row
