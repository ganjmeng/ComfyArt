"""Provider catalogs and the WaveSpeed ↔ Replicate coverage audit.

Adding a later model is a catalog entry that names an adapter already implemented
and contract-tested. The settings page renders this data. It does not hardcode a
vendor, and it does not treat a similar model as compatible.

Audit rows are not routes. ``enabled`` is true only for adapters this process
actually calls, and only after the matching contract tests.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Official model cards fetched 2026-11-08. One Replicate model covers text, edit
# and GIF. WaveSpeed splits text-to-image and edit into different ids.
# https://replicate.com/openai/gpt-image-2.6-flare
# https://replicate.com/openai/gpt-image-2.6-sunburst
REPLICATE_GPT_IMAGE_26 = {
    "adapter": "replicate_gpt_image_26",
    "quote": "unknown",
    "docs": "https://replicate.com/openai/gpt-image-2.6-flare",
    "capabilities": ["text_to_image", "image_edit", "text_to_gif", "reference_gif"],
    "differences": {
        "zh": "与 WaveSpeed 的 …/text-to-image、…/edit 不是同一请求。参考图字段是 input_images；GIF 用 output_format=gif，另有 frame_count（2–16）和 frame_duration_ms（20–2000）。静图尺寸不会自动套到 GIF。费用未知。",
        "en": "Not the same request as WaveSpeed …/text-to-image or …/edit. References use input_images. GIF sets output_format=gif plus frame_count (2–16) and frame_duration_ms (20–2000). Still-image sizes are not reused as a GIF price. Price unknown.",
    },
}

IMAGE_PROVIDERS = [
    {
        "id": "wavespeed",
        "label": {"zh": "WaveSpeed", "en": "WaveSpeed"},
        "mode": "existing",
        "secret_env": "WAVESPEED_API_KEY",
        "models": [],
        "note": {
            "zh": "未保存，或保存为 WaveSpeed 时，图像仍走现有路由和现有模型。本页不改默认模型。",
            "en": "Unsaved, or saved as WaveSpeed, image jobs keep the current route and models. This page does not change the default model.",
        },
        "capabilities": {
            "text_to_image": {"supported": True, "enabled": True},
            "image_edit": {"supported": True, "enabled": True, "formats": ["png", "jpeg", "webp"]},
            "text_to_gif": {"supported": True, "enabled": True},
            "reference_gif": {
                "supported": False,
                "enabled": False,
                "reason": {
                    "zh": "WaveSpeed 编辑不接受 gif（仅 png/jpeg/webp，带图 GIF 会 HTTP 400）。这里不能选，也不会把带参考图的请求改成无图文生。",
                    "en": "WaveSpeed edit does not accept gif (png/jpeg/webp only; an image GIF returns HTTP 400). It cannot be selected here, and a reference image is not dropped to make a text-only GIF.",
                },
            },
        },
    },
    {
        "id": "replicate",
        "label": {"zh": "Replicate", "en": "Replicate"},
        "mode": "replicate",
        "secret_env": "REPLICATE_API_TOKEN",
        "note": {
            "zh": "可选备用。保存后只有新的文生图、图编辑、文生 GIF、参考图 GIF 走这里。不会自动改回 WaveSpeed。视频和其他工具仍走 WaveSpeed。",
            "en": "Optional backup. After save, only new text-to-image, edit, text GIF and reference GIF jobs use it. No automatic return to WaveSpeed. Video and other tools stay on WaveSpeed.",
        },
        "models": [
            {"id": "openai/gpt-image-2.6-flare", "label": "GPT Image 2.6 Flare", **REPLICATE_GPT_IMAGE_26,
             "docs": "https://replicate.com/openai/gpt-image-2.6-flare"},
            {"id": "openai/gpt-image-2.6-sunburst", "label": "GPT Image 2.6 Sunburst", **REPLICATE_GPT_IMAGE_26,
             "docs": "https://replicate.com/openai/gpt-image-2.6-sunburst"},
        ],
    },
]

# Official first-call page, 2026-11-08: https://api-docs.deepseek.com/
# deepseek-flash is served by DeepSeek-V4.1-Flash-1017. That is not the WaveSpeed id.
# Chat schema: thinking defaults on; deepseek-flash non-thinking temperature is fixed at 1.0;
# tool calls exist, and thinking-mode tool turns must echo reasoning_content.
LLM_PROVIDERS = [
    {
        "id": "wavespeed",
        "label": {"zh": "WaveSpeed", "en": "WaveSpeed"},
        "mode": "existing",
        "secret_env": "",
        "models": [
            {
                "id": "existing",
                "adapter": "existing",
                "passthrough": True,
                "label": {
                    "zh": "现有配置 · deepseek/deepseek-v4.1-flash-1017",
                    "en": "Current setup · deepseek/deepseek-v4.1-flash-1017",
                },
                "request_model": "deepseek/deepseek-v4.1-flash-1017",
                "quote": "settings",
                "note": {
                    "zh": "生产默认。保存这一项，或根本不保存，都继续用现有 bot-local-llm-url 和 bot-model-local-llm。",
                    "en": "Production default. Saving this, or not saving, keeps the current bot-local-llm-url and bot-model-local-llm.",
                },
            }
        ],
    },
    {
        "id": "deepseek",
        "label": {"zh": "DeepSeek 官方", "en": "DeepSeek official"},
        "mode": "openai_chat",
        "base_url": "https://api.deepseek.com",
        "secret_env": "DEEPSEEK_API_KEY",
        "docs": "https://api-docs.deepseek.com/",
        "models": [
            {
                "id": "deepseek-flash",
                "adapter": "deepseek_official",
                "label": {"zh": "deepseek-flash", "en": "deepseek-flash"},
                "request_model": "deepseek-flash",
                "quote": "unknown",
                "note": {
                    "zh": "官方调用名。文档写明现由 DeepSeek-V4.1-Flash-1017 提供。它不是 WaveSpeed 的 deepseek/deepseek-v4.1-flash-1017，不能当成无差异替换。",
                    "en": "Official id. Docs say it is served by DeepSeek-V4.1-Flash-1017. It is not WaveSpeed's deepseek/deepseek-v4.1-flash-1017 and is not a drop-in replacement.",
                },
                "differences": [
                    {"zh": "地址改为 https://api.deepseek.com，密钥只读环境变量 DEEPSEEK_API_KEY。", "en": "Base URL becomes https://api.deepseek.com. The key is only DEEPSEEK_API_KEY."},
                    {"zh": "省略 thinking 时官方默认开启思考。现有 Agent 不回传 reasoning_content，所以这条路由显式关闭思考。这是适配，不是同一行为。", "en": "Official thinking defaults on when omitted. This agent does not echo reasoning_content, so this route sends thinking disabled. That is an adapter, not the same behavior."},
                    {"zh": "deepseek-flash 在非思考模式下 temperature 固定为 1.0，传入 0.2 会被忽略。", "en": "In non-thinking mode deepseek-flash fixes temperature at 1.0. A sent 0.2 is ignored."},
                    {"zh": "现有链路是整段 JSON，不开启 stream。官方流式是另一套 SSE，这里没有启用。", "en": "The current loop reads one JSON body and does not set stream. Official streaming is SSE and is not enabled here."},
                    {"zh": "工具调用按官方非思考示例保留 tools。本环境没有付费实测工具闭环。", "en": "tools are kept, matching the official non-thinking example. The tool loop was not live-tested here."},
                    {"zh": "价格未知。此页不发起连通或模型探测。", "en": "Price unknown. This page does not run a connectivity or model probe."},
                ],
            },
            {
                "id": "deepseek-v4-pro",
                "adapter": "deepseek_official",
                "label": {"zh": "deepseek-v4-pro", "en": "deepseek-v4-pro"},
                "request_model": "deepseek-v4-pro",
                "quote": "unknown",
                "note": {
                    "zh": "官方列出的另一个模型，不是 Flash 1017。思考、温度和工具规则与 flash 不同，费用未知。",
                    "en": "A different official model, not Flash 1017. Thinking, temperature and tool rules differ from flash. Price unknown.",
                },
                "differences": [
                    {"zh": "同样关闭思考以适配现有 Agent，但官方写明 pro 在思考模式和工具调用上的温度规则与 flash 不同。未实测。", "en": "Thinking is disabled for the current agent, but the docs give pro different temperature rules for thinking and tool calls. Not live-tested."},
                    {"zh": "价格未知。不会回退到 WaveSpeed。", "en": "Price unknown. It does not fall back to WaveSpeed."},
                ],
            },
        ],
    },
]

IMPLEMENTED_ADAPTERS = {"existing", "deepseek_official", "replicate_gpt_image_26"}
IMAGE_CAPS = ("text_to_image", "image_edit", "text_to_gif", "reference_gif")

# Names seen on Replicate collection pages on 2026-11-08. Schemas were not compared.
# A sighting is not compatibility.
_SIGHTED = (
    "nano-banana-pro", "nano-banana-2.1", "flux-3", "seedream-4.5", "ideogram-4",
    "p-image", "kling-v3", "kling-v4", "kling-v2.6", "kling-v2.5", "kling-lip",
    "seedance-2.0", "veo3.1", "veo-3.1",
)


def _text(value: dict | str, lang: str) -> str:
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or "")
    return str(value or "")


def image_provider(provider_id: str) -> dict | None:
    return next((p for p in IMAGE_PROVIDERS if p["id"] == provider_id), None)


def image_model(provider_id: str, model_id: str) -> dict | None:
    provider = image_provider(provider_id)
    if not provider:
        return None
    return next((m for m in provider.get("models") or [] if m["id"] == model_id), None)


def llm_provider(provider_id: str) -> dict | None:
    return next((p for p in LLM_PROVIDERS if p["id"] == provider_id), None)


def llm_model(provider_id: str, model_id: str) -> dict | None:
    provider = llm_provider(provider_id)
    if not provider:
        return None
    return next((m for m in provider.get("models") or [] if m["id"] == model_id), None)


def model_supports(model: dict, capability: str) -> bool:
    return capability in (model.get("capabilities") or [])


def public_image_providers(configured: dict[str, bool]) -> list[dict]:
    out = []
    for provider in IMAGE_PROVIDERS:
        models = []
        for model in provider.get("models") or []:
            models.append({
                "id": model["id"],
                "label": model["label"],
                "adapter": model.get("adapter") or "",
                "capabilities": list(model.get("capabilities") or []),
                "quote": model.get("quote") or "unknown",
                "docs": model.get("docs") or "",
                "differences": model.get("differences") or {},
            })
        caps = {}
        for name, cap in (provider.get("capabilities") or {}).items():
            caps[name] = {
                "supported": bool(cap.get("supported")),
                "enabled": bool(cap.get("enabled")),
                "formats": list(cap.get("formats") or []),
                "reason": cap.get("reason") or {},
            }
        out.append({
            "id": provider["id"],
            "label": provider["label"],
            "mode": provider["mode"],
            "configured": bool(configured.get(provider["id"])),
            "secret_env": provider.get("secret_env") or "",
            "note": provider.get("note") or {},
            "models": models,
            "capabilities": caps,
        })
    return out


def public_llm_providers(configured: dict[str, bool]) -> list[dict]:
    out = []
    for provider in LLM_PROVIDERS:
        models = []
        for model in provider["models"]:
            models.append({
                "id": model["id"],
                "label": model["label"],
                "adapter": model.get("adapter") or "",
                "passthrough": bool(model.get("passthrough")),
                "request_model": model.get("request_model") or "",
                "quote": model.get("quote") or "unknown",
                "note": model.get("note") or {},
                "differences": list(model.get("differences") or []),
            })
        out.append({
            "id": provider["id"],
            "label": provider["label"],
            "mode": provider["mode"],
            "base_url": provider.get("base_url") or "",
            "configured": bool(configured.get(provider["id"])),
            "secret_env": provider.get("secret_env") or "",
            "docs": provider.get("docs") or "",
            "models": models,
        })
    return out


def _curated() -> dict:
    with open(ROOT / "curated_models.json", encoding="utf-8") as f:
        return json.load(f)["features"]


def _tools() -> dict:
    with open(ROOT / "wavespeed_models.json", encoding="utf-8") as f:
        return json.load(f).get("tool_features") or {}


def _sighted(model_id: str) -> str:
    hay = model_id.lower()
    for name in _SIGHTED:
        if name in hay:
            return name
    return ""


# Official pages opened 2026-11-08. A page is not an adapter.
# connected: schema checked and the product adapter is contract-tested.
# same_model_pending: same Replicate id, schema read, not wired.
# alternative_explicit: a different id was seen; never auto-selected.
# unverified: not located on the pages opened. This is not "unsupported".
_EXACT = {
    "openai/gpt-image-2.6-flare/text-to-image": ("connected", "openai/gpt-image-2.6-flare"),
    "openai/gpt-image-2.6-flare/edit": ("connected", "openai/gpt-image-2.6-flare"),
    "openai/gpt-image-2.6-sunburst/text-to-image": ("connected", "openai/gpt-image-2.6-sunburst"),
    "openai/gpt-image-2.6-sunburst/edit": ("connected", "openai/gpt-image-2.6-sunburst"),
    "openai/gpt-image-2.5-flare/text-to-image": ("same_model_pending", "openai/gpt-image-2.5-flare"),
    "openai/gpt-image-2.5-flare/edit": ("same_model_pending", "openai/gpt-image-2.5-flare"),
    "openai/gpt-image-2/text-to-image": ("same_model_pending", "openai/gpt-image-2"),
    "openai/gpt-image-2/edit": ("same_model_pending", "openai/gpt-image-2"),
    "google/nano-banana-2/text-to-image": ("alternative_explicit", "google/nano-banana-2"),
    "google/nano-banana-2/edit": ("alternative_explicit", "google/nano-banana-2"),
    "google/nano-banana-2.1/text-to-image": ("alternative_explicit", "google/nano-banana-2.1"),
    "google/nano-banana-2.1/edit": ("alternative_explicit", "google/nano-banana-2.1"),
    "google/nano-banana-2-lite/text-to-image": ("alternative_explicit", "google/nano-banana-2-lite"),
    "google/nano-banana-2-lite/edit": ("alternative_explicit", "google/nano-banana-2-lite"),
    "google/nano-banana-pro/text-to-image": ("alternative_explicit", "google/nano-banana-pro"),
    "google/nano-banana-pro/edit": ("alternative_explicit", "google/nano-banana-pro"),
    "bytedance/seedream-v4": ("alternative_explicit", "bytedance/seedream-4"),
    "bytedance/seedream-v4/edit": ("alternative_explicit", "bytedance/seedream-4"),
    "bytedance/seedance-2.0/text-to-video": ("alternative_explicit", "bytedance/seedance-2.0"),
    "bytedance/seedance-2.0/image-to-video": ("alternative_explicit", "bytedance/seedance-2.0"),
    "google/veo3.1/text-to-video": ("alternative_explicit", "google/veo-3.1"),
    "google/veo3.1/image-to-video": ("alternative_explicit", "google/veo-3.1"),
    "google/veo3.1-fast/text-to-video": ("alternative_explicit", "google/veo-3.1-fast"),
    "google/veo3.1-fast/image-to-video": ("alternative_explicit", "google/veo-3.1-fast"),
    "black-forest-labs/flux-3/text-to-image": ("alternative_explicit", "black-forest-labs/flux-3-image"),
    "black-forest-labs/flux-3/image-edit": ("alternative_explicit", "black-forest-labs/flux-3-image"),
}
_DETAIL = {
    "connected": {
        "zh": "同一个 2.6 模型已接到产品适配器。字段仍和 WaveSpeed 不同，GIF 不能按静图计价。",
        "en": "The same 2.6 model is wired. Fields still differ from WaveSpeed, and a GIF is not priced as a still.",
    },
    "same_model_pending": {
        "zh": "Replicate 上有同名模型，官方字段已看过，但产品还没接。2.5 / Image 2 的输出格式没有 gif。不会自动换过去。",
        "en": "The same Replicate model exists and its fields were read, but it is not wired. 2.5 and Image 2 do not list gif. It is not selected automatically.",
    },
    "alternative_explicit": {
        "zh": "官方页是另一个 model id。只能人工点名，不能自动替换，视频也不会改道。",
        "en": "The official page uses a different model id. It can only be chosen by hand. Nothing is switched automatically, including video.",
    },
    "unverified": {
        "zh": "这次打开的官方页没有定位到这个 id。这是未核实，不是不支持，仍然走现有 WaveSpeed。",
        "en": "The opened official pages did not locate this id. Unverified is not the same as unsupported. It stays on WaveSpeed.",
    },
}


def classify_model(feature: str, model_id: str) -> dict:
    """One curated WaveSpeed id. Never calls a provider."""
    verdict, replicate_id = _EXACT.get(model_id, ("unverified", ""))
    enabled = verdict == "connected" and feature in ("text_to_image", "image_edit")
    detail = _DETAIL[verdict]
    return {
        "feature": feature,
        "wavespeed_model": model_id,
        "verdict": verdict,
        "replicate_model": replicate_id,
        "enabled": enabled,
        "implemented": enabled,
        "detail": detail,
    }


def capability_rows() -> list[dict]:
    """Implementation coverage for the four image capabilities. Separate from the model audit."""
    return [
        {"capability": "text_to_image", "provider": "replicate", "models": ["openai/gpt-image-2.6-flare", "openai/gpt-image-2.6-sunburst"],
         "implemented": True, "quote": "unknown",
         "detail": {"zh": "已实现并有契约测试。无参考图时不发送 input_images。", "en": "Implemented and contract-tested. No input_images when there is no reference."}},
        {"capability": "image_edit", "provider": "replicate", "models": ["openai/gpt-image-2.6-flare", "openai/gpt-image-2.6-sunburst"],
         "implemented": True, "quote": "unknown",
         "detail": {"zh": "已实现。必须带 input_images。输出不是 gif。", "en": "Implemented. input_images is required. Output is not gif."}},
        {"capability": "text_to_gif", "provider": "replicate", "models": ["openai/gpt-image-2.6-flare", "openai/gpt-image-2.6-sunburst"],
         "implemented": True, "quote": "unknown",
         "detail": {"zh": "已实现。output_format=gif，不带参考图。不按静图价报价。", "en": "Implemented. output_format=gif and no reference image. Not priced as a still."}},
        {"capability": "reference_gif", "provider": "replicate", "models": ["openai/gpt-image-2.6-flare", "openai/gpt-image-2.6-sunburst"],
         "implemented": True, "quote": "unknown",
         "detail": {"zh": "已实现。input_images 加 output_format=gif。缺图则失败，不降级成无图文生。", "en": "Implemented. input_images plus output_format=gif. Missing images fail; it does not degrade to text-only."}},
        {"capability": "reference_gif", "provider": "wavespeed", "models": [],
         "implemented": False, "quote": "unknown",
         "detail": {"zh": "未启用。编辑不接受 gif。保存 WaveSpeed 也不改现有未托管路由。", "en": "Not enabled. Edit does not accept gif. Saving WaveSpeed does not rewrite the current unmanaged route."}},
    ]


def audit_rows() -> list[dict]:
    rows = []
    for feature, spec in _curated().items():
        ids = list(spec.get("models") or []) + list(spec.get("more") or [])
        for model_id in ids:
            rows.append(classify_model(feature, model_id))
    return rows


def tool_rows() -> list[dict]:
    """Every agent tool. Only generate/edit image can leave WaveSpeed, and only when saved."""
    routed = {"generate_image", "edit_image"}
    rows = []
    for tool, feature in _tools().items():
        rows.append({
            "tool": tool,
            "feature": feature,
            "replicate_enabled": tool in routed,
            "detail": {
                "zh": "保存 Replicate 后，新的文生/编辑才可能改走 2.6。其他工具保持 WaveSpeed。" if tool in routed
                else "不在本次实现里。保持 WaveSpeed。",
                "en": "After Replicate is saved, new text/edit jobs may use 2.6. Other tools stay on WaveSpeed." if tool in routed
                else "Not in this implementation. Stays on WaveSpeed.",
            },
        })
    return rows


def audit_summary() -> dict:
    rows = audit_rows()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    enabled = [r for r in rows if r["enabled"]]
    return {
        "checked_at": "2026-11-08",
        "sources": [
            "https://replicate.com/openai/gpt-image-2.6-flare",
            "https://replicate.com/openai/gpt-image-2.6-sunburst",
            "https://replicate.com/collections/text-to-image",
            "https://replicate.com/collections/image-to-video",
            "https://api-docs.deepseek.com/",
            "https://api-docs.deepseek.com/api/create-chat-completion",
            "https://api-docs.deepseek.com/guides/tool_calls",
        ],
        "model_counts": counts,
        "models_listed": len(rows),
        "replicate_enabled_models": enabled,
        "capabilities": capability_rows(),
        "tools": tool_rows(),
        "llm": {
            "production": {
                "provider": "wavespeed",
                "base_url": "https://llm.wavespeed.ai/v1",
                "model": "deepseek/deepseek-v4.1-flash-1017",
            },
            "optional": [
                {"provider": "deepseek", "base_url": "https://api.deepseek.com", "model": "deepseek-flash", "quote": "unknown"},
                {"provider": "deepseek", "base_url": "https://api.deepseek.com", "model": "deepseek-v4-pro", "quote": "unknown"},
            ],
            "not_a_drop_in": True,
        },
    }


def render_audit_markdown() -> str:
    summary = audit_summary()
    counts = summary["model_counts"]
    lines = [
        "# WaveSpeed 与 Replicate / DeepSeek 覆盖核对",
        "",
        "核对日期：2026-11-08。没有调用付费生成，没有使用真实密钥。",
        "实现覆盖和审计覆盖分开。只有契约测试过的路由可以在设置里保存后用于新任务。",
        "相近模型不能当成同一条路由。",
        "",
        "## 实现覆盖（会在保存后生效）",
        "",
        "| 能力 | 供应商 | 状态 | 说明 |",
        "| --- | --- | --- | --- |",
    ]
    for row in summary["capabilities"]:
        state = "已实现" if row["implemented"] else "不启用"
        lines.append(f"| {row['capability']} | {row['provider']} | {state} | {row['detail']['zh']} |")
    lines += [
        "",
        "Replicate 只登记了官方模型卡已核对的 GPT Image 2.6 Flare 与 Sunburst。",
        "参数差异：WaveSpeed 用分开的 `/text-to-image` 与 `/edit`，参考图常见字段是 `images`；Replicate 用 `input_images`。",
        "GIF 需要 `output_format=gif`，`frame_count` 2–16（默认 9），`frame_duration_ms` 20–2000（默认 200）。",
        "官方说明 GIF 的 1:1 帧是 512×512、16:9 是 896×512，因为所有帧共用图像预算。这和静图尺寸不是一回事，静图价不能套到 GIF。费用显示为未知。",
        "WaveSpeed 编辑 GIF 未启用：编辑只接受 png/jpeg/webp。",
        "",
        "## 审计覆盖（不因此启用）",
        "",
        f"精选模型 {summary['models_listed']} 条。",
        f"同模型已接通 {counts.get('connected', 0)}。",
        f"同模型已看过 schema、尚未接入 {counts.get('same_model_pending', 0)}。",
        f"替代模型，必须人工点名 {counts.get('alternative_explicit', 0)}。",
        f"未核实（不是不支持）{counts.get('unverified', 0)}。",
        "",
        "Replicate 集合页见过 nano-banana、FLUX.3、Seedream 4.5、Ideogram 4.5、Kling、以及文案中的 Seedance / Veo。",
        "这些 id 与仓库里的 WaveSpeed id 并不相同，没有逐字段对照，设置里不能选。",
        "",
        "| 功能 | WaveSpeed 模型 | 结论 | 启用 |",
        "| --- | --- | --- | --- |",
    ]
    for row in audit_rows():
        lines.append(
            f"| {row['feature']} | `{row['wavespeed_model']}` | {row['verdict']} | {'是' if row['enabled'] else '否'} |"
        )
    lines += [
        "",
        "## 工具",
        "",
        "| 工具 | 功能 | Replicate |",
        "| --- | --- | --- |",
    ]
    for row in summary["tools"]:
        lines.append(f"| {row['tool']} | {row['feature']} | {'仅保存后的文生/编辑' if row['replicate_enabled'] else '否，留在 WaveSpeed'} |")
    lines += [
        "",
        "## LLM",
        "",
        "没有管理员覆盖时，语言模型默认是官方 `https://api.deepseek.com` 的 `deepseek-flash`。显式保存 WaveSpeed 才继续用 `deepseek/deepseek-v4.1-flash-1017`。",
        "官方可选项是 `https://api.deepseek.com` 的 `deepseek-flash`（文档：现由 DeepSeek-V4.1-Flash-1017 提供）和 `deepseek-v4-pro`。",
        "调用名不同。官方省略 thinking 时默认开启思考；思考模式下工具调用必须回传 reasoning_content，否则 400。",
        "现有 Agent 不回传 reasoning_content，因此官方路由会显式关闭思考。deepseek-flash 非思考温度固定 1.0。",
        "现有链路不使用 SSE 流式。工具调用形状按官方非思考文档对齐，本环境未做付费实测。",
        "价格未知。不保存不改变活动配置。无密钥则新任务失败，不回退 WaveSpeed。",
        "不能据此认为任意 OpenAI 兼容模型都可以换上。",
        "",
    ]
    return "\n".join(lines) + "\n"
