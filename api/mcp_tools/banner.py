"""#youtube-channel-banner 精确排版: compose_banner_text (server-side text on the text-free base).

The image model never draws the text on this path. The server reads the base image,
upscales it to exactly 2560×1440 and sets the picked lines with the bundled font inside
YouTube's safe areas (api/banner_compose.py). No WaveSpeed call, so no charge.
Only the youtube-channel-banner user-side final may call it.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from urllib.parse import urlencode

from .. import banner_compose
from ..mcp_commands import submit_command
from ._context import BOT_CHAT_ID, PROJECT

log = logging.getLogger("comfyart")

SUBFOLDER = "comfyart/banner"
PLACE_ACTION = "place_banner"


def _failed(error: str, kind: str) -> dict:
    return {"status": "failed", "generation_succeeded": False, "submitted": False, "charged": False,
            "error": error, "kind": kind}


def _local_bytes(src: str) -> bytes | None:
    from ...bot.ref_orientation import _src_bytes

    return _src_bytes(src)


async def _canvas_shapes() -> list[dict]:
    try:
        res = await submit_command("get_canvas", {}, PROJECT.get(), 20.0, chat=BOT_CHAT_ID.get())
    except Exception as e:  # the page may be gone; a URL base still works
        log.warning("compose_banner_text: get_canvas failed: %s", e)
        return []
    return list((res or {}).get("shapes") or []) if isinstance(res, dict) else []


async def _resolve_base(base: str) -> tuple[bytes | None, str | None]:
    """(bytes, shape id) of the base image from a shape id or a local /api/view URL."""
    near = None
    url = base if not base.startswith("shape:") else ""
    shapes = await _canvas_shapes()
    for s in shapes:
        if base.startswith("shape:") and s.get("id") == base:
            url, near = str(s.get("url") or ""), base
            break
        if url and s.get("url") == url:
            near = str(s.get("id") or "") or None
            break
    return (_local_bytes(url) if url else None), near


def _save(png: bytes) -> dict:
    import folder_paths

    name = f"yt-banner-{hashlib.sha1(png).hexdigest()[:12]}.png"
    root = os.path.abspath(folder_paths.get_output_directory())
    path = os.path.join(root, SUBFOLDER, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return {"filename": name, "subfolder": SUBFOLDER, "type": "output",
            "metadata": {"width": banner_compose.CANVAS[0], "height": banner_compose.CANVAS[1]}}


def view_url(ref: dict) -> str:
    return "/api/view?" + urlencode({"filename": ref["filename"], "subfolder": ref["subfolder"], "type": ref["type"]})


async def compose_banner_text(args: dict) -> dict:
    skill = str(args.get("skill") or "")
    try:
        banner_compose.guard(skill, banner_compose.PURPOSE_USER_FINAL)
    except banner_compose.CompositorRefused as e:
        return _failed(str(e), "bannerComposeRefused")
    base = str(args.get("base") or "").strip()
    if not base:
        return _failed("base is required: the text-free base image's shape id or URL", "bannerComposeNoBase")
    data, near = await _resolve_base(base)
    if not data:
        return _failed(f"could not read the base image {base!r}; pass the URL or shape id wait_generation returned",
                       "bannerComposeNoBase")
    try:
        png, report = await asyncio.to_thread(
            banner_compose.compose, data,
            channel=str(args.get("channel_name") or ""), tagline=str(args.get("tagline") or ""),
            schedule=str(args.get("schedule") or ""), brand_color=args.get("brand_color"),
            skill=skill, purpose=banner_compose.PURPOSE_USER_FINAL)
    except banner_compose.LayoutError as e:
        return _failed(str(e), "bannerComposeLayout")
    ref = _save(png)
    placed = await submit_command(PLACE_ACTION, {"image": ref, "near": near or "", "name": "YouTube banner 2560×1440"},
                                  PROJECT.get(), 30.0, chat=BOT_CHAT_ID.get())
    out = {
        "status": "done", "charged": False,
        "id": (placed or {}).get("id") if isinstance(placed, dict) else None,
        "url": view_url(ref), "width": report["width"], "height": report["height"],
        "all_inside_strict_core": report["all_inside_strict_core"],
        "all_inside_hard_boundary": report["all_inside_hard_boundary"],
        "text_area_clear": report["text_area_clear"],
        "lines": [{"role": r["role"], "text": r["text"], "ink_bbox": r["ink_bbox"]} for r in report["lines"]],
    }
    if not report["text_area_clear"]:
        out["note"] = ("The text overlaps part of the base graphic. Tell the user and offer one new base "
                       "with the graphic kept to the right of the middle band; do not regenerate unasked.")
    return out


TOOLS: dict[str, dict] = {
    "compose_banner_text": {
        "description": (
            "youtube-channel-banner only, 精确排版 final: set the picked banner text on the text-free base "
            "image with a bundled Chinese sans-serif font. The server upscales the base to exactly 2560x1440 and "
            "places channel_name (largest, brand_color), tagline, a thin accent line and schedule left-aligned "
            "inside the YouTube safe area, then puts the result on the canvas next to the base. No model call, "
            "no charge. base: the base image's shape id or URL from wait_generation. skill must be "
            "youtube-channel-banner. Pass only the lines the user picked, spelled exactly."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "base": {"type": "string"}, "skill": {"type": "string"},
                "channel_name": {"type": "string"}, "tagline": {"type": "string"},
                "schedule": {"type": "string"}, "brand_color": {"type": "string", "description": "hex like #2F6BFF"},
            },
            "required": ["base", "skill", "channel_name"],
            "additionalProperties": False,
        },
        "handler": compose_banner_text,
    },
}
