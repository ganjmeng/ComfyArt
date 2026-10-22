"""WaveSpeed cloud provider: runs ComfyArt generation on api.wavespeed.ai instead of local ComfyUI models.

The frontend queues a pseudo graph {"ws": {"class_type": "WaveSpeedRun", "inputs": {...}}}; this module
submits it to WaveSpeed, polls the result, downloads outputs into ComfyUI's output folder and answers in
ComfyUI /history shape so the existing job flow is unchanged. The API key only comes from the
WAVESPEED_API_KEY environment variable and is never logged or sent to the browser.
"""

import asyncio
import io
import json
import logging
import math
import mimetypes
import os
import re
import threading
import time
import urllib.request
import uuid

import aiohttp
import folder_paths
from aiohttp import web

from ._common import error, json_body, routes

log = logging.getLogger("comfyart.wavespeed")

DEFAULT_BASE = "https://api.wavespeed.ai"


def _base() -> str:
    return (os.environ.get("WAVESPEED_BASE_URL") or DEFAULT_BASE).rstrip("/")


CONFIG = os.path.join(os.path.dirname(__file__), "wavespeed_models.json")
CATALOG_TTL = 24 * 3600
POLL_MIN = 2.0
JOB_TIMEOUT = float(os.environ.get("WAVESPEED_JOB_TIMEOUT") or 30 * 60)
ANNOTATED = re.compile(r"^(.+) \[(input|output|temp)\]$")
SUBFOLDER = "wavespeed"

_catalog: dict = {"at": 0.0, "models": {}}
_jobs: dict[str, dict] = {}
_uploaded: dict[tuple[str, int, int], str] = {}


class WaveSpeedError(Exception):
    def __init__(self, message: str, status: int = 502, confirm: float | None = None):
        super().__init__(message)
        self.status = status
        self.confirm = confirm


def _key() -> str:
    key = os.environ.get("WAVESPEED_API_KEY", "").strip()
    if not key:
        raise WaveSpeedError("WaveSpeed needs an API key: set WAVESPEED_API_KEY and restart ComfyUI", 400)
    return key


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_key()}"}


def load_config() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def feature_of(tool_or_feature: str) -> str:
    cfg = load_config()
    if tool_or_feature in cfg["features"]:
        return tool_or_feature
    return cfg["tool_features"].get(tool_or_feature, "")


def _status_error(status: int, body) -> WaveSpeedError:
    msg = ""
    if isinstance(body, dict):
        msg = str(body.get("message") or (body.get("data") or {}).get("error") or "")
    if status == 401:
        return WaveSpeedError("WaveSpeed rejected the API key (401): check WAVESPEED_API_KEY", 401)
    if status == 402 or "balance" in msg.lower():
        return WaveSpeedError(f"WaveSpeed account balance is too low ({status}) {msg}".strip(), 402)
    if status == 429:
        return WaveSpeedError("WaveSpeed rate limit reached (429): try again shortly", 429)
    return WaveSpeedError(f"WaveSpeed request failed ({status}) {msg}".strip(), 502 if status >= 500 else status)


async def _json(res: aiohttp.ClientResponse):
    try:
        return await res.json(content_type=None)
    except (ValueError, aiohttp.ContentTypeError):
        return None


async def _fetch_models(session: aiohttp.ClientSession) -> dict:
    async with session.get(f"{_base()}/api/v3/models") as res:
        body = await _json(res)
        if res.status >= 400:
            raise _status_error(res.status, body)
    data = body.get("data") if isinstance(body, dict) else body
    return {m["model_id"]: m for m in data or [] if isinstance(m, dict) and "model_id" in m}


async def catalog(refresh: bool = False) -> dict:
    """WaveSpeed model metadata (price, schema), cached 24h; falls back to the stale cache on failure."""
    if refresh or not _catalog["models"] or time.time() - _catalog["at"] > CATALOG_TTL:
        try:
            async with aiohttp.ClientSession(headers=_headers()) as session:
                _catalog["models"] = await _fetch_models(session)
            _catalog["at"] = time.time()
            _catalog.pop("stale", None)
        except (TimeoutError, aiohttp.ClientError, WaveSpeedError) as e:
            if not _catalog["models"]:
                raise WaveSpeedError(f"could not load the WaveSpeed model list: {e}")
            _catalog["stale"] = True
    return _catalog["models"]


def _schema(meta: dict | None) -> dict:
    try:
        return meta["api_schema"]["api_schemas"][0]["request_schema"] or {}
    except (KeyError, IndexError, TypeError):
        return {}


def _caps(schema: dict) -> dict:
    props = schema.get("properties") or {}
    out = {"inputs": [k for k in props if not k.startswith("enable_")]}
    for k in ("aspect_ratio", "resolution", "duration"):
        if props.get(k, {}).get("enum"):
            out[k + "s"] = props[k]["enum"]
    if "images" in props:
        out["max_images"] = props["images"].get("maxItems")
    return out


async def grouped_models(refresh: bool = False) -> dict:
    """Curated models per feature, enriched with WaveSpeed price/description/capabilities."""
    cfg = load_config()
    try:
        meta = await catalog(refresh)
    except WaveSpeedError:
        meta = {}
    out = {}
    for name, feature in cfg["features"].items():
        models = []
        for entry in feature["models"]:
            m = meta.get(entry["id"]) or {}
            models.append({
                "id": entry["id"],
                "label": m.get("name") or entry["id"].split("/", 1)[-1],
                "price": m.get("base_price"),
                "desc": (m.get("description") or "")[:240],
                "local_equivalent": entry.get("local"),
                "default": entry["id"] == feature["default"],
                **_caps(_schema(m)),
            })
        out[name] = {"default": feature["default"], "types": feature["types"], "available": name not in cfg.get("pending_features", []), "models": models}
    return out


def resolve_model(feature: str, model: str | None) -> str:
    config = load_config()
    cfg = config["features"].get(feature)
    if not cfg or feature in config.get("pending_features", []):
        raise WaveSpeedError(f"{feature or 'this tool'} is not available in cloud mode yet", 400)
    if not model:
        return cfg["default"]
    if model not in [m["id"] for m in cfg["models"]]:
        raise WaveSpeedError(f"unknown model {model!r} for {feature}; pick one from list_models", 400)
    return model


def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _write(path: str, data: bytes) -> None:
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _local_path(value: str) -> str | None:
    m = ANNOTATED.match(value)
    if m:
        root = os.path.abspath(folder_paths.get_directory_by_type(m.group(2)))
        path = os.path.abspath(os.path.join(root, m.group(1)))
        return path if os.path.commonpath([root, path]) == root else None
    if value.startswith(("/api/view?", "/view?")):
        from ._common import view_path
        return view_path(value)
    return None


async def _upload(session: aiohttp.ClientSession, path: str, data: bytes | None = None, name: str | None = None) -> str:
    if data is None:
        stat = os.stat(path)
        cache = (path, stat.st_mtime_ns, stat.st_size)
        if cache in _uploaded:
            return _uploaded[cache]
        data = _read(path)
    else:
        cache = None
    name = name or os.path.basename(path)
    form = aiohttp.FormData()
    form.add_field("file", data, filename=name, content_type=mimetypes.guess_type(name)[0] or "application/octet-stream")
    async with session.post(f"{_base()}/api/v3/media/upload/binary", data=form) as res:
        body = await _json(res)
        if res.status >= 400:
            raise _status_error(res.status, body)
    url = ((body or {}).get("data") or {}).get("download_url")
    if not url:
        raise WaveSpeedError(f"WaveSpeed upload of {name} returned no URL")
    if cache:
        _uploaded[cache] = url
    return url


async def _media(session: aiohttp.ClientSession, value: str) -> str:
    if value.startswith(("http://", "https://", "data:")):
        return value
    path = _local_path(value)
    if not path or not os.path.isfile(path):
        raise WaveSpeedError(f"input file not found: {value}", 400)
    return await _upload(session, path)


def mask_to_white(data: bytes) -> bytes:
    """ComfyArt masks are white with the target area cut out (transparent); WaveSpeed wants white = target on black."""
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGBA")
    alpha = img.getchannel("A")
    out = alpha.point(lambda a: 255 - a).convert("L")
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def _nearest(options: list[str], aspect: float) -> str:
    def ratio(s: str) -> float:
        a, b = s.split(":")
        return float(a) / float(b)
    return min(options, key=lambda o: abs(math.log(ratio(o) / aspect)))


def _resolution(options: list[str], long_side: int) -> str:
    def px(s: str) -> float:
        return float(s.lower().rstrip("kp")) * (1024 if s.lower().endswith("k") else 1)
    fits = [o for o in options if px(o) >= long_side * 0.9]
    return min(fits, key=px) if fits else max(options, key=px)


MEDIA_FIELDS = ("video", "audio", "last_image")
MEDIA_LISTS = ("reference_images", "reference_videos", "reference_audios")


async def _media_fields(session: aiohttp.ClientSession, props: dict, inputs: dict, payload: dict) -> None:
    for k in MEDIA_FIELDS:
        if inputs.get(k) and k in props:
            payload[k] = await _media(session, str(inputs[k]))
    for k in MEDIA_LISTS:
        if inputs.get(k) and k in props:
            urls = [await _media(session, str(v)) for v in inputs[k]]
            limit = props[k].get("maxItems")
            payload[k] = urls[:limit] if limit else urls


def _pick(options: list, value):
    """Exact enum match (case-insensitive), else the numerically nearest option, else the first."""
    for o in options:
        if str(o).lower() == str(value).lower():
            return o
    digits = re.sub(r"[^0-9.]", "", str(value))
    if not digits:
        return options[0]
    try:
        num = float(digits)
        nums = [(abs(float(re.sub(r"[^0-9.]", "", str(o)) or "inf") - num), o) for o in options]
        best = min(nums, key=lambda t: t[0])
        if best[0] != float("inf"):
            return best[1]
    except ValueError:
        pass
    return options[0]


def _av_fields(props: dict, required: set, inputs: dict, payload: dict) -> None:
    """Video/audio knobs: duration, resolution, text, voice, language, lyrics."""
    seconds = inputs.get("duration")
    if seconds:
        if "duration" in props:
            enum = props["duration"].get("enum")
            payload["duration"] = _pick(enum, seconds) if enum else seconds
        elif "music_length_ms" in props:
            payload["music_length_ms"] = int(float(seconds) * 1000)
    if inputs.get("resolution") and props.get("resolution", {}).get("enum"):
        payload["resolution"] = _pick(props["resolution"]["enum"], inputs["resolution"])
    if inputs.get("text") and "text" in props:
        payload["text"] = str(inputs["text"])
    if "lyrics" in props and (inputs.get("lyrics") or "lyrics" in required):
        payload["lyrics"] = str(inputs.get("lyrics") or "[instrumental]")
    voice = inputs.get("voice")
    for k in ("voice", "voice_id"):
        if k in props:
            enum = props[k].get("enum")
            if enum:
                payload[k] = _pick(enum, voice) if voice else enum[0]
            elif voice:
                payload[k] = str(voice)
    lang = props.get("language", {}).get("enum")
    if lang and "text" in payload:
        payload["language"] = "auto" if "auto" in lang else lang[0]


async def build_payload(session: aiohttp.ClientSession, schema: dict, inputs: dict) -> dict:
    """Map ComfyArt's logical inputs onto whatever fields this model's schema accepts."""
    props = schema.get("properties") or {}
    payload: dict = {}
    images = [v for v in ([inputs.get("image")] if inputs.get("image") else []) + list(inputs.get("images") or []) if v]
    if images:
        urls = [await _media(session, v) for v in images]
        if "images" in props:
            limit = props["images"].get("maxItems")
            payload["images"] = urls[:limit] if limit else urls
        elif "image" in props:
            payload["image"] = urls[0]
    if inputs.get("mask") and ("mask_image" in props):
        path = _local_path(inputs["mask"])
        if not path:
            raise WaveSpeedError("mask file not found", 400)
        payload["mask_image"] = await _upload(session, path, mask_to_white(_read(path)), f"mask-{uuid.uuid4().hex[:8]}.png")
    w, h = inputs.get("width"), inputs.get("height")
    if w and h:
        if "size" in props and not props["size"].get("x-hidden"):
            payload["size"] = f"{int(w)}*{int(h)}"
        if props.get("aspect_ratio", {}).get("enum"):
            payload["aspect_ratio"] = _nearest(props["aspect_ratio"]["enum"], w / h)
        if props.get("resolution", {}).get("enum"):
            payload["resolution"] = _resolution(props["resolution"]["enum"], max(int(w), int(h)))
    elif inputs.get("ratio") and props.get("aspect_ratio", {}).get("enum"):
        a, b = str(inputs["ratio"]).split(":")
        payload["aspect_ratio"] = _nearest(props["aspect_ratio"]["enum"], float(a) / float(b))
    await _media_fields(session, props, inputs, payload)
    _av_fields(props, set(schema.get("required") or []), inputs, payload)
    for k, v in (inputs.get("params") or {}).items():
        if k in props and v is not None:
            payload[k] = v
    prompt = str(inputs.get("prompt") or "").strip()
    layers = inputs.get("layers")
    if isinstance(layers, int) and layers > 0:
        if "num_layers" in props:
            payload["num_layers"] = layers
        elif "prompt" in props:
            # models without a layer-count field (seedream) take the user's count in the prompt
            prompt = f"{prompt}{'. ' if prompt else ''}Separate into {layers} layers."
    if prompt and "prompt" not in props and "tags" in props:
        payload["tags"] = prompt  # ACE-Step names its style prompt "tags"
    if prompt and "prompt" in props:
        payload["prompt"] = prompt
    if inputs.get("seed") is not None and "seed" in props:
        payload["seed"] = int(inputs["seed"]) % 2147483647
    if inputs.get("png") and "png" in (props.get("output_format", {}).get("enum") or []):
        payload["output_format"] = "png"
    missing = [k for k in schema.get("required") or [] if k not in payload]
    if missing:
        raise WaveSpeedError(f"this model needs {', '.join(missing)}", 400)
    return payload


_submits: list[float] = []


def limits() -> dict:
    base = {"wavespeed_concurrent": 300, "wavespeed_submits_per_minute": 500, "app_concurrent": 8, "batch_max": 50, "confirm_usd": 0.5}
    return {**base, **(load_config().get("limits") or {})}


def _check_limits() -> None:
    lim = limits()
    active = min(lim["app_concurrent"], lim["wavespeed_concurrent"])
    if _active() >= active:
        raise WaveSpeedError(f"too many cloud jobs running (max {active}); wait for one to finish", 429)
    now = time.time()
    _submits[:] = [t for t in _submits if now - t < 60]
    if len(_submits) >= lim["wavespeed_submits_per_minute"]:
        raise WaveSpeedError("too many cloud submits this minute; try again shortly", 429)


def _active() -> int:
    return sum(1 for j in _jobs.values() if not j.get("done"))


async def submit(inputs: dict) -> str:
    feature = feature_of(str(inputs.get("feature") or ""))
    model = resolve_model(feature, inputs.get("model"))
    _check_limits()
    meta = (await catalog()).get(model)
    price = (meta or {}).get("base_price")
    if isinstance(price, (int, float)) and price >= limits()["confirm_usd"] and not inputs.get("confirmed"):
        # expensive job: the page asks the user and resubmits with confirmed=true
        raise WaveSpeedError(f"{model} costs about ${price} per run; confirm to continue", 409, confirm=float(price))
    async with aiohttp.ClientSession(headers=_headers()) as session:
        payload = await build_payload(session, _schema(meta), inputs)
        _submits.append(time.time())
        # never auto-retry a submit: a retry could be charged twice
        async with session.post(f"{_base()}/api/v3/{model}", json=payload) as res:
            body = await _json(res)
            if res.status >= 400:
                raise _status_error(res.status, body)
    task = ((body or {}).get("data") or {}).get("id")
    if not task:
        raise WaveSpeedError("WaveSpeed did not return a task id")
    _jobs[task] = {"model": model, "feature": feature, "started": time.time(), "next_poll": time.time() + POLL_MIN}
    log.info("WaveSpeed task %s submitted (%s)", task, model)
    return task


def _ext(url: str, default: str) -> str:
    ext = os.path.splitext(url.split("?", 1)[0])[1].lower()
    return ext if 1 < len(ext) <= 5 else default


async def _download(session: aiohttp.ClientSession, task: str, index: int, url: str) -> dict:
    root = os.path.abspath(folder_paths.get_output_directory())
    filename = f"ws_{task[:12]}_{index}{_ext(url, '.png')}"
    path = os.path.join(root, SUBFOLDER, filename)
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        async with session.get(url) as res:
            if res.status >= 400:
                raise WaveSpeedError(f"downloading WaveSpeed output failed ({res.status})")
            data = await res.read()
        _write(path, data)
    return {"filename": filename, "subfolder": SUBFOLDER, "type": "output"}


def _history(task: str, status: str, messages: list, outputs: dict) -> dict:
    done = status in ("completed", "failed")
    return {f"ws:{task}": {"status": {"completed": done, "status_str": "error" if status == "failed" else status, "messages": messages}, "outputs": outputs}}


def _fail(task: str, message: str) -> dict:
    job = _jobs.get(task)
    if job:
        job["done"] = True
        job["result"] = _history(task, "failed", [["execution_error", {"exception_message": message}]], {})
        return job["result"]
    return _history(task, "failed", [["execution_error", {"exception_message": message}]], {})


async def poll(task: str) -> dict:
    job = _jobs.get(task)
    if job is None:
        job = _jobs[task] = {"started": time.time(), "next_poll": 0.0}
    if job.get("result"):
        return job["result"]
    now = time.time()
    if now - job["started"] > JOB_TIMEOUT:
        return _fail(task, f"WaveSpeed task timed out after {int(JOB_TIMEOUT)}s")
    if now < job["next_poll"]:
        return _history(task, "processing", [], {})
    job["next_poll"] = now + POLL_MIN
    async with aiohttp.ClientSession(headers=_headers()) as session:
        async with session.get(f"{_base()}/api/v3/predictions/{task}/result") as res:
            body = await _json(res)
            if res.status == 429:
                retry = res.headers.get("Retry-After")
                job["next_poll"] = now + max(POLL_MIN, float(retry) if retry and retry.replace(".", "", 1).isdigit() else 10.0)
                return _history(task, "processing", [], {})
            if res.status == 404:
                return {}
            if res.status >= 400:
                err = _status_error(res.status, body)
                if res.status in (401, 402, 403):
                    return _fail(task, str(err))
                return _history(task, "processing", [], {})
        data = (body or {}).get("data") or {}
        status = data.get("status")
        if status == "failed":
            return _fail(task, f"WaveSpeed task failed: {data.get('error') or 'unknown error'}")
        if status != "completed":
            return _history(task, status or "processing", [], {})
        outputs = data.get("outputs") or []
        if not outputs:
            return _fail(task, "WaveSpeed task finished without output")
        # CDN URLs expire after 7 days: keep a local copy right away
        refs = [await _download(session, task, i, url) for i, url in enumerate(outputs) if isinstance(url, str)]
    job["done"] = True
    job["result"] = _history(task, "completed", [], {"ws": {"images": refs}})
    log.info("WaveSpeed task %s completed (%d output%s)", task, len(refs), "" if len(refs) == 1 else "s")
    return job["result"]


async def run_raw(inputs: dict, timeout: float = 120.0) -> list:
    """Submit and wait for a small job whose outputs are read directly (e.g. OCR text), not downloaded."""
    task = await submit(inputs)
    deadline = time.time() + timeout
    try:
        async with aiohttp.ClientSession(headers=_headers()) as session:
            while time.time() < deadline:
                await asyncio.sleep(max(POLL_MIN, 0.01))
                async with session.get(f"{_base()}/api/v3/predictions/{task}/result") as res:
                    body = await _json(res)
                    if res.status == 429:
                        continue
                    if res.status >= 400:
                        raise _status_error(res.status, body)
                data = (body or {}).get("data") or {}
                if data.get("status") == "failed":
                    raise WaveSpeedError(f"WaveSpeed task failed: {data.get('error') or 'unknown error'}")
                if data.get("status") == "completed":
                    return list(data.get("outputs") or [])
        raise WaveSpeedError(f"WaveSpeed task timed out after {int(timeout)}s", 504)
    finally:
        if task in _jobs:
            _jobs[task]["done"] = True


async def fetch_text(url: str) -> str:
    async with aiohttp.ClientSession() as session, session.get(url) as res:
        if res.status >= 400:
            raise WaveSpeedError(f"downloading WaveSpeed output failed ({res.status})")
        return await res.text()


def _respond_error(e: WaveSpeedError) -> web.Response:
    body: dict = {"message": str(e)}
    if e.confirm is not None:
        body["confirm_usd"] = e.confirm
    return web.json_response({"error": body}, status=e.status)


@routes.post("/comfyart/wavespeed/run")
async def wavespeed_run(request: web.Request) -> web.Response:
    inputs = (await json_body(request)).get("inputs")
    if not isinstance(inputs, dict):
        return error("inputs must be an object", 400)
    try:
        task = await submit(inputs)
    except WaveSpeedError as e:
        return _respond_error(e)
    except aiohttp.ClientError as e:
        return _respond_error(WaveSpeedError(f"could not reach WaveSpeed: {e}"))
    return web.json_response({"prompt_id": f"ws:{task}"})


@routes.get("/comfyart/wavespeed/history/{task}")
async def wavespeed_history(request: web.Request) -> web.Response:
    try:
        return web.json_response(await poll(request.match_info["task"]))
    except WaveSpeedError as e:
        return _respond_error(e)
    except (TimeoutError, aiohttp.ClientError):
        return web.json_response(_history(request.match_info["task"], "processing", [], {}))


@routes.post("/comfyart/wavespeed/cancel/{task}")
async def wavespeed_cancel(request: web.Request) -> web.Response:
    # WaveSpeed has no cancel endpoint; stop tracking so the slot frees up
    job = _jobs.get(request.match_info["task"])
    if job:
        job["done"] = True
    return web.json_response({})


@routes.post("/comfyart/wavespeed/transcribe")
async def wavespeed_transcribe(request: web.Request) -> web.Response:
    src = (await json_body(request)).get("src")
    if not isinstance(src, str) or not src:
        return error("src must be a /api/view URL", 400)
    try:
        outputs = await run_raw({"feature": "transcribe", "audio": src})
        parts = []
        for out in outputs:
            text = await fetch_text(out) if isinstance(out, str) and out.startswith(("http://", "https://")) else out
            if isinstance(text, dict):
                text = text.get("text") or ""
            parts.append(str(text))
    except WaveSpeedError as e:
        return _respond_error(e)
    except ValueError as e:
        return error(str(e), 404)
    return web.json_response({"text": "\n".join(p.strip() for p in parts if p and p.strip())})


@routes.get("/comfyart/wavespeed/models")
async def wavespeed_models(request: web.Request) -> web.Response:
    return web.json_response({"enabled": bool(os.environ.get("WAVESPEED_API_KEY")), "stale": bool(_catalog.get("stale")), "features": await grouped_models(request.query.get("refresh") == "1")})


def check_key_at_startup() -> None:
    """Validate the key once with the free /balance endpoint and log pass/fail (never the key itself)."""
    key = os.environ.get("WAVESPEED_API_KEY", "").strip()
    if not key:
        log.warning("[ComfyArt] WAVESPEED_API_KEY is not set: cloud generation is disabled")
        return

    def run() -> None:
        req = urllib.request.Request(f"{_base()}/api/v3/balance", headers={"Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                ok = res.status == 200
        except Exception as e:  # noqa: BLE001 - only log the outcome
            code = getattr(e, "code", None)
            log.warning("[ComfyArt] WaveSpeed key check failed%s", f" (HTTP {code})" if code else f": {type(e).__name__}")
            return
        log.info("[ComfyArt] WaveSpeed key check %s", "passed" if ok else "failed")

    threading.Thread(target=run, name="wavespeed-key-check", daemon=True).start()


if not os.environ.get("COMFYART_SKIP_KEY_CHECK"):
    check_key_at_startup()
