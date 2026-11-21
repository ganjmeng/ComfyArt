"""Canonical assistant history shared by the budget and legacy loops.

No provider or loop imports: this module must remain safe for either caller.
"""
from __future__ import annotations


def replay_tool_calls(tool_calls):
    """Tool calls as they are stored for the next supplier request.

    A legitimate sequence ``index`` is the call's own position: a real ``int``
    equal to that slot (``True`` is not an int here). That one key is omitted
    from the replay. This does not say where a stored ``index`` came from.

    ``id``, ``type``, and the ``function`` name and arguments value are copied
    through. The arguments value is not re-encoded. The ``function`` object is
    a new dict, so a later in-place rewrite of the provider object's arguments
    does not change the replayed string. This function runs when the assistant
    row is first serialized, which is before that rewrite.

    Any other extra key is left in place. An ``index`` of the wrong type, or an
    int that is not this slot's position, is left in place. The request
    validator still rejects those shapes. The input list and its dicts are not
    mutated. A list that needs no change is returned as the same object.

    Already-stored history is not rewritten here. A checkpoint that already
    contains ``index`` does not pass through this function on resume.
    """
    if type(tool_calls) is not list:
        return tool_calls
    replayed = [_replay_tool_call(call, position) for position, call in enumerate(tool_calls)]
    if all(replayed[i] is tool_calls[i] for i in range(len(tool_calls))):
        return tool_calls
    return replayed


def _replay_tool_call(call, position: int):
    if type(call) is not dict or "index" not in call:
        return call
    index = call.get("index")
    # Legitimate sequence metadata only. Bool is an int subclass and is not a position.
    if type(index) is not int or index != position:
        return call
    replay = {key: value for key, value in call.items() if key != "index"}
    function = replay.get("function")
    if type(function) is dict:
        replay["function"] = dict(function)
    return replay


def assistant_history_message(message: dict, content, tool_calls=None) -> dict:
    """Assistant message appended to history for the next official request.

    Canonical ``reasoning_content`` is preserved when the server sent it. Official
    thinking+tools requires that field to be echoed; this does not disable thinking.
    Supplier replay of ``tool_calls`` drops only a legitimate sequence ``index``.
    """
    row = {"role": "assistant", "content": content or (None if tool_calls else "")}
    if tool_calls:
        row["tool_calls"] = replay_tool_calls(tool_calls)
    if isinstance(message, dict) and "reasoning_content" in message:
        rc = message.get("reasoning_content")
        if type(rc) is str:
            row["reasoning_content"] = rc
    return row
