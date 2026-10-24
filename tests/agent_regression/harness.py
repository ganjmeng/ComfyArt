"""#231 Agent regression harness. Everything is mocked: no real LLM, WaveSpeed or deepseek traffic.

One aiohttp test server on 127.0.0.1 carries:
  * the real ComfyArt routes (bot send, /comfyart/mcp, chat store),
  * a scripted mock LLM (OpenAI-compatible /mockllm/v1/chat/completions),
  * a mock WaveSpeed submit endpoint (/mockws/api/v3/{model}) that counts paid calls.
The ComfyArt browser page is replaced by FakePage: it plays the page's part of each canvas tool (in-memory
shapes; paid tools submit once per unit to the mock WaveSpeed; COST_DECLINED when the user cancels the confirm).
The real built-in agent (api/providers.AgentLlmProvider -> bot/local_llm.py, unchanged) runs the loop and
the real MCP dispatch + paid guard sit in between. Any DNS lookup of a non-local host is recorded and refused.
"""
from __future__ import annotations

import asyncio
import json
import re
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from aiohttp import web

ROOT = Path(__file__).resolve().parents[2]
WS_KEY = "ws-SENTINEL-231-do-not-log"
LLM_KEY = "llm-SENTINEL-231-do-not-log"
CJK = re.compile(r"[\u3400-\u9fff]")

# COST_DECLINED in src/botCommands.ts (what the page returns when the user cancels the cost confirm)
COST_DECLINED = {
    "cancelled": True, "status": "declined",
    "note": "已取消该生成，未扣费 / Cancelled this generation; nothing was charged. "
            "Reply to the user with that message in a normal chat message (not as an error or notice), "
            "then ask how they want to adjust. Do not retry, resubmit, or change model/params for this plan item in this turn.",
}


def curated_ids() -> dict[str, set[str]]:
    data = json.loads((ROOT / "api" / "curated_models.json").read_text())["features"]
    return {f: {*spec.get("models", []), *spec.get("more", []), spec.get("default")} - {None}
            for f, spec in data.items() if isinstance(spec, dict)}


# ---------------------------------------------------------------- network guard
class NetGuard:
    LOCAL = {"127.0.0.1", "localhost", "::1", None, ""}

    def __init__(self) -> None:
        self.blocked: list[str] = []
        self._orig = socket.getaddrinfo

    def __enter__(self):
        def guarded(host, *a, **k):
            h = host.decode() if isinstance(host, bytes) else host
            if h not in self.LOCAL:
                self.blocked.append(str(h))
                raise socket.gaierror(f"agent regression: network to {h} is blocked")
            return self._orig(host, *a, **k)
        socket.getaddrinfo = guarded
        return self

    def __exit__(self, *exc):
        socket.getaddrinfo = self._orig


# ---------------------------------------------------------------- the fake page
@dataclass
class Shape:
    id: str
    type: str
    x: float = 0
    y: float = 0
    w: float = 512
    h: float = 512
    text: str = ""
    parent: str = ""
    props: dict = field(default_factory=dict)

    def view(self) -> dict:
        d = {"id": self.id, "type": self.type, "x": self.x, "y": self.y, "width": self.w, "height": self.h}
        if self.text:
            d["text"] = self.text
        if self.parent:
            d["parent"] = self.parent
        d.update(self.props)
        return d


KINDS = {"generate_image": "image", "edit_image": "image", "generate_video": "video", "animate_image": "image",
         "generate_music": "audio", "generate_sound_effect": "audio", "text_to_speech": "audio",
         "image_to_3d": "model3d", "edit_elements": "image"}


class FakePage:
    def __init__(self, *, ws_url: str, decline: bool = False, shapes: Optional[list[Shape]] = None,
                 selection: Optional[list[str]] = None, brand_kit: Optional[dict] = None) -> None:
        self.ws_url = ws_url
        self.decline = decline
        self.shapes: dict[str, Shape] = {s.id: s for s in shapes or []}
        self.selection = selection or []
        self.brand_kit = brand_kit
        self.jobs: dict[str, list[str]] = {}
        self.models: list[tuple[str, str, str]] = []  # (tool, feature, model)
        self.n = 0
        self.confirms = 0
        self.payloads: list[dict] = []       # what went to (mock) WaveSpeed, per submit
        self.edits: list[dict] = []          # edit_image: snapshot of the input shape + the output id

    def _new(self, kind: str, **kw) -> Shape:
        self.n += 1
        s = Shape(id=f"shape:gen{self.n}", type=kind, x=600 * self.n, **kw)
        if kind in ("image", "video", "audio", "model3d"):
            s.props.setdefault("asset", f"asset:{s.id}")
        self.shapes[s.id] = s
        return s

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for s in self.shapes.values():
            out[s.type] = out.get(s.type, 0) + 1
        return out

    async def _submit(self, tool: str, args: dict, units: int) -> str:
        from ComfyArt.api import wavespeed
        cfg = wavespeed.load_config()
        feature = cfg["tool_features"].get(tool) or ""
        if tool == "generate_video":
            feature = "image_to_video" if args.get("first_frame") else "text_to_video"
        if tool == "generate_image" and (args.get("refs") or args.get("base")):
            feature = "image_edit"
        model = str(args.get("edit_model") or args.get("model") or cfg["features"][feature]["default"])
        self.models.append((tool, feature, model))
        import aiohttp
        payload = {"prompt": args.get("prompt") or args.get("text") or ""}
        src = self.shapes.get(str(args.get("id") or args.get("first_frame") or ""))
        if src is not None:
            payload["image"] = src.props.get("asset", "")  # the input image the edit/i2v is made from
        async with aiohttp.ClientSession() as s:
            for _ in range(units):
                self.payloads.append({"tool": tool, "model": model, **payload})
                async with s.post(f"{self.ws_url}/api/v3/{model}", headers={"Authorization": f"Bearer {wavespeed._key()}"},
                                  json=payload) as r:
                    assert r.status == 200
        return model

    async def __call__(self, action: str, args: dict, project: str, timeout: float = 20, chat: str = "") -> dict:
        from ComfyArt.api.paid_guard import gen_units
        if action == "get_canvas":
            return {"page": args.get("page") or "Page 1", "shapes": [s.view() for s in self.shapes.values()],
                    "selection": self.selection, "brand_kit": (self.brand_kit or {}).get("name")}
        if action == "brand_kits":
            return {"kits": [self.brand_kit] if self.brand_kit else [], "linked": (self.brand_kit or {}).get("name")}
        if action == "wait_generation":
            return {"status": "done", "results": [{"id": i, "status": "done", "shapes": self.jobs.get(i, [])}
                                                  for i in args.get("ids") or []]}
        if action == "update_shapes":
            for u in args.get("updates") or []:
                s = self.shapes[u["id"]]
                if "text" in u:
                    s.text = u["text"]
                if "color" in u:
                    s.props["color"] = u["color"]
            return {"ok": True}
        if action == "add_text":
            s = self._new("text", text=args["text"], props={k: args[k] for k in ("font", "color") if k in args})
            return {"id": s.id}
        if action == "create_slides":
            frames, gens = [], []
            images = [sl for sl in args["slides"] if sl.get("image")]
            if images:
                self.confirms += 1
                if self.decline:
                    return dict(COST_DECLINED)
            for sl in args["slides"]:
                f = self._new("frame", w=1280, h=720, props={"name": sl["title"]})
                self._new("text", text=sl["title"], parent=f.id)
                for b in sl.get("bullets") or []:
                    self._new("text", text=b, parent=f.id)
                if sl.get("image"):
                    await self._submit("generate_image", {"prompt": sl["image"]}, 1)
                    img = self._new("image", parent=f.id)
                    gens.append(img.id)
                    self.jobs[img.id] = [img.id]
                frames.append(f.id)
            return {"frames": frames, "ids": gens}
        if action in KINDS:
            self.confirms += 1
            if self.decline:
                return dict(COST_DECLINED)
            units = gen_units(action, args)
            if action == "edit_image":
                from dataclasses import asdict
                self.edits.append({"input": asdict(self.shapes[args["id"]]), "before": set(self.shapes)})
            model = await self._submit(action, args, units)
            job = f"job:{len(self.jobs) + 1}"
            if action == "edit_elements":
                frame = self._new("frame")
                bg = self._new("image", parent=frame.id)
                title = self._new("text", text="SUMMER", parent=frame.id, props={"name": "title"})
                sub = self._new("text", text="50% OFF", parent=frame.id)
                self.jobs[job] = [bg.id, title.id, sub.id]
            else:
                extra = {"source": args["id"]} if action == "edit_image" else {}
                self.jobs[job] = [self._new(KINDS[action], props=dict(extra)).id for _ in range(units)]
            if action == "edit_image":
                self.edits[-1]["output"] = self.jobs[job]
            return {"ids": [job], "model": model, "note": "call wait_generation with these ids"}
        return {"ok": True}


# ---------------------------------------------------------------- the scripted LLM
@dataclass
class Step:
    """One LLM response: tool calls, or a final reply, or an injected fault ("timeout" | 429 | 500)."""
    calls: list[tuple[str, Any]] = field(default_factory=list)
    reply: Optional[dict] = None
    fault: Any = None


def _last_tool(messages: list[dict]) -> dict:
    for m in reversed(messages):
        if m.get("role") == "tool":
            try:
                return json.loads(m["content"])
            except (ValueError, TypeError):
                return {}
    return {}


class MockLLM:
    def __init__(self, script: list[Step]) -> None:
        self.script = list(script)
        self.requests: list[dict] = []
        self.auth: list[str] = []
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}
        self.timeout_sleep = 1.0

    async def models(self, _r):
        return web.json_response({"data": [{"id": "mock-agent-model"}]})

    async def chat(self, request: web.Request):
        body = await request.json()
        self.requests.append(body)
        self.auth.append(request.headers.get("Authorization", ""))
        if not self.script:
            return web.json_response({"error": "script exhausted"}, status=500)
        step = self.script.pop(0)
        if step.fault == "timeout":
            await asyncio.sleep(self.timeout_sleep)
            return web.json_response({"error": "late"}, status=504)
        if step.fault:
            return web.json_response({"error": {"message": f"mock {step.fault}"}}, status=int(step.fault))
        msgs = body["messages"]
        user = next(m for m in reversed(msgs) if m["role"] == "user" and isinstance(m.get("content"), str))
        lang = "zh" if CJK.search(user["content"]) else "en"  # the model follows the user's language (AGENT_GUIDE)
        last = _last_tool(msgs)
        calls = []
        for i, (name, args) in enumerate(step.calls):
            a = args(last) if callable(args) else args
            calls.append({"id": f"c{len(self.requests)}_{i}", "type": "function",
                          "function": {"name": name, "arguments": json.dumps(a, ensure_ascii=False)}})
        prompt_t = len(json.dumps(msgs, ensure_ascii=False)) // 4
        completion_t = 20 + 10 * len(calls)
        self.usage["prompt_tokens"] += prompt_t
        self.usage["completion_tokens"] += completion_t
        msg = {"role": "assistant", "content": (step.reply or {}).get(lang, "") if step.reply else "",
               "tool_calls": calls}
        return web.json_response({"choices": [{"message": msg}],
                                  "usage": {"prompt_tokens": prompt_t, "completion_tokens": completion_t}})


class MockWS:
    def __init__(self) -> None:
        self.submits: list[str] = []
        self.auth: list[str] = []

    async def submit(self, request: web.Request):
        self.submits.append(request.match_info["model"])
        self.auth.append(request.headers.get("Authorization", ""))
        return web.json_response({"code": 200, "data": {"id": f"task{len(self.submits)}", "status": "created"}})
