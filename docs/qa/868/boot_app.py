#!/usr/bin/env python3
"""Boot a $0 local ComfyArt app (stubbed host + mock WaveSpeed catalog) for #868 shots."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import types
from pathlib import Path


def _make_module(name: str, **attrs) -> types.ModuleType:
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


def install_stubs(base: Path) -> None:
    state = {"base": base}

    def _annotated_filepath(name: str) -> str:
        kind = "input"
        for t in ("input", "output", "temp"):
            if name.endswith(f" [{t}]"):
                name, kind = name[: -len(t) - 3], t
        return str(state["base"] / kind / name)

    def _save_image_path(prefix: str, root: str):
        subfolder, _, name = prefix.rpartition("/")
        folder = os.path.join(root, subfolder)
        os.makedirs(folder, exist_ok=True)
        return folder, name, 1, subfolder, prefix

    def user_dir() -> str:
        return str(state["base"] / "user")

    _make_module(
        "folder_paths",
        STATE=state,
        SYSTEM_USER_PREFIX="__",
        get_user_directory=user_dir,
        get_system_user_directory=lambda name="system": os.path.join(user_dir(), f"__{name}"),
        get_public_user_directory=lambda user: None if user.startswith("__") else os.path.join(user_dir(), user),
        get_input_directory=lambda: str(state["base"] / "input"),
        get_output_directory=lambda: str(state["base"] / "output"),
        get_temp_directory=lambda: str(state["base"] / "temp"),
        get_annotated_filepath=_annotated_filepath,
        get_save_image_path=_save_image_path,
        get_directory_by_type=lambda t: str(state["base"] / t) if t in ("input", "output", "temp") else None,
        get_filename_list=lambda kind: [],
        get_full_path_or_raise=lambda kind, name: name,
        folder_names_and_paths={},
    )
    comfy = _make_module("comfy")
    comfy.ops = _make_module("comfy.ops", manual_cast=object)
    comfy.sd = _make_module("comfy.sd", load_diffusion_model=lambda *a, **k: None)
    comfy.utils = _make_module("comfy.utils", ProgressBar=lambda total: types.SimpleNamespace(update=lambda n: None))
    comfy.model_management = _make_module(
        "comfy.model_management", throw_exception_if_processing_interrupted=lambda: None
    )
    comfy.cli_args = _make_module(
        "comfy.cli_args", args=types.SimpleNamespace(tls_keyfile=None, tls_certfile=None)
    )

    from aiohttp import web

    class _UserManager:
        users = {"default", "alice"}

        def get_request_user_id(self, request):
            user = request.headers.get("comfy-user", "default")
            if user not in self.users:
                raise KeyError("Unknown user: " + user)
            return user

        def get_request_user_filepath(self, request, file, create_dir=True):
            root = os.path.join(user_dir(), self.get_request_user_id(request))
            path = os.path.abspath(os.path.join(root, file))
            return path if os.path.commonpath((root, path)) == root else None

    class _Queue:
        def get_tasks_remaining(self):
            return 0

    class _PromptServer:
        instance = None

    ps = _PromptServer()
    ps.routes = web.RouteTableDef()
    ps.address = "127.0.0.1"
    ps.port = 8188
    ps.user_manager = _UserManager()
    ps.prompt_queue = _Queue()
    ps.sockets = {}
    ps.send_sync = lambda event, data, sid=None: None
    _PromptServer.instance = ps
    _make_module("server", PromptServer=_PromptServer)


def bind_comfyart(root: Path) -> None:
    """Load this checkout as ComfyArt even when the folder is not named ComfyArt."""
    import importlib.util

    parent = str(root.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    for k in [k for k in sys.modules if k == "ComfyArt" or k.startswith("ComfyArt.")]:
        sys.modules.pop(k, None)
    spec = importlib.util.spec_from_file_location(
        "ComfyArt", root / "__init__.py", submodule_search_locations=[str(root)]
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import ComfyArt from {root}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ComfyArt"] = mod
    spec.loader.exec_module(mod)


async def start(root: Path, port: int) -> None:
    from aiohttp import web

    base = Path(tempfile.mkdtemp(prefix="ca868-"))
    for d in ("input", "output", "temp", "user/default"):
        (base / d).mkdir(parents=True, exist_ok=True)
    install_stubs(base)

    os.environ["COMFYART_SKIP_KEY_CHECK"] = "1"
    os.environ.pop("WAVESPEED_API_KEY", None)
    os.environ.pop("KIE_API_KEY", None)

    # Mock WaveSpeed first so we can point the app at it before importing routes that might read env later.
    fixture_path = root / "tests/fixtures/wavespeed_catalog_subset.json"
    catalog = json.loads(fixture_path.read_text()) if fixture_path.is_file() else {}
    models = list(catalog.values()) if isinstance(catalog, dict) else []

    mock_app = web.Application(client_max_size=50 * 2**20)

    async def ws_models(_r):
        return web.json_response({"code": 200, "data": models})

    async def ws_price(r):
        b = await r.json()
        return web.json_response(
            {"code": 200, "data": {"model_id": b.get("model_id"), "price": 0.01, "unit_price": 0.01, "currency": "USD"}}
        )

    async def ws_upload(_r):
        return web.json_response({"code": 200, "data": {"download_url": "http://127.0.0.1/cdn/up.png"}})

    async def ws_ok(_r):
        return web.json_response({"code": 200, "data": {"id": "task0", "status": "created"}})

    mock_app.router.add_get("/api/v3/models", ws_models)
    mock_app.router.add_post("/api/v3/model/price", ws_price)
    mock_app.router.add_post("/api/v3/media/upload/binary", ws_upload)
    mock_app.router.add_post("/api/v3/{model:.+}", ws_ok)
    mock_runner = web.AppRunner(mock_app)
    await mock_runner.setup()
    mock_site = web.TCPSite(mock_runner, "127.0.0.1", 0)
    await mock_site.start()
    mock_port = mock_site._server.sockets[0].getsockname()[1]
    os.environ["WAVESPEED_BASE_URL"] = f"http://127.0.0.1:{mock_port}"
    os.environ["WAVESPEED_API_KEY"] = "mock-not-a-real-key"

    bind_comfyart(root)
    from server import PromptServer

    app = web.Application(client_max_size=200 * 2**20)
    app.router.add_routes(PromptServer.instance.routes)
    for rd in PromptServer.instance.routes:
        if isinstance(rd, web.RouteDef):
            app.router.add_route(rd.method, "/api" + rd.path, rd.handler)

    def ud(r):
        return base / "user/default" / r.match_info["file"]

    async def ud_get(r):
        return web.FileResponse(ud(r)) if ud(r).is_file() else web.Response(status=404)

    async def ud_post(r):
        ud(r).parent.mkdir(parents=True, exist_ok=True)
        ud(r).write_bytes(await r.read())
        return web.json_response(r.match_info["file"])

    async def view(r):
        q = r.query
        p = base / q.get("type", "output") / q.get("subfolder", "") / q["filename"]
        return web.FileResponse(p) if p.is_file() else web.Response(status=404)

    async def upload_image(r):
        form = await r.post()
        f, sub, kind = form["image"], form.get("subfolder", ""), form.get("type", "input")
        (base / kind / sub).mkdir(parents=True, exist_ok=True)
        (base / kind / sub / f.filename).write_bytes(f.file.read())
        return web.json_response({"name": f.filename, "subfolder": sub, "type": kind})

    async def wsock(r):
        s = web.WebSocketResponse()
        await s.prepare(r)
        async for _ in s:
            pass
        return s

    def js(v):
        async def h(_r):
            return web.json_response(v)
        return h

    for path, h in (
        ("/api/userdata", js([])),
        ("/api/models/{k}", js([])),
        ("/api/settings/{id}", js(None)),
        ("/api/queue", js({"queue_running": [], "queue_pending": []})),
        ("/api/view", view),
        ("/api/userdata/{file:.+}", ud_get),
        ("/ws", wsock),
    ):
        app.router.add_get(path, h)
    for path, h in (
        ("/api/settings/{id}", js({})),
        ("/api/queue", js({})),
        ("/api/interrupt", js({})),
        ("/api/userdata/{file:.+}", ud_post),
        ("/api/upload/image", upload_image),
    ):
        app.router.add_post(path, h)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    print(f"READY http://127.0.0.1:{port}/comfyart/", flush=True)
    while True:
        await asyncio.sleep(3600)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--port", type=int, required=True)
    args = p.parse_args()
    root = Path(args.root).resolve()
    if not (root / "dist" / "index.html").is_file():
        raise SystemExit(f"no dist in {root}: run npm run build first")
    asyncio.run(start(root, args.port))


if __name__ == "__main__":
    main()
