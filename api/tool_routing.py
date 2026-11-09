"""Per-tool provider routes and the fallback rules.

A tool that has no saved route keeps the existing WaveSpeed path. Saving one
tool never changes another. Fallback is off until an admin saves it on, and it
runs at most once, only when the provider contract says no task was created.
"""
from __future__ import annotations

import json

from .provider_catalog import IMAGE_PROVIDERS, image_model

FLARE = "openai/gpt-image-2.6-flare"
SUNBURST = "openai/gpt-image-2.6-sunburst"
CONNECTED = (FLARE, SUNBURST)

# User-facing tools. `match` is how a request is recognized when it does not
# already carry tool=. Shared features stay distinct: 改图 is custom=edit,
# 改字 is the same custom with the toolbar's text prompt, 风格 is custom=style.
TOOLS = [
    {"id": "generate_image", "group": "image", "label": {"zh": "生成图片", "en": "Generate image"},
     "blurb": {"zh": "用文字生成图片。带参考图时仍保留图片。", "en": "Text to image. Reference images stay attached."},
     "caps": ["text_to_image", "image_edit", "text_to_gif", "reference_gif"], "wavespeed_backup": ["text_to_image", "image_edit", "text_to_gif"]},
    {"id": "edit_image", "group": "image", "label": {"zh": "改图", "en": "Edit image"},
     "blurb": {"zh": "按说明改一张已有的图。", "en": "Edit an existing image from instructions."},
     "caps": ["image_edit"], "wavespeed_backup": ["image_edit"]},
    {"id": "to_gif", "group": "image", "label": {"zh": "静图转动图", "en": "Still to GIF"},
     "blurb": {"zh": "保留这张图，做成循环 GIF。", "en": "Keep this still and make a looping GIF."},
     "caps": ["reference_gif"], "wavespeed_backup": []},
    {"id": "replace_text", "group": "image", "label": {"zh": "改字", "en": "Replace text"},
     "blurb": {"zh": "只改画面里的文字。", "en": "Change only the text in the image."},
     "caps": ["image_edit"], "wavespeed_backup": ["image_edit"]},
    {"id": "style_transfer", "group": "image", "label": {"zh": "风格迁移", "en": "Style transfer"},
     "blurb": {"zh": "换成另一种画风，主体还在。", "en": "Restyle the image and keep the subject."},
     "caps": ["image_edit"], "wavespeed_backup": ["image_edit"]},
    {"id": "upscale_image", "group": "image", "label": {"zh": "放大图片", "en": "Upscale image"},
     "blurb": {"zh": "把图片放大变清晰。", "en": "Enlarge an image."},
     "caps": [], "wavespeed_backup": []},
    {"id": "remove_background", "group": "image", "label": {"zh": "去背景", "en": "Remove background"},
     "blurb": {"zh": "抠出主体。", "en": "Cut the subject out."},
     "caps": [], "wavespeed_backup": []},
    {"id": "expand_image", "group": "image", "label": {"zh": "扩图", "en": "Expand image"},
     "blurb": {"zh": "把画面向外补全。", "en": "Extend the canvas outward."},
     "caps": [], "wavespeed_backup": []},
    {"id": "change_angle", "group": "image", "label": {"zh": "换角度", "en": "Change angle"},
     "blurb": {"zh": "换一个观看角度。", "en": "Show the subject from another angle."},
     "caps": [], "wavespeed_backup": []},
    {"id": "erase_region", "group": "image", "label": {"zh": "消除", "en": "Erase"},
     "blurb": {"zh": "擦掉选中的区域。", "en": "Remove the painted area."},
     "caps": [], "wavespeed_backup": []},
    {"id": "split_layers", "group": "image", "label": {"zh": "拆图层", "en": "Split layers"},
     "blurb": {"zh": "把一张图拆成几层。", "en": "Split one image into layers."},
     "caps": [], "wavespeed_backup": []},
    {"id": "edit_elements", "group": "image", "label": {"zh": "选元素", "en": "Select elements"},
     "blurb": {"zh": "按文字选出画面里的东西。", "en": "Select objects from a description."},
     "caps": [], "wavespeed_backup": []},
    {"id": "create_mockup", "group": "image", "label": {"zh": "样机", "en": "Mockup"},
     "blurb": {"zh": "贴到样机场景里。", "en": "Place the design on a mockup."},
     "caps": [], "wavespeed_backup": []},
    {"id": "generate_video", "group": "video", "label": {"zh": "生成视频", "en": "Generate video"},
     "blurb": {"zh": "文生或图生视频。不会自动改供应商。", "en": "Text or image to video. The provider is not switched automatically."},
     "caps": [], "wavespeed_backup": []},
    {"id": "animate_image", "group": "video", "label": {"zh": "图生动效", "en": "Animate image"},
     "blurb": {"zh": "让一张图动起来，这是视频，不是 GIF。", "en": "Motion from a still. This is video, not a GIF."},
     "caps": [], "wavespeed_backup": []},
    {"id": "extend_video", "group": "video", "label": {"zh": "延长视频", "en": "Extend video"},
     "blurb": {"zh": "把视频往后接一段。", "en": "Continue a video."},
     "caps": [], "wavespeed_backup": []},
    {"id": "upscale_video", "group": "video", "label": {"zh": "放大视频", "en": "Upscale video"},
     "blurb": {"zh": "提高视频清晰度。", "en": "Enlarge a video."},
     "caps": [], "wavespeed_backup": []},
    {"id": "remove_video_background", "group": "video", "label": {"zh": "视频去背景", "en": "Remove video background"},
     "blurb": {"zh": "抠掉视频背景。", "en": "Cut a video background."},
     "caps": [], "wavespeed_backup": []},
    {"id": "generate_music", "group": "other", "label": {"zh": "音乐", "en": "Music"},
     "blurb": {"zh": "生成一段音乐。", "en": "Generate music."},
     "caps": [], "wavespeed_backup": []},
    {"id": "generate_sound_effect", "group": "other", "label": {"zh": "音效", "en": "Sound effect"},
     "blurb": {"zh": "生成音效。", "en": "Generate a sound effect."},
     "caps": [], "wavespeed_backup": []},
    {"id": "text_to_speech", "group": "other", "label": {"zh": "朗读", "en": "Speech"},
     "blurb": {"zh": "把文字读出来。", "en": "Read text aloud."},
     "caps": [], "wavespeed_backup": []},
    {"id": "image_to_3d", "group": "other", "label": {"zh": "图生三维", "en": "Image to 3D"},
     "blurb": {"zh": "由图片生成三维模型。", "en": "Make a 3D model from an image."},
     "caps": [], "wavespeed_backup": []},
    {"id": "ocr", "group": "other", "label": {"zh": "识别文字", "en": "Read text"},
     "blurb": {"zh": "识别图里的文字。", "en": "Read text from an image."},
     "caps": [], "wavespeed_backup": []},
    {"id": "transcribe", "group": "other", "label": {"zh": "转写", "en": "Transcribe"},
     "blurb": {"zh": "把音频转成文字。", "en": "Turn audio into text."},
     "caps": [], "wavespeed_backup": []},
]

BY_ID = {tool["id"]: tool for tool in TOOLS}
FEATURE_TOOL = {
    "upscale_image": "upscale_image",
    "remove_background": "remove_background",
    "expand_image": "expand_image",
    "change_angle": "change_angle",
    "erase_region": "erase_region",
    "split_layers": "split_layers",
    "segment": "edit_elements",
    "edit_elements": "edit_elements",
    "mockup_surface": "create_mockup",
    "create_mockup": "create_mockup",
    "text_to_video": "generate_video",
    "image_to_video": "generate_video",
    "generate_video": "generate_video",
    "extend_video": "extend_video",
    "upscale_video": "upscale_video",
    "remove_video_background": "remove_video_background",
    "music": "generate_music",
    "generate_music": "generate_music",
    "sound_effect": "generate_sound_effect",
    "generate_sound_effect": "generate_sound_effect",
    "text_to_speech": "text_to_speech",
    "image_to_3d": "image_to_3d",
    "ocr": "ocr",
    "transcribe": "transcribe",
}

# Confirmed: the provider did not create a task. Unknown means it might have.
ELIGIBLE = {"not_accepted", "auth", "balance", "rate_limit", "unsupported"}
HUMAN = {"unknown", "accepted", "safety", "invalid_params", "confirm", "price", "incompatible"}


class RouteFailure(Exception):
    def __init__(self, kind: str, message: str = "", task_id: str | None = None):
        super().__init__(message or kind)
        self.kind = kind
        self.task_id = task_id


def tool_of(inputs: dict) -> str | None:
    """The user tool this request belongs to. Explicit tool= wins."""
    if not isinstance(inputs, dict):
        return None
    named = str(inputs.get("tool") or "")
    if named in BY_ID:
        return named
    feature = str(inputs.get("feature") or "")
    custom = str(inputs.get("custom") or "")
    prompt = str(inputs.get("prompt") or "")
    from . import gif_image
    gif = gif_image.requests_gif(inputs)
    refs = _refs(inputs)
    if feature in {"text_to_image", "generate_image"}:
        if gif and refs:
            return "to_gif"
        return "generate_image"
    if feature in {"image_edit", "edit_image"}:
        if custom == "style":
            return "style_transfer"
        if prompt.startswith("Change the text") or prompt.startswith("Remove the text"):
            return "replace_text"
        return "edit_image"
    if custom == "animate" or feature == "animate_image":
        return "animate_image"
    return FEATURE_TOOL.get(feature)


def capability_for(tool_id: str, inputs: dict) -> str | None:
    tool = BY_ID.get(tool_id)
    if not tool or not tool["caps"]:
        return None
    from . import gif_image
    gif = gif_image.requests_gif(inputs)
    refs = _refs(inputs)
    if gif and refs:
        cap = "reference_gif"
    elif gif:
        cap = "text_to_gif"
    elif refs:
        cap = "image_edit"
    else:
        cap = "text_to_image"
    return cap if cap in tool["caps"] else None


def _refs(inputs: dict) -> list:
    images = inputs.get("images") if isinstance(inputs.get("images"), list) else []
    refs = inputs.get("refs") if isinstance(inputs.get("refs"), list) else []
    return [v for v in [inputs.get("image"), inputs.get("base"), *images, *refs] if v]


def connected(model_id: str) -> bool:
    return model_id in CONNECTED


def choice_enabled(tool: dict, provider: str, model: str) -> tuple[bool, str]:
    if provider == "wavespeed" and model == "existing":
        # Still→GIF live default is Replicate; WaveSpeed must not be a primary pick.
        if tool.get("id") == "to_gif":
            return False, "静图转动图主线路禁止 WaveSpeed，请用 Replicate"
        return True, ""
    if provider != "replicate" or model not in CONNECTED:
        return False, "未核实或尚未接入，不能选"
    if not tool["caps"]:
        return False, "这个工具还没有接到 Replicate"
    row = image_model("replicate", model)
    if not row:
        return False, "目录里没有这个模型"
    if not set(tool["caps"]) & set(row.get("capabilities") or []):
        return False, "这个模型盖不住这个工具要做的事"
    return True, ""


def backup_ok(tool: dict, provider: str, model: str, capability: str | None) -> bool:
    ok, _ = choice_enabled(tool, provider, model)
    if not ok:
        return False
    if provider == "wavespeed":
        return bool(capability) and capability in tool["wavespeed_backup"]
    row = image_model("replicate", model)
    return bool(row and capability and capability in (row.get("capabilities") or []) and capability in tool["caps"])


def endpoint(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    provider = str(raw.get("provider") or "")
    model = str(raw.get("model") or "")
    if provider == "wavespeed" and model in {"", "existing"}:
        return {"provider": "wavespeed", "model": "existing"}
    if provider == "replicate" and model in CONNECTED:
        return {"provider": "replicate", "model": model}
    return None


def normalize_route(tool_id: str, body: dict) -> dict | None:
    tool = BY_ID.get(tool_id)
    if not tool or not isinstance(body, dict):
        return None
    primary = endpoint(body.get("primary"))
    if not primary:
        return None
    ok, _ = choice_enabled(tool, primary["provider"], primary["model"])
    if not ok:
        return None
    backup = endpoint(body.get("backup")) if body.get("backup") else None
    if backup and (backup == primary or not choice_enabled(tool, backup["provider"], backup["model"])[0]):
        return None
    if backup and backup["provider"] == "wavespeed" and not tool["wavespeed_backup"]:
        return None
    return {"primary": primary, "backup": backup, "fallback": bool(body.get("fallback")) and backup is not None}


def public_choices(tool: dict) -> list[dict]:
    ban_ws = tool.get("id") == "to_gif"
    rows = [{
        "provider": "wavespeed", "model": "existing",
        "label": {"zh": "WaveSpeed · 现有模型", "en": "WaveSpeed · current model"},
        "enabled": not ban_ws, "quote": "provider",
        "reason": "静图转动图主线路禁止 WaveSpeed，请用 Replicate" if ban_ws else "",
        "backup": bool(tool["wavespeed_backup"]),
        "backup_reason": (
            "静图转动图不可用 WaveSpeed 作备选" if ban_ws
            else ("" if tool["wavespeed_backup"] else "这个工具的结果 WaveSpeed 接不住，不能当备选")
        ),
    }]
    for model in CONNECTED:
        ok, reason = choice_enabled(tool, "replicate", model)
        label = "Flare" if model == FLARE else "Sunburst"
        rows.append({
            "provider": "replicate", "model": model,
            "label": {"zh": f"Replicate · {label}", "en": f"Replicate · {label}"},
            "enabled": ok, "quote": "unknown", "reason": reason,
            "backup": ok, "backup_reason": reason,
        })
    if not tool["caps"]:
        rows.append({
            "provider": "replicate", "model": "",
            "label": {"zh": "Replicate · 未核实", "en": "Replicate · unverified"},
            "enabled": False, "quote": "unknown",
            "reason": "还没在官方 schema 上接通。未核实不是不支持，也不会自动换。",
            "backup": False,
            "backup_reason": "还没接通，不能当备选",
        })
    return rows


def logical_key(inputs: dict, route: dict) -> str:
    params = inputs.get("params") if isinstance(inputs.get("params"), dict) else {}
    payload = {
        "tool": route["tool"],
        "revision": route["revision"],
        "prompt": str(inputs.get("prompt") or ""),
        "feature": str(inputs.get("feature") or ""),
        "fmt": str(params.get("output_format") or inputs.get("output_format") or ""),
        "images": [str(v) for v in _refs(inputs)],
        "w": inputs.get("width"), "h": inputs.get("height"),
    }
    return json.dumps(payload, sort_keys=True, default=str)


def classify_failure(exc: Exception) -> str:
    if isinstance(exc, RouteFailure):
        return exc.kind
    status = int(getattr(exc, "status", 0) or 0)
    kind = str(getattr(exc, "kind", "") or "")
    task_id = getattr(exc, "task_id", None)
    if getattr(exc, "confirm", None) is not None or getattr(exc, "unpriced", False):
        return "confirm"
    if kind == "price" or kind == "quote_unknown":
        return "price"
    if kind == "provider_unconfigured":
        return "auth"
    if task_id or kind in {"timeout", "noOutput", "unknown"}:
        return "accepted" if task_id else "unknown"
    if kind in {"moderation", "safety"} or status == 451:
        return "safety"
    if kind in {"invalidKey"} or status in {401, 403}:
        return "auth"
    if kind in {"insufficientCredit"} or status == 402:
        return "balance"
    if kind in {"rateLimit", "rate_limit"} or status == 429:
        return "rate_limit"
    if status >= 500 or isinstance(exc, TimeoutError):
        return "unknown"
    if kind == "unsupported":
        return "unsupported"
    if status == 400:
        return "invalid_params"
    if kind == "not_accepted":
        return "not_accepted"
    return "unknown"


def explain(kind: str) -> str:
    text = {
        "not_accepted": "对方明确没建任务，可以试备选",
        "auth": "鉴权失败且没有任务号，可以试另一个供应商",
        "balance": "余额不足且没有任务号，可以试备选",
        "rate_limit": "被限流且没有任务号，可以试备选",
        "unsupported": "这个模型明确做不到，备选如果做得到可以试一次",
        "unknown": "提交结果不清楚，不能假定没受理，所以不换路",
        "accepted": "已经有任务号，只查原任务，不另开一条",
        "safety": "内容或安全拒绝，不换供应商绕过",
        "invalid_params": "参数无效，不拿同一份错误请求去打另一家",
        "confirm": "还在等费用确认，不自动换路",
        "price": "备选价格对不上或还未知，停下来，不编造报价",
        "incompatible": "备选保不住这个工具要的图、格式或 GIF",
        "route_changed": "估价之后配置变了，请重新估价。这次没有发送",
        "primary": "走了主线路",
    }
    return text.get(kind, kind)


def replicate_models():
    provider = next(p for p in IMAGE_PROVIDERS if p["id"] == "replicate")
    return provider["models"]
