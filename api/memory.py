"""#381: the one memory store. Every memory read/write goes through these two routes.

The read-modify-write is closed on the server: a write carries the `rev` it was based on, and the check + write run under
a per-user asyncio lock, so a stale write (another tab, the agent's proactive learning) gets 409 and the client re-reads
and re-applies its edit. Files stay where they were (`<user>/comfyart/memory*.json`), so no migration.

Records carry `owner_id` + `workspace_id` with fixed local defaults. No tenancy or auth today: nothing filters on them;
they are stamped so a later per-user / per-project split needs no data migration."""
import asyncio

from aiohttp import web
from server import PromptServer

from ._common import error, json_body, read_json, routes, write_json

OWNER_DEFAULT = "local"  # owner_id (= user_id); single local user
WORKSPACE_DEFAULT = "local"  # workspace_id (= project_id); memory is account-level, so one local workspace
FILES = {"memory": "comfyart/memory.json", "log": "comfyart/memory-log.json", "meta": "comfyart/memory-meta.json"}
_LOCKS: dict[str, asyncio.Lock] = {}


def _paths(request: web.Request) -> dict[str, str]:
    try:
        um = PromptServer.instance.user_manager
        paths = {k: um.get_request_user_filepath(request, f, create_dir=True) for k, f in FILES.items()}
    except KeyError:
        raise web.HTTPForbidden()
    if None in paths.values():
        raise web.HTTPForbidden()
    return paths


def stamp(record: dict) -> dict:
    return {**record, "owner_id": record.get("owner_id") or OWNER_DEFAULT, "workspace_id": record.get("workspace_id") or WORKSPACE_DEFAULT}


def _state(paths: dict[str, str]) -> dict:
    memory, log, meta = (read_json(paths[k], None) for k in ("memory", "log", "meta"))
    rev = meta.get("rev", 0) if isinstance(meta, dict) and isinstance(meta.get("rev"), int) else 0
    # null = never written: the client may then fall back to its local copy (home / mock); [] is a real "0 memories"
    return {"memory": [stamp(m) for m in memory if isinstance(m, dict)] if isinstance(memory, list) else None,
            "log": log if isinstance(log, list) else None, "meta": meta if isinstance(meta, dict) else None, "rev": rev}


def lock_for(key: str) -> asyncio.Lock:
    return _LOCKS.setdefault(key, asyncio.Lock())


@routes.get("/comfyart/memory")
async def read_memory(request: web.Request) -> web.Response:
    paths = _paths(request)
    async with lock_for(paths["memory"]):  # reads take the lock too: memory + rev are never read half-written
        return web.json_response(await asyncio.to_thread(_state, paths))


@routes.post("/comfyart/memory")
async def write_memory(request: web.Request) -> web.Response:
    body = await json_body(request)
    memory, log, meta, base = body.get("memory"), body.get("log"), body.get("meta") or {}, body.get("base_rev")
    if not isinstance(memory, list) or not isinstance(log, list) or not isinstance(meta, dict) or not isinstance(base, int):
        return error("memory, log (lists), meta (object) and base_rev (int) are required", 400)
    paths = _paths(request)
    async with lock_for(paths["memory"]):
        current = await asyncio.to_thread(_state, paths)  # file I/O off the event loop; the lock spans read+check+write
        if current["rev"] != base:
            return web.json_response({"error": "stale memory write", "state": current}, status=409)
        await asyncio.to_thread(_write, paths, memory, log, {**meta, "rev": base + 1})
        return web.json_response(await asyncio.to_thread(_state, paths))


def _write(paths: dict[str, str], memory: list, log: list, meta: dict) -> None:
    write_json(paths["memory"], [stamp(m) for m in memory if isinstance(m, dict)])
    write_json(paths["log"], log)
    write_json(paths["meta"], meta)  # last: rev only advances once the data is on disk
