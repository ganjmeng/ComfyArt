from aiohttp import web

from ..bot import get_provider, list_providers
from ..bot.providers import ProviderStatus
from . import bot_asks, chat_store
from . import bot_send as send_core
from ._common import error, json_body, request_user, routes
from .bot_turns import ACTIVE_TURNS, QUEUED, broadcast
from .settings import bot_disabled, bot_enabled, get_setting, mcp_enabled

EXTERNAL_NEEDS_MCP = "external agents need MCP: turn on MCP in Agent settings"


@routes.get("/comfyart/bot/status")
async def bot_status(request: web.Request) -> web.Response:
    user = request_user(request)
    if not bot_enabled():
        return web.json_response({"enabled": False, "user": user, "providers": []})
    refresh = request.rel_url.query.get("refresh") == "1"
    out = []
    for provider in list_providers():
        if refresh:
            provider.clear_probe_cache()
        try:
            st = await provider.probe()
        except Exception as e:
            st = ProviderStatus(available=False, detail=f"probe failed: {e}")
        caps = provider.capabilities()
        entry = {
            "id": provider.id,
            "label": provider.label,
            "available": st.available,
            "version": st.version,
            "logged_in": st.logged_in,
            "detail": st.detail,
            "stateful": caps.stateful,
            "attachments": caps.attachments,
            "branch": provider.supports_branch,
            "models": await provider.list_models(),
        }
        options = provider.model_options()
        if options:
            entry["model_options"] = options
        out.append(entry)
    return web.json_response({"enabled": True, "user": user, "providers": out})


def _owned_chat(request: web.Request) -> dict:
    chat = chat_store.get_chat(request.match_info["cid"])
    if chat is None or chat["user"] != request_user(request):
        raise web.HTTPNotFound(text='{"error": "chat not found"}', content_type="application/json")
    return chat


@routes.get("/comfyart/bot/chats")
async def bot_list_chats(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chats = chat_store.list_chats(request_user(request), request.query.get("project", ""),
                                  include_archived=request.query.get("archived") == "1")
    for c in chats:
        c["busy"] = c["id"] in ACTIVE_TURNS
    return web.json_response({"chats": chats})


@routes.post("/comfyart/bot/chats")
async def bot_create_chat(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    body = await json_body(request)
    provider_id = str(body.get("provider") or "")
    if get_provider(provider_id) is None:
        return error(f"unknown provider {provider_id!r}", 400)
    project = str(body.get("project") or "")
    if not project:
        return error("project required", 400)
    run_mode = body.get("run_mode") or "auto"
    if run_mode not in ("auto", "ask"):
        return error("run_mode must be 'auto' or 'ask'", 400)
    chat = chat_store.create_chat(user=request_user(request), project=project, provider=provider_id,
                                  title=str(body.get("title") or ""), run_mode=run_mode)
    broadcast("chat_created", {"chat": chat})
    return web.json_response({"chat": chat})


@routes.get("/comfyart/bot/chats/{cid}")
async def bot_get_chat(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    messages = chat_store.list_messages(chat["id"])
    state = ACTIVE_TURNS.get(chat["id"])
    if state is not None:
        for m in messages:
            if m["id"] == state.message_id:
                m["blocks"] = state.blocks
    chat["busy"] = state is not None
    return web.json_response({"chat": chat, "messages": messages})


@routes.patch("/comfyart/bot/chats/{cid}")
async def bot_update_chat(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    body = await json_body(request)
    run_mode = body.get("run_mode")
    if run_mode is not None and run_mode not in ("auto", "ask"):
        return error("run_mode must be 'auto' or 'ask'", 400)
    title = body.get("title")
    updated = chat_store.update_chat(
        chat["id"],
        title=str(title) if title is not None else None,
        run_mode=run_mode,
        pinned=bool(body["pinned"]) if "pinned" in body else None,
        archived=bool(body["archived"]) if "archived" in body else None,
    )
    broadcast("chat_updated", {"chat": updated})
    return web.json_response({"chat": updated})


@routes.delete("/comfyart/bot/chats/{cid}")
async def bot_delete_chat(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    await remove_chat(_owned_chat(request))
    return web.json_response({"ok": True})


async def remove_chat(chat: dict) -> None:
    QUEUED.pop(chat["id"], None)
    state = ACTIVE_TURNS.get(chat["id"])
    if state is not None:
        await get_provider(chat["provider"]).stop(state.handle)
    chat_store.delete_chat(chat["id"])
    broadcast("chat_deleted", {"chat_id": chat["id"]})


@routes.post("/comfyart/bot/chats/{cid}/send")
async def bot_send(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    body = await json_body(request)
    text = str(body.get("text") or "").strip()
    try:
        refs = send_core.parse_refs(body.get("refs"))
        kits = send_core.parse_kits(body.get("kits"))
        docs = send_core.parse_docs(body.get("docs"))
    except ValueError as e:
        return error(str(e), 400)
    if not text and not refs and not docs:
        return error("text, refs or docs required", 400)
    provider = get_provider(chat["provider"])
    # #219: external tools reach the canvas through the external MCP endpoint, which stays closed while the switch is off
    if provider is not None and chat["provider"] != "local-llm" and not mcp_enabled():
        return error(EXTERNAL_NEEDS_MCP, 403)
    if provider is None:
        return error(f"unknown provider {chat['provider']!r}", 400)
    can_see = provider.capabilities().attachments
    if (send_core.visual_refs(refs) or any(k["images"] for k in kits)) and not can_see:
        return error(f"{provider.label} cannot take images; pick another agent or remove the references", 400)
    skill_name = str(body.get("skill") or "").strip()
    try:
        attachments, lines = await send_core.prepare_attachments(refs, kits, docs, page_images=can_see)
    except ValueError as e:
        return error(str(e), 400)
    display_blocks = [{"type": r["kind"], "url": r["src"], "shape": r["id"]} for r in refs]
    display_blocks += [{"type": "file", "url": d["src"], "name": d["name"]} for d in docs]
    display_blocks += [{"type": "kit", "name": k["name"]} for k in kits]
    if skill_name:
        display_blocks.append({"type": "skill", "name": skill_name})
    if text:
        display_blocks.append({"type": "text", "text": text})
    context = str(body.get("context") or "").strip()
    # #364: Review default ON — flag steers Done post-image 审图思考 in AGENT_GUIDE
    review_on = get_setting("bot-enable-review") is not False
    provider_text = send_core.compose_provider_text(
        text, skill_name=skill_name, memory=str(body.get("memory") or ""),
        lines=[*lines, *([context] if context else [])], review=review_on)
    lang = str(body.get("lang") or "")
    user_msg, assistant_msg = send_core.queue_or_begin(
        chat, text=text, provider_text=provider_text,
        attachments=attachments, display_blocks=display_blocks,
        lang=lang if lang in ("zh", "en") else "")
    if assistant_msg is None:
        return web.json_response({"queued": True, "user_message": user_msg})
    return web.json_response({"user_message": user_msg, "assistant_message": assistant_msg})


@routes.post("/comfyart/bot/chats/{cid}/log")
async def bot_log(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    body = await json_body(request)
    blocks = body.get("blocks")
    if not isinstance(blocks, list):
        return error("blocks must be a list", 400)
    text = str(body.get("text") or "").strip()
    user_msg = chat_store.create_message(chat_id=chat["id"], role="user", blocks=[{"type": "text", "text": text}])
    assistant_msg = chat_store.create_message(chat_id=chat["id"], role="assistant", blocks=blocks, parent_id=user_msg["id"])
    if not chat["title"]:
        broadcast("chat_updated", {"chat": chat_store.update_chat(chat["id"], title=" ".join(text.split())[:48])})
    broadcast("messages_logged", {"chat_id": chat["id"], "messages": [user_msg, assistant_msg]})
    return web.json_response({"messages": [user_msg, assistant_msg]})


@routes.patch("/comfyart/bot/chats/{cid}/messages/{mid}")
async def bot_patch_message(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    body = await json_body(request)
    if not isinstance(body.get("blocks"), list):
        return error("blocks must be a list", 400)
    state = ACTIVE_TURNS.get(chat["id"])
    if state is not None and state.message_id == request.match_info["mid"]:
        return error("message is streaming", 409)
    message = chat_store.update_message(chat["id"], request.match_info["mid"], blocks=body["blocks"])
    if message is None:
        return error("message not found", 404)
    return web.json_response({"message": message})


@routes.post("/comfyart/bot/chats/{cid}/stop")
async def bot_stop(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    state = ACTIVE_TURNS.get(chat["id"])
    if state is None:
        return error("no active turn", 409)
    bot_asks.cancel_chat_asks(chat["id"])
    await get_provider(chat["provider"]).stop(state.handle)
    return web.json_response({"ok": True})


@routes.post("/comfyart/bot/chats/{cid}/branch")
async def bot_branch_chat(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    body = await json_body(request)
    message_id = str(body.get("message_id") or "")
    if not message_id:
        return error("message_id required", 400)
    provider = get_provider(chat["provider"])
    if not provider.supports_branch:
        return error(f"{provider.label} sessions cannot be forked, so this chat cannot be branched. Start a new chat instead.", 400)
    branch = chat_store.branch_chat(chat["id"], message_id)
    if branch is None:
        return error("message not found", 404)
    broadcast("chat_created", {"chat": branch})
    return web.json_response({"chat": branch, "messages": chat_store.list_messages(branch["id"])})


@routes.post("/comfyart/bot/chats/{cid}/asks/{aid}/answer")
async def bot_answer_ask(request: web.Request) -> web.Response:
    if not bot_enabled():
        return bot_disabled()
    chat = _owned_chat(request)
    body = await json_body(request)
    raw_selected = body.get("selected")
    if raw_selected is None:
        selected: list[str] = []
    elif isinstance(raw_selected, list):
        selected = [str(s) for s in raw_selected]
    else:
        return error("selected must be a list", 400)
    other_text = str(body.get("other_text") or "")
    ask = bot_asks.PENDING.get(request.match_info["aid"])
    if ask is None or ask.chat_id != chat["id"]:
        return error("ask not found or already resolved", 409)
    raw_answers = body.get("answers")
    answers = None
    if raw_answers is not None:
        if not isinstance(raw_answers, dict):
            return error("answers must be an object", 400)
        answers = {}
        for qid, ans in raw_answers.items():
            if not isinstance(ans, dict):
                return error(f"answers[{qid}] must be an object", 400)
            entry = {"selected": [str(s) for s in (ans.get("selected") or [])]}
            oth = str(ans.get("other_text") or "")
            if oth:
                entry["other_text"] = oth
            answers[str(qid)] = entry
        qs = ask.spec.get("questions") or []
        # Flatten single-question answers onto selected/other_text for legacy.
        if len(qs) == 1 and qs[0]["id"] in answers and not selected and not other_text:
            flat = answers[qs[0]["id"]]
            selected = list(flat.get("selected") or [])
            other_text = str(flat.get("other_text") or "")
    try:
        bot_asks.validate_answer(ask.spec, selected, other_text, answers)
    except ValueError as e:
        return error(str(e), 422)
    if bot_asks.resolve_ask(ask.id, "answered", selected, other_text or None, answers) is None:
        return error("ask not found or already resolved", 409)
    return web.json_response({"ok": True}, status=202)



@routes.post("/comfyart/bot/local-llm/test")
async def bot_test_local_llm(request: web.Request) -> web.Response:
    """#321: test Local LLM URL / key / model from the settings draft (no chat turn)."""
    import os

    from ..bot.local_llm import _API_KEY_ENV, test_local_llm
    from .llm_key import is_wavespeed_url, llm_api_key
    from .settings import MASK, get_setting

    body = await json_body(request)
    url = str(body["url"] if "url" in body else get_setting("bot-local-llm-url") or "").strip()
    model = str(body["model"] if "model" in body else get_setting("bot-model-local-llm") or "").strip()
    raw_key = body.get("key")
    env = os.environ.get(_API_KEY_ENV, "")
    if env:
        key = env
    elif raw_key is not None and raw_key != MASK:
        key = str(raw_key).strip()
        if not key and is_wavespeed_url(url):
            key = llm_api_key(url)
    else:
        key = llm_api_key(url)
    result = await test_local_llm(base_url=url, api_key=key, model=model)
    return web.json_response(result)



def reap_stale_messages() -> None:
    chat_store.abort_unfinished()


# #391: continue a paused run from its server-side checkpoint. The DB lease makes it idempotent:
# of two concurrent "Continue" presses exactly one starts a turn, the other gets 409.
_CONTINUE_TEXT = {"zh": "继续", "en": "Continue"}


def request_owner_id(request: web.Request) -> str:
    """Who is asking. The local build has one owner ("local"); a hosted build resolves it from its
    auth layer here. Kept as the single place so /continue never hard-codes the owner."""
    from ..bot.run_budget import LOCAL_OWNER_ID
    return str(request.get("comfyart_owner_id") or LOCAL_OWNER_ID)


@routes.post("/comfyart/bot/runs/{rid}/continue")
async def bot_run_continue(request: web.Request) -> web.Response:
    import uuid

    from ..bot.run_budget import resolve_policy
    from .bot_turns import begin_turn
    from .providers import ensure_run_store, user_policy_layer

    if not bot_enabled():
        return bot_disabled()
    body = await json_body(request)
    lang = str(body.get("lang") or "")
    lang = lang if lang in ("zh", "en") else "zh"
    store = ensure_run_store()
    run = store.get_run(request.match_info["rid"], owner_id=request_owner_id(request))
    if run is None:
        return error("run not found", 404)
    if run["status"] != "paused":
        return error(f"run is {run['status']}, not paused", 409)
    chat = chat_store.get_chat(run["chat_id"])
    if chat is None:
        return error("chat not found", 404)
    if chat["id"] in ACTIVE_TURNS:
        return error("this chat is busy", 409)
    lease_owner = f"lease-{uuid.uuid4().hex}"
    ttl = resolve_policy(user=user_policy_layer())["lease_s"]
    if not store.acquire_lease(run["id"], lease_owner, ttl):
        return error("this run is already being continued", 409)
    user_msg = chat_store.create_message(chat_id=chat["id"], role="user",
                                         blocks=[{"type": "text", "text": _CONTINUE_TEXT[lang]}])
    assistant_msg = begin_turn(chat, text="", provider_text="", attachments=[], user_msg=user_msg,
                               lang=lang, resume_run_id=run["id"], lease_owner=lease_owner)
    return web.json_response({"run_id": run["id"], "user_message": user_msg, "assistant_message": assistant_msg})
