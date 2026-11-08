"""#826: SVG download is an attachment. The thumb route rasterizes; this route never inlines."""
from __future__ import annotations

import os

from aiohttp import web

from ._common import routes, view_path
from .svg_image import admit, read_limited

_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "sandbox; default-src 'none'",
    "Cache-Control": "no-store",
}


@routes.get("/comfyart/svg_download")
async def svg_download(request: web.Request) -> web.StreamResponse:
    url = request.query.get("url", "")
    try:
        path = view_path(url)
        data = read_limited(path)
    except (OSError, ValueError):
        raise web.HTTPNotFound()
    verdict = admit(data)
    if verdict.status == "rejected" or verdict.download is None:
        # The body is the readable refusal, never the SVG bytes.
        raise web.HTTPNotFound(text=verdict.message, content_type="text/plain")
    name = os.path.basename(path)
    if not name.lower().endswith(".svg"):
        name = f"{name}.svg"
    safe = name.replace('"', "")
    return web.Response(body=verdict.download, headers={
        **_HEADERS,
        "Content-Type": "image/svg+xml",
        "Content-Disposition": f'attachment; filename="{safe}"',
    })
