import asyncio
import uuid

from aiohttp import web
from server import PromptServer

from ._common import json_body, routes

COMMAND_EVENT = "comfyart-mcp-command"
DEFAULT_TIMEOUT_S = 20.0

_pending: dict[str, asyncio.Future] = {}
_pages: dict[str, str] = {}


def _open_pages() -> dict[str, str]:
    live = PromptServer.instance.sockets
    for client in [c for c in _pages if c not in live]:
        del _pages[client]
    return _pages


def _target(project: str) -> tuple[str, str]:
    pages = _open_pages()
    if project:
        clients = [c for c, p in pages.items() if p == project]
        if not clients:
            raise ValueError(f"project {project} is not open in any browser tab — open it in ComfyArt and retry")
        return clients[-1], project
    projects = list(dict.fromkeys(pages.values()))
    if not projects:
        raise ValueError("no ComfyArt project is open in a browser tab — open one and retry")
    if len(projects) > 1:
        raise ValueError(f"several ComfyArt projects are open ({', '.join(projects)}); connect with ?project=<id> to pick one")
    return _target(projects[0])


def require_project_tab(project: str) -> str:
    """Read the live tab table. Does not register a page, open a socket, or start a session.

    Missing, mismatched, stale, and disconnected tabs all fail through ``_target``
    with the same actionable error the tool would raise later.
    """
    _client, resolved = _target(project)
    return resolved


def mandatory_browser_stop(text: str) -> str:
    """Return *text* when the live-tab prerequisite failed, else ``""``.

    Only the prerequisite failures raised by ``_target`` and a tab that closed
    during the command. A page timeout or any other tool error stays recoverable.
    """
    if "is not open in any browser tab" in text or "no ComfyArt project is open in a browser tab" in text:
        return text
    if "several ComfyArt projects are open" in text:
        return text
    if "the ComfyArt tab of project " in text and " closed before " in text:
        return text
    return ""


async def submit_command(action: str, payload: dict, project: str,
                         timeout: float = DEFAULT_TIMEOUT_S, chat: str = "") -> dict:
    client, project = _target(project)
    command_id = uuid.uuid4().hex
    future: asyncio.Future = asyncio.get_running_loop().create_future()
    _pending[command_id] = future
    try:
        PromptServer.instance.send_sync(COMMAND_EVENT, {"id": command_id, "action": action, "project": project, "chat": chat, "args": payload}, client)
        return await asyncio.wait_for(future, timeout)
    except asyncio.TimeoutError:
        if client not in _open_pages():
            raise ValueError(f"the ComfyArt tab of project {project} closed before {action!r} finished")
        raise ValueError(
            f"the ComfyArt page did not finish {action!r} within {timeout:.0f}s; it may still complete — "
            f"check get_canvas before retrying")
    finally:
        _pending.pop(command_id, None)


@routes.post("/comfyart/mcp_page")
async def register_page(request: web.Request) -> web.Response:
    body = await json_body(request)
    client, project = str(body.get("client_id") or ""), str(body.get("project") or "")
    if not client or not project:
        return web.json_response({"error": "client_id and project are required"}, status=400)
    _pages.pop(client, None)
    _pages[client] = project
    return web.json_response({"ok": True})


@routes.post("/comfyart/mcp_command_result")
async def post_command_result(request: web.Request) -> web.Response:
    body = await json_body(request)
    future = _pending.get(str(body.get("command_id") or ""))
    if future is None or future.done():
        return web.json_response({"ok": False, "reason": "unknown or expired command"})
    if body.get("ok"):
        result = body.get("result")
        future.set_result(result if isinstance(result, dict) else {"result": result})
    else:
        future.set_exception(ValueError(str(body.get("error") or "command failed in the ComfyArt page")))
    return web.json_response({"ok": True})
