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


def finalize_qwen_prompt(model: str, prompt: str, hints: list[str] | None = None) -> tuple[str, str]:
    """Join ref hints onto the prompt, then measure. Returns (final, error). Never slices."""
    text = str(prompt or "")
    extra = [str(hint).strip() for hint in (hints or []) if str(hint or "").strip() and str(hint).strip() not in text]
    if extra:
        if text.startswith("Use only the visual style") or text.startswith("Use image 1 as the content reference"):
            text = " ".join(extra + [text])
        else:
            text = " ".join([text, *extra])
    return text, over_prompt_cap(model, text)
