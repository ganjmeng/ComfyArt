"""#707: declared canvas size for skills whose deliverable is not 1024x1024.

The agent is told the size in the skill text. This module also fills generate_image
when a skill run omits it, and skips the list_models / expand / extra-frame detour
on a single-image skill. It does not choose a model and does not change the #706
identical-call guard.
"""
from __future__ import annotations

# images: how many separate generate_image calls the skill is built for.
# A single-image skill is exactly one call. pose-fission is one call per shot.
OUTPUTS: dict[str, dict] = {
    "before-after": {
        "width": 1024, "height": 1280, "ratio": "4:5", "images": 1,
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


def apply_generate(args: dict | None, current_skill: str = "") -> dict:
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
        # A pinned skill that is not in OUTPUTS still needs skill= on the call
        # so the registered model pin applies. Do not invent a canvas size.
        pin_sid = str(current_skill or "").strip()
        if pin_sid and not raw:
            from ..api.auto_models import skill_pin
            if skill_pin(pin_sid):
                args["skill"] = pin_sid
        return args
    row = OUTPUTS[sid]
    if not named:
        args["skill"] = sid
    args["width"] = int(row["width"])
    args["height"] = int(row["height"])
    args["count"] = 1
    if row.get("ratio"):
        args["ratio"] = row["ratio"]
    else:
        args.pop("ratio", None)
    # The page audits the downloaded file against these pixels. This does not change the model.
    args["size_lock"] = True
    return args


def run_hint(name: object) -> str:
    """One line appended to the skill-start user text. Empty when the skill has no declared size."""
    sid = resolve(name)
    if not sid:
        return ""
    row = OUTPUTS[sid]
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
