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
    # #911: clothing-swap follows the person photo (image 1); see FOLLOW_REF_SIZES.
    # This row is only the fallback when image 1's size cannot be read.
    "clothing-swap": {
        "width": 1536, "height": 2048, "ratio": "3:4", "images": 1,
        "names": ("clothing-swap", "AI服装换装", "AI Clothing Swap"),
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


# #911: skills whose output ratio follows image 1 (the first reference). The
# server reads that image's pixel size and snaps to the closest ratio here
# (api/wavespeed._nearest, the same snap used for a model's aspect_ratio enum;
# the model's own enum snap still runs on submit). One in-limit size per ratio.
# If image 1 cannot be read, the OUTPUTS row (3:4) is used.
FOLLOW_REF_SIZES: dict[str, dict[str, tuple[int, int]]] = {
    "clothing-swap": {
        "1:1": (1536, 1536),
        "4:5": (1600, 2000), "5:4": (2000, 1600),
        "3:4": (1536, 2048), "4:3": (2048, 1536),
        "2:3": (1344, 2016), "3:2": (2016, 1344),
        "9:16": (1152, 2048), "16:9": (2048, 1152),
    },
}
# Marker so the relay pass (no image bytes) keeps the ratio the chat loop read.
REF_RATIO_KEY = "_ref_ratio"


def follows_ref(name: object) -> bool:
    sid = resolve(name)
    return bool(sid) and sid in FOLLOW_REF_SIZES


def image_size(data: bytes | None) -> tuple[int, int] | None:
    """Pixel (width, height) of image bytes; None when absent or undecodable."""
    if not data:
        return None
    try:
        import io

        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
    except Exception:
        return None
    return (int(w), int(h)) if w and h else None


def ref_ratio(sid: str, data: bytes | None) -> str | None:
    """Closest FOLLOW_REF_SIZES ratio to image 1's pixel aspect; None if unreadable."""
    table = FOLLOW_REF_SIZES.get(sid)
    size = image_size(data)
    if not table or not size:
        return None
    from ..api.wavespeed import _nearest
    return _nearest(list(table), size[0] / size[1])


def apply_generate(args: dict | None, current_skill: str = "",
                   ref_image: bytes | None = None) -> dict:
    """Fill the skill id and its declared pixels. Unknown skills are left alone.

    A declared size replaces a square default or a ratio the model invented.
    count stays 1: a multi-shot skill varies the prompt per call, not count.
    #911: a FOLLOW_REF_SIZES skill takes image 1's ratio (ref_image bytes, or the
    marker a previous pass set); unreadable -> the declared fallback row.
    """
    args = dict(args or {})
    raw = str(args.get("skill") or "").strip()
    named = resolve(raw)
    if raw and not named:
        return args
    sid = named or resolve(current_skill)
    if not sid:
        # #911 / #912: studio-model and ai-model are not in OUTPUTS (no
        # declared canvas). Still pass skill= on generate_image so the call
        # is attributable. Only in that skill's session, only when skill is
        # omitted, and only when the call did not name an explicit model.
        # Do not invent a size, do not use a generic skill_pin hook, and
        # do not fill when the call already names a model.
        from ..api.auto_models import named_or_none
        cur = str(current_skill or "").strip().casefold()
        if (
            cur in {"studio-model", "ai-model"}
            and not raw
            and not named_or_none(args.get("model"))
            and not named_or_none(args.get("edit_model"))
        ):
            args["skill"] = cur
        return args
    row = OUTPUTS[sid]
    if not named:
        args["skill"] = sid
    picked = None
    if sid in FOLLOW_REF_SIZES:
        picked = ref_ratio(sid, ref_image) if ref_image is not None else None
        if picked is None and ref_image is None:
            marker = str(args.get(REF_RATIO_KEY) or "")
            picked = marker if marker in FOLLOW_REF_SIZES[sid] else None
    args.pop(REF_RATIO_KEY, None)
    if picked:
        args["width"], args["height"] = FOLLOW_REF_SIZES[sid][picked]
        args["ratio"] = picked
        args[REF_RATIO_KEY] = picked
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


def run_hint(name: object) -> str:
    """One line appended to the skill-start user text. Empty when the skill has no declared size."""
    sid = resolve(name)
    if not sid:
        return ""
    row = OUTPUTS[sid]
    size = f"width={row['width']} height={row['height']}"
    if row.get("ratio"):
        size += f" ratio={row['ratio']}"
    if sid in FOLLOW_REF_SIZES:
        # #911: the server sets width/height/ratio from image 1; the model must not pick one.
        size = "the size and ratio of image 1 (the server fills width, height and ratio; do not pass them)"
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
