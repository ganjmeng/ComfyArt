"""#381: the one memory store. Every memory read/write goes through these two routes.

The read-modify-write is closed on the server: a write carries the `rev` it was based on, and the check + write run under
a per-user asyncio lock, so a stale write (another tab, the agent's proactive learning) gets 409 and the client re-reads
and re-applies its edit.

Storage is ONE file, `<user>/comfyart/memory-store.json` = {memory, log, meta, rev, ops}, written atomically
(random-suffix temp file → fsync → os.replace → fsync dir). memory, log, meta and rev therefore always change together;
a crash mid-write leaves the previous state intact. If the file does not exist yet, the pre-#381 files
(`memory.json`, `memory-log.json`, `memory-meta.json`) are read once as the starting state (left untouched, no migration).

`op_id` is the client's idempotency key: a write retried after a network error (the first one may have landed) is
recognised from the last `op_ids_kept` ids and answered with the current state instead of being applied twice.

Records carry `owner_id` + `workspace_id` with fixed local defaults (api/memory_policy.json). No tenancy or auth today:
nothing filters on them; they are stamped so a later per-user / per-project split needs no data migration."""
import asyncio
import json
import os
import secrets

from aiohttp import web
from server import PromptServer

from ._common import error, json_body, read_json, routes

# shared with the client (src/memoryStore.ts imports the same JSON): defaults, retry counts, log/op caps
POLICY = read_json(os.path.join(os.path.dirname(__file__), "memory_policy.json"), {})
OWNER_DEFAULT = POLICY.get("owner_default", "local")  # owner_id (= user_id); single local user
WORKSPACE_DEFAULT = POLICY.get("workspace_default", "local")  # workspace_id (= project_id); one local workspace
OPS_KEPT = int(POLICY.get("op_ids_kept", 50))
STORE = "comfyart/memory-store.json"
LEGACY = {"memory": "comfyart/memory.json", "log": "comfyart/memory-log.json", "meta": "comfyart/memory-meta.json"}
META_SCHEMA = {"demoCleanup381": bool}  # every meta key the client may write today, with its type
# TODO(#381): this lock is per process. It is correct for one ComfyUI server; a multi-instance deployment must replace
# it with a DB row lease / compare-and-swap on `rev` (the rev check itself already makes the protocol safe to move).
_LOCKS: dict[str, asyncio.Lock] = {}


def _paths(request: web.Request) -> dict[str, str]:
    try:
        um = PromptServer.instance.user_manager
        paths = {k: um.get_request_user_filepath(request, f, create_dir=True) for k, f in {"store": STORE, **LEGACY}.items()}
    except KeyError:
        raise web.HTTPForbidden()
    if None in paths.values():
        raise web.HTTPForbidden()
    return paths


def stamp(record: dict) -> dict:
    return {**record, "owner_id": record.get("owner_id") or OWNER_DEFAULT, "workspace_id": record.get("workspace_id") or WORKSPACE_DEFAULT}


def _load(paths: dict[str, str]) -> dict:
    """Full on-disk state (incl. ops). Lists are always lists: a missing store is a real 0 memories."""
    raw = read_json(paths["store"], None)
    if not isinstance(raw, dict):  # not written yet → start from the legacy files (if any)
        meta = read_json(paths["meta"], None)
        meta = meta if isinstance(meta, dict) else {}
        raw = {"memory": read_json(paths["memory"], []), "log": read_json(paths["log"], []), "meta": meta,
               "rev": meta.get("rev", 0), "ops": []}
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    meta = {k: v for k, v in meta.items() if k != "rev"}
    return {"memory": [stamp(m) for m in raw.get("memory") or [] if isinstance(m, dict)] if isinstance(raw.get("memory"), list) else [],
            "log": raw["log"] if isinstance(raw.get("log"), list) else [], "meta": meta,
            "rev": raw["rev"] if isinstance(raw.get("rev"), int) else 0,
            "ops": [o for o in raw.get("ops") or [] if isinstance(o, str)] if isinstance(raw.get("ops"), list) else []}


def _public(state: dict) -> dict:
    return {k: state[k] for k in ("memory", "log", "meta", "rev")}


def atomic_write_json(path: str, data) -> None:
    """temp file with a random suffix in the same dir → fsync → os.replace → fsync dir. Readers see old or new, never half."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    tmp = f"{path}.{secrets.token_hex(6)}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    try:  # make the rename itself durable (POSIX); not available on Windows
        fd = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def _meta_error(meta: dict) -> str | None:
    for k, v in meta.items():
        if k == "rev":
            continue  # older clients echo rev back; the server owns it and ignores this
        if k not in META_SCHEMA:
            return f"unknown meta key: {k}"
        if not isinstance(v, META_SCHEMA[k]):
            return f"meta.{k} must be {META_SCHEMA[k].__name__}"
    return None


def lock_for(key: str) -> asyncio.Lock:
    return _LOCKS.setdefault(key, asyncio.Lock())


@routes.get("/comfyart/memory")
async def read_memory(request: web.Request) -> web.Response:
    paths = _paths(request)
    async with lock_for(paths["store"]):
        return web.json_response(_public(await asyncio.to_thread(_load, paths)))


@routes.post("/comfyart/memory")
async def write_memory(request: web.Request) -> web.Response:
    body = await json_body(request)
    memory, log, meta, base, op = body.get("memory"), body.get("log"), body.get("meta") or {}, body.get("base_rev"), body.get("op_id")
    if not isinstance(memory, list) or not isinstance(log, list) or not isinstance(meta, dict) or not isinstance(base, int):
        return error("memory, log (lists), meta (object) and base_rev (int) are required", 400)
    if op is not None and (not isinstance(op, str) or not 0 < len(op) <= 100):
        return error("op_id must be a short string", 400)
    if (bad := _meta_error(meta)) is not None:
        return error(bad, 400)
    paths = _paths(request)
    async with lock_for(paths["store"]):
        current = await asyncio.to_thread(_load, paths)  # file I/O off the event loop; the lock spans read+check+write
        if op and op in current["ops"]:  # retry of a write that already landed: do not apply it twice
            return web.json_response({**_public(current), "replayed": True})
        if current["rev"] != base:
            return web.json_response({"error": "stale memory write", "state": _public(current)}, status=409)
        nxt = {"memory": [stamp(m) for m in memory if isinstance(m, dict)], "log": log,
               "meta": {k: v for k, v in meta.items() if k != "rev"}, "rev": base + 1,
               "ops": ([*current["ops"], op] if op else current["ops"])[-OPS_KEPT:]}
        await asyncio.to_thread(atomic_write_json, paths["store"], nxt)
        return web.json_response(_public(nxt))
