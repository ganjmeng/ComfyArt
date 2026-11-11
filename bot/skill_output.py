"""#707: declared canvas size for skills whose deliverable is not 1024x1024.

The agent is told the size in the skill text. This module also fills generate_image
when a skill run omits it, and skips the list_models / expand / extra-frame detour
on a single-image skill. It does not choose a model and does not change the #706
identical-call guard.
"""
from __future__ import annotations

import re

# images: how many separate generate_image calls the skill is built for.
# A single-image skill is exactly one call. pose-fission is one call per shot.
OUTPUTS: dict[str, dict] = {
    "before-after": {
        "width": 1920, "height": 1080, "ratio": "16:9", "images": 1,
        "names": ("before-after", "前后对比视觉", "Before / After Visuals"),
    },
    "pose-fission": {
        "width": 1536, "height": 2048, "ratio": "3:4", "images": 4,
        "names": ("pose-fission", "电商同场景角色姿势裂变", "Same-Scene Pose Fission"),
    },
    "game-art": {
        "width": 1024, "height": 1824, "ratio": "9:16", "images": 1,
        "names": ("game-art", "游戏美术与运营视觉设计", "Game Art & Ops Visuals"),
    },
    "linkedin-banner": {
        "width": 1584, "height": 396, "images": 1,
        "names": ("linkedin-banner", "LinkedIn横幅", "LinkedIn Banner"),
    },
}

_BY_NAME = {n.casefold(): sid for sid, row in OUTPUTS.items() for n in row["names"]}
_DETOUR = frozenset({"list_models", "expand_image", "create_frame"})


def resolve(name: object) -> str | None:
    key = str(name or "").strip().casefold()
    return _BY_NAME.get(key)


def output_of(name: object) -> dict | None:
    sid = resolve(name)
    return OUTPUTS.get(sid) if sid else None


def is_single(name: object) -> bool:
    row = output_of(name)
    return bool(row) and int(row["images"]) == 1

# #905: a ratio the user wrote in their own message overrides the default, for before-after only.
# One exact size per ratio. A ratio the chat model wrote is ignored; a ratio not in the table falls back.
USER_RATIOS: dict[str, dict[str, tuple[int, int]]] = {
    "before-after": {"16:9": (1920, 1080), "4:5": (1024, 1280), "1:1": (1024, 1024), "9:16": (1080, 1920)},
}
_RATIO_WORDS = {"横版": "16:9", "竖版": "9:16", "方图": "1:1", "正方形": "1:1"}
_RATIO_RE = re.compile(r"(?<![\d.])(\d{1,2})\s*[:：]\s*(\d{1,2})(?![\d.])")
# Text the app adds to the user turn (skill start hint, output lock); never the user's own words.
_INJECTED_RE = re.compile(r"Use the ComfyArt skill [\s\S]*?then follow those instructions\.|Output lock:[^\n]*")
USER_RATIO_KEY = "_user_ratio"


def user_ratio(sid: str, user_text: object) -> str | None:
    """The first whitelisted ratio in the user's own text, or None (default size)."""
    table = USER_RATIOS.get(sid)
    if not table:
        return None
    text = _INJECTED_RE.sub(" ", str(user_text or ""))
    for m in _RATIO_RE.finditer(text):
        r = f"{int(m.group(1))}:{int(m.group(2))}"
        if r in table:
            return r
    for word, r in _RATIO_WORDS.items():
        if word in text and r in table:
            return r
    return None


def apply_generate(args: dict | None, current_skill: str = "", user_text: str | None = None,
                   ref_image: bytes | None = None) -> dict:
    """Fill the skill id and its declared pixels. Unknown skills are left alone.

    A declared size replaces a square default or a ratio the model invented.
    count stays 1: a multi-shot skill varies the prompt per call, not count.
    """
    args = dict(args or {})
    raw = str(args.get("skill") or "").strip()
    named = resolve(raw)
    if raw and not named:
        return args
    sid = named or resolve(current_skill)
    if not sid:
        return args
    row = OUTPUTS[sid]
    if not named:
        args["skill"] = sid
    # #905: user_text is given only where the user's own message is known (the chat loop); it sets
    # or clears the marker. Without it (the relay), only a marker matching the table is kept.
    if user_text is not None:
        picked = user_ratio(sid, user_text)
        if not picked and ref_image and args.get("refs") and sid in USER_RATIOS:
            # #905: no ratio in the user message, but a reference: follow the card inside it.
            # Decided from pixels on the server (bot/ref_orientation.py); the model has no say.
            from .ref_orientation import reference_ratio
            ref = reference_ratio(ref_image)
            picked = ref if ref in USER_RATIOS[sid] else None
    else:
        picked = str(args.get(USER_RATIO_KEY) or "")
        picked = picked if picked in USER_RATIOS.get(sid, {}) else None
    args.pop(USER_RATIO_KEY, None)
    if picked:
        w, h = USER_RATIOS[sid][picked]
        args["width"], args["height"], args["ratio"] = w, h, picked
        args[USER_RATIO_KEY] = picked
    else:
        args["width"] = int(row["width"])
        args["height"] = int(row["height"])
        if row.get("ratio"):
            args["ratio"] = row["ratio"]
        else:
            args.pop("ratio", None)
    args["count"] = 1
    # The page audits the downloaded file against these pixels. This does not change the model.
    args["size_lock"] = True
    return args


def run_hint(name: object, user_text: str = "", ref_image: bytes | None = None) -> str:
    """One line appended to the skill-start user text. Empty when the skill has no declared size.

    #905: when the user's own message names a whitelisted ratio, the lock states that size, so the
    model is not told 16:9 while the user asked for 4:5.
    """
    sid = resolve(name)
    if not sid:
        return ""
    row = OUTPUTS[sid]
    picked = user_ratio(sid, user_text) if user_text else None
    if not picked and ref_image and sid in USER_RATIOS:
        from .ref_orientation import reference_ratio
        ref = reference_ratio(ref_image)
        picked = ref if ref in USER_RATIOS[sid] else None
    if picked:
        w, h = USER_RATIOS[sid][picked]
        size = f"width={w} height={h} ratio={picked}"
    else:
        size = f"width={row['width']} height={row['height']}"
        if row.get("ratio"):
            size += f" ratio={row['ratio']}"
    if int(row["images"]) == 1:
        return (
            f"Output lock: call generate_image exactly once with skill={sid!r}, {size}, count=1. "
            "Do not call list_models, expand_image, or create_frame. Do not outpaint. "
            "Then wait_generation and finish. Lettering must be real words in quotes, large enough to read."
        )
    return (
        f"Output lock: each generate_image uses skill={sid!r}, {size}, count=1, and a different prompt "
        "(pose and angle only, not camera or shot size). Do not repeat the same arguments. Do not use 1024x1024."
    )


def single_image_skip(tool: str, skill: object, lang: str, generated: int) -> str | None:
    """Canned result for a detour or a second generate on a single-image skill. None = run the tool.

    The text is a normal tool result, not a non-retryable error, so the model can finish.
    """
    sid = resolve(skill)
    if not sid or not is_single(sid):
        return None
    row = OUTPUTS[sid]
    base = tool.split(".")[-1]
    if base == "generate_image" and generated < 1:
        return None
    if base != "generate_image" and base not in _DETOUR:
        return None
    size = f"{row['width']}x{row['height']}"
    if lang == "zh":
        if base == "generate_image":
            return (
                f"单图技能 {sid} 只生成 1 次，这一次没有提交，也没有扣费。"
                f"请调用 wait_generation 查看已有结果，然后结束。不要再生成、不要扩图、不要 list_models。"
            )
        return (
            f"单图技能 {sid} 不使用 {base}。请直接 generate_image 一次，"
            f"skill={sid}，width={row['width']}，height={row['height']}（{size}），count=1。"
            "不要扩图，不要另建不同尺寸的画框。"
        )
    if base == "generate_image":
        return (
            f"Single-image skill {sid} already used its one generate_image. This call did not submit "
            "and nothing was charged. Call wait_generation if needed, then finish. "
            "Do not generate again, expand, or list models."
        )
    return (
        f"Single-image skill {sid} does not use {base}. Call generate_image once with "
        f"skill={sid!r}, width={row['width']}, height={row['height']} ({size}), count=1. "
        "Do not outpaint and do not create a frame at another size."
    )
