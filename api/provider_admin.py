"""Admin provider settings for image jobs and the LLM.

Nothing here runs unless an admin has saved that section. Unsaved, or saved as
the existing WaveSpeed route, the current image and LLM code paths are used
unchanged. A save affects only new tasks. Jobs already started keep the provider
they locked. Secrets stay in environment variables and are never stored or returned.

Deployment:
  COMFYART_ADMIN_USERS   comma-separated ComfyUI user ids (default: default)
  REPLICATE_API_TOKEN    Replicate, server only. Absence shows 未配置 and blocks paid calls.
  DEEPSEEK_API_KEY       Official DeepSeek, server only. Same rule.
  WAVESPEED_API_KEY      existing WaveSpeed key. This page does not collect it.
Do not put tokens in settings.json, this file, logs, or screenshots.
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import time

from aiohttp import web

from ._common import app_path, error, json_body, read_json, request_user, routes, write_json
from .provider_catalog import (
    IMAGE_CAPS,
    audit_summary,
    image_model,
    image_provider,
    llm_model,
    llm_provider,
    model_supports,
    public_image_providers,
    public_llm_providers,
)
from .replicate_image import PayloadError, prediction_body, prediction_url

log = logging.getLogger("comfyart.provider_admin")

FILE = "media_provider.json"
TICKET_TTL = 600
_llm_lock: contextvars.ContextVar = contextvars.ContextVar("comfyart_llm_lock", default=None)
_tickets: dict[str, dict] = {}
_image_orig = None
_estimate_orig = None
_quote_orig = None
_poll_orig = None
_llm_http = None
_llm_orig_send = None
_replicate_jobs: dict[str, dict] = {}
_quote_override = None  # tests only: async (model, capability, inputs) -> (price, source)


def reset_runtime() -> None:
    """Drop in-memory route tickets. Does not touch the saved file or a turn already running."""
    _tickets.clear()
    _replicate_jobs.clear()


def _path() -> str:
    return app_path(FILE)


def _empty_section() -> dict:
    return {"revision": 0, "active": None, "previous": None}


def _section(value) -> dict:
    if not isinstance(value, dict):
        return _empty_section()
    try:
        revision = int(value.get("revision") or 0)
    except (TypeError, ValueError):
        revision = 0
    active = value.get("active") if isinstance(value.get("active"), dict) else None
    previous = value.get("previous") if isinstance(value.get("previous"), dict) else None
    return {"revision": max(0, revision), "active": active, "previous": previous}


def load_doc() -> dict:
    raw = read_json(_path(), {})
    if not isinstance(raw, dict):
        raw = {}
    return {"image": _section(raw.get("image")), "llm": _section(raw.get("llm"))}


def _write(doc: dict) -> None:
    write_json(_path(), doc, mode=0o600)


def admin_ids() -> set[str]:
    raw = os.environ.get("COMFYART_ADMIN_USERS", "default")
    return {part.strip() for part in raw.split(",") if part.strip()}


def require_admin(request: web.Request) -> str:
    user = request_user(request)
    if user not in admin_ids():
        raise web.HTTPForbidden(
            text=json.dumps({"error": "admin only"}),
            content_type="application/json",
        )
    return user


def _env_configured(name: str) -> bool:
    return bool(name and os.environ.get(name, "").strip())


def _wavespeed_configured() -> bool:
    from .wavespeed import key_source
    return bool(key_source()[0])


def _configured_map() -> tuple[dict[str, bool], dict[str, bool]]:
    image = {
        "wavespeed": _wavespeed_configured(),
        "replicate": _env_configured("REPLICATE_API_TOKEN"),
    }
    llm = {
        "wavespeed": True,
        "deepseek": _env_configured("DEEPSEEK_API_KEY"),
    }
    return image, llm


def _reject_secrets(body: dict) -> web.Response | None:
    blocked = {"token", "api_key", "apikey", "key", "secret", "authorization", "password"}
    found = [k for k in body if str(k).lower() in blocked or str(k).upper().endswith("_KEY") or str(k).upper().endswith("_TOKEN")]
    if found:
        return error("secrets are not accepted here; set them in the server environment", 400)
    return None


def _valid_image(active: dict | None) -> dict | None:
    if not active:
        return None
    provider_id = str(active.get("provider") or "")
    provider = image_provider(provider_id)
    if not provider:
        return None
    if provider["mode"] == "existing":
        return {"provider": "wavespeed"}
    models = active.get("models") if isinstance(active.get("models"), dict) else None
    if not models:
        return None
    cleaned = {}
    for cap in IMAGE_CAPS:
        model_id = str(models.get(cap) or "")
        model = image_model(provider_id, model_id)
        if not model or model.get("adapter") not in ("replicate_gpt_image_26",) or not model_supports(model, cap):
            return None
        cleaned[cap] = model_id
    return {"provider": provider_id, "models": cleaned}


def _valid_llm(active: dict | None) -> dict | None:
    if not active:
        return None
    provider_id = str(active.get("provider") or "")
    model_id = str(active.get("model") or "")
    model = llm_model(provider_id, model_id)
    if not model or model.get("adapter") not in ("existing", "deepseek_official"):
        return None
    if model.get("passthrough"):
        return {"provider": "wavespeed", "model": "existing"}
    if not model.get("request_model") or not (llm_provider(provider_id) or {}).get("base_url"):
        return None
    return {"provider": provider_id, "model": model_id}


def active_image() -> dict | None:
    return _valid_llm_safe(load_doc()["image"]["active"], _valid_image)


def active_llm() -> dict | None:
    return _valid_llm_safe(load_doc()["llm"]["active"], _valid_llm)


def _valid_llm_safe(active, checker):
    try:
        return checker(active)
    except Exception:
        log.warning("ignoring unreadable provider config")
        return None


def image_revision() -> int:
    return int(load_doc()["image"]["revision"])


def llm_model_override() -> str | None:
    """Model id for a new turn. None keeps the existing settings model."""
    active = active_llm()
    if not active or active.get("model") == "existing" or active.get("provider") == "wavespeed":
        return None
    model = llm_model(active["provider"], active["model"])
    if not model or model.get("passthrough"):
        return None
    return str(model.get("request_model") or "") or None


def llm_route(active: dict | None = None) -> dict | None:
    """Resolved official route, or None when the existing LLM path must be left alone."""
    active = active_llm() if active is None else _valid_llm(active)
    if not active or active.get("provider") == "wavespeed":
        return None
    provider = llm_provider(active["provider"])
    model = llm_model(active["provider"], active["model"])
    if not provider or not model or model.get("passthrough"):
        return None
    return {
        "provider": provider["id"],
        "model": model["request_model"],
        "catalog_model": model["id"],
        "base_url": str(provider.get("base_url") or "").rstrip("/"),
        "secret_env": provider.get("secret_env") or "",
        "adapter": model.get("adapter") or "",
        "passthrough": False,
        "quote": model.get("quote") or "unknown",
    }


def adapt_llm_body(body: dict | None, url: str) -> dict | None:
    """Official DeepSeek defaults thinking on. The agent does not echo reasoning_content, so disable it.

    Streaming stays off: the agent reads one JSON body. This is not a drop-in conversion.
    """
    lock = _llm_lock.get()
    if not lock or lock.get("passthrough") or not isinstance(body, dict):
        return body
    if not str(url).rstrip("/").endswith("/chat/completions"):
        return body
    adapted = dict(body)
    adapted.setdefault("thinking", {"type": "disabled"})
    if adapted.get("stream") is True:
        adapted["stream"] = False
    return adapted


def _public_state() -> dict:
    doc = load_doc()
    image_on, llm_on = _configured_map()
    image_active = _valid_image(doc["image"]["active"])
    llm_active = _valid_llm(doc["llm"]["active"])
    return {
        "admin": True,
        "image": {
            "saved": image_active is not None,
            "revision": doc["image"]["revision"],
            "active": image_active,
            "ignored": doc["image"]["active"] is not None and image_active is None,
            "can_restore": doc["image"]["previous"] is not None or image_active is not None,
            "providers": public_image_providers(image_on),
        },
        "llm": {
            "saved": llm_active is not None and not (llm_active.get("provider") == "wavespeed" and llm_active.get("model") == "existing" and doc["llm"]["revision"] == 0),
            "revision": doc["llm"]["revision"],
            "active": llm_active,
            "ignored": doc["llm"]["active"] is not None and llm_active is None,
            "can_restore": doc["llm"]["previous"] is not None or (llm_active is not None and doc["llm"]["revision"] > 0),
            "providers": public_llm_providers(llm_on),
            "probe": "off",
        },
        "audit": {
            "summary": {
                "checked_at": audit_summary()["checked_at"],
                "model_counts": audit_summary()["model_counts"],
                "models_listed": audit_summary()["models_listed"],
                "capabilities": audit_summary()["capabilities"],
            },
            "note": {
                "zh": "审计不是路由。未实现的工具保持 WaveSpeed，设置里不能选。",
                "en": "The audit is not a route. Tools that are not implemented stay on WaveSpeed and cannot be selected.",
            },
        },
    }


def _save_section(name: str, active: dict | None) -> dict:
    doc = load_doc()
    section = doc[name]
    section["previous"] = section["active"]
    section["active"] = active
    section["revision"] = int(section["revision"]) + 1
    doc[name] = section
    _write(doc)
    return _public_state()


def _restore_section(name: str) -> dict:
    doc = load_doc()
    section = doc[name]
    current = section["active"]
    section["active"] = section["previous"]
    section["previous"] = current
    section["revision"] = int(section["revision"]) + 1
    doc[name] = section
    _write(doc)
    return _public_state()


def _issues_image(body: dict) -> list[str]:
    provider_id = str(body.get("provider") or "")
    provider = image_provider(provider_id)
    if not provider:
        return ["unknown image provider"]
    if provider["mode"] == "existing":
        return []
    models = body.get("models") if isinstance(body.get("models"), dict) else {}
    issues = []
    for cap in IMAGE_CAPS:
        cap_info = (provider.get("capabilities") or {}).get(cap) or {}
        if cap_info.get("supported") is False:
            issues.append(f"{cap} is not supported on {provider_id}")
            continue
        model = image_model(provider_id, str(models.get(cap) or ""))
        if not model:
            issues.append(f"{cap} needs a catalog model")
        elif not model_supports(model, cap):
            issues.append(f"{model['id']} does not support {cap}")
        elif model.get("adapter") != "replicate_gpt_image_26":
            issues.append(f"{model['id']} has no implemented adapter")
    return issues


def _issues_llm(body: dict) -> list[str]:
    model = llm_model(str(body.get("provider") or ""), str(body.get("model") or ""))
    if not model:
        return ["unknown llm provider or model"]
    if model.get("adapter") not in ("existing", "deepseek_official"):
        return ["that model has no implemented adapter"]
    return []


@routes.get("/comfyart/provider-admin")
async def get_provider_admin(request: web.Request) -> web.Response:
    require_admin(request)
    return web.json_response(_public_state())


@routes.put("/comfyart/provider-admin/image")
async def put_image_provider(request: web.Request) -> web.Response:
    require_admin(request)
    body = await json_body(request)
    blocked = _reject_secrets(body)
    if blocked:
        return blocked
    issues = _issues_image(body)
    if issues:
        return web.json_response({"error": "invalid image provider", "issues": issues}, status=400)
    active = {"provider": "wavespeed"} if body.get("provider") == "wavespeed" else {
        "provider": body["provider"],
        "models": {cap: str(body["models"][cap]) for cap in IMAGE_CAPS},
    }
    state = _save_section("image", active)
    log.info("image provider saved provider=%s revision=%s", active["provider"], state["image"]["revision"])
    return web.json_response(state)


@routes.post("/comfyart/provider-admin/image/restore")
async def restore_image_provider(request: web.Request) -> web.Response:
    require_admin(request)
    state = _restore_section("image")
    log.info("image provider restored revision=%s", state["image"]["revision"])
    return web.json_response(state)


@routes.put("/comfyart/provider-admin/llm")
async def put_llm_provider(request: web.Request) -> web.Response:
    require_admin(request)
    body = await json_body(request)
    blocked = _reject_secrets(body)
    if blocked:
        return blocked
    issues = _issues_llm(body)
    if issues:
        return web.json_response({"error": "invalid llm provider", "issues": issues}, status=400)
    active = {"provider": str(body["provider"]), "model": str(body["model"])}
    state = _save_section("llm", active)
    log.info("llm provider saved provider=%s model=%s revision=%s", active["provider"], active["model"], state["llm"]["revision"])
    return web.json_response(state)


@routes.post("/comfyart/provider-admin/llm/restore")
async def restore_llm_provider(request: web.Request) -> web.Response:
    require_admin(request)
    state = _restore_section("llm")
    log.info("llm provider restored revision=%s", state["llm"]["revision"])
    return web.json_response(state)


def _refs(inputs: dict) -> list:
    images = inputs.get("images") if isinstance(inputs.get("images"), list) else []
    refs = inputs.get("refs") if isinstance(inputs.get("refs"), list) else []
    return [v for v in [inputs.get("image"), inputs.get("base"), *images, *refs] if v]


def capability_of(inputs: dict) -> str | None:
    """Image capabilities this settings page is allowed to move. Everything else stays put."""
    if not isinstance(inputs, dict) or inputs.get("custom") or isinstance(inputs.get("scenes"), list):
        return None
    if inputs.get("paste") is not None or inputs.get("feature") in {"move_object", "mockup_surface"}:
        return None
    raw = str(inputs.get("feature") or "")
    if raw and raw not in {"text_to_image", "image_edit", "generate_image", "edit_image"}:
        return None
    from .wavespeed import feature_of
    mapped = feature_of(raw) or raw
    if mapped not in {"text_to_image", "image_edit"}:
        return None
    fmt = ""
    params = inputs.get("params") if isinstance(inputs.get("params"), dict) else {}
    fmt = str(params.get("output_format") or inputs.get("output_format") or "").lower()
    if fmt == "svg":
        return None
    from . import gif_image
    gif = gif_image.requests_gif(inputs)
    refs = _refs(inputs)
    if gif and refs:
        return "reference_gif"
    if gif:
        return "text_to_gif"
    if refs:
        return "image_edit"
    return "text_to_image"


def _fingerprint(inputs: dict) -> str:
    params = inputs.get("params") if isinstance(inputs.get("params"), dict) else {}
    payload = {
        "feature": str(inputs.get("feature") or ""),
        "fmt": str(params.get("output_format") or inputs.get("output_format") or "").lower(),
        "has_image": bool(_refs(inputs)),
        "model": str(inputs.get("model") or ""),
        "w": inputs.get("width"),
        "h": inputs.get("height"),
        "frames": params.get("frame_count", inputs.get("frame_count")),
        "ms": params.get("frame_duration_ms", inputs.get("frame_duration_ms")),
        "prompt": str(inputs.get("prompt") or ""),
    }
    return json.dumps(payload, sort_keys=True, default=str)


def decide_image(inputs: dict) -> dict:
    active = active_image()
    if not active or active.get("provider") == "wavespeed":
        return {"passthrough": True, "revision": image_revision()}
    cap = capability_of(inputs)
    if not cap:
        return {"passthrough": True, "revision": image_revision()}
    model_id = str((active.get("models") or {}).get(cap) or "")
    model = image_model("replicate", model_id)
    if not model or not model_supports(model, cap):
        return {"passthrough": False, "unsupported": True, "capability": cap, "revision": image_revision(),
                "provider": "replicate", "model": model_id}
    return {
        "passthrough": False,
        "unsupported": False,
        "provider": "replicate",
        "model": model_id,
        "capability": cap,
        "revision": image_revision(),
        "quote": "unknown",
    }


def _remember(inputs: dict, decision: dict) -> None:
    _tickets[_fingerprint(inputs)] = {**decision, "at": time.time(), "fp": _fingerprint(inputs)}


def _route_changed(inputs: dict, decision: dict) -> bool:
    ticket = _tickets.get(_fingerprint(inputs))
    if not ticket or time.time() - float(ticket.get("at") or 0) > TICKET_TTL:
        return False
    if int(ticket.get("revision") or 0) == int(decision.get("revision") or 0):
        return False
    return not (ticket.get("passthrough") and decision.get("passthrough"))


async def _quote_status(decision: dict, inputs: dict):
    if _quote_override is not None:
        return await _quote_override(decision.get("model"), decision.get("capability"), inputs)
    return None, "unknown"


def _estimate_body(decision: dict) -> dict:
    from .wavespeed import confirm_usd
    return {
        "price": None,
        "currency": "USD",
        "source": "none",
        "confirm_usd": confirm_usd(),
        "confirm": False,
        "quote_status": "unknown",
        "provider": decision.get("provider"),
        "model": decision.get("model"),
        "capability": decision.get("capability"),
        "blocked": True,
    }


async def _replicate_execute(decision: dict, inputs: dict) -> str:
    from .wavespeed import WaveSpeedError
    if decision.get("unsupported"):
        raise WaveSpeedError("这个能力没有已实现的 Replicate 路由，未发送请求", 400, kind="unsupported")
    if not _env_configured("REPLICATE_API_TOKEN"):
        raise WaveSpeedError("Replicate 未配置 REPLICATE_API_TOKEN，未发送请求", 400, kind="provider_unconfigured")
    price, source = await _quote_status(decision, inputs)
    if source != "quote" or not isinstance(price, (int, float)) or isinstance(price, bool):
        raise WaveSpeedError("价格未知，已停止。不会按静图价确认，也未向供应商发送请求", 400, kind="quote_unknown")
    try:
        body = prediction_body(decision["capability"], inputs)
    except PayloadError as e:
        raise WaveSpeedError(str(e), 400, kind="unsupported") from e
    if decision["capability"] == "reference_gif" and not (body.get("input") or {}).get("input_images"):
        raise WaveSpeedError("参考图 GIF 缺少 input_images，未发送", 400, kind="unsupported")
    url = prediction_url(decision["model"])
    token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    try:
        prediction_id = await _post_prediction(url, body, token)
    except TimeoutError as e:
        from . import gen_ledger
        gen_ledger.record_failure(None, "replicate", decision["model"], "submit timeout", kind="unknown", feature=decision["capability"])
        raise WaveSpeedError("Replicate 提交超时，状态未知，没有改走其他供应商", 504, kind="unknown") from e
    except WaveSpeedError:
        raise
    from . import gen_ledger
    gen_ledger.record_submit(prediction_id, "replicate", decision["model"], decision["capability"], float(price))
    _replicate_jobs[prediction_id] = {
        "provider": "replicate", "model": decision["model"], "capability": decision["capability"],
        "revision": decision["revision"], "started": time.time(),
    }
    log.info("replicate task %s submitted model=%s capability=%s", prediction_id, decision["model"], decision["capability"])
    return prediction_id


async def _post_prediction(url: str, body: dict, token: str) -> str:
    import aiohttp
    from .wavespeed import WaveSpeedError
    timeout = aiohttp.ClientTimeout(total=60)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=body, headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }) as res:
                text = await res.text()
                if res.status == 429:
                    raise WaveSpeedError("Replicate 限流，请稍后再试。没有自动改走其他供应商", 429, kind="rate_limit")
                if res.status >= 400:
                    log.warning("replicate prediction failed status=%s", res.status)
                    raise WaveSpeedError(f"Replicate 拒绝了请求 (HTTP {res.status})，没有改走其他供应商", res.status, kind="failed")
                try:
                    data = json.loads(text) if text else {}
                except ValueError:
                    data = {}
    except WaveSpeedError:
        raise
    except TimeoutError:
        raise
    except Exception as e:
        log.warning("replicate prediction transport %s", type(e).__name__)
        raise WaveSpeedError("Replicate 提交失败，状态未知，没有改走其他供应商", 502, kind="unknown") from e
    prediction_id = str((data or {}).get("id") or "")
    if not prediction_id:
        raise WaveSpeedError("Replicate 没有返回任务 id，没有重试", 502, kind="unknown")
    return prediction_id


def install() -> None:
    global _image_orig, _estimate_orig, _quote_orig, _poll_orig, _llm_http, _llm_orig_send
    if getattr(install, "done", False):
        return
    from . import wavespeed
    from ..bot.providers import TurnResult, get_provider
    _image_orig = wavespeed.submit
    _estimate_orig = wavespeed.estimate
    _quote_orig = wavespeed.quote
    _poll_orig = wavespeed.poll

    async def submit(inputs):
        decision = decide_image(inputs if isinstance(inputs, dict) else {})
        if isinstance(inputs, dict) and _route_changed(inputs, decision):
            from .wavespeed import WaveSpeedError
            raise WaveSpeedError("供应商配置在估价之后变了，请重新估价。未发送请求", 409, kind="route_changed")
        if decision.get("passthrough"):
            return await _image_orig(inputs)
        return await _replicate_execute(decision, inputs)

    async def estimate(inputs):
        decision = decide_image(inputs if isinstance(inputs, dict) else {})
        if isinstance(inputs, dict):
            _remember(inputs, decision)
        if decision.get("passthrough"):
            return await _estimate_orig(inputs)
        if decision.get("unsupported"):
            from .wavespeed import WaveSpeedError
            raise WaveSpeedError("这个能力没有已实现的 Replicate 路由", 400, kind="unsupported")
        return _estimate_body(decision)

    async def quote(model, inputs):
        decision = decide_image(inputs if isinstance(inputs, dict) else {})
        if isinstance(inputs, dict):
            _remember(inputs, decision)
        if decision.get("passthrough"):
            return await _quote_orig(model, inputs)
        return None, "unknown"

    async def poll(task):
        job = _replicate_jobs.get(task)
        if not job:
            return await _poll_orig(task)
        return await _poll_replicate(task, job)

    wavespeed.submit = submit
    wavespeed.estimate = estimate
    wavespeed.quote = quote
    wavespeed.poll = poll

    provider = get_provider("local-llm")
    if provider is not None:
        _llm_http = provider._request_json
        _llm_orig_send = provider.send

        async def _request_json(session, method, url, *, headers, json_body=None, timeout=120):
            body = adapt_llm_body(json_body, url)
            return await _llm_http(session, method, url, headers=headers, json_body=body, timeout=timeout)

        async def send(turn, emit, handle):
            route = llm_route()
            if route is None:
                return await _llm_orig_send(turn, emit, handle)
            if not _env_configured(route["secret_env"]):
                return TurnResult(error="DeepSeek 官方未配置 DEEPSEEK_API_KEY，未发送请求 / Official DeepSeek has no DEEPSEEK_API_KEY, so nothing was sent.")
            from dataclasses import replace
            locked_turn = replace(turn, model=route["model"])
            token = _llm_lock.set(route)
            try:
                return await _llm_orig_send(locked_turn, emit, handle)
            finally:
                _llm_lock.reset(token)

        def _base_url():
            lock = _llm_lock.get()
            if lock and not lock.get("passthrough"):
                return lock["base_url"]
            return provider._saved_base_url()

        def _api_headers():
            lock = _llm_lock.get()
            if lock and not lock.get("passthrough"):
                key = os.environ.get(lock["secret_env"], "").strip()
                headers = {"Content-Type": "application/json"}
                if key:
                    headers["Authorization"] = f"Bearer {key}"
                return headers
            return provider._saved_headers()

        provider._saved_base_url = provider._base_url_source
        provider._saved_headers = provider._api_headers
        provider._base_url_source = _base_url
        provider._api_headers = _api_headers
        provider._request_json = _request_json
        provider.send = send
    install.done = True


async def _fetch_prediction(task: str, token: str) -> str:
    import aiohttp
    url = f"https://api.replicate.com/v1/predictions/{task}"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        async with session.get(url, headers={"Authorization": f"Bearer {token}"}) as res:
            data = await res.json(content_type=None)
            return str((data or {}).get("status") or "")


async def _poll_replicate(task: str, job: dict) -> dict:
    """One status read for a prediction already created. Never submits again."""
    from .wavespeed import WaveSpeedError, _history
    token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not token:
        return _history(task, "failed", [["execution_error", {"exception_message": "Replicate token missing; not resubmitted"}]], {})
    try:
        status = await _fetch_prediction(task, token)
    except (TimeoutError, OSError) as e:
        log.warning("replicate poll %s %s; not resubmitted", task, type(e).__name__)
        raise WaveSpeedError("Replicate 查询超时或失败，状态未知，没有重新提交", 504, kind="unknown") from e
    except Exception as e:
        log.warning("replicate poll %s %s; not resubmitted", task, type(e).__name__)
        raise WaveSpeedError("Replicate 查询超时或失败，状态未知，没有重新提交", 504, kind="unknown") from e
    if status == "succeeded":
        return _history(task, "completed", [], {})
    if status in {"failed", "canceled"}:
        return _history(task, "failed", [["execution_error", {"exception_message": "Replicate task failed; not resubmitted"}]], {})
    return _history(task, "processing", [], {})
