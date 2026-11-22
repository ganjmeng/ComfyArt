import asyncio
import os

from aiohttp import web

from ..bot import BotEvent, TurnHandle, TurnRequest, get_provider, list_providers
from ._common import error, json_body, request_user, routes
from .bot_media import ATTACH_MAX_COUNT, MEDIA_ERRORS, ImageUnreadable, PlannerPixelOverflow, render_attachment
from .bot_turns import provider_model
from .settings import bot_disabled, bot_enabled, get_setting

# Ledger id for a one-shot call that is not inside a saved open project.
# It is not "local" and not empty, so canvas projects do not share it.
# A client cannot choose it: a claimed id is used only when it is a stored
# project whose tab is open.
OUTSIDE_PROJECT_PREFIX = "oneshot-outside:"


async def default_provider():
    saved = get_provider(str(get_setting("bot-provider")))
    if saved is not None and (await saved.probe()).available:
        return saved
    for provider in list_providers():
        if (await provider.probe()).available:
            return provider
    return None


def outside_project_id(user: str) -> str:
    return OUTSIDE_PROJECT_PREFIX + str(user or "")


def _stored_project(user: str, project_id: str) -> bool:
    if not project_id or project_id == "local" or project_id.startswith(OUTSIDE_PROJECT_PREFIX):
        return False
    from .project_store import get_snapshot
    return get_snapshot(user, project_id) is not None


def _tab_open(project_id: str) -> bool:
    from .mcp_commands import require_project_tab
    try:
        require_project_tab(project_id)
    except ValueError:
        return False
    return True


def resolve_oneshot_project(user: str, claimed: object) -> tuple[str, str]:
    """Return ``(project_id, "")`` or ``("", block_code)``.

    A claimed id is accepted only when that project is saved for this user
    and open in a live tab. Anything else is refused, not booked as a new
    bucket and not folded into ``local`` or ``""``. With no claim, the only
    verified open project is used; several verified projects are refused;
    none uses the per-user outside-project bucket.
    """
    claim = claimed.strip() if isinstance(claimed, str) else ""
    if claim:
        if _stored_project(user, claim) and _tab_open(claim):
            return claim, ""
        return "", "project_unverified"

    from .mcp_commands import _open_pages
    verified: list[str] = []
    for project_id in dict.fromkeys(_open_pages().values()):
        if _stored_project(user, str(project_id)) and _tab_open(str(project_id)):
            verified.append(str(project_id))
    if len(verified) == 1:
        return verified[0], ""
    if len(verified) > 1:
        return "", "project_unverified"
    outside = outside_project_id(user)
    from .project_store import get_snapshot
    # A saved project must not share this bucket. The prefix is refused as a
    # claim, so the only safe response here is to block.
    if get_snapshot(user, outside) is not None:
        return "", "project_unverified"
    return outside, ""


def _notice_response(code: str, lang: str, status: int = 400) -> web.Response:
    from ..bot.llm_usd_gate import user_notice
    return error(user_notice(code, lang), status)


def _is_user_notice(message: str) -> bool:
    from ..bot.llm_usd_gate import user_notice
    for code in ("image_too_large", "unbounded_multimodal", "unreadable", "over_budget", "project_unverified"):
        if message == user_notice(code, "zh") or message == user_notice(code, "en"):
            return True
    return False


def _notice_lang(body: dict) -> str:
    lang = str(body.get("lang") or "")
    return lang if lang in ("zh", "en") else "zh"


@routes.post("/comfyart/bot/complete")
async def bot_complete(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    body = await json_body(request)
    text = str(body.get("text") or "").strip()
    system = str(body.get("system") or "").strip()
    images = body.get("images") or []
    if not text or not isinstance(images, list):
        return error("text and an images list are required", 400)
    provider = await default_provider()
    if provider is None:
        return error("no agent is available; set one up in Agent settings", 400)
    if images and not provider.capabilities().attachments:
        return error(f"{provider.label} cannot read images; pick another default agent in Agent settings", 400)
    notice_lang = _notice_lang(body)
    try:
        attachments = [await asyncio.to_thread(render_attachment, str(u)) for u in images[:ATTACH_MAX_COUNT]]
    except PlannerPixelOverflow:
        return _notice_response("image_too_large", notice_lang)
    except ImageUnreadable:
        return _notice_response("unreadable", notice_lang)
    except MEDIA_ERRORS as e:
        return error(str(e), 400)
    from .provider_admin import llm_route
    project_id = "local"
    if provider.id == "local-llm" and llm_route() is not None:
        # The installed send path binds "local" when the turn has no canvas
        # project. That bucket is shared, so an official one-shot without a
        # verified open project is refused before send.
        project_id, block = resolve_oneshot_project(request_user(request), body.get("project"))
        if block or project_id.startswith(OUTSIDE_PROJECT_PREFIX):
            return _notice_response(block or "project_unverified", notice_lang)
    parts: list[str] = []

    async def emit(ev: BotEvent) -> None:
        if ev.t == "delta":
            parts.append(ev.text)

    result = await provider.send(TurnRequest(
        chat_id="complete",
        user_text=f"{system}\n\n{text}" if system else text,
        attachments=attachments,
        model=provider_model(provider.id),
        project_id=project_id,
        lang=notice_lang,
    ), emit, TurnHandle())
    if result.error:
        if _is_user_notice(result.error):
            return error(result.error, 400)
        return error(f"{provider.label}: {result.error}", 502)
    return web.json_response({"text": "".join(parts), "provider": provider.id})


async def _completion_transport(session, method, url, *, headers, json_body=None, timeout=120):
    """The physical POST. HTTP errors keep the body so a verified usage can settle."""
    import aiohttp

    from ..bot.llm_input_envelope import FrozenJsonBody
    from ..bot.local_llm import LlmHttpError

    frozen = isinstance(json_body, FrozenJsonBody)
    payload = {"data": json_body.encoded} if frozen else {"json": json_body}
    limit = timeout if isinstance(timeout, aiohttp.ClientTimeout) else aiohttp.ClientTimeout(total=timeout)
    async with session.request(
        method, url, headers=headers, timeout=limit, **payload,
    ) as res:
        text = await res.text()
        if res.status >= 400:
            raise LlmHttpError(res.status, text)
        import json
        return json.loads(text) if text else {}


@routes.post("/comfyart/llm/complete")
async def llm_complete(request: web.Request) -> web.Response:
    """One-shot completion for kit, memory, and reference calls.

    Official DeepSeek goes through ``gated_llm_http`` and the durable ledger.
    A settings passthrough endpoint is unchanged: the same function forwards
    it, and this route does not add a switch that skips the gate.
    """
    import aiohttp

    from ..bot.local_llm import _user_content
    from ..bot.llm_usd_gate import LlmBudgetBlocked, bind_llm_project, reset_llm_project
    from .llm_key import llm_api_key
    from .provider_admin import _env_configured, gated_llm_http, llm_route

    body = await json_body(request)
    text = str(body.get("text") or "").strip()
    system = str(body.get("system") or "").strip()
    images = body.get("images") or []
    if not text or not isinstance(images, list):
        return error("text and an images list are required", 400)
    route = llm_route()
    base = str(get_setting("bot-local-llm-url") or "").strip().rstrip("/")
    if route is None and not base:
        return error("no LLM endpoint configured; set the OpenAI-compatible endpoint URL in Agent settings", 400)
    notice_lang = _notice_lang(body)
    try:
        attachments = [await asyncio.to_thread(render_attachment, str(u)) for u in images[:ATTACH_MAX_COUNT]]
    except PlannerPixelOverflow:
        return _notice_response("image_too_large", notice_lang)
    except ImageUnreadable:
        return _notice_response("unreadable", notice_lang)
    except MEDIA_ERRORS as e:
        return error(str(e), 400)
    project_id = ""
    if route is not None:
        project_id, block = resolve_oneshot_project(request_user(request), body.get("project"))
        if block:
            return _notice_response(block, notice_lang)
        if not _env_configured(str(route.get("secret_env") or "")):
            return _notice_response("project_unverified", notice_lang)
        base = str(route.get("base_url") or "").rstrip("/")
        model = str(route.get("model") or "")
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(str(route.get("secret_env") or ""), "").strip()
        if key:
            headers["Authorization"] = f"Bearer {key}"
    else:
        headers = {"Content-Type": "application/json"}
        if key := llm_api_key(base):
            headers["Authorization"] = f"Bearer {key}"
        model = ""
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": _user_content(text, attachments)},
    ]
    from ..bot.local_llm import LlmHttpError
    lock = None
    project_token = None
    try:
        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=300)) as session:
            if route is None:
                model = provider_model("local-llm")
                if not model:
                    async with session.get(f"{base}/models") as res:
                        data = await res.json(content_type=None) if res.status < 400 else {}
                    model = next((str(m.get("id")) for m in (data or {}).get("data") or [] if m.get("id")), "")
            from . import provider_admin
            if route is not None:
                lock = provider_admin._llm_lock.set(route)
                project_token = bind_llm_project(project_id)
            reply = await gated_llm_http(
                session, "POST", f"{base}/chat/completions",
                headers=headers,
                json_body={"model": model, "messages": messages, "stream": False},
                timeout=300,
                transport=_completion_transport,
            )
    except LlmBudgetBlocked as exc:
        return _notice_response(exc.code, notice_lang)
    except LlmHttpError as exc:
        return error(f"LLM endpoint: HTTP {exc.status}", 502)
    except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
        return error(f"LLM endpoint unreachable: {exc}", 502)
    finally:
        if project_token is not None:
            reset_llm_project(project_token)
        if lock is not None:
            from . import provider_admin
            provider_admin._llm_lock.reset(lock)
    content = (((reply or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return web.json_response({"text": content if isinstance(content, str) else str(content), "model": model})
