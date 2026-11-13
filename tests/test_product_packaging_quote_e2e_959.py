"""#959 / #963 Full App mock e2e ($0): quote card → Start → four real submits.

The real built app, real ComfyArt routes, real chat panel, real LocalLlmProvider
agent loop with a scripted LLM (no LLM call), the real plan gate, real MCP tool
dispatch and the real generate_image handler; WaveSpeed is the local mock and
nothing is submitted to it.

Shows the four-line plan-quote card, clicks Start (the real answer route), then
asserts the four submissions use the quote's per-image parameters (anchor 3:4 2k
1 ref, extensions 4:3 2k 2 refs, Sunburst edit) and the real anchor replaces the
quote placeholder. EVIDENCE_959_SHOTS=/dir keeps the zh/en screenshots for
review-assets.

dist/ must be a local build of this tree (`npx vite build`, not committed); a
missing or stale dist/ or a missing Chromium is a hard failure, never a skip.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import re
from pathlib import Path

import pytest

from conftest import write_settings
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (real routes + local mock WaveSpeed)
from test_skill_e2e_portrait_studio import ws_forward  # noqa: F401

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
SHOTS = os.environ.get("EVIDENCE_959_SHOTS")
LOC = {lg: json.loads((ROOT / f"src/locales/{lg}.json").read_text(encoding="utf-8")) for lg in ("zh", "en")}
UPLOAD = Path(__file__).parent / "fixtures" / "ma_subject_691.png"
USER_TEXT = {"zh": "用这张产品图做一套包装。", "en": "Make a packaging set from this product photo."}
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"


@pytest.fixture(autouse=True, scope="module")
def built_dist():
    index = ROOT / "dist" / "index.html"
    if not index.is_file():
        pytest.fail("dist/index.html is missing: run `npx vite build` (local build, not committed) before this e2e")
    bundle = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "dist").rglob("*.js"))
    if "pk_scope" not in bundle or "chat-inline-planquote" not in bundle:
        pytest.fail("dist/ is stale (no packaging card / plan-quote card): run `npx vite build` (local, not committed)")


@pytest.fixture(autouse=True)
def no_paid_keys(monkeypatch):
    for key in ("WAVESPEED_API_KEY", "KIE_API_KEY", "DEEPSEEK_API_KEY", "REPLICATE_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def _mock_price(inputs: dict) -> float:
    unit = {"3:4": 0.03, "4:3": 0.05}[str(inputs.get("ratio") or inputs.get("aspect_ratio") or "3:4")]
    if str(inputs.get("resolution")) == "2k":
        unit += 0.02
    unit += 0.01 * max(0, len(inputs.get("images") or []) - 1)
    return round(unit, 6)


def _steps() -> list[dict]:
    prompts = ["anchor: the package and the product in one key visual",
               "the outer box from several angles", "the label close up",
               "the unboxing with the inner tray"]
    out = []
    for i, prompt in enumerate(prompts):
        refs = ["loose:0"] if i == 0 else ["loose:0", "shape:planned-anchor-959"]
        out.append({"text": f"图 {i + 1}", "tool": "generate_image", "model": "",
                    "arguments": {"prompt": prompt, "skill": "product-to-packaging", "refs": refs, "count": 1}})
    return out


def _anchor_from(messages: list) -> str:
    """The placed anchor, read from the image-1 / wait_generation tool results (what the agent sees)."""
    for m in reversed(messages):
        if m.get("role") != "tool":
            continue
        try:
            data = json.loads(str(m.get("content") or ""))
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        results = data.get("results")
        if isinstance(results, list) and results and (results[0] or {}).get("urls"):
            return str(results[0]["urls"][0])
        ids = data.get("ids")
        if ids:
            return str(ids[0])
    return ""


def _tc(i, name, args):
    return {"id": f"t{i}", "function": {"name": name, "arguments": json.dumps(args)}}


def _calls(*items):
    return {"choices": [{"message": {"content": "", "tool_calls": [
        _tc(i, n, a) for i, (n, a) in enumerate(items)]}}]}


def _reply(text):
    return {"choices": [{"message": {"content": text, "tool_calls": []}}]}


@pytest.fixture
def local_agent(monkeypatch):
    """The real built-in agent loop with a scripted LLM; the MCP call dispatches the real tools."""
    from ComfyArt.api import mcp
    from ComfyArt.bot import providers
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID, GUARD_CHAT_ID, PROJECT
    from ComfyArt.bot.guide import CORE_MCP_TOOLS
    from ComfyArt.bot.local_llm import LocalLlmProvider

    provider = LocalLlmProvider(base_url=lambda: "http://fake-llm/v1")
    state = {"n": 0, "quote": None, "routed": [], "product": ""}

    def product_of(messages):
        # The uploaded product photo: the first /api/view image in the turn (attachments),
        # never a later generated result that the extension calls add.
        for m in messages:
            text = m.get("content") if isinstance(m.get("content"), str) else json.dumps(m.get("content"))
            found = re.search(r"/api/view\?filename=[^\s\"')\\]+", text or "")
            if found:
                return found.group(0).rstrip(".,;")
        return ""

    def plan_of(product):
        out = _steps()
        for i, step in enumerate(out):
            step["arguments"]["refs"] = [product] if i == 0 else [product, "shape:planned-anchor-959"]
        return out

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        body = json_body or {}
        if body.get("method") == "tools/list":
            return {"result": {"tools": [
                {"name": n, "description": "", "inputSchema": {"type": "object", "properties": {}}}
                for n in CORE_MCP_TOOLS]}}
        if not str(url).endswith("/chat/completions"):
            return {"data": [{"id": "fake-959", "context_length": 32000}]}
        messages = body.get("messages") or []
        product = product_of(messages) or state.get("product")
        state["product"] = product
        plan = plan_of(product)
        n = state["n"]
        state["n"] += 1
        if n == 0:
            return _calls(("quote_plan", {"steps": plan}))
        if n == 1:
            return _calls(("generate_image", copy.deepcopy(plan[0]["arguments"])))
        if n == 2:
            return _calls(("wait_generation", {"ids": [_anchor_from(messages)]}))
        if 3 <= n <= 5:
            # All three extensions extend image 1 (the anchor), whose delivered URL is
            # in the wait_generation result; the plan's placeholder is replaced by it.
            anchor = state.setdefault("anchor", _anchor_from(messages))
            args = copy.deepcopy(plan[n - 2]["arguments"])
            args["refs"] = [product, anchor]
            state.setdefault("actual", []).append(copy.deepcopy(args))
            return _calls(("generate_image", args))
        return _reply("好")

    async def real_mcp(session, endpoint, name, arguments):
        from ComfyArt.api import chat_store
        chat_id = state.get("chat") or ""
        row = chat_store.get_chat(chat_id) if chat_id else None
        project = str((row or {}).get("project") or "")
        token = BOT_CHAT_ID.set(chat_id)
        guard_token = GUARD_CHAT_ID.set(chat_id)
        project_token = PROJECT.set(project)
        try:
            out = await mcp._tools_call({"name": name, "arguments": arguments})
        finally:
            BOT_CHAT_ID.reset(token)
            GUARD_CHAT_ID.reset(guard_token)
            PROJECT.reset(project_token)
        content = out.get("content") or []
        text = next((b["text"] for b in content if b.get("type") == "text"), "")
        images = [b["data"] for b in content if b.get("type") == "image"]
        return text, images

    async def context_window(session, model):
        return 32000

    async def price_one(model, inputs):
        return _mock_price(inputs)

    async def no_models(feature):
        raise AssertionError(f"a pinned packaging quote must not price the dearest {feature}")

    real_quote = provider._quote_steps
    real_route = LocalLlmProvider._quote_route

    async def quote_capture(steps, lang):
        quote = await real_quote(steps, lang)
        state["quote"] = quote
        return quote

    def route_capture(tool, args, position=0):
        routed = real_route(tool, args, position)
        if routed is None:
            return None
        model, inputs = routed
        state["routed"].append({"position": position, "model": model, "inputs": copy.deepcopy(inputs)})
        return model, inputs

    def run_store():
        return None

    real_send = provider.send

    async def send_capture(turn, emit, handle):
        state["turn"] = turn
        token = BOT_CHAT_ID.set(turn.chat_id)
        guard_token = GUARD_CHAT_ID.set(turn.chat_id)
        try:
            res = await real_send(turn, emit, handle)
        finally:
            BOT_CHAT_ID.reset(token)
            GUARD_CHAT_ID.reset(guard_token)
        state["result"] = res
        return res

    from ComfyArt.api import wavespeed
    fixture = json.loads((Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())
    real_catalog = wavespeed.catalog

    async def catalog_with_26(refresh: bool = False):
        out = dict(await real_catalog(refresh))
        for mid in ("openai/gpt-image-2.6-sunburst/edit", "openai/gpt-image-2.6-sunburst/text-to-image"):
            out[mid] = fixture[mid]
        return out

    monkeypatch.setattr(wavespeed, "catalog", catalog_with_26)
    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", real_mcp)
    monkeypatch.setattr(provider, "_context_window", context_window)
    monkeypatch.setattr(provider, "_price_one", price_one)
    monkeypatch.setattr(provider, "_models_for", no_models)
    monkeypatch.setattr(provider, "_threshold", lambda: 0.0)
    monkeypatch.setattr(provider, "_quote_steps", quote_capture)
    monkeypatch.setattr(provider, "_quote_route", route_capture)
    monkeypatch.setattr(provider, "_run_store", run_store)
    monkeypatch.setattr(provider, "send", send_capture)
    monkeypatch.setitem(providers._REGISTRY, "local-llm", provider)
    write_settings(**{
        "bot-provider": "local-llm", "bot-model-local-llm": "fake-959",
        "bot-local-llm-url": "http://fake-llm/v1", "enable-bot": True, "enable-mcp": True,
        "agent-budget-loop": True,
    })
    return provider, state


async def _bind_open_project(pg):
    """Stub PromptServer has no live sockets; seed the current tab like the other Full App e2e."""
    from ComfyArt.api import mcp_commands
    from server import PromptServer
    project = await pg.evaluate("() => new URL(location.href).searchParams.get('project') || ''")
    pages = {}
    for _ in range(50):
        pages = dict(mcp_commands._pages)
        if project and project in pages.values():
            break
        await asyncio.sleep(0.1)
    for client, proj in list(pages.items()):
        if not project or proj == project:
            PromptServer.instance.sockets[client] = object()
    bound = {c: pr for c, pr in mcp_commands._pages.items() if not project or pr == project}
    assert bound, f"the canvas did not register a project (url={project!r} pages={pages!r})"
    return project, bound


async def _open_skill(p, app_url, lang, sockets):  # noqa: F811
    try:
        browser = await p.chromium.launch()
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"chromium not available, this e2e must not skip: {e}")
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900},
                                    locale="zh-CN" if lang == "zh" else "en-US")
    await ctx.route_web_socket(re.compile(r"/ws(\?|$)"), lambda ws: sockets.append(ws))
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','light')")
    await pg.goto(app_url)
    await pg.get_by_test_id("rail-skills").click()
    await pg.get_by_test_id("skills-wall").wait_for(timeout=20000)
    card = pg.locator(f'[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="product-to-packaging"]')
    await card.scroll_into_view_if_needed()
    await card.hover()
    await card.get_by_test_id("skills-card-try").click()
    dlg = pg.locator('[data-testid="skill-run-dialog"][data-skill="product-to-packaging"]')
    await dlg.wait_for(timeout=15000)
    await dlg.locator('input[type="file"]').first.set_input_files(str(UPLOAD))
    await pg.wait_for_function(
        "() => { const b = document.querySelector('[data-testid=skill-run-go]');"
        " return b && !b.disabled && !b.getAttribute('data-missing'); }"
    )
    await dlg.get_by_test_id("skill-run-go").click()
    await pg.locator(".ca-composer__input").wait_for(timeout=20000)
    await pg.locator(".ca-composer").get_by_text(LOC[lang]["skills.productToPackaging"]).first.wait_for(timeout=15000)
    # The Agent provider list must have arrived before the composer can send (#294).
    await pg.locator('.ca-composer__mode[data-agent="local-llm"]').wait_for(timeout=20000)
    return browser, pg


async def _send_text(pg, text):
    """Fill the composer, wait for the Agent list to finish loading, then press send."""
    box = pg.locator(".ca-composer__input")
    await box.fill(text)
    await pg.wait_for_function(
        "() => { const b = document.querySelector('.ca-composer__slotwrap button[data-slot=send]');"
        " return b && !b.disabled; }",
        timeout=60000,
    )
    await pg.locator('.ca-composer__slotwrap button[data-slot="send"]').click()


async def _wait(predicate, timeout=60.0, interval=0.05):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        value = predicate()
        if value:
            return value
        await asyncio.sleep(interval)
    return predicate()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_quote_card_then_four_real_submits(app_url, mock_ws, local_agent, ws_forward, lang, monkeypatch):  # noqa: F811
    provider, state = local_agent
    from ComfyArt.api import bot_asks, chat_store
    real_ask = bot_asks.create_ask

    def spy(chat_id, message_id, spec):
        state["chat"] = chat_id
        return real_ask(chat_id, message_id, spec)

    monkeypatch.setattr(bot_asks, "create_ask", spy)

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, lang, ws_forward)
        try:
            await _bind_open_project(pg)
            from ComfyArt.api import mcp_commands as _mc
            monkeypatch.setattr(_mc, "_open_pages", lambda: dict(_mc._pages))
            await _send_text(pg, USER_TEXT[lang])
            card = pg.locator('[data-testid="chat-inline-planquote"]')
            await card.wait_for(timeout=40000)
            assert state["chat"], "the quote card did not belong to a chat"
            await card.scroll_into_view_if_needed()
            lines = [t.strip() for t in await card.locator(".ca-keys__row .ca-lib__name").all_inner_texts()]
            prices = [t.strip() for t in await card.locator(".ca-keys__row .ca-panel__val").all_inner_texts()]
            assert len(lines) == 5 and len(prices) == 5, (lines, prices)  # four images + total
            assert len({ln.split(" · ")[0] for ln in lines[:4]}) == 4, lines
            assert all("Sunburst" in ln for ln in lines[:4]), lines
            # Mock table in UI credits: .05/.08/.08/.08 -> 5/8/8/8, total 29.
            assert [re.sub(r"\D", "", p) for p in prices[:4]] == ["5", "8", "8", "8"], prices
            assert "29" in prices[-1], prices
            if SHOTS:
                Path(SHOTS).mkdir(parents=True, exist_ok=True)
                await pg.wait_for_timeout(400)
                await pg.screenshot(path=str(Path(SHOTS) / f"quote-{lang}.png"))
                await card.screenshot(path=str(Path(SHOTS) / f"quote-card-{lang}.png"))
            await card.get_by_test_id("chat-inline-confirm-ok").click()
            await _wait(lambda: len(mock_ws["submits"]) >= 4, timeout=30.0)
            assert len(mock_ws["submits"]) == 4, mock_ws["submits"]
            quote = state["quote"]
            assert quote is not None and quote.total == 0.29, quote
            assert [line.amount for line in quote.lines] == [0.05, 0.08, 0.08, 0.08]
            assert [r["inputs"]["image_index"] for r in state["routed"]] == [1, 2, 3, 4]
            assert [r["inputs"]["ratio"] for r in state["routed"]] == ["3:4", "4:3", "4:3", "4:3"]
            assert all(r["model"] == SUNBURST_EDIT for r in state["routed"]), state["routed"]
            # What the supplier received (mock): the quote's per-image plan, not the placeholder.
            payloads = [body for _model, body in mock_ws["submits"]]
            # The four jobs are submitted concurrently: compare the set, not the arrival order.
            assert sorted((p.get("aspect_ratio"), len(p.get("images") or [])) for p in payloads) == [
                ("3:4", 1), ("4:3", 2), ("4:3", 2), ("4:3", 2)], payloads
            assert all(p.get("resolution") == "2k" for p in payloads), payloads
            assert all("shape:planned-anchor-959" not in json.dumps(p) for p in payloads)
            by_prompt = {p.get("prompt"): p for p in payloads}
            assert len(by_prompt) == 4, payloads
            # The real chat shows four submitted generate_image results and no plan-gate refusal.
            await pg.wait_for_timeout(2500)
            await pg.mouse.click(1000, 500)
            await pg.keyboard.press("Shift+1")
            await pg.wait_for_timeout(800)
            await pg.keyboard.press("Escape")
            blocks = [b for m in chat_store.list_messages(state["chat"]) for b in (m.get("blocks") or [])]
            results = [b for b in blocks if b.get("type") == "tool_result" and b.get("name") == "generate_image"]
            assert len(results) == 4, results
            assert all("quote_plan" not in str(b.get("text")) and "ids" in str(b.get("text")) for b in results), results
            table = []
            for i, (routed, line) in enumerate(zip(state["routed"], quote.lines)):
                payload = by_prompt[routed["inputs"]["prompt"]]
                table.append({
                    "image": routed["inputs"]["image_index"], "role": routed["inputs"]["image_role"],
                    "quote": {"ratio": routed["inputs"]["ratio"],
                              "resolution": routed["inputs"]["resolution"],
                              "refs": len(routed["inputs"]["images"]),
                              "model": routed["model"], "usd_mock": line.amount},
                    "actual": {"ratio": payload.get("aspect_ratio"),
                               "resolution": payload.get("resolution"),
                               "refs": len(payload.get("images") or []),
                               "model": SUNBURST_EDIT, "usd_mock": _mock_price(payload)},
                })
            assert all(row["quote"] == row["actual"] for row in table), table
            assert [row["image"] for row in table] == [1, 2, 3, 4]
            if SHOTS:
                (Path(SHOTS) / f"quote-actual-{lang}.json").write_text(
                    json.dumps({"lang": lang, "total_mock_usd": quote.total, "rows": table},
                               ensure_ascii=False, indent=2))
                from ComfyArt.api import mcp
                from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID, GUARD_CHAT_ID, PROJECT
                chat_row = chat_store.get_chat(state["chat"]) or {}
                token = BOT_CHAT_ID.set(state["chat"])
                guard_token = GUARD_CHAT_ID.set(state["chat"])
                project_token = PROJECT.set(str(chat_row.get("project") or ""))
                try:
                    out = await mcp._tools_call({"name": "view_canvas", "arguments": {"max_px": 1400}})
                finally:
                    BOT_CHAT_ID.reset(token)
                    GUARD_CHAT_ID.reset(guard_token)
                    PROJECT.reset(project_token)
                image = next((b for b in out.get("content") or [] if b.get("type") == "image"), None)
                if image:
                    import base64
                    (Path(SHOTS) / f"results-{lang}.png").write_bytes(base64.b64decode(image["data"]))
                await pg.screenshot(path=str(Path(SHOTS) / f"app-results-{lang}.png"))
        finally:
            await browser.close()
