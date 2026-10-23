"""WaveSpeed cloud provider: runs ComfyArt generation on api.wavespeed.ai instead of local ComfyUI models.

The frontend queues a pseudo graph {"ws": {"class_type": "WaveSpeedRun", "inputs": {...}}}; this module
submits it to WaveSpeed, polls the result, downloads outputs into ComfyUI's output folder and answers in
ComfyUI /history shape so the existing job flow is unchanged. The API key comes from the
WAVESPEED_API_KEY environment variable (wins) or the key saved in Settings (a 0600 file in the ComfyUI user
directory). It is never logged, and the browser only ever sees whether it is set and its last 4 characters.
"""

import asyncio
import io
import json
import logging
import math
import mimetypes
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid

import aiohttp
import folder_paths
from aiohttp import web

from . import refprep
from ._common import app_path, error, json_body, routes

log = logging.getLogger("comfyart.wavespeed")

DEFAULT_BASE = "https://api.wavespeed.ai"


def _base() -> str:
    return (os.environ.get("WAVESPEED_BASE_URL") or DEFAULT_BASE).rstrip("/")


CONFIG = os.path.join(os.path.dirname(__file__), "wavespeed_models.json")
CURATED = os.path.join(os.path.dirname(__file__), "curated_models.json")
CATALOG_TTL = 24 * 3600
POLL_MIN = 2.0
POLL_MAX_BACKOFF = 15.0
JOB_TIMEOUT = float(os.environ.get("WAVESPEED_JOB_TIMEOUT") or 30 * 60)
ANNOTATED = re.compile(r"^(.+) \[(input|output|temp)\]$")
SUBFOLDER = "wavespeed"

_catalog: dict = {"at": 0.0, "models": {}}
_jobs: dict[str, dict] = {}
_uploaded: dict[tuple[str, int, int], str] = {}


class WaveSpeedError(Exception):
    def __init__(self, message: str, status: int = 502, confirm: float | None = None, seg_splits: int | None = None, seg_capped: bool = False):
        super().__init__(message)
        self.status = status
        self.confirm = confirm
        self.seg_splits = seg_splits  # #135: 「识别加最多 N 次分割」 in the confirm dialog
        self.seg_capped = seg_capped  # True: N is the upper bound (nothing recognised yet, caption included)


KEY_FILE = "wavespeed_key.json"


def _key_path() -> str:
    return app_path(KEY_FILE)


def _saved_key() -> str:
    try:
        with open(_key_path(), encoding="utf-8") as f:
            return str(json.load(f).get("key") or "").strip()
    except (OSError, ValueError, AttributeError):
        return ""


def _save_key(key: str) -> None:
    path = _key_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"key": key}, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _delete_key() -> None:
    try:
        os.remove(_key_path())
    except FileNotFoundError:
        pass


def key_source() -> tuple[str, str]:
    """(key, source): the environment variable wins over the key saved in Settings."""
    env = os.environ.get("WAVESPEED_API_KEY", "").strip()
    if env:
        return env, "env"
    saved = _saved_key()
    return (saved, "settings") if saved else ("", "none")


def has_key() -> bool:
    return bool(key_source()[0])


def _key() -> str:
    key = key_source()[0]
    if not key:
        raise WaveSpeedError("WaveSpeed needs an API key: add one in Settings > WaveSpeed API key or set WAVESPEED_API_KEY", 400)
    return key


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_key()}"}


def load_curated() -> dict:
    """feature -> {"needs": [...], "models": [ids], "default"?: id} from api/curated_models.json (#95);
    default = the explicit "default" (#134), else the first id."""
    with open(CURATED, encoding="utf-8") as f:
        return json.load(f)["features"]


def model_defaults(model: str) -> dict:
    """Request fields filled in when a job leaves them unset (#134): a feature's 'default_params' for its 'default' model
    (the default starts at its lowest quality tier). Keyed by the single 'default' value, so a switch is one edit."""
    out: dict = {}
    for cur in load_curated().values():
        if model and cur.get("default") == model:
            out.update(cur.get("default_params") or {})
    return out


def apply_curation(cfg: dict, curated: dict) -> dict:
    """Narrow each curated feature to exactly the curated ids (in order; default = "default" if set, else first)."""
    for name, cur in curated.items():
        feature = cfg["features"].get(name)
        if feature is None or not cur.get("models"):
            continue
        old = {m["id"]: m for m in feature["models"]}
        feature["models"] = [old.get(i, {"id": i}) for i in cur["models"] + cur.get("more", [])]
        feature["default"] = cur["default"] if cur.get("default") in cur["models"] + cur.get("more", []) else cur["models"][0]
        # #134: a default from 'more' (flare edit) is still offered in the agent's recommended view
        feature["recommended"] = list(cur["models"]) + ([feature["default"]] if feature["default"] not in cur["models"] else [])
    return cfg


def load_config() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        return apply_curation(json.load(f), load_curated())


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
        return WaveSpeedError("WaveSpeed rejected the API key (401): check it in Settings > WaveSpeed API key", 401)
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
    if props.get("quality", {}).get("enum"):
        out["qualities"] = props["quality"]["enum"]
    if "images" in props:
        out["max_images"] = props["images"].get("maxItems")
    defaults = {k: props[k]["default"] for k in ("aspect_ratio", "resolution", "duration", "quality") if "default" in (props.get(k) or {})}
    if defaults:
        out["defaults"] = defaults
    return out


_GENERIC = {"text-to-image", "image-to-image", "edit", "image-edit", "text-to-video", "image-to-video"}


def short_label(model_id: str) -> str:
    """One-line picker name: vendor and generic task suffixes stripped (openai/gpt-image-2.5-flare/text-to-image -> gpt-image-2.5-flare)."""
    parts = model_id.split("/")[1:] or [model_id]
    while len(parts) > 1 and parts[-1] in _GENERIC:
        parts.pop()
    return " ".join(parts)


def subtitle(model_id: str, display_name: str | None) -> str:
    """Picker subtitle: WaveSpeed display name, else the model ID without its vendor prefix. Never the old local model name."""
    return display_name or model_id.split("/", 1)[-1]


_VENDORS = (("nano-banana", "Nano Banana"), ("gpt-image", "GPT Image"), ("seedream", "Seedream"), ("seedance", "Seedance"),
            ("uni-v1", "Luma"), ("flux", "Flux"), ("qwen-image", "Qwen-Image"), ("midjourney", "Midjourney"),
            ("ideogram", "Ideogram"), ("recraft", "Recraft"), ("kling", "Kling"), ("veo", "Veo"), ("gemini-omni", "Gemini Omni"),
            ("wan-", "Wan"), ("vidu", "Vidu"), ("hailuo", "Hailuo"), ("minimax", "MiniMax"), ("ltx", "LTX"))


_DISPLAY: dict | None = None


def _display() -> dict:
    global _DISPLAY
    if _DISPLAY is None:
        with open(os.path.join(os.path.dirname(__file__), "model_display.json"), encoding="utf-8") as f:
            _DISPLAY = json.load(f)
    return _DISPLAY


def display_of(model_id: str) -> dict | None:
    """Lovart-style row (#95): display name + one-line zh/en description from api/model_display.json."""
    hit = next((row for row in _display()["families"] if row[0] in model_id), None)
    return {"name": hit[1], "blurb": {"zh": hit[2], "en": hit[3]}} if hit else None


def picker_order(feature: str, models: list[dict]) -> list[str]:
    """Dropdown order (#95 product ruling): the first curated id first, then Lovart's in-app order;
    recommended models are not pulled to the top. Features Lovart has no dropdown for keep config order.
    #134: an explicit feature default does not move in the dropdown (design rule); only Auto points at it."""
    order = _display()["lovart_order"].get({"text_to_image": "image", "image_edit": "image",
                                            "text_to_video": "video", "image_to_video": "video"}.get(feature, ""))
    if not order or not models:
        return [m["id"] for m in models]
    rank = {name: i for i, name in enumerate(order)}
    first = models[0]
    rest = sorted(models[1:], key=lambda m: rank.get(m.get("name") or "", len(rank)))
    return [first["id"]] + [m["id"] for m in rest]


def vendor_of(model_id: str) -> str:
    """Picker group like Lovart's dropdown (#95): model family, else the WaveSpeed vendor prefix."""
    low = model_id.lower()
    return next((name for key, name in _VENDORS if key in low), model_id.split("/", 1)[0])


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
                "label": short_label(entry["id"]),
                "subtitle": subtitle(entry["id"], m.get("name")),
                "price": m.get("base_price"),
                "desc": (m.get("description") or "")[:240],
                "local_equivalent": entry.get("local"),
                "default": entry["id"] == feature["default"],
                "recommended": entry["id"] in feature.get("recommended", [entry["id"]]),
                "vendor": vendor_of(entry["id"]),
                **(display_of(entry["id"]) or {}),
                **_caps(_schema(m)),
            })
        out[name] = {"default": feature["default"], "picker_order": picker_order(name, models), "types": feature["types"], "available": name not in cfg.get("pending_features", []), "models": models}
    return out


AUDIO_FEATURES = {"music", "sound_effect", "text_to_speech", "voice_clone", "transcribe"}
MODEL_KINDS = ("image", "image_tools", "video", "video_tools", "audio", "3d")
VIDEO_TOOLS = {"upscale_video", "remove_video_background"}


def feature_kind(name: str) -> str:
    if "3d" in name:
        return "3d"
    if name in VIDEO_TOOLS:  # own kind so "video" fits the 4000-char cap with 5 curated models (#95)
        return "video_tools"
    if "video" in name or name in ("motion_control", "lip_sync"):
        return "video"
    if name in AUDIO_FEATURES:
        return "audio"
    return "image" if name in ("text_to_image", "image_edit") else "image_tools"


def _compact_choices(v):
    """[3, 4, ..., 15] -> "3-15" so the video kind stays under the 4000-char cap (#95)."""
    if (isinstance(v, list) and len(v) >= 4 and all(isinstance(x, int) and not isinstance(x, bool) for x in v)
            and v == list(range(v[0], v[0] + len(v)))):
        return f"{v[0]}-{v[-1]}"
    return v


PAGE_BUDGET = 3800  # under the agent's 4000-char TOOL_RESULT_CAP (bot/_cli_common.py) with room for the wrapper


def _one_line(text: str, limit: int = 90) -> str:
    line = " ".join(str(text or "").split())
    line = line.split(". ")[0]
    return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"


def _entry(m: dict) -> dict:
    """One list_models row: id, starting price (USD per run) and a one-line description."""
    return {"id": m["id"], "usd": m.get("price"), "desc": _one_line(m.get("desc") or m.get("subtitle") or "")}


def _size(obj) -> int:
    return len(json.dumps(obj, ensure_ascii=False))


def compact_models(grouped: dict, kind: str | None = None, tool_features: dict | None = None,
                   all_models: bool = False, page: int = 1) -> dict:
    """list_models output that fits the agent's 4000-char tool-result cap (#95, modelled on Lovart).

    No kind: each available feature's default plus the kinds to ask for. kind (image/video/audio/3d or a
    feature name): by default only each feature's recommended models (the curated set, default first) with
    a hint to page through the rest; all_models=True pages through every model, each page under the cap."""
    live = {n: f for n, f in grouped.items() if f.get("available", True)}
    if not kind:
        return {"defaults": {n: f["default"] for n, f in live.items()},
                "kinds": {k: [n for n in live if feature_kind(n) == k] for k in MODEL_KINDS},
                "hint": "call list_models with type image, image_tools, video, video_tools, audio, 3d or a feature name "
                        "for its recommended models; model_id=<id> for one model's params and quality tiers"}
    names = [kind] if kind in live else [n for n in live if feature_kind(n) == kind]
    if not names:
        raise WaveSpeedError(f"unknown type {kind!r}; use one of {', '.join(MODEL_KINDS)} or a feature name", 400)
    tools: dict[str, list[str]] = {}
    for tool, feature in (tool_features or {}).items():
        tools.setdefault(feature, []).append(tool)
    # generate_video runs both text-to-video and image-to-video ids (src/models.ts VIDEO_MODELS)
    if "generate_video" in tools.get("image_to_video", []):
        tools.setdefault("text_to_video", []).insert(0, "generate_video")

    def head(n: str) -> dict:
        return {"tools": tools.get(n, []), "default": live[n]["default"], "total": len(live[n]["models"])}

    # the agent sees each feature's default first (#134: the explicit default, not the first dropdown row)
    every = [(n, m) for n in names for m in sorted(live[n]["models"], key=lambda m: m["id"] != live[n]["default"])]
    chosen = every if all_models else [(n, m) for n, m in every if m.get("recommended", True)]
    # default view: Chinese footer in the same style as the paged one (#95 EL ruling)
    hint = (f"共 {len(every)} 个，当前为推荐 {len(chosen)} 个，查看全部传 all=true、page=1"
            if len(chosen) < len(every) else None)

    def render(chunk: list, p: int, of: int) -> dict:
        feats: dict = {}
        for n, e in chunk:
            feats.setdefault(n, {**head(n), "models": []})["models"].append(e)
        out = {"page": p, "pages": of, "features": feats}
        # footer is always the last key so it renders at the bottom, single page included (#95 rulings)
        out["footer"] = f"共 {len(chosen)} 个，第 {p}/{of} 页" + (f"，翻页传 page={p + 1}" if p < of else "") \
            + (f"；{hint}" if hint else "")
        return out

    # greedy page packing over (feature, model) rows in feature order, every page under the cap
    pages: list[list] = [[]]
    for n, m in chosen:
        row = (n, _entry(m))
        if pages[-1] and _size(render(pages[-1] + [row], 999, 999)) > PAGE_BUDGET:
            pages.append([])
        pages[-1].append(row)
    if not all_models and len(pages) == 1:
        # single default page: features then a Chinese footer as the last key (#95 EL ruling)
        return {"features": render(pages[0], 1, 1)["features"],
                "footer": hint or f"共 {len(chosen)} 个，第 1/1 页"}
    if not 1 <= page <= len(pages):
        raise WaveSpeedError(f"page {page} out of range; {kind} has {len(pages)} page(s)", 400)
    return render(pages[page - 1], page, len(pages))


def model_details(grouped: dict, model_id: str) -> dict:
    """list_models(model_id=...): one model's features, price, params and quality tiers."""
    hits = [(n, m) for n, f in grouped.items() for m in f["models"] if m["id"] == model_id]
    if not hits:
        raise WaveSpeedError(f"unknown model {model_id!r}; call list_models with a type to see ids", 400)
    m = hits[0][1]
    out = {"id": m["id"], "features": [n for n, _ in hits], "usd": m.get("price"), "desc": str(m.get("desc") or "")[:1500]}
    for k in ("inputs", "durations", "aspect_ratios", "resolutions", "max_images"):
        if m.get(k):
            out[k] = _compact_choices(m[k])
    if m.get("qualities"):
        out["tiers"] = m["qualities"]
    return out


def resolve_model(feature: str, model: str | None) -> str:
    config = load_config()
    cfg = config["features"].get(feature)
    if not cfg or feature in config.get("pending_features", []):
        raise WaveSpeedError(f"{feature or 'this tool'} is not available in cloud mode yet", 400)
    if not model:
        return cfg["default"]
    if model not in [m["id"] for m in cfg["models"]]:
        valid = ", ".join(m["id"] for m in cfg["models"])
        raise WaveSpeedError(f"unknown model {model!r} for {feature}; valid ids: {valid} (default {cfg['default']})", 400)
    return model


# custom_workflow (cloud): a feature can run any WaveSpeed model; "fields" maps ComfyArt's values
# (the upstream @markers) onto that model's request fields.
MARKER_INPUTS = {"image", "image2", "mask", "last", "prompt", "size", "width", "height", "count", "seconds"}
MEDIA_MARKERS = {"image", "image2", "mask", "last"}
AUTO_FIELDS = {"image", "images", "mask_image", "prompt", "tags", "size", "aspect_ratio", "resolution", "duration",
               "music_length_ms", "last_image", "num_layers", "seed", "output_format", "text", "lyrics", "voice", "voice_id", "language"}


def custom_model(model: str | None, meta: dict) -> str:
    if not isinstance(model, str) or "/" not in model:
        raise WaveSpeedError("custom workflow needs a WaveSpeed model id like owner/model", 400)
    if model not in meta:
        raise WaveSpeedError(f"WaveSpeed has no model {model!r}", 400)
    return model


def check_custom(spec: dict, required: list[str], optional: list[str], meta: dict) -> dict:
    """Validate a cloud custom workflow {model, fields: {"@marker": field}, params} for one feature."""
    errors: list[str] = []
    warnings: list[str] = []
    codes: list[dict] = []  # structured errors so the UI can localize them
    model = spec.get("model") if isinstance(spec, dict) else None
    try:
        custom_model(model, meta)
    except WaveSpeedError as e:
        code = "badModelId" if not (isinstance(model, str) and "/" in model) else "unknownModel"
        return {"ok": False, "errors": [str(e)], "warnings": [], "fields": {}, "codes": [{"code": code, "model": str(model or "")}]}
    schema = _schema(meta[model])
    props = schema.get("properties") or {}
    fields = {str(k).lstrip("@").lower(): v for k, v in (spec.get("fields") or {}).items()}
    params = spec.get("params") or {}
    usable = set(required) | set(optional) | ({"width", "height"} if "size" in required + optional else set())
    for marker, field in fields.items():
        if marker not in MARKER_INPUTS:
            warnings.append(f"@{marker} is not a ComfyArt marker and is ignored.")
        elif marker not in usable:
            warnings.append(f"@{marker} is not used by this feature and is ignored.")
        elif field not in props:
            errors.append(f"@{marker} is mapped to {field!r}, which {model} does not accept.")
            codes.append({"code": "badField", "model": model, "marker": "@" + marker, "field": str(field)})
    for k in params:
        if k not in props:
            errors.append(f"param {k!r} is not accepted by {model}.")
            codes.append({"code": "badParam", "model": model, "param": str(k)})
    auto = {"image": "image" in props or "images" in props, "image2": "images" in props, "mask": "mask_image" in props,
            "last": "last_image" in props, "prompt": "prompt" in props or "tags" in props,
            "size": bool({"size", "aspect_ratio", "resolution"} & set(props)), "count": "num_layers" in props or "prompt" in props,
            "seconds": "duration" in props or "music_length_ms" in props}
    missing = [m for m in required if m not in fields and not auto.get(m) and not (m == "size" and "width" in fields and "height" in fields)]
    if missing:
        errors.append(f"{model} has no field for {', '.join('@' + m for m in missing)}; map it under fields.")
        codes.append({"code": "missingFields", "model": model, "markers": ["@" + m for m in missing]})
    covered = AUTO_FIELDS | set(fields.values()) | set(params)
    unfilled = [k for k in schema.get("required") or [] if k not in covered]
    if unfilled:
        errors.append(f"{model} requires {', '.join(unfilled)}; set it under params or map a marker to it.")
        codes.append({"code": "requiredParams", "model": model, "params": unfilled})
    return {"ok": not errors, "errors": errors, "warnings": warnings, "fields": fields, "codes": codes, "price": meta[model].get("base_price")}


async def _custom_fields(session: aiohttp.ClientSession, inputs: dict, payload: dict) -> None:
    images = list(inputs.get("images") or [])
    values = {"image": inputs.get("image"), "image2": images[0] if images else None, "mask": inputs.get("mask"),
              "last": inputs.get("last_image"), "prompt": inputs.get("prompt"), "width": inputs.get("width"),
              "height": inputs.get("height"), "count": inputs.get("layers"), "seconds": inputs.get("duration")}
    if inputs.get("width") and inputs.get("height"):
        values["size"] = f"{int(inputs['width'])}*{int(inputs['height'])}"
    for marker, field in (inputs.get("fields") or {}).items():
        marker = str(marker).lstrip("@").lower()
        value = values.get(marker)
        if value in (None, ""):
            continue
        if marker == "mask":
            path = _local_path(str(value))
            if not path:
                raise WaveSpeedError("mask file not found", 400)
            payload[field] = await _upload(session, path, mask_to_white(_read(path)), f"mask-{uuid.uuid4().hex[:8]}.png")
        elif marker in MEDIA_MARKERS:
            payload[field] = await _media(session, str(value))
        else:
            payload[field] = value


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


async def _image_size(value: str) -> tuple[int, int] | None:
    """Pixel size of a source image, or None when it can't be read."""
    from PIL import Image

    try:
        if value.startswith("data:"):
            import base64
            data = base64.b64decode(value.split(",", 1)[1])
        else:
            data = await _source_bytes(value)
        with Image.open(io.BytesIO(data)) as img:
            return img.size
    except Exception:  # noqa: BLE001 - unreadable source: the caller falls back to the pre-submit error
        return None


async def seg_prompts(inputs: dict) -> dict:
    """#120: sam3-image needs at least one of prompt / box_prompts / point_prompts. Use the user's boxes or
    points when given; else the object description (or this generation's prompt) as text; else one
    full-image box. With none of those the job fails here, before submit, so nothing is charged."""
    params = dict(inputs.get("params") or {})
    if params.get("box_prompts") or params.get("point_prompts"):
        return inputs
    text = str(inputs.get("prompt") or inputs.get("object") or "").strip()
    if text:
        return {**inputs, "prompt": text}
    size = await _image_size(str(inputs.get("image") or "")) if inputs.get("image") else None
    if not size:
        raise WaveSpeedError(SEG_TARGET_MISSING, 400)
    params["box_prompts"] = [{"x_min": 0, "y_min": 0, "x_max": int(size[0]), "y_max": int(size[1])}]
    return {**inputs, "params": params}


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


def _clamp(spec: dict, value):
    """Keep a free numeric value inside the schema's minimum/maximum (e.g. ace-step-1.5 takes 5..240 s)."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return value
    if spec.get("minimum") is not None:
        num = max(num, float(spec["minimum"]))
    if spec.get("maximum") is not None:
        num = min(num, float(spec["maximum"]))
    return int(num) if spec.get("type") == "integer" or num.is_integer() else num


VOICE_SAMPLE_MISSING = "Please upload a voice sample first"
# #120: wavespeed-ai/sam3-image rejects a job with no prompt, box or point; caught before submit (no charge)
SEG_TARGET_MISSING = "Select or describe the object to segment first"
SAM3_MODEL = "wavespeed-ai/sam3-image"


def default_voice(spec: dict) -> str | None:
    """First preset voice a free-text voice field lists: schema default, else x-suggestions, else the
    'system voice IDs: A, B, ...' list in its description."""
    if spec.get("default"):
        return str(spec["default"])
    sugg = spec.get("x-suggestions") or []
    if sugg:
        return str(sugg[0])
    m = re.search(r"voice IDs?:\s*([A-Za-z0-9_\-]+)", str(spec.get("description") or spec.get("x-hint") or ""))
    return m.group(1) if m else None


def needs_voice_sample(model: str, feature: str, schema: dict, inputs: dict) -> bool:
    """Voice-clone models need an uploaded sample; say so before any quote/confirm/charge."""
    cloning = feature == "voice_clone" or "voice-clone" in model
    return cloning and "audio" in (schema.get("required") or []) and not inputs.get("audio")


def _av_fields(props: dict, required: set, inputs: dict, payload: dict) -> None:
    """Video/audio knobs: duration, resolution, text, voice, language, lyrics."""
    seconds = inputs.get("duration")
    if seconds:
        if "duration" in props:
            spec = props["duration"]
            enum = spec.get("enum")
            payload["duration"] = _pick(enum, seconds) if enum else _clamp(spec, seconds)
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
            elif k in required and (preset := default_voice(props[k])):
                payload[k] = preset  # free-text voice ids (speech-2.8-turbo, eleven-v4): first listed preset
    if "custom_voice_id" in required and "custom_voice_id" not in payload and payload.get("audio"):
        # minimax/voice-clone names the new voice: >= 8 chars, starts with a letter, letters + digits
        payload["custom_voice_id"] = f"ComfyArt{uuid.uuid4().hex[:8]}"
    model_spec = props.get("model") or {}
    if "model" in required and model_spec.get("enum") and "model" not in payload:
        payload["model"] = model_spec.get("default") or model_spec["enum"][0]
    lang = props.get("language", {}).get("enum")
    if lang and "text" in payload:
        payload["language"] = "auto" if "auto" in lang else lang[0]


def _size_value(spec: dict, w: int, h: int) -> str:
    """size as the schema wants it: free W*H, or the closest enum entry (ratios like 16:9 or sizes like 1024*1536)."""
    enum = [str(v) for v in spec.get("enum") or []]
    if not enum:
        return f"{w}*{h}"
    def shape(v: str):
        for sep in (":", "*", "x"):
            if sep in v:
                a, b = v.split(sep, 1)
                try:
                    return float(a), float(b)
                except ValueError:
                    return None
        return None
    parsed = [(v, shape(v)) for v in enum]
    good = [(v, d) for v, d in parsed if d and d[1]]
    if not good:
        return enum[0]
    ratio = w / h
    return min(good, key=lambda vd: (abs(math.log((vd[1][0] / vd[1][1]) / ratio)), abs(vd[1][0] * vd[1][1] - w * h) if ":" not in vd[0] else 0))[0]


# ACE-Step's tempo / lyrics language / key (agent generate_music, upstream v1.0.1). The frontend only
# sends them for ACE-Step; a schema without dedicated fields gets them appended to the style tags.
MUSIC_FIELDS = {"bpm": ("bpm",), "language": ("language", "vocal_language"), "key": ("keyscale", "key_scale", "key")}


def _ace_music_fields(props: dict, music, payload: dict) -> None:
    if not isinstance(music, dict):
        return
    extra = []
    for name, fields in MUSIC_FIELDS.items():
        value = music.get(name)
        if value in (None, ""):
            continue
        field = next((f for f in fields if f in props), None)
        if field:
            payload[field] = int(value) if name == "bpm" else str(value)
        else:
            extra.append(f"{int(value)} bpm" if name == "bpm" else f"{'key' if name == 'key' else 'language'} {value}")
    if extra:
        payload["tags"] = ", ".join([payload["tags"], *extra])


async def build_payload(session: aiohttp.ClientSession, schema: dict, inputs: dict, model: str = "") -> dict:
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
            payload["size"] = _size_value(props["size"], int(w), int(h))
        if props.get("aspect_ratio", {}).get("enum"):
            payload["aspect_ratio"] = _nearest(props["aspect_ratio"]["enum"], w / h)
        if props.get("resolution", {}).get("enum"):
            payload["resolution"] = _resolution(props["resolution"]["enum"], max(int(w), int(h)))
    elif inputs.get("ratio") and props.get("aspect_ratio", {}).get("enum"):
        a, b = str(inputs["ratio"]).split(":")
        payload["aspect_ratio"] = _nearest(props["aspect_ratio"]["enum"], float(a) / float(b))
    await _media_fields(session, props, inputs, payload)
    _av_fields(props, set(schema.get("required") or []), inputs, payload)
    if inputs.get("custom"):
        await _custom_fields(session, inputs, payload)
    for k, v in (inputs.get("params") or {}).items():
        if k in props and v is not None:
            payload[k] = v
    for k, v in model_defaults(model).items():
        if k in props and k not in payload:
            payload[k] = v
    prompt = str(inputs.get("prompt") or "").strip()
    layers = inputs.get("layers")
    if isinstance(layers, int) and layers > 0:
        if "num_layers" in props:
            payload["num_layers"] = layers
        elif "prompt" in props:
            # models without a layer-count field (seedream) take the user's count in the prompt
            base = prompt.rstrip(" .。")
            prompt = f"{base}{'. ' if base else ''}Separate into {layers} layers."
    if prompt and "prompt" not in props and "tags" in props:
        payload["tags"] = prompt  # ACE-Step names its style prompt "tags"
        _ace_music_fields(props, inputs.get("music"), payload)
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


PREFS_FILE = "wavespeed_prefs.json"
QUOTE_TTL = 300.0
_quotes: dict[str, tuple[float, float]] = {}
# scalar fields that change a model's price; media and prompts never do
_PRICE_FIELDS = ("duration", "resolution", "aspect_ratio", "ratio", "size", "num_images", "quality")


def confirm_usd() -> float:
    """Cost at or above which a job needs a second confirmation; 0 means always confirm."""
    try:
        v = json.loads(open(app_path(PREFS_FILE)).read()).get("confirm_usd")
        if valid_confirm_usd(v):
            return float(v)
    except (OSError, ValueError, AttributeError):
        pass
    return float(limits()["confirm_usd"])


def valid_confirm_usd(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 1000


def needs_confirm(price: float) -> bool:
    limit = confirm_usd()
    return limit == 0 or price >= limit


def _price_inputs(inputs: dict, model: str = "") -> dict:
    """Price-relevant fields; a tier picked under params (quality) and #134 model_defaults count too,
    so the confirm price is the one for the tier that will actually run."""
    params = inputs.get("params") if isinstance(inputs.get("params"), dict) else {}
    merged = {**model_defaults(model), **{k: v for k, v in params.items() if v is not None}, **inputs}
    out = {k: merged[k] for k in _PRICE_FIELDS if isinstance(merged.get(k), (int, float, str)) and k in merged}
    inputs = merged
    if "ratio" in out:
        out["aspect_ratio"] = out.pop("ratio")
    if isinstance(inputs.get("width"), int) and isinstance(inputs.get("height"), int):
        out["size"] = f"{inputs['width']}*{inputs['height']}"
    return out


async def quote(model: str, inputs: dict) -> tuple[float | None, str]:
    """Price of one run via WaveSpeed's free POST /api/v3/model/price, cached 5 minutes.
    Falls back to the catalog base_price when the quote fails."""
    body = {"model_id": model, "inputs": _price_inputs(inputs, model)}
    ck = json.dumps(body, sort_keys=True)
    hit = _quotes.get(ck)
    if hit and time.time() - hit[1] < QUOTE_TTL:
        return hit[0], "quote"
    try:
        async with aiohttp.ClientSession(headers=_headers()) as session:
            async with session.post(f"{_base()}/api/v3/model/price", json=body, timeout=aiohttp.ClientTimeout(total=10)) as res:
                data = ((await _json(res)) or {}).get("data") or {} if res.status < 400 else {}
        price = data.get("discounted_price", data.get("price")) if isinstance(data, dict) else None
        if isinstance(price, (int, float)) and not isinstance(price, bool):
            _quotes[ck] = (float(price), time.time())
            return float(price), "quote"
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        pass
    base = ((await catalog()).get(model) or {}).get("base_price")
    return (float(base) if isinstance(base, (int, float)) else None), "catalog"


async def estimate(inputs: dict) -> dict:
    """Estimated total for a job; a storyboard is priced as the sum of its scenes."""
    if isinstance(inputs.get("scenes"), list):
        scenes = [sc for sc in inputs["scenes"] if isinstance(sc, dict)]
        base = {k: v for k, v in inputs.items() if k != "scenes"}
        feature = "image_to_video" if base.get("image") else "text_to_video"
        first = resolve_model(feature, base.get("model") if feature == base.get("feature") else None)
        chain = resolve_model("image_to_video", base.get("model") if base.get("feature") == "image_to_video" else None)
        total, sources = 0.0, set()
        for i, sc in enumerate(scenes):
            p, src = await quote(first if i == 0 else chain, {**base, **({"duration": sc["duration"]} if sc.get("duration") else {})})
            total += p or 0.0
            sources.add(src)
        price, source = round(total, 4), ("quote" if sources == {"quote"} else "catalog")
    else:
        if inputs.get("feature") == "mockup_surface":
            return {"price": None, "currency": "USD", "source": "none", "confirm_usd": confirm_usd(), "confirm": confirm_usd() == 0}
        feature = feature_of(str(inputs.get("feature") or ""))
        picked = inputs.get("model")
        if feature == "structure_control" and not picked:
            picked = _structure_pick(inputs)
        model = resolve_model(feature, picked)
        price, source = await quote(model, inputs)
        if feature == "structure_control" and price is not None:
            extra = await _steps_price(inputs)  # depth / sam3 map calls are paid too (#80)
            price = None if extra is None else round(float(price) + extra, 6)
    return {"price": price, "currency": "USD", "source": source, "confirm_usd": confirm_usd(),
            "confirm": needs_confirm(price) if price is not None else confirm_usd() == 0}


STRUCTURE_EXTRACT_MODEL = "wavespeed-ai/z-image-turbo/controlnet"
STRUCTURE_FILTER_MODEL = "wavespeed-ai/flux-controlnet-union-pro-2.0"


def _controls(inputs: dict) -> list[dict]:
    """All structure refs of a job (#80): `controls` list (each with its own `image`), or the legacy single `control`."""
    cs = inputs.get("controls")
    if isinstance(cs, list):
        return [c for c in cs if isinstance(c, dict)]
    c = inputs.get("control")
    return [{**c, "image": c.get("image") or inputs.get("image")}] if isinstance(c, dict) else []


def _full_window(c: dict) -> bool:
    return float(c.get("start", 0)) <= 0 and float(c.get("end", 100)) >= 100


def structure_model(mode: str, count: int = 1, full_window: bool = True) -> str:
    """Pose alone with the default 0-100 window uses z-image-turbo/controlnet, which extracts the skeleton
    itself (WaveSpeed has no pose estimator and z-image returns no pose map). z-image has no start/end, so a
    pose ref with a custom window, or mixed with other refs, goes to flux-controlnet-union-pro-2.0 with a
    soft-edge map of the pose reference instead of being dropped (#80)."""
    if mode in refprep.EXTRACTED and count == 1 and full_window:
        return STRUCTURE_EXTRACT_MODEL
    return STRUCTURE_FILTER_MODEL


def _structure_pick(inputs: dict) -> str:
    cs = _controls(inputs)
    c = cs[0] if cs else {}
    return structure_model(str(c.get("mode") or ""), len(cs), _full_window(c))


def _map_steps(inputs: dict) -> list[str]:
    """Features of the extra cloud map calls (depth-anything / sam3) a structure job runs before control.
    #135: a seg map is one caption call plus up to SEG_MAX_CLASSES sam3 calls. Nothing is recognised before the
    confirm, so the quote is that upper bound; the job is charged per class actually found."""
    steps: list[str] = []
    for c in _controls(inputs):
        mode = str(c.get("mode") or "")
        if mode not in refprep.CLOUD_MAP or _map_key(c) in _map_cache:
            continue
        if mode == "seg":
            steps += _seg_steps(str(c.get("image") or ""))
        else:
            steps.append(refprep.CLOUD_MAP[mode][0])
    return steps


SEG_NONE = "No segmentable objects found; only the one recognition call was charged"  # zh: jobs.segNone
SEG_ALL_BLACK = "Only classes with the same color as the background were found, so the map would be all black; stopped, only the recognition call was charged"  # zh: jobs.segAllBlack
_seg_cats: dict[str, list[str]] = {}
# #138: one sam3 mask per (image, class); a retry reruns only the classes that have no mask yet
_seg_masks: dict[tuple[str, str], bytes] = {}


def _seg_steps(image: str) -> list[str]:
    """Paid calls a seg map still needs. Before recognition: caption + SEG_MAX_CLASSES sam3 (upper bound).
    After (e.g. a retry): only the classes whose mask is not cached yet, no second caption."""
    if image in _seg_cats:
        return ["segment"] * sum(1 for l in _seg_cats[image] if (image, l) not in _seg_masks)
    return ["caption"] + ["segment"] * refprep.SEG_MAX_CLASSES


async def _seg_categories(image: str) -> list[str]:
    """#135: COCO classes in the image, from one captioner call (cached per image). Only called after the
    user confirmed: nothing is charged before the confirm dialog. None found -> SEG_NONE before any sam3
    call is made, so only the captioner was charged."""
    if image not in _seg_cats:
        text = await run_text({"feature": "caption", "image": image, "confirmed": True})
        _seg_cats[image] = refprep.seg_categories(text)
    if not _seg_cats[image]:
        raise WaveSpeedError(SEG_NONE, 422)
    if all(refprep.SEG_COLORS[l] == (0, 0, 0) for l in _seg_cats[image]):
        # upstream palette unchanged: class 0 (person) is black like unlabeled, so the map would be all black
        raise WaveSpeedError(SEG_ALL_BLACK, 422)
    return _seg_cats[image]




def _seg_max_splits(inputs: dict) -> int | None:
    """#135: upper bound of sam3 calls for the confirm dialog (no recognition before the confirm)."""
    n = sum(1 for f in _map_steps(inputs) if f == "segment")
    return n or None


async def _semantic_map(image: str) -> bytes:
    """Upstream OneFormer COCO seg map rebuilt in the cloud: caption -> sam3 per class -> upstream palette."""
    masks = []
    for label in await _seg_categories(image):
        if (image, label) not in _seg_masks:
            _seg_masks[(image, label)] = await _cloud_map("segment", {"apply_mask": False, "output_format": "png"}, image, refprep.seg_name(label))
        masks.append((label, _seg_masks[(image, label)]))
    return refprep.to_png(refprep.semantic_map(masks))


# #81: cloud maps (depth / normal / seg) already extracted for a preview, keyed on (src, mode, res), so the
# job that follows reuses the map with no second extraction or charge while those three are unchanged.
_map_cache: dict[tuple[str, str, int], bytes] = {}
_MAP_CACHE_MAX = 32


def _map_key(c: dict, res_default: int = 1024) -> tuple[str, str, int]:
    return (str(c.get("image") or ""), str(c.get("mode") or ""), int(c.get("res") or res_default))


async def _steps_price(inputs: dict) -> float | None:
    total = 0.0
    for feature in _map_steps(inputs):
        price, _ = await quote(resolve_model(feature, None), {})
        if price is None:
            return None
        total += float(price)
    return total


async def _source_bytes(value: str) -> bytes:
    if value.startswith(("http://", "https://")):
        # separate session: never send the WaveSpeed key to another host
        async with aiohttp.ClientSession() as plain, plain.get(value) as res:
            if res.status >= 400:
                raise WaveSpeedError(f"could not read reference image ({res.status})", 400)
            return await res.read()
    path = _local_path(value)
    if not path or not os.path.isfile(path):
        raise WaveSpeedError(f"input file not found: {value}", 400)
    return _read(path)


async def _prepped(session: aiohttp.ClientSession, value: str, mode: str, res: int = 1024, size=None, resize: str = "crop") -> str:
    data = refprep.process_bytes(await _source_bytes(value), mode, res, size, resize)
    return await _upload(session, "", data, f"ref-{mode}-{uuid.uuid4().hex[:8]}.png")


async def _cloud_map(feature: str, params: dict, image: str, prompt: str = "") -> bytes:
    """One paid map call (depth-anything-v3 / sam3-image); already covered by the confirmed estimate.
    #120: the seg map passes this generation's prompt to sam3-image as its text prompt."""
    outs = await run_raw({"feature": feature, "image": image, "params": dict(params), "confirmed": True,
                          **({"prompt": prompt} if prompt else {})})
    if not outs:
        raise WaveSpeedError(f"{feature} returned no map", 502)
    return await _source_bytes(str(outs[0]))


async def _control_map(c: dict, size, res_default: int = 1024, fresh: bool = False):
    mode = str(c.get("mode") or "")
    res, resize = int(c.get("res") or res_default), str(c.get("resize") or "crop")
    if mode in refprep.CLOUD_MAP:
        key = _map_key(c, res_default)
        data = None if fresh else _map_cache.get(key)  # fresh: 「重新提取」 forces a new paid extraction
        if data is None:
            feature, params = refprep.CLOUD_MAP[mode]
            data = await _semantic_map(str(c["image"])) if mode == "seg" else await _cloud_map(feature, params, str(c["image"]), str(c.get("prompt") or "").strip() if feature == "segment" else "")
            _map_cache.pop(key, None)  # the new map replaces the old entry
            if len(_map_cache) >= _MAP_CACHE_MAX:
                _map_cache.pop(next(iter(_map_cache)))
            _map_cache[key] = data
    else:
        data = await _source_bytes(str(c["image"]))
    # no pose estimator on WaveSpeed: on flux a pose ref guides through its soft-edge map
    return refprep.process_image(data, refprep.POSE_FALLBACK if mode in refprep.EXTRACTED else mode, res, size, resize)


def preview_estimate(inputs: dict) -> list[str]:
    """Map-call features a preview request would pay for: none when cached, unless `fresh` (re-extract)."""
    image, mode, res = str(inputs.get("image") or ""), str(inputs.get("mode") or ""), int(inputs.get("res") or 1024)
    if mode not in refprep.CLOUD_MAP or (not inputs.get("fresh") and (image, mode, res) in _map_cache):
        return []
    if mode == "seg":
        return ["caption"] + ["segment"] * refprep.SEG_MAX_CLASSES if inputs.get("fresh") else _seg_steps(image)
    return [refprep.CLOUD_MAP[mode][0]]


async def control_preview(inputs: dict) -> bytes:
    """Upstream previewControl (#81): the control map one structure / color ref produces, as PNG.
    Filtered modes are local Pillow filters (free); depth / normal / seg run their paid cloud map call
    first, so they go through the same cost confirmation as a job. Pose has no cloud estimator: the
    preview is the soft-edge map the flux path uses (the z-image default path extracts its skeleton itself)."""
    image, mode = str(inputs.get("image") or ""), str(inputs.get("mode") or "")
    if not image or not mode:
        raise WaveSpeedError("image and mode are required", 400)
    res = int(inputs.get("res") or 1024)
    # #81: `fresh` is 「重新提取」 — skip the cache, re-run (and re-confirm) the paid extraction
    fresh = bool(inputs.get("fresh"))
    # #109: one rule — preview_estimate says which map calls this request pays for (none when cached, unless fresh)
    prompt = str(inputs.get("prompt") or "").strip()
    if fresh and mode == "seg":
        # #138: re-extract drops recognition + per-class masks *before* the quote, so it always re-confirms
        # at the upper bound (the retry-only-missing-classes cache is for retries after a failure)
        _seg_cats.pop(image, None)
        for k in [k for k in _seg_masks if k[0] == image]:
            _seg_masks.pop(k)
    paid = [] if inputs.get("confirmed") else preview_estimate({"image": image, "mode": mode, "res": res, "fresh": fresh})
    splits = paid.count("segment") if paid and mode == "seg" else None
    capped = "caption" in paid
    if paid:
        price = 0.0
        for f in paid:
            p, _ = await quote(resolve_model(f, None), {})
            price = None if p is None or price is None else price + float(p)
        price = None if price is None else round(price, 6)
        if price is not None and needs_confirm(price):
            raise WaveSpeedError(f"control map preview costs about ${price}; confirm to continue", 409, confirm=float(price), seg_splits=splits, seg_capped=capped)
    if mode in refprep.COLOR:
        return refprep.process_bytes(await _source_bytes(image), mode, res)
    return refprep.to_png(await _control_map({"image": image, "mode": mode, "res": res, "prompt": prompt}, None, fresh=fresh))


async def _prepare(session: aiohttp.ClientSession, model: str, inputs: dict) -> dict:
    """Structure control (#80): every structure ref becomes the control model's fields with its knobs;
    color modes replace their reference with the processed image (upstream preprocessor nodes)."""
    controls = _controls(inputs)
    inputs = dict(inputs)
    inputs.pop("control", None)
    inputs.pop("controls", None)
    w, h = inputs.get("width"), inputs.get("height")
    size = (int(w), int(h)) if w and h else None
    controls = [c for c in controls if c.get("image")]
    if controls:
        params = dict(inputs.get("params") or {})
        strengths = [float(c.get("strength", 80)) / 100 for c in controls]
        if model == STRUCTURE_EXTRACT_MODEL:
            c = controls[0]
            # z-image takes the raw ref (WaveSpeed extracts the skeleton); apply the resolution / fit knobs before upload
            data = refprep.scale_fit(await _source_bytes(str(c["image"])), int(c.get("res") or 1024), size, str(c.get("resize") or "crop"))
            inputs["image"] = await _upload(session, "", refprep.to_png(data), f"ref-pose-{uuid.uuid4().hex[:8]}.png")
            params.update({"mode": "pose" if c.get("mode") == "pose" else "canny", "strength": min(1.0, strengths[0])})
        else:
            inputs.pop("image", None)
            maps = [await _control_map({**c, "prompt": inputs.get("prompt")}, size) for c in controls]
            img = maps[0] if len(maps) == 1 else refprep.composite(list(zip(maps, strengths)), size or maps[0].size)
            params.update({
                "control_image": await _upload(session, "", refprep.to_png(img), f"ref-control-{uuid.uuid4().hex[:8]}.png"),
                "controlnet_conditioning_scale": min(2.0, max(strengths)),
                # one control_image: the guidance window spans every ref's start..end
                "control_guidance_start": min(float(c.get("start", 0)) for c in controls) / 100,
                "control_guidance_end": max(float(c.get("end", 100)) for c in controls) / 100,
            })
        inputs["params"] = params
    prep = inputs.pop("prep", None)
    if prep and inputs.get("images"):
        inputs["images"] = [await _prepped(session, v, m) if m in refprep.COLOR else v for v, m in zip(inputs["images"], list(prep) + [None] * len(inputs["images"]))]
    return inputs


async def submit(inputs: dict) -> str:
    if isinstance(inputs.get("scenes"), list):
        return await _submit_scenes(inputs)
    if inputs.get("feature") == "mockup_surface":
        return await _submit_surface(inputs)
    feature = feature_of(str(inputs.get("feature") or ""))
    if inputs.get("custom"):
        model = custom_model(inputs.get("model"), await catalog())
    else:
        picked = inputs.get("model")
        if feature == "structure_control" and not picked:
            picked = _structure_pick(inputs)
        model = resolve_model(feature, picked)
    _check_limits()
    meta = (await catalog()).get(model)
    if meta and needs_voice_sample(model, feature, _schema(meta), inputs):
        raise WaveSpeedError(VOICE_SAMPLE_MISSING, 400)
    if feature == "segment" or model == SAM3_MODEL:
        inputs = await seg_prompts(inputs)
    if not inputs.get("confirmed"):
        splits = _seg_max_splits(inputs) if feature == "structure_control" else None
        capped = feature == "structure_control" and "caption" in _map_steps(inputs)
        price, _ = await quote(model, inputs)
        if feature == "structure_control" and price is not None:
            extra = await _steps_price(inputs)
            price = None if extra is None else round(float(price) + extra, 6)
        if price is not None and needs_confirm(price):
            # expensive job: the page asks the user and resubmits with confirmed=true
            raise WaveSpeedError(f"{model} costs about ${price} per run; confirm to continue", 409, confirm=float(price), seg_splits=splits, seg_capped=capped)
    async with aiohttp.ClientSession(headers=_headers()) as session:
        payload = await build_payload(session, _schema(meta), await _prepare(session, model, inputs), model)
        _submits.append(time.time())
        # never auto-retry a submit: a retry could be charged twice
        async with session.post(f"{_base()}/api/v3/{model}", json=payload) as res:
            body = await _json(res)
            if res.status >= 400:
                raise _status_error(res.status, body)
    task = ((body or {}).get("data") or {}).get("id")
    if not task:
        raise WaveSpeedError("WaveSpeed did not return a task id")
    _jobs[task] = {"model": model, "feature": feature, "started": time.time(), "next_poll": time.time() + POLL_MIN,
                   "inputs": _price_inputs(inputs)}
    log.info("WaveSpeed task %s submitted (%s)", task, model)
    return task


async def _submit_scenes(inputs: dict) -> str:
    """Storyboard: scenes run one after another on image-to-video, each starting from the
    previous clip's last frame; the clips are then concatenated locally (no model)."""
    scenes = [sc for sc in inputs["scenes"] if isinstance(sc, dict) and str(sc.get("prompt") or "").strip()]
    if not scenes:
        raise WaveSpeedError("storyboard has no scenes", 400)
    base = {k: v for k, v in inputs.items() if k != "scenes"}
    feature = "image_to_video" if base.get("image") else "text_to_video"
    first_model = resolve_model(feature, base.get("model") if feature == base.get("feature") else None)
    chain_model = resolve_model("image_to_video", base.get("model") if base.get("feature") == "image_to_video" else None)
    total = (await estimate({**base, "scenes": scenes}))["price"] or 0.0
    if needs_confirm(total) and not base.get("confirmed"):
        raise WaveSpeedError(f"{len(scenes)} scenes cost about ${total:.2f}; confirm to continue", 409, confirm=round(total, 2))
    jobs = [{**base, "feature": feature if i == 0 else "image_to_video", "model": first_model if i == 0 else chain_model,
             "confirmed": True, "prompt": str(sc["prompt"]), **({"duration": sc["duration"]} if sc.get("duration") else {})}
            for i, sc in enumerate(scenes)]
    first = await submit(jobs[0])
    group = f"sb-{first}"
    _jobs[group] = {"group": [first], "pending": jobs[1:], "clips": [], "started": time.time(), "next_poll": 0.0, "done": False}
    return group


async def _submit_surface(inputs: dict) -> str:
    """Mockup surface (upstream mockup-surface.api.json): depth map + subject mask of one photo.
    Depth Anything replaces DepthAnythingV2Preprocessor, the background remover replaces BiRefNet."""
    if not inputs.get("image"):
        raise WaveSpeedError("mockup needs an image", 400)
    image = inputs["image"]
    depth = await submit({"feature": "depth_estimation", "image": image, "params": {"colormap": "grayscale", "output_format": "png"}})
    cut = await submit({"feature": "remove_background", "image": image, "png": True})
    group = f"ms-{depth}"
    _jobs[group] = {"surface": [depth, cut], "started": time.time(), "next_poll": 0.0, "done": False}
    return group


def cutout_to_mask(data: bytes) -> bytes:
    """Background-remover cutout (subject on transparent) -> white subject on black, like MaskToImage."""
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    alpha = img.convert("RGBA").getchannel("A")
    buf = io.BytesIO()
    alpha.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


async def _poll_surface(group: str, job: dict) -> dict:
    refs = []
    for task in job["surface"]:
        entry = (await poll(task)).get(f"ws:{task}") or {}
        status = entry.get("status") or {}
        if status.get("status_str") == "error":
            job["done"] = True
            job["result"] = _history(group, "failed", status.get("messages") or [], {})
            return job["result"]
        if not status.get("completed"):
            return _history(group, "processing", [], {})
        img = (((entry.get("outputs") or {}).get("ws") or {}).get("images") or [None])[0]
        if img is None:
            return _fail(group, "mockup surface finished without output")
        refs.append(img)
    depth, cut = refs
    mask = {"filename": f"ws_{group[:15]}_mask.png", "subfolder": SUBFOLDER, "type": "output"}
    try:
        _write(_ref_path(mask), cutout_to_mask(_read(_ref_path(cut))))
    except (OSError, ValueError) as e:
        return _fail(group, f"mockup mask failed: {e}")
    job["done"] = True
    job["result"] = _history(group, "completed", [], {"ws": {"images": [depth]}, "mask": {"images": [mask]}})
    return job["result"]


def _last_frame(video_path: str, out_path: str) -> None:
    import av  # ships with ComfyUI
    last = None
    with av.open(video_path) as box:
        for frame in box.decode(video=0):
            last = frame
    if last is None:
        raise WaveSpeedError("storyboard clip has no frames")
    last.to_image().save(out_path)


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError as e:
            raise WaveSpeedError("ffmpeg is needed to join storyboard clips") from e
    return exe


def _concat(paths: list[str], out_path: str) -> None:
    # same as the local graph: keep clip 1, drop the first frame (= previous last frame) of later clips
    args = [_ffmpeg(), "-y", "-loglevel", "error"]
    for p in paths:
        args += ["-i", p]
    parts, n = [], len(paths)
    for i in range(n):
        drop = "" if i == 0 else "select=gte(n\\,1),"
        parts.append(f"[{i}:v]{drop}setpts=N/FRAME_RATE/TB[v{i}]")
    parts.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]")
    subprocess.run(args + ["-filter_complex", ";".join(parts), "-map", "[v]", "-pix_fmt", "yuv420p", out_path], check=True)


def _ref_path(ref: dict) -> str:
    return os.path.join(os.path.abspath(folder_paths.get_output_directory()), ref["subfolder"], ref["filename"])


async def _poll_group(group: str, job: dict) -> dict:
    task = job["group"][-1]
    entry = (await poll(task)).get(f"ws:{task}") or {}
    status = entry.get("status") or {}
    if status.get("status_str") == "error":
        job["done"] = True
        job["result"] = _history(group, "failed", status.get("messages") or [], {})
        return job["result"]
    if not status.get("completed"):
        return _history(group, "processing", [], {})
    clip = (((entry.get("outputs") or {}).get("ws") or {}).get("images") or [None])[0]
    if clip is None:
        return _fail(group, "storyboard scene finished without a clip")
    job["clips"].append(clip)
    try:
        if job["pending"]:
            nxt = job["pending"].pop(0)
            name = f"ws_{group[:15]}_last{len(job['clips'])}.png"
            os.makedirs(folder_paths.get_input_directory(), exist_ok=True)
            await asyncio.to_thread(_last_frame, _ref_path(clip), os.path.join(folder_paths.get_input_directory(), name))
            job["group"].append(await submit({**nxt, "image": f"{name} [input]"}))
            return _history(group, "processing", [], {})
        out = {"filename": f"ws_{group[:15]}_storyboard.mp4", "subfolder": SUBFOLDER, "type": "output"}
        await asyncio.to_thread(_concat, [_ref_path(c) for c in job["clips"]], _ref_path(out))
    except (OSError, subprocess.CalledProcessError) as e:
        return _fail(group, f"storyboard failed: {e}")
    except WaveSpeedError as e:
        return _fail(group, str(e))
    job["done"] = True
    job["result"] = _history(group, "completed", [], {"ws": {"images": [out]}})
    return job["result"]


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
            if res.status >= 500 or res.status == 429:
                raise _Transient(f"download HTTP {res.status}")
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
    if job.get("group"):
        return await _poll_group(task, job)
    if job.get("surface"):
        return await _poll_surface(task, job)
    now = time.time()
    if now - job["started"] > JOB_TIMEOUT:
        if job.get("model"):
            return _fail(task, str(await _timeout_error(task)))
        return _fail(task, f"WaveSpeed task timed out after {int(JOB_TIMEOUT)}s")
    if now < job["next_poll"]:
        return _history(task, "processing", [], {})
    job["next_poll"] = now + POLL_MIN
    try:
        return await _poll_once(task, job, now)
    except (TimeoutError, asyncio.TimeoutError, aiohttp.ClientError, OSError) as e:
        # result GET is free: a network blip only delays the next check, never resubmits
        return _backoff(task, job, now, type(e).__name__)
    except _Transient as e:
        return _backoff(task, job, now, str(e))


class _Transient(Exception):
    """Retryable result/download failure (5xx)."""


def _backoff(task: str, job: dict, now: float, reason: str) -> dict:
    n = job.get("errors", 0)
    job["errors"] = n + 1
    job["next_poll"] = now + min(max(POLL_MIN, 0.01) * 2 ** n, POLL_MAX_BACKOFF)
    log.warning("WaveSpeed poll for %s hit a transient error (%s), retry #%d", task, reason, n + 1)
    return _history(task, "processing", [], {})


async def _poll_once(task: str, job: dict, now: float) -> dict:
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
                raise _Transient(f"HTTP {res.status}")
        job["errors"] = 0
        data = (body or {}).get("data") or {}
        status = data.get("status")
        if status == "timeout":
            return _fail(task, str(await _timeout_error(task)))
        if status in FAILED_STATUSES:
            return _fail(task, f"WaveSpeed task {status}: {data.get('error') or 'unknown error'}")
        if status != "completed":
            return _history(task, status or "processing", [], {})
        outputs = [o for o in (data.get("outputs") or []) if isinstance(o, str) and o.startswith(("http://", "https://"))]
        if not outputs:
            # #120: text-only results (or nothing) can't be saved as files; never report an empty success
            return _fail(task, NO_OUTPUT)
        # CDN URLs expire after 7 days: keep a local copy right away
        refs = [await _download(session, task, i, url) for i, url in enumerate(outputs) if isinstance(url, str)]
    job["done"] = True
    job["result"] = _history(task, "completed", [], {"ws": {"images": refs}})
    log.info("WaveSpeed task %s completed (%d output%s)", task, len(refs), "" if len(refs) == 1 else "s")
    return job["result"]


FAILED_STATUSES = ("failed", "cancelled", "timeout", "deleted")
TEXT_KEYS = ("text", "transcription", "caption", "result", "output", "content")
NO_OUTPUT = "WaveSpeed task finished without output"
NO_TEXT = "WaveSpeed task finished without text"


async def _timeout_error(task: str) -> "WaveSpeedError":
    """#120: a timed-out task may still be billed; say how much (free price quote) instead of 'please retry'."""
    job = _jobs.get(task) or {}
    price = None
    if job.get("model"):
        try:
            price, _ = await quote(job["model"], dict(job.get("inputs") or {}))
        except Exception:  # noqa: BLE001 - the message is still useful without a price
            price = None
    if price is None:
        return WaveSpeedError("WaveSpeed task timed out", 504)
    return WaveSpeedError(f"WaveSpeed task timed out, may have been charged about (quoted price) ${round(float(price), 6):g}", 504)


def text_of(value) -> str:
    """Text from one text-model output: a plain string, a JSON string, or an object with a text-like field."""
    if isinstance(value, str):
        v = value.strip()
        if v[:1] in "{[":
            try:
                return text_of(json.loads(v))
            except ValueError:
                return v
        return v
    if isinstance(value, list):
        return "\n".join(t for t in (text_of(x) for x in value) if t)
    if isinstance(value, dict):
        for k in TEXT_KEYS:
            if value.get(k):
                return text_of(value[k])
        if isinstance(value.get("segments"), list):
            return " ".join(t for t in (text_of(x) for x in value["segments"]) if t)
    return ""


async def run_text(inputs: dict) -> str:
    """Text models (whisper transcribe, image captioner): outputs may be text, JSON objects or text-file URLs."""
    parts = []
    for out in await run_raw(inputs):
        if isinstance(out, str) and out.startswith(("http://", "https://")):
            out = await fetch_text(out)
        parts.append(text_of(out))
    text = "\n".join(p for p in parts if p)
    if not text:
        raise WaveSpeedError(NO_TEXT, 502)
    return text


async def run_raw(inputs: dict, timeout: float = 120.0) -> list:
    """Submit and wait for a small job whose outputs are read directly (e.g. OCR text), not downloaded."""
    task = await submit(inputs)
    deadline = time.time() + timeout
    try:
        async with aiohttp.ClientSession(headers=_headers()) as session:
            while time.time() < deadline:
                await asyncio.sleep(max(POLL_MIN, 0.01))
                try:
                    async with session.get(f"{_base()}/api/v3/predictions/{task}/result") as res:
                        body = await _json(res)
                        if res.status == 429 or res.status >= 500:
                            continue
                        if res.status >= 400:
                            raise _status_error(res.status, body)
                except (TimeoutError, asyncio.TimeoutError, aiohttp.ClientError):
                    continue  # free result GET: retry until the deadline, never resubmit
                data = (body or {}).get("data") or {}
                status = data.get("status")
                if status == "timeout":
                    raise await _timeout_error(task)
                if status in FAILED_STATUSES:
                    raise WaveSpeedError(f"WaveSpeed task {status}: {data.get('error') or 'unknown error'}")
                if status == "completed":
                    outs = [o for o in (data.get("outputs") or []) if o not in (None, "", [], {})]
                    if not outs:
                        # some text models put the result next to outputs instead of inside it
                        outs = [data[k] for k in TEXT_KEYS if isinstance(data.get(k), (str, dict, list)) and data.get(k)]
                    if not outs:
                        raise WaveSpeedError(NO_OUTPUT, 502)
                    return outs
        raise await _timeout_error(task)
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
        if e.seg_splits is not None:
            body["seg_splits"] = e.seg_splits
            body["seg_capped"] = e.seg_capped
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


@routes.post("/comfyart/wavespeed/control_preview")
async def wavespeed_control_preview(request: web.Request) -> web.Response:
    inputs = (await json_body(request)).get("inputs")
    if not isinstance(inputs, dict):
        return error("inputs must be an object", 400)
    try:
        return web.Response(body=await control_preview(inputs), content_type="image/png")
    except WaveSpeedError as e:
        return _respond_error(e)
    except aiohttp.ClientError as e:
        return _respond_error(WaveSpeedError(f"could not reach WaveSpeed: {e}"))


@routes.post("/comfyart/wavespeed/estimate")
async def wavespeed_estimate(request: web.Request) -> web.Response:
    inputs = (await json_body(request)).get("inputs")
    if not isinstance(inputs, dict):
        return error("inputs must be an object", 400)
    try:
        return web.json_response(await estimate(inputs))
    except WaveSpeedError as e:
        return _respond_error(e)


@routes.get("/comfyart/wavespeed/confirm")
async def wavespeed_confirm_get(_request: web.Request) -> web.Response:
    return web.json_response({"confirm_usd": confirm_usd()})


@routes.put("/comfyart/wavespeed/confirm")
async def wavespeed_confirm_put(request: web.Request) -> web.Response:
    v = (await json_body(request)).get("confirm_usd")
    if not valid_confirm_usd(v):
        return error("confirm_usd must be a number from 0 to 1000 (0 = always confirm)", 400)
    path = app_path(PREFS_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"confirm_usd": float(v)}, f)
    return web.json_response({"confirm_usd": float(v)})


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
        text = await run_text({"feature": "transcribe", "audio": src})
    except WaveSpeedError as e:
        return _respond_error(e)
    except ValueError as e:
        return error(str(e), 404)
    return web.json_response({"text": text})


@routes.post("/comfyart/wavespeed/caption")
async def wavespeed_caption(request: web.Request) -> web.Response:
    src = (await json_body(request)).get("src")
    if not isinstance(src, str) or not src:
        return error("src must be a /api/view URL", 400)
    try:
        text = await run_text({"feature": "caption", "image": src})
    except WaveSpeedError as e:
        return _respond_error(e)
    except ValueError as e:
        return error(str(e), 404)
    return web.json_response({"text": text})


@routes.post("/comfyart/wavespeed/custom/check")
async def wavespeed_custom_check(request: web.Request) -> web.Response:
    body = await json_body(request)
    try:
        meta = await catalog()
    except WaveSpeedError as e:
        return _respond_error(e)
    return web.json_response(check_custom(body.get("spec") or {}, list(body.get("required") or []), list(body.get("optional") or []), meta))


@routes.get("/comfyart/wavespeed/models")
async def wavespeed_models(request: web.Request) -> web.Response:
    return web.json_response({"enabled": has_key(), "stale": bool(_catalog.get("stale")), "features": await grouped_models(request.query.get("refresh") == "1")})


async def fetch_balance(key: str) -> float:
    """Free GET /api/v3/balance. Raises WaveSpeedError: 401 invalid key, 503 network, other codes as-is."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(f"{_base()}/api/v3/balance", headers={"Authorization": f"Bearer {key}"}) as res:
                body = await _json(res)
                if res.status in (401, 403):
                    raise WaveSpeedError("WaveSpeed rejected the API key", 401)
                if res.status != 200 or not isinstance(body, dict) or body.get("code") not in (None, 200):
                    raise _status_error(res.status if res.status != 200 else 502, body)
                balance = (body.get("data") or {}).get("balance")
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
        raise WaveSpeedError(f"could not reach WaveSpeed ({type(e).__name__})", 503) from e
    if not isinstance(balance, (int, float)):
        raise WaveSpeedError("WaveSpeed returned no balance", 502)
    return float(balance)


def _key_status(balance: float | None = None, err: str | None = None) -> dict:
    key, source = key_source()
    out: dict = {"configured": bool(key), "source": source, "last4": key[-4:] if len(key) >= 8 else "", "balance": balance}
    if err:
        out["error"] = err
    return out


def _reason(e: WaveSpeedError) -> str:
    return {401: "invalid", 503: "network"}.get(e.status, "error")


@routes.get("/comfyart/wavespeed/key")
async def wavespeed_key_status(request: web.Request) -> web.Response:
    """Key status for Settings and the top bar: never the key itself, only source + last 4 + balance."""
    key = key_source()[0]
    if not key or request.query.get("balance") == "0":
        return web.json_response(_key_status())
    try:
        return web.json_response(_key_status(await fetch_balance(key)))
    except WaveSpeedError as e:
        return web.json_response(_key_status(err=_reason(e)))


@routes.put("/comfyart/wavespeed/key")
async def wavespeed_key_save(request: web.Request) -> web.Response:
    if key_source()[1] == "env":
        return error("the key comes from WAVESPEED_API_KEY and can't be changed here", 409)
    key = str((await json_body(request)).get("key") or "").strip()
    if not key or len(key) > 512 or any(c.isspace() for c in key):
        return error("enter a WaveSpeed API key", 400)
    try:
        balance = await fetch_balance(key)
    except WaveSpeedError as e:
        # invalid or unreachable keys are not saved; the reason drives the message in Settings
        return web.json_response({"error": {"message": str(e), "reason": _reason(e)}}, status=e.status)
    _save_key(key)
    log.info("[ComfyArt] WaveSpeed key saved in settings")
    return web.json_response(_key_status(balance))


@routes.delete("/comfyart/wavespeed/key")
async def wavespeed_key_delete(_request: web.Request) -> web.Response:
    _delete_key()
    return web.json_response(_key_status())


def check_key_at_startup() -> None:
    """Validate the key once with the free /balance endpoint and log pass/fail (never the key itself)."""
    key = key_source()[0]
    if not key:
        log.warning("[ComfyArt] no WaveSpeed key (Settings or WAVESPEED_API_KEY): cloud generation is disabled")
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
