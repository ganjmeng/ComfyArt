import asyncio
import json
import logging
import os
import re
import time
from typing import Callable, Optional

import aiohttp

from ._cli_common import (
    PROBE_CACHE_S,
    TOOL_RESULT_CAP,
    merge_usage,
)
from . import lms
from .guide import AGENT_GUIDE, CORE_MCP_TOOLS, PAID_TOOLS
from .providers import (
    AgentProvider,
    BotEvent,
    EmitFn,
    ProviderCaps,
    ProviderStatus,
    TurnHandle,
    TurnRequest,
    TurnResult,
)

_log = logging.getLogger(__name__)
_NET_ERRORS = (aiohttp.ClientError, asyncio.TimeoutError, OSError, RuntimeError, ValueError)

_API_KEY_ENV = "COMFYART_LOCAL_LLM_API_KEY"
_MAX_ITERATIONS = 80
_MAX_WAIT_SLICES = 12
_LLM_TIMEOUT_S = 300
_HISTORY_CHAR_CAP = 16_000
_REPEAT_STOP = 3
_CACHED_SKILL_STOP = 3  # cumulative cached skill re-reads per turn (A/B/A/B...)
_REPEAT_STOP_TEXT = {
    "zh": "任务卡在重复步骤，已停止，未继续扣费。",
    "en": "The task got stuck repeating a step and was stopped; no further "
          "charges.",
}
_PAID_GEN_CAP = 4  # paid generations per plan item per turn (#142)
_PAID_CAP_TEXT = {
    "zh": "已生成 {n} 张仍未完成，已停止，未继续扣费，请告诉我怎么调整",
    "en": "Generated {n} images and still not done, so I stopped; no further "
          "charges. Tell me how to adjust.",
}
_REF_BLOCK_TEXT = (
    "[tool error] blocked before submitting (nothing was charged): the user "
    "supplied the product image {ids}. Every {tool} call must pass it — put "
    "the shape id in {field}. Describing it in the prompt does not send the "
    "image.")
_ZH_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
           "七": 7, "八": 8, "九": 9, "十": 10}
_COUNT_RE = re.compile(
    r"(\d+|[一两二三四五六七八九十])\s*(?:张|幅|款|个版本|images?\b|pictures?\b"
    r"|photos?\b|versions?\b|variations?\b)", re.I)
_SHAPE_ID_RE = re.compile(r"shape:[A-Za-z0-9_\-]+")
_PRODUCT_RE = re.compile(r"产品|商品|电商|\bproducts?\b", re.I)
# where each generation tool takes an input image
_REF_FIELDS = {
    "generate_image": ("refs", "base"),
    "generate_video": ("first_frame", "last_frame", "reference_images"),
}
# Same wording as the chat panel's TOOL_LABELS (src/bot.ts + locales).
_STEP_LABELS: dict[str, tuple[str, str]] = {
    'ToolSearch': ('查找工具', 'Find tools'),
    'tool_search': ('查找工具', 'Find tools'),
    'server_info': ('查看状态', 'Check status'),
    'get_canvas': ('查看画布', 'View canvas'),
    'view_canvas': ('观察画面', 'Look at canvas'),
    'view_video': ('查看视频', 'Watch video'),
    'list_models': ('查看模型', 'View models'),
    'brand_kits': ('查看品牌套件', 'View brand kit'),
    'generate_image': ('生成图像', 'Generate image'),
    'generate_video': ('生成视频', 'Generate video'),
    'edit_video': ('编辑视频', 'Edit video'),
    'edit_image': ('编辑图片', 'Edit image'),
    'animate_image': ('动态图片', 'Animate Image'),
    'upscale_image': ('放大', 'Upscale'),
    'remove_background': ('去背景', 'Remove Background'),
    'expand_image': ('扩图', 'Expand image'),
    'split_layers': ('图层拆分', 'Split Layers'),
    'change_angle': ('多角度', 'Multi-Angle'),
    'replace_text': ('编辑文字', 'Edit Text'),
    'edit_region': ('局部重绘', 'Inpaint'),
    'erase_region': ('橡皮工具', 'Eraser'),
    'move_object': ('移动对象', 'Move Object'),
    'style_transfer': ('风格迁移', 'Style Transfer'),
    'vectorize_image': ('矢量化', 'Vectorize'),
    'extend_video': ('视频延长', 'Extend Video'),
    'upscale_video': ('视频放大', 'Upscale Video'),
    'remove_video_background': ('去背景', 'Remove Background'),
    'generate_music': ('配乐', 'Music'),
    'generate_sound_effect': ('音效', 'Sound effect'),
    'text_to_speech': ('配音', 'Voiceover'),
    'edit_elements': ('编辑元素', 'Edit Elements'),
    'create_mockup': ('样机', 'Mockup'),
    'place_design': ('设计稿', 'Design'),
    'image_to_3d': ('转 3D', 'Image to 3D'),
    'wait_generation': ('等待生成结果', 'Wait for results'),
    'place_html': ('放置网页', 'Place web page'),
    'create_slides': ('制作 PPT', 'Create PPT'),
    'add_text': ('添加文字', 'Add text'),
    'add_shape': ('添加形状', 'Add shape'),
    'create_frame': ('创建画板', 'Create artboard'),
    'update_shapes': ('调整元素', 'Adjust elements'),
    'delete_shapes': ('删除元素', 'Delete elements'),
    'focus': ('定位元素', 'Locate elements'),
    'memory': ('记忆', 'Memory'),
    'skill': ('技能', 'Skill'),
    'custom_workflow': ('自定义工作流', 'Custom workflows'),
    'ask_user': ('向你提问', 'Ask you'),
    'update_plan': ('计划', 'Plan'),
}
_CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
_SKILL_HINT_RE = re.compile(
    r"Use the ComfyArt skill [\s\S]*?then follow those instructions\.")


def _reply_lang(user_text: str) -> str:
    """Reply in the user's language (same rule as AGENT_GUIDE)."""
    text = _SKILL_HINT_RE.sub("", user_text or "")
    return "zh" if _CJK_RE.search(text) else "en"


def _requested_count(user_text: str) -> int:
    """Images the user explicitly asked for ("做 6 张", "3 images"), else 0."""
    text = _SKILL_HINT_RE.sub("", user_text or "")
    best = 0
    for m in _COUNT_RE.finditer(text):
        raw = m.group(1)
        n = int(raw) if raw.isdigit() else _ZH_NUM.get(raw, 0)
        best = max(best, n)
    return best


def _product_refs(user_text: str) -> list[str]:
    """Image shape ids the user supplied for a product task (#142).

    Attached images arrive as "[Attached image 1: shape id shape:x ...]";
    users can also name an id in the text. Audio/video attachments are not
    product references."""
    text = user_text or ""
    skill = re.search(r"Use the ComfyArt skill '([^']+)'", text)
    body = _SKILL_HINT_RE.sub("", text)
    if not ((skill and skill.group(1) == "product") or _PRODUCT_RE.search(body)):
        return []
    ids: list[str] = []
    for line in body.splitlines():
        if re.match(r"\s*\[Attached (audio|video)", line):
            continue
        for sid in _SHAPE_ID_RE.findall(line):
            if sid not in ids:
                ids.append(sid)
    return ids


def _passes_ref(name: str, args: dict, refs: list[str]) -> bool:
    fields = _REF_FIELDS.get(name)
    if not fields or not refs:
        return True
    given: list[str] = []
    for f in fields:
        v = args.get(f)
        given += [str(x) for x in v] if isinstance(v, list) else [str(v or "")]
    return any(r in given for r in refs)


def _gen_units(name: str, args: dict) -> int:
    if name == "generate_image":
        try:
            return max(1, int(args.get("count") or 1))
        except (TypeError, ValueError):
            return 1
    return 1


def _active_plan_item(args: dict) -> Optional[str]:
    steps = args.get("steps")
    if not isinstance(steps, list):
        return None
    for st in steps:
        if isinstance(st, dict) and st.get("status") == "active":
            return str(st.get("text") or "")
    return ""


def _paid_ok(result_text: str) -> bool:
    """A paid call that was declined, cancelled or failed charged nothing."""
    if result_text.startswith("[tool error]") or result_text.startswith("[error]"):
        return False
    try:
        data = json.loads(result_text)
    except ValueError:
        return True
    return not (isinstance(data, dict) and (data.get("cancelled") or data.get("error")))


def _call_key(name: str, args: dict) -> str:
    return name + "\x00" + json.dumps(args, sort_keys=True, ensure_ascii=False)


def _skill_read_key(name: str, args: dict) -> str:
    if name != "skill" or str(args.get("action") or "").lower() != "read":
        return ""
    ref = args.get("name") or args.get("id") or ""
    return str(ref).strip().lower()


def _step_label(name: str, args: dict, lang: str) -> str:
    zh = lang == "zh"
    base = re.sub(r"^mcp__\w+__", "", name or "")
    if base == "skill":
        ref = str(args.get("name") or args.get("id") or "").strip()
        if str(args.get("action") or "").lower() == "read" and ref:
            return f"读取技能：{ref}" if zh else f"Read skill: {ref}"
    pair = _STEP_LABELS.get(base)
    if pair:
        return pair[0] if zh else pair[1]
    return "其他步骤" if zh else "Other step"


def _stop_summary(done: list[str], lang: str = "zh") -> str:
    """One line: shown in the chat panel's error notice (no line breaks)."""
    zh = lang == "zh"
    counts: dict[str, int] = {}
    for label in done:
        counts[label] = counts.get(label, 0) + 1
    items = [n + (f" ×{c}" if c > 1 else "") for n, c in counts.items()]
    if zh:
        return (_REPEAT_STOP_TEXT["zh"] + "已完成："
                + ("、".join(items) if items else "无"))
    return (_REPEAT_STOP_TEXT["en"] + " Done so far: "
            + (", ".join(items) if items else "nothing") + ".")


def _paid_cap_summary(n: int, done: list[str], lang: str = "zh") -> str:
    """#142 stop line, same red error notice and step list as #137."""
    zh = lang == "zh"
    counts: dict[str, int] = {}
    for label in done:
        counts[label] = counts.get(label, 0) + 1
    items = [k + (f" ×{c}" if c > 1 else "") for k, c in counts.items()]
    if zh:
        return (_PAID_CAP_TEXT["zh"].format(n=n) + "。已完成："
                + ("、".join(items) if items else "无"))
    return (_PAID_CAP_TEXT["en"].format(n=n) + " Done so far: "
            + (", ".join(items) if items else "nothing") + ".")


_THINK_RE = re.compile(r"(?:<think>|^)([\s\S]*?)</think>|<think>([\s\S]*)$")

_SYSTEM_PROMPT = AGENT_GUIDE


def _user_content(text: str, attachments: Optional[list[dict]]):
    images = [
        {"type": "image_url",
         "image_url": {"url": f"data:{a.get('media_type') or 'image/jpeg'}"
                              f";base64,{a['data']}"}}
        for a in attachments or [] if a.get("data")
    ]
    if not images:
        return text
    return [{"type": "text", "text": text}, *images]


class LocalLlmProvider(AgentProvider):
    id = "local-llm"
    label = "Local LLM"

    def __init__(self, *, base_url: Callable[[], str]) -> None:
        self._base_url_source = base_url
        self._probe_cache: Optional[tuple[float, str, ProviderStatus]] = None

    def capabilities(self) -> ProviderCaps:
        return ProviderCaps(stateful=False, tools="mcp", attachments=True)

    def _base_url(self) -> str:
        return self._base_url_source().strip().rstrip("/")

    def _api_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(_API_KEY_ENV, "")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    @staticmethod
    def _mcp_headers() -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    async def _request_json(self, session: aiohttp.ClientSession, method: str,
                            url: str, *, headers: dict,
                            json_body: Optional[dict] = None,
                            timeout: float = 120) -> dict:
        async with session.request(
            method, url, headers=headers, json=json_body,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status}: {text[:300]}")
            return json.loads(text) if text else {}

    async def probe(self) -> ProviderStatus:
        now = time.monotonic()
        base = self._base_url()
        if self._probe_cache and self._probe_cache[1] == base and now - self._probe_cache[0] < PROBE_CACHE_S:
            return self._probe_cache[2]
        if not base:
            status = ProviderStatus(
                available=False,
                detail="no endpoint configured — set the Local LLM endpoint "
                       "URL under Agent Settings",
            )
            self._probe_cache = (now, base, status)
            return status
        try:
            async with aiohttp.ClientSession() as session:
                data = await self._request_json(
                    session, "GET", f"{base}/models",
                    headers=self._api_headers(), timeout=10,
                )
            models = [str(m.get("id") or "") for m in data.get("data") or []]
            models = [m for m in models if m]
            if not models:
                status = ProviderStatus(
                    available=False,
                    detail="the endpoint is up but reports no models — load "
                           "a model first",
                )
            else:
                status = ProviderStatus(
                    available=True, version=models[0], logged_in=True,
                )
        except _NET_ERRORS as e:
            status = ProviderStatus(available=False, detail=str(e))
        self._probe_cache = (now, base, status)
        return status

    async def list_models(self) -> list[str]:
        base = self._base_url()
        if not base:
            return []
        try:
            async with aiohttp.ClientSession() as session:
                data = await self._request_json(
                    session, "GET", f"{base}/models",
                    headers=self._api_headers(), timeout=10,
                )
            models = [str(m.get("id") or "") for m in data.get("data") or []]
            return [m for m in models if m]
        except _NET_ERRORS:
            return []

    async def _mcp_list_tools(self, session: aiohttp.ClientSession,
                              endpoint: str) -> list[dict]:
        data = await self._request_json(
            session, "POST", endpoint, headers=self._mcp_headers(),
            json_body={"jsonrpc": "2.0", "id": "tools", "method": "tools/list",
                       "params": {}}, timeout=30,
        )
        tools = (data.get("result") or {}).get("tools") or []
        return [t for t in tools if t.get("name") in CORE_MCP_TOOLS]

    async def _mcp_call_tool(self, session: aiohttp.ClientSession,
                             endpoint: str, name: str,
                             arguments: dict) -> tuple[str, list[str]]:
        data = await self._request_json(
            session, "POST", endpoint, headers=self._mcp_headers(),
            json_body={"jsonrpc": "2.0", "id": f"call-{name}",
                       "method": "tools/call",
                       "params": {"name": name, "arguments": arguments}},
            timeout=560 if name == "ask_user" else 200,
        )
        result = data.get("result") or {}
        content = result.get("content")
        text = self._extract_text(content)
        images = [f"data:{b.get('mimeType') or 'image/png'};base64,{b['data']}"
                  for b in content or [] if isinstance(b, dict)
                  and b.get("type") == "image" and b.get("data")]
        if result.get("isError"):
            return "[tool error] " + text, []
        return text, images

    @staticmethod
    def _extract_text(content: object) -> str:
        if isinstance(content, str):
            return content
        parts = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
        return "\n".join(parts)

    @staticmethod
    def _build_tools(tools: list[dict]) -> list[dict]:
        return [{
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": str(tool.get("description") or "").strip(),
                "parameters": tool.get("inputSchema")
                or {"type": "object", "properties": {}},
            },
        } for tool in tools]

    @staticmethod
    def _history_messages(history: Optional[list[dict]]) -> list[dict]:
        out: list[dict] = []
        total = 0
        for msg in reversed(history or []):
            role = msg.get("role")
            text = str(msg.get("text") or "").strip()
            if role not in ("user", "assistant") or not text:
                continue
            total += len(text)
            if total > _HISTORY_CHAR_CAP:
                break
            out.append({"role": role, "content": text})
        out.reverse()
        return out

    async def _wait_stage_done(self, session: aiohttp.ClientSession,
                               endpoint: str, args: dict, model: str,
                               handle: TurnHandle) -> str:
        args = dict(args)
        args.setdefault("timeout_s", 170)
        unloaded = bool(lms.lms_bin()) and await lms.unload_models()
        try:
            raw = ""
            for _ in range(_MAX_WAIT_SLICES):
                if handle.stop_requested:
                    break
                raw, _images = await self._mcp_call_tool(
                    session, endpoint, "wait_generation", args)
                try:
                    data = json.loads(raw)
                except ValueError:
                    break
                if not isinstance(data, dict) or data.get("status") != "running":
                    break
            return raw
        finally:
            if unloaded:
                await lms.load_model(model)

    async def send(self, turn: TurnRequest, emit: EmitFn,
                   handle: TurnHandle) -> TurnResult:
        base = self._base_url()
        if not base:
            return TurnResult(
                error="no Local LLM endpoint configured — set the endpoint "
                      "URL under Agent Settings")
        try:
            async with aiohttp.ClientSession() as session:
                handle.process = session
                model = turn.model
                if not model:
                    models = await self.list_models()
                    model = models[0] if models else ""
                if not model:
                    return TurnResult(
                        error="no model available on the Local LLM endpoint")

                tools = self._build_tools(
                    await self._mcp_list_tools(session, turn.mcp_endpoint)) if turn.mcp_endpoint else []
                messages: list[dict] = [
                    *([{"role": "system", "content": _SYSTEM_PROMPT}] if tools else []),
                    *self._history_messages(turn.history),
                    {"role": "user",
                     "content": _user_content(turn.user_text,
                                              turn.attachments)},
                ]

                usage: Optional[dict] = None
                last_key = ""
                repeat = 0
                done: list[str] = []
                lang = (turn.lang if turn.lang in ("zh", "en")
                        else _reply_lang(turn.user_text))
                cache_hits = 0
                skill_cache: dict[str, str] = {}
                # an explicit "N 张" above 4 raises the cap (still quote-confirmed); a
                # smaller N keeps 4 so one retry of "做一张海报" is not blocked
                paid_cap = max(_requested_count(turn.user_text), _PAID_GEN_CAP)
                paid_used: dict[str, int] = {}
                plan_item = ""
                product_refs = _product_refs(turn.user_text)
                for _ in range(_MAX_ITERATIONS):
                    if handle.stop_requested:
                        return TurnResult(aborted=True, usage=usage)
                    data = await self._request_json(
                        session, "POST", f"{base}/chat/completions",
                        headers=self._api_headers(),
                        json_body={
                            "model": model,
                            "messages": messages,
                            **({"tools": tools, "tool_choice": "auto"} if tools else {}),
                            "temperature": 0.2,
                        },
                        timeout=_LLM_TIMEOUT_S,
                    )
                    usage = merge_usage(usage, data.get("usage"))
                    message = (data.get("choices") or [{}])[0].get("message") or {}
                    content = self._extract_text(message.get("content") or "")
                    thought = _THINK_RE.search(content)
                    reasoning = str(message.get("reasoning_content") or message.get("reasoning") or "") or (thought.group(1) or thought.group(2) or "" if thought else "")
                    content = _THINK_RE.sub("", content).strip()
                    tool_calls = message.get("tool_calls") or []

                    if reasoning.strip():
                        await emit(BotEvent(t="thinking", text=reasoning.strip()))
                    if content:
                        await emit(BotEvent(t="delta", text=content))
                    if not tool_calls:
                        return TurnResult(usage=usage)

                    messages.append({
                        "role": "assistant",
                        "content": content or None,
                        "tool_calls": tool_calls,
                    })
                    for tool_call in tool_calls:
                        if handle.stop_requested:
                            return TurnResult(aborted=True, usage=usage)
                        fn = tool_call.get("function") or {}
                        name = str(fn.get("name") or "")
                        tc_id = str(tool_call.get("id") or "")
                        raw_args = fn.get("arguments") or "{}"
                        try:
                            args = (json.loads(raw_args)
                                    if isinstance(raw_args, str) else raw_args)
                        except ValueError:
                            args = {}
                        if not isinstance(args, dict):
                            args = {}
                        key = _call_key(name, args)
                        repeat = repeat + 1 if key == last_key else 1
                        last_key = key
                        skill_key = _skill_read_key(name, args)
                        cached = bool(skill_key) and skill_key in skill_cache
                        if cached:
                            cache_hits += 1
                        if repeat >= _REPEAT_STOP or (
                                cache_hits >= _CACHED_SKILL_STOP):
                            _log.warning("[ComfyArt/local-llm] loop guard: %s "
                                         "repeat=%d cached_skill_reads=%d, "
                                         "stopping", name, repeat, cache_hits)
                            return TurnResult(usage=usage,
                                              error=_stop_summary(done, lang))
                        paid = name in PAID_TOOLS
                        units = _gen_units(name, args) if paid else 0
                        if paid and paid_used.get(plan_item, 0) + units > paid_cap:
                            _log.warning("[ComfyArt/local-llm] paid-gen guard: "
                                         "%s plan item %r used %d of %d, "
                                         "stopping", name, plan_item,
                                         paid_used.get(plan_item, 0), paid_cap)
                            return TurnResult(usage=usage, error=_paid_cap_summary(
                                paid_cap, done, lang))
                        await emit(BotEvent(t="tool_use", name=name, input=args,
                                            id=tc_id))
                        tool_failed = False
                        images: list[str] = []
                        ref_blocked = not _passes_ref(name, args, product_refs)
                        try:
                            if ref_blocked:
                                field = _REF_FIELDS[name][0]
                                result_text = _REF_BLOCK_TEXT.format(
                                    ids=", ".join(product_refs), tool=name,
                                    field=field)
                                tool_failed = True
                            elif cached:
                                result_text = skill_cache[skill_key]
                            elif name == "wait_generation":
                                result_text = await self._wait_stage_done(
                                    session, turn.mcp_endpoint, args, model,
                                    handle)
                            else:
                                result_text, images = await self._mcp_call_tool(
                                    session, turn.mcp_endpoint, name, args)
                        except _NET_ERRORS as e:
                            result_text = f"[error] {type(e).__name__}: {e}"
                            tool_failed = True
                        if skill_key and not tool_failed:
                            skill_cache.setdefault(skill_key, result_text)
                        if name == "update_plan" and not tool_failed:
                            item = _active_plan_item(args)
                            if item is not None:
                                plan_item = item
                        if paid and not tool_failed and _paid_ok(result_text):
                            paid_used[plan_item] = paid_used.get(plan_item, 0) + units
                        if not cached and not ref_blocked:  # only steps that actually ran
                            done.append(_step_label(name, args, lang))
                        if len(result_text) > TOOL_RESULT_CAP:
                            result_text = (
                                result_text[:TOOL_RESULT_CAP]
                                + f"\n…[truncated {len(result_text) - TOOL_RESULT_CAP} chars]")
                        await emit(BotEvent(
                            t="tool_result", name=name, text=result_text,
                            id=tc_id, is_error=tool_failed))
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id or name,
                            "content": result_text,
                        })
                        if images:
                            messages.append({"role": "user", "content": [
                                {"type": "text",
                                 "text": f"Images returned by {name}:"},
                                *({"type": "image_url", "image_url": {"url": u}}
                                  for u in images),
                            ]})
                return TurnResult(error="too many tool-call iterations",
                                  usage=usage)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if handle.stop_requested:
                return TurnResult(aborted=True)
            _log.exception("[ComfyArt/local-llm] turn failed")
            return TurnResult(error=str(e) or type(e).__name__)
        finally:
            handle.process = None

    async def stop(self, handle: TurnHandle) -> None:
        handle.stop_requested = True
        session = handle.process
        if isinstance(session, aiohttp.ClientSession):
            await session.close()
