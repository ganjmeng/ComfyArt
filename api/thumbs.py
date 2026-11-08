import asyncio
import hashlib
import os
import uuid

from aiohttp import web
from PIL import Image, ImageOps

from ._common import app_path, routes, view_path
from .bot_media import VIDEO_EXT, video_frames
from .svg_image import admit, read_limited

SIZES = (256, 512, 1024)
SKIP_FACTOR = 1.25
QUALITY = 85


def _size(max_edge: int) -> int:
    return next((s for s in SIZES if max_edge <= s), SIZES[-1])


def thumb_for(url: str, max_edge: int) -> str:
    src = view_path(url)
    if src.lower().endswith(".svg"):
        return src
    size = _size(max_edge)
    video = src.lower().endswith(VIDEO_EXT)
    st = os.stat(src)
    key = hashlib.sha1(f"{src}|{st.st_size}|{st.st_mtime_ns}|{size}".encode()).hexdigest()
    dest = app_path("thumbs", f"{key}.webp")
    if os.path.isfile(dest):
        return dest
    with (video_frames(src, 1)[0][0][1] if video else Image.open(src)) as im:
        if not video and not getattr(im, "is_animated", False) and max(im.size) <= size * SKIP_FACTOR:
            return src
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGBA" if "A" in im.getbands() or "transparency" in im.info else "RGB")
        im.thumbnail((size, size), Image.LANCZOS)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = f"{dest}.{uuid.uuid4().hex[:8]}.tmp"
        im.save(tmp, format="WEBP", quality=QUALITY)
    os.replace(tmp, dest)
    return dest


@routes.get("/comfyart/thumb")
async def thumb(request: web.Request) -> web.StreamResponse:
    url = request.query.get("url", "")
    max_edge = int(request.query.get("max", "256")) if request.query.get("max", "256").isdigit() else 256
    try:
        path = await asyncio.get_running_loop().run_in_executor(None, thumb_for, url, max_edge)
    except (ValueError, OSError):
        raise web.HTTPNotFound()
    headers = {"Cache-Control": "no-cache"}
    if path.endswith(".webp"):
        headers["Content-Type"] = "image/webp"
    elif path.lower().endswith(".svg"):
        # #826: never serve the SVG document as an image. Raster PNG, or 404 when the file is rejected.
        verdict = admit(read_limited(path))
        if verdict.status == "rejected" or not verdict.preview_png:
            raise web.HTTPNotFound(text=verdict.message, content_type="text/plain")
        return web.Response(body=verdict.preview_png, headers={
            **headers,
            "Content-Type": "image/png",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "X-Content-Type-Options": "nosniff",
        })
    return web.FileResponse(path, headers=headers)
