import json
import os
from urllib.parse import parse_qs, urlparse

import folder_paths
from aiohttp import web
from server import PromptServer

routes = PromptServer.instance.routes


def app_path(*parts: str) -> str:
    return os.path.join(folder_paths.get_system_user_directory("comfyart"), *parts)


def request_user(request: web.Request) -> str:
    try:
        return PromptServer.instance.user_manager.get_request_user_id(request)
    except KeyError as e:
        raise web.HTTPForbidden(text=json.dumps({"error": str(e)}), content_type="application/json")


def error(message: str, status: int) -> web.Response:
    return web.json_response({"error": message}, status=status)


def bad_request(message: str) -> web.HTTPBadRequest:
    return web.HTTPBadRequest(text=json.dumps({"error": message}), content_type="application/json")


async def json_body(request: web.Request) -> dict:
    try:
        body = await request.json()
    except ValueError:
        raise bad_request("invalid JSON body")
    if not isinstance(body, dict):
        raise bad_request("body must be an object")
    return body


def read_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path: str, data, mode: int | None = None) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    if mode is not None:  # create the temp file with the final mode, so it is never readable by others
        if os.path.exists(tmp):
            os.remove(tmp)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        os.chmod(tmp, mode)
        handle = os.fdopen(fd, "w", encoding="utf-8")
    else:
        handle = open(tmp, "w", encoding="utf-8")
    with handle as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def view_path(url: str) -> str:
    query = parse_qs(urlparse(url).query)
    name = (query.get("filename") or [""])[0]
    subfolder = (query.get("subfolder") or [""])[0]
    root = folder_paths.get_directory_by_type((query.get("type") or ["output"])[0])
    if not name or root is None:
        raise ValueError(f"not a ComfyUI file URL: {url}")
    root = os.path.abspath(root)
    path = os.path.abspath(os.path.join(root, subfolder, name))
    if os.path.commonpath([root, path]) != root or not os.path.isfile(path):
        raise ValueError(f"file not found: {url}")
    return path
