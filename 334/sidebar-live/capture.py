#!/usr/bin/env python3
"""#334 #78: capture Question card inside real tip dist AgentPanel (.ca-agent).

Honest label: Playwright Chromium + tip dist AgentPanel (production React QuestionCard)
against stubbed ComfyArt aiohttp routes — NOT full Electron desktop / not live LLM ask.
Closer than tip-CSS / chat-shell HTML harness: real .ca-agent chrome, composer, chat list,
tip CSS/JS from dist @ HEAD (#334 open-text clip + last Submit #2d2d2d+#fff + multi-block page chrome).

Shots: light+dark × soft-select letter + multi-block page (open/single/multi) × Lovart compares.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path("/workspace/ComfyArt_334").resolve()
OUT = Path("/workspace/comfyart-334-sidebar-live/shots")
OUT.mkdir(parents=True, exist_ok=True)

# Import path: /workspace/ComfyArt -> ComfyArt_337
sys.path.insert(0, str(ROOT.parent))
os.environ.setdefault("COMFYART_SKIP_KEY_CHECK", "1")

# --- stubs (mirrors tests/conftest.py, minimal) ---
BASE = Path(tempfile.mkdtemp(prefix="ca337-sidebar-"))
SENT: list = []


def _make_module(name: str, **attrs) -> types.ModuleType:
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


def _install_stubs() -> None:
    state = {"base": BASE}

    def _annotated_filepath(name: str) -> str:
        kind = "input"
        for t in ("input", "output", "temp"):
            if name.endswith(f" [{t}]"):
                name, kind = name[: -len(t) - 3], t
        return str(state["base"] / kind / name)

    def _save_image_path(prefix: str, root: str):
        subfolder, _, name = prefix.rpartition("/")
        folder = os.path.join(root, subfolder)
        os.makedirs(folder, exist_ok=True)
        return folder, name, 1, subfolder, prefix

    def user_dir() -> str:
        return str(state["base"] / "user")

    _make_module(
        "folder_paths",
        STATE=state,
        SYSTEM_USER_PREFIX="__",
        get_user_directory=user_dir,
        get_system_user_directory=lambda name="system": os.path.join(user_dir(), f"__{name}"),
        get_public_user_directory=lambda user: None if user.startswith("__") else os.path.join(user_dir(), user),
        get_input_directory=lambda: str(state["base"] / "input"),
        get_output_directory=lambda: str(state["base"] / "output"),
        get_temp_directory=lambda: str(state["base"] / "temp"),
        get_annotated_filepath=_annotated_filepath,
        get_save_image_path=_save_image_path,
        get_directory_by_type=lambda t: str(state["base"] / t) if t in ("input", "output", "temp") else None,
        get_filename_list=lambda kind: [],
        get_full_path_or_raise=lambda kind, name: name,
        folder_names_and_paths={},
    )
    comfy = _make_module("comfy")
    comfy.ops = _make_module("comfy.ops", manual_cast=object)
    comfy.sd = _make_module("comfy.sd", load_diffusion_model=lambda *a, **k: None)
    comfy.utils = _make_module("comfy.utils", ProgressBar=lambda total: types.SimpleNamespace(update=lambda n: None))
    comfy.model_management = _make_module(
        "comfy.model_management", throw_exception_if_processing_interrupted=lambda: None
    )
    comfy.cli_args = _make_module(
        "comfy.cli_args", args=types.SimpleNamespace(tls_keyfile=None, tls_certfile=None)
    )

    from aiohttp import web

    class _UserManager:
        users = {"default", "alice"}

        def get_request_user_id(self, request):
            user = request.headers.get("comfy-user", "default")
            if user not in self.users:
                raise KeyError("Unknown user: " + user)
            return user

        def get_request_user_filepath(self, request, file, create_dir=True):
            root = os.path.join(user_dir(), self.get_request_user_id(request))
            path = os.path.abspath(os.path.join(root, file))
            return path if os.path.commonpath((root, path)) == root else None

    class _Queue:
        def get_tasks_remaining(self):
            return 0

    class _PromptServer:
        instance = None

    ps = _PromptServer()
    ps.routes = web.RouteTableDef()
    ps.address = "127.0.0.1"
    ps.port = 8188
    ps.user_manager = _UserManager()
    ps.prompt_queue = _Queue()
    ps.sockets = {}
    ps.send_sync = lambda event, data, sid=None: SENT.append(
        (event, {**data, "_sid": sid} if sid else data)
    )
    _PromptServer.instance = ps
    _make_module("server", PromptServer=_PromptServer)


_install_stubs()

# Importing ComfyArt registers routes on PromptServer.instance.routes
from aiohttp import web  # noqa: E402
from aiohttp.test_utils import TestServer  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

import ComfyArt  # noqa: E402,F401
from ComfyArt.api import bot_asks, chat_store, project_store  # noqa: E402
from server import PromptServer  # noqa: E402

PID = "p337sidebar"
PROMPT = "这套视觉面向哪类消费者与价格带？"
OPTS = [
    {"id": "a", "label": "高端精品茶饮"},
    {"id": "b", "label": "年轻快时尚茶饮"},
    {"id": "c", "label": "社区日常茶饮"},
]


def _snapshot(name: str) -> dict:
    store = {
        "document:document": {"id": "document:document", "typeName": "document", "name": name},
        "page:page": {
            "id": "page:page",
            "typeName": "page",
            "name": "Page 1",
            "index": "a1",
            "meta": {},
        },
    }
    return {"document": {"store": store, "schema": {}}, "session": {}}


async def start_app() -> tuple[TestServer, str]:
    base = BASE
    for d in ("input", "output", "temp", "user/default"):
        (base / d).mkdir(parents=True, exist_ok=True)

    app = web.Application(client_max_size=200 * 2**20)
    app.router.add_routes(PromptServer.instance.routes)
    for rd in PromptServer.instance.routes:
        if isinstance(rd, web.RouteDef):
            app.router.add_route(rd.method, "/api" + rd.path, rd.handler)

    def ud(r):
        return base / "user/default" / r.match_info["file"]

    async def ud_get(r):
        return web.FileResponse(ud(r)) if ud(r).is_file() else web.Response(status=404)

    async def ud_post(r):
        ud(r).parent.mkdir(parents=True, exist_ok=True)
        ud(r).write_bytes(await r.read())
        return web.json_response(r.match_info["file"])

    async def view(r):
        q = r.query
        p = base / q.get("type", "output") / q.get("subfolder", "") / q["filename"]
        return web.FileResponse(p) if p.is_file() else web.Response(status=404)

    async def upload_image(r):
        form = await r.post()
        f, sub, kind = form["image"], form.get("subfolder", ""), form.get("type", "input")
        (base / kind / sub).mkdir(parents=True, exist_ok=True)
        (base / kind / sub / f.filename).write_bytes(f.file.read())
        return web.json_response({"name": f.filename, "subfolder": sub, "type": kind})

    async def wsock(r):
        s = web.WebSocketResponse()
        await s.prepare(r)
        async for _ in s:
            pass
        return s

    def js(v):
        async def h(r):
            return web.json_response(v)

        return h

    for path, h in (
        ("/api/userdata", js([])),
        ("/api/models/{k}", js([])),
        ("/api/settings/{id}", js(None)),
        ("/api/queue", js({"queue_running": [], "queue_pending": []})),
        ("/api/view", view),
        ("/api/userdata/{file:.+}", ud_get),
        ("/ws", wsock),
    ):
        app.router.add_get(path, h)
    for path, h in (
        ("/api/settings/{id}", js({})),
        ("/api/queue", js({})),
        ("/api/interrupt", js({})),
        ("/api/userdata/{file:.+}", ud_post),
        ("/api/upload/image", upload_image),
    ):
        app.router.add_post(path, h)

    server = TestServer(app)
    await server.start_server()
    return server, str(server.make_url("/comfyart/"))


def seed_chat(
    *,
    pid: str,
    title: str,
    prompt: str | None = None,
    options: list[dict] | None = None,
    max_selections: int = 1,
    placeholder: str | None = None,
    questions: list[dict] | None = None,
    page_count: int | None = None,
) -> tuple[str, str]:
    """Create project + chat + pending kind=question ask. Returns (chat_id, ask_id)."""
    project_store.save_project(
        "default", pid, json.dumps(_snapshot(f"#340 {title}"), ensure_ascii=False), f"#340 {title}", []
    )
    chat = chat_store.create_chat(
        user="default", project=pid, provider="comfyart", title=title, run_mode="ask"
    )
    user_msg = chat_store.create_message(
        chat_id=chat["id"],
        role="user",
        blocks=[{"type": "text", "text": "帮我做一套新中式茶饮品牌视觉"}],
    )
    if questions is not None:
        spec_raw: dict = {
            "questions": questions,
            "allow_skip": True,
        }
        if page_count is not None:
            spec_raw["page_count"] = page_count
    else:
        spec_raw = {
            "prompt": prompt or "",
            "options": options or [],
            "allow_other": True,
            "allow_skip": True,
            "min_selections": 1,
            "max_selections": max_selections,
        }
        if placeholder:
            spec_raw["placeholder"] = placeholder
    spec = bot_asks.validate_spec(spec_raw)
    asst = chat_store.create_message(
        chat_id=chat["id"],
        role="assistant",
        parent_id=user_msg["id"],
        blocks=[{"type": "text", "text": "先确认几个方向，方便我出更贴的方案："}],
        status="done",
    )
    ask = bot_asks.create_ask(chat["id"], asst["id"], spec)
    block = {"type": "ask", "ask_id": ask.id, "status": "pending", **spec}
    chat_store.update_message(
        chat["id"],
        asst["id"],
        blocks=[
            {"type": "text", "text": "先确认几个方向，方便我出更贴的方案："},
            block,
        ],
    )
    nq = len(spec.get("questions") or [])
    print(
        "seeded chat",
        chat["id"],
        "ask",
        ask.id,
        "spec.kind",
        spec.get("kind"),
        "questions",
        nq,
        "pages",
        spec.get("page_count"),
        "max",
        max_selections,
    )
    return chat["id"], ask.id


async def open_seeded_chat(page, chat_id: str) -> None:
    await page.locator("aside.ca-agent").wait_for(timeout=30000)
    hist = page.locator(
        'button.ca-split__chev[title*="历史"], button.ca-split__chev[title*="History"], button.ca-split__chev'
    ).first
    await hist.wait_for(timeout=15000)
    await hist.click()
    item = page.locator(".ca-history__item").first
    await item.wait_for(timeout=10000)
    await item.click()
    await page.locator(".ca-q").wait_for(timeout=15000)


async def shot_state(page, name: str) -> None:
    agent = page.locator("aside.ca-agent")
    await agent.wait_for()
    await agent.screenshot(path=str(OUT / f"{name}-col.png"))
    box = await agent.bounding_box()
    if box:
        await page.screenshot(
            path=str(OUT / f"{name}.png"),
            clip={
                "x": max(0, box["x"]),
                "y": max(0, box["y"]),
                "width": min(box["width"] + 220, page.viewport_size["width"] - box["x"]),
                "height": box["height"],
            },
        )
    # card crop for denser compare
    card = page.locator(".ca-q")
    if await card.count():
        await card.first.screenshot(path=str(OUT / f"{name}-card.png"))
    print("wrote", name)


async def interact_single(page, theme: str) -> None:
    prefix = theme
    await page.locator(".ca-q").wait_for()
    other = page.locator(".ca-q__opt[data-other] .ca-q__input")
    await other.fill("")
    await shot_state(page, f"{prefix}-empty")

    await other.fill("包装袋")
    await other.blur()
    await page.wait_for_timeout(200)
    await shot_state(page, f"{prefix}-other")

    await page.locator(".ca-q__opt").filter(has=page.locator(".ca-q__letter", has_text="A")).click()
    await page.wait_for_timeout(200)
    val = await other.input_value()
    assert val == "包装袋", val
    await shot_state(page, f"{prefix}-keep")

    await other.fill("")
    await page.locator(".ca-q__opt").filter(has=page.locator(".ca-q__letter", has_text="B")).click()
    await page.wait_for_timeout(200)
    await shot_state(page, f"{prefix}-soft")


async def interact_multi(page, theme: str) -> None:
    """RS/105: （多选） hint, ≥2 soft-select stacked, Other末字母 input."""
    prefix = f"{theme}-multi"
    await page.locator(".ca-q").wait_for()
    hint = page.locator(".ca-q__hint")
    assert await hint.count() >= 1, "missing （多选） hint"
    # select A then B (stacked soft)
    await page.locator(".ca-q__opt").filter(has=page.locator(".ca-q__letter", has_text="A")).click()
    await page.locator(".ca-q__opt").filter(has=page.locator(".ca-q__letter", has_text="B")).click()
    await page.wait_for_timeout(150)
    other = page.locator(".ca-q__opt[data-other] .ca-q__input")
    await other.fill("其他方向补充")
    await other.blur()
    await page.wait_for_timeout(200)
    # A and B should stay on in multi; other also soft-on
    on_count = await page.locator(".ca-q__opt[data-on]").count()
    assert on_count >= 2, f"expected ≥2 soft-select, got {on_count}"
    await shot_state(page, prefix)


async def interact_multicard(page, theme: str) -> None:
    """#334: open-text empty/filled + mid Next + body clip + last-page 提交↵ (disabled+enabled)."""
    prefix = f"{theme}-multicard"
    await page.locator(".ca-q").wait_for()
    blocks = page.locator(".ca-q__block")
    n_blocks = await blocks.count()
    assert n_blocks >= 2, f"expected multi-block page, got {n_blocks} .ca-q__block"
    pager = page.locator(".ca-q__page")
    assert await pager.count() >= 1, "missing ‹ n of N › pager"
    # #334: empty open-text row before fill (placeholder clip/ellipsis)
    await shot_state(page, prefix + "-opentext-empty")
    # soft-select on single block (2nd) option B
    await page.locator(".ca-q__block").nth(1).locator(".ca-q__opt").filter(
        has=page.locator(".ca-q__letter", has_text="B")
    ).click()
    # multi block (3rd) pick A+B
    multi_block = page.locator(".ca-q__block").nth(2)
    assert await multi_block.locator(".ca-q__hint").count() >= 1, "missing （多选）"
    await multi_block.locator(".ca-q__opt").filter(has=page.locator(".ca-q__letter", has_text="A")).click()
    await multi_block.locator(".ca-q__opt").filter(has=page.locator(".ca-q__letter", has_text="B")).click()
    # fill open text so pageOk for Next
    open_in = page.locator(".ca-q__block").nth(0).locator(".ca-q__input")
    await open_in.fill("源野 / 户外背包")
    await open_in.blur()
    await page.wait_for_timeout(200)
    next_btn = page.locator(".ca-q__submit")
    txt = (await next_btn.inner_text()).replace("\n", " ")
    assert "下一步" in txt or "Next" in txt or "→" in txt, f"expected mid-page Next, got {txt!r}"
    await shot_state(page, prefix)
    # scroll body so multi block + （多选） / 末题脚裁切 visible (RS/94)
    body = page.locator(".ca-q__body")
    await body.evaluate("el => { el.scrollTop = el.scrollHeight }")
    await page.wait_for_timeout(150)
    await shot_state(page, prefix + "-scroll")
    assert n_blocks >= 3, f"expected ≥3 blocks on page, got {n_blocks}"
    # #334: advance to last page → 提交↵
    await body.evaluate("el => { el.scrollTop = 0 }")
    await next_btn.click()
    await page.wait_for_timeout(250)
    submit = page.locator(".ca-q__submit")
    stxt = (await submit.inner_text()).replace("\n", " ")
    assert "提交" in stxt or "Submit" in stxt or "↵" in stxt, f"expected last-page Submit, got {stxt!r}"
    # disabled until page-2 filled
    assert await submit.is_disabled(), "last-page Submit should be disabled before page-2 answer"
    await shot_state(page, prefix + "-last-disabled")
    # fill page-2 single select
    await page.locator(".ca-q__block").nth(0).locator(".ca-q__opt").filter(
        has=page.locator(".ca-q__letter", has_text="A")
    ).click()
    await page.wait_for_timeout(150)
    assert await submit.is_enabled(), "last-page Submit should enable when all pages filled"
    stxt2 = (await submit.inner_text()).replace("\n", " ")
    assert "提交" in stxt2 or "↵" in stxt2, f"expected 提交↵, got {stxt2!r}"
    await shot_state(page, prefix + "-last-submit")


async def run_theme(browser, base_url: str, pid: str, theme: str, mode: str) -> None:
    ctx = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="zh-CN",
        color_scheme="dark" if theme == "dark" else "light",
    )
    page = await ctx.new_page()
    await page.add_init_script(
        f"""
      localStorage.setItem('comfyart.lang', 'zh');
      localStorage.setItem('comfyart.theme', '{theme}');
    """
    )
    await page.goto(base_url + f"?project={pid}", wait_until="networkidle")
    try:
        await page.locator("aside.ca-agent").wait_for(timeout=45000)
    except Exception:
        await page.screenshot(path=str(OUT / f"debug-{theme}-{mode}-boot.png"), full_page=True)
        html = await page.content()
        (OUT / f"debug-{theme}-{mode}-boot.html").write_text(html[:50000], encoding="utf-8")
        raise
    await page.wait_for_timeout(1200)
    if await page.locator(".ca-modal").count():
        try:
            await page.locator(".ca-modal button").last.click(timeout=2000)
        except Exception:
            pass

    await open_seeded_chat(page, "")
    await page.wait_for_timeout(400)
    if mode == "multicard":
        await interact_multicard(page, theme)
    elif mode == "multi":
        await interact_multi(page, theme)
    else:
        await interact_single(page, theme)
    await ctx.close()


async def main() -> None:
    single_opts = [
        {"id": "a", "label": "高端精品茶饮"},
        {"id": "b", "label": "年轻快时尚茶饮"},
        {"id": "c", "label": "社区日常茶饮"},
    ]
    multi_opts = [
        {"id": "a", "label": "品牌故事海报"},
        {"id": "b", "label": "包装袋主视觉"},
        {"id": "c", "label": "门店空间物料"},
    ]
    # RS/94·105 multi-block page (open + single + multi) + page 2 for pager/Next
    multicard_questions = [
        {
            "id": "brand",
            "prompt": "品牌名称是什么？行业或品类是什么？",
            "options": [],
            "allow_other": True,
            "placeholder": "例如：源野 / 户外背包品牌…",
            "page": 1,
        },
        {
            "id": "vibe",
            "prompt": "品牌想传递什么样的气质或风格？",
            "options": [
                {"id": "a", "label": "极简高级"},
                {"id": "b", "label": "活泼年轻"},
                {"id": "c", "label": "自然有机"},
                {"id": "d", "label": "未来科技"},
            ],
            "allow_other": True,
            "max_selections": 1,
            "min_selections": 1,
            "page": 1,
        },
        {
            "id": "deliverables",
            "prompt": "你期望这套品牌视觉包含哪些交付物？",
            "options": [
                {"id": "a", "label": "品牌故事海报"},
                {"id": "b", "label": "包装袋主视觉"},
                {"id": "c", "label": "门店空间物料"},
            ],
            "allow_other": True,
            "max_selections": 3,
            "min_selections": 1,
            "placeholder": "其他方向…",
            "page": 1,
        },
        {
            "id": "audience",
            "prompt": "这套视觉面向哪类消费者与价格带？",
            "options": single_opts,
            "allow_other": True,
            "max_selections": 1,
            "min_selections": 1,
            "page": 2,
        },
    ]
    pid_single = "p340sidebar"
    pid_multi = "p340multi"
    pid_multicard = "p340multicard"
    seed_chat(
        pid=pid_single,
        title="茶饮视觉方向",
        prompt="这套视觉面向哪类消费者与价格带？",
        options=single_opts,
        max_selections=1,
    )
    seed_chat(
        pid=pid_multi,
        title="多选物料方向",
        prompt="本次需要哪些视觉物料？",
        options=multi_opts,
        max_selections=3,
        placeholder="其他方向…",
    )
    seed_chat(
        pid=pid_multicard,
        title="一卡多题叠卡",
        questions=multicard_questions,
        page_count=2,
    )
    server, base_url = await start_app()
    print("app", base_url)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            for theme in ("light", "dark"):
                await run_theme(browser, base_url, pid_single, theme, "single")
                await run_theme(browser, base_url, pid_multi, theme, "multi")
                await run_theme(browser, base_url, pid_multicard, theme, "multicard")
            await browser.close()
    finally:
        await server.close()
    print("DONE shots in", OUT)
    for f in sorted(OUT.glob("*.png")):
        print(" ", f.name, f.stat().st_size)


if __name__ == "__main__":
    asyncio.run(main())
