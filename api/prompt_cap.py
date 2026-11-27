"""One character limit per model id, applied to the final provider prompt."""

PROMPT_CHAR_CAP = {
    "wavespeed-ai/qwen-image-2.0/text-to-image": 2800,
    "wavespeed-ai/qwen-image-2.0/edit": 2800,
}


def over_prompt_cap(model: str, prompt: str) -> str:
    """Empty when the prompt may be sent. Never shortens the text."""
    cap = PROMPT_CHAR_CAP.get(str(model or ""))
    if cap is None:
        return ""
    length = len(str(prompt or ""))
    if length <= cap:
        return ""
    return (
        f"prompt is {length} characters; {model} accepts at most {cap}. "
        "The prompt was not truncated."
    )


def _hint_kind(text: str) -> str:
    body = str(text or "").strip()
    if body.startswith("Use only the visual style"):
        return "style"
    if body.startswith("Use image ") and "content reference" in body:
        return "content"
    return ""


def finalize_qwen_prompt(model: str, prompt: str, hints: list[str] | None = None) -> tuple[str, str]:
    """Join ref hints onto the prompt, then measure. Returns (final, error). Never slices.

    Exact duplicates are dropped. A caller that already brought one hint kind
    does not receive a second kind.
    """
    text = str(prompt or "")
    caller_kind = _hint_kind(text)
    seen = {caller_kind} if caller_kind else set()
    extra: list[str] = []
    for hint in hints or []:
        piece = str(hint or "").strip()
        if not piece or piece in text or piece in extra:
            continue
        kind = _hint_kind(piece)
        if caller_kind and kind and kind != caller_kind:
            continue
        if kind and kind in seen:
            continue
        if kind:
            seen.add(kind)
        extra.append(piece)
    if extra:
        if text.startswith("Use only the visual style") or text.startswith("Use image 1 as the content reference"):
            text = " ".join(extra + [text])
        else:
            text = " ".join([text, *extra])
    return text, over_prompt_cap(model, text)
