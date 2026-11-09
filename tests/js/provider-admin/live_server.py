"""Isolated settings server for the provider page.

Serves the built preview and the real /comfyart/provider-admin routes.
The user directory is a fresh temp folder. No generation provider is called.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
os.environ.setdefault("COMFYART_SKIP_KEY_CHECK", "1")
os.environ.setdefault("COMFYART_SKIP_NODE_TESTS", "1")
sys.path.insert(0, str(ROOT.parent))
runpy.run_path(str(ROOT / "tests" / "conftest.py"))

from aiohttp import web  # noqa: E402
import server  # noqa: E402
from ComfyArt.api.provider_admin import _path  # noqa: E402

DIST = Path(os.environ.get("PROVIDER_UI_DIST", "/tmp/provider-ui"))
PORT = int(os.environ.get("PORT", "8765"))


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "store": _path(), "dist": str(DIST)})


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_routes(server.PromptServer.instance.routes)

    async def index(_request: web.Request) -> web.FileResponse:
        return web.FileResponse(DIST / "index.html")

    async def favicon(_request: web.Request) -> web.Response:
        return web.Response(status=204)

    app.router.add_get("/favicon.ico", favicon)

    if (DIST / "index.html").is_file():
        app.router.add_get("/", index)
        app.router.add_static("/assets", DIST / "assets")
    return app


if __name__ == "__main__":
    print(f"STORE {_path()}", flush=True)
    print(f"DIST {DIST}", flush=True)
    web.run_app(make_app(), host="127.0.0.1", port=PORT)
