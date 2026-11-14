"""#911 A-class Full App mock e2e ($0): clothing-swap and pose-fission, default input → ask card →
real generate_image calls → canvas results.

The real built app (dist/), the real ComfyArt routes, the real chat panel, the real
LocalLlmProvider agent loop with a scripted LLM (no LLM call), the real plan gate for
pose-fission (#710), the real MCP tool dispatch and the real generate_image handler.
WaveSpeed is the local mock and nothing is submitted to it.

clothing-swap (green): the person and the garment are attached in the composer in that
order (the skill dialog's one upload field cannot carry both refs). The scripted turn
asks ONE upper-body swap question (id upper_body_swap), the test answers option A, the
model calls generate_image once, and the app submits one Sunburst edit with refs
[person, garment] at the person photo's 3:4 1536x2048, then places one image shape.

pose-fission: the real #710 plan card renders four plan lines in the composer dock. Test 3
clicks 开始生成 and its real Submit must return 202 (not the #971 422), then four jobs are
submitted. Test 4 drives the same UI for the whole chain: four server-bound plan prompts
(sha256-equal to the plan), four Nano Banana Pro 3:4 2k submits, four canvas image shapes.
Test 5 clicks 跳过: the same Submit shape returns 202, the answer is recorded as a skip
(empty answers, never option A), and the shown plan still runs. Test 6 clicks 换一组方案:
202, a new four-line plan, then A → four prompts bound to the second plan.

EVIDENCE_911_SHOTS=/dir keeps screenshots under <dir>/<skill>/. A missing/stale dist/
or a missing Chromium is a hard failure, never a skip.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
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
SHOTS = os.environ.get("EVIDENCE_911_SHOTS")
LOC = {lg: json.loads((ROOT / f"src/locales/{lg}.json").read_text(encoding="utf-8")) for lg in ("zh", "en")}
PERSON = Path(__file__).parent / "fixtures" / "person_911_3x4.jpg"
GARMENT = Path(__file__).parent / "fixtures" / "garment_911.jpg"

SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"
NANO_PRO_EDIT = "google/nano-banana-pro/edit"

# The scripted model sees the same Attached-lines the real agent sees.
ATTACH = re.compile(r'\[Attached image (\d+)(?: "([^"]*)")?: shape id ([^ ]+) — (\S+?)\.?(?:\s|\]|$)')


@pytest.fixture(autouse=True, scope="module")
def built_dist():
    index = ROOT / "dist" / "index.html"
    if not index.is_file():
        pytest.fail("dist/index.html is missing: run `npx vite build` (local build, not committed) before this e2e")
    bundle = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "dist").rglob("*.js"))
    for needle in ("question-plan-line", "question-dock", "composer-capsule", "upper_body_swap", "skill-run-dialog"):
        if needle not in bundle:
            pytest.fail(f"dist/ is stale (no {needle}): run `npx vite build` (local, not committed)")


@pytest.fixture(autouse=True)
def no_paid_keys(monkeypatch):
    for key in ("WAVESPEED_API_KEY", "KIE_API_KEY", "DEEPSEEK_API_KEY", "REPLICATE_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def _tc(i, name, args):
    return {"id": f"t{i}", "function": {"name": name, "arguments": json.dumps(args)}}


def _sha(text) -> str:
    """sha256 of the exact prompt string: the plan line and the generate_image arg must match."""
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _calls(*items):
    return {"choices": [{"message": {"content": "", "tool_calls": [
        _tc(i, n, a) for i, (n, a) in enumerate(items)]}}]}


def _reply(text):
    return {"choices": [{"message": {"content": text, "tool_calls": []}}]}


def _messages_text(messages: list) -> str:
    parts: list[str] = []
    for m in messages:
        content = m.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
    return "\n".join(parts)


def _attached(messages: list) -> list[dict]:
    out = []
    for n, name, shape_id, src in ATTACH.findall(_messages_text(messages)):
        out.append({"n": int(n), "name": name, "id": shape_id, "src": src})
    return out


def _last_tool_json(messages: list, key: str):
    for m in reversed(messages):
        if m.get("role") != "tool":
            continue
        try:
            data = json.loads(str(m.get("content") or ""))
        except ValueError:
            continue
        if isinstance(data, dict) and data.get(key):
            return data
    return None


def _refs(attached: list[dict]) -> list[str]:
    return [row["id"] for row in attached]


def _all_ids(messages: list) -> list[str]:
    """Every generate_image result id in this turn, in call order (one per plan line)."""
    out: list[str] = []
    for m in messages:
        if m.get("role") != "tool":
            continue
        try:
            data = json.loads(str(m.get("content") or ""))
        except ValueError:
            continue
        for value in (data.get("ids") or []) if isinstance(data, dict) else []:
            if str(value) not in out:
                out.append(str(value))
    return out


def _clothing_card(lang: str) -> dict:
    """The live card a compliant model writes from image 1 + image 2 (no hard-coded garment)."""
    if lang == "zh":
        return {
            "questions": [{
                "id": "upper_body_swap",
                "prompt": "图1人物穿着驼色西装外套，想怎么替换上身？",
                "allow_other": True,
                "options": [
                    {"id": "A", "label": "整体换成图2的蓝色大衣"},
                    {"id": "B", "label": "只把西装外套换成图2的蓝色大衣，保留白衬衫"},
                    {"id": "C", "label": "换成图2大衣，领带和衬衫保持图1"},
                ],
            }],
            "page_count": 1,
        }
    return {
        "questions": [{
            "id": "upper_body_swap",
            "prompt": "The person in image 1 wears a camel blazer; how should the upper body be replaced?",
            "allow_other": True,
            "options": [
                {"id": "A", "label": "Replace the whole upper body with the blue coat from image 2"},
                {"id": "B", "label": "Replace only the blazer with the blue coat, keep the white shirt"},
                {"id": "C", "label": "Wear the blue coat, keep the tie and shirt from image 1"},
            ],
        }],
        "page_count": 1,
    }


def _clothing_prompt(lang: str, button: str) -> str:
    if lang == "zh":
        return (f"把图1人物上身的驼色西装外套换成图2的蓝色大衣（{button}），"
                "保持人物、姿势和构图不变；T 恤图案照第二张图保留；consistent lighting with the original photo")
    return (f"Replace the camel blazer in image 1 with the blue coat from image 2 ({button}); "
            "keep the person and pose; Keep the T-shirt pattern as shown in image 2; "
            "consistent lighting with the original photo")


def _clothing_script(state: dict, lang: str):
    card = _clothing_card(lang)
    question = card["questions"][0]

    def respond(messages: list, n: int):
        attached = _attached(messages)
        if attached:
            state["attached"] = attached
        if n == 0:
            return _calls(("skill", {"action": "read", "name": "clothing-swap"}),
                          ("ask_user", copy.deepcopy(card)))
        if n == 1:
            refs = _refs(state.get("attached") or [])
            label = question["options"][0]["label"]
            return _calls(("generate_image", {
                "prompt": _clothing_prompt(lang, label),
                "skill": "clothing-swap",
                "refs": refs,
                "count": 1,
            }))
        if n == 2:
            ids = _last_tool_json(messages, "ids")
            return _calls(("wait_generation", {"ids": (ids or {}).get("ids") or []}))
        return _reply("已按你选的整体换装方案完成，1 张 3:4 服装换装图已放到画布。" if lang == "zh"
                      else "Done: one 3:4 clothing-swap still is on the canvas.")

    return respond


def _pose_script(state: dict, lang: str):
    def respond(messages: list, n: int):
        attached = _attached(messages)
        if attached:
            state["attached"] = attached
        if n < 4:
            base = (_refs(state.get("attached") or []) or [""])[0]
            return _calls(("generate_image", {
                "prompt": f"pose line {n + 1}",
                "skill": "pose-fission",
                "refs": [base] if base else [],
                "ratio": "3:4",
                "width": 1536,
                "height": 2048,
                "count": 1,
            }))
        if n == 4:
            return _calls(("wait_generation", {"ids": _all_ids(messages)}))
        return _reply("4 张同人同衣同景的姿势裂变图已放到画布。" if lang == "zh"
                      else "Done: four 3:4 pose-fission stills are on the canvas.")

    return respond


def _catalog_with_pins():
    """The real catalog plus the pinned rows (#959's pattern); never a network call."""
    from ComfyArt.api import wavespeed
    fixture = json.loads((Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())
    real = wavespeed.catalog

    async def catalog_with_pins(refresh: bool = False):
        out = dict(await real(refresh))
        for mid in (SUNBURST_EDIT, NANO_PRO_EDIT, "google/nano-banana-2.1/edit",
                    "google/nano-banana-pro/text-to-image", "openai/gpt-image-2.6-sunburst/text-to-image"):
            out[mid] = fixture[mid]
        return out

    return catalog_with_pins


@pytest.fixture
def local_agent(monkeypatch):
    """The real built-in agent loop with a scripted LLM; the MCP call dispatches the real tools."""
    from ComfyArt.api import mcp, wavespeed
    from ComfyArt.bot import providers
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID, GUARD_CHAT_ID, PROJECT
    from ComfyArt.bot.guide import CORE_MCP_TOOLS
    from ComfyArt.bot.local_llm import LocalLlmProvider

    provider = LocalLlmProvider(base_url=lambda: "http://fake-llm/v1")
    state = {"n": 0, "respond": None, "chat": "", "mcp": [], "turn": None, "result": None,
             "attached": [], "ask": None, "wait": None}

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        body = json_body or {}
        if body.get("method") == "tools/list":
            return {"result": {"tools": [
                {"name": n, "description": "", "inputSchema": {"type": "object", "properties": {}}}
                for n in CORE_MCP_TOOLS]}}
        if not str(url).endswith("/chat/completions"):
            return {"data": [{"id": "fake-911", "context_length": 32000}]}
        state["messages"] = body.get("messages") or []
        n = state["n"]
        state["n"] += 1
        return (state["respond"] or (lambda *_: _reply("ok")))(state["messages"], n)

    async def real_mcp(session, endpoint, name, arguments):
        from ComfyArt.api import chat_store
        chat_id = state.get("chat") or ""
        row = chat_store.get_chat(chat_id) if chat_id else None
        project = str((row or {}).get("project") or "")
        state["mcp"].append((name, copy.deepcopy(arguments)))
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
        try:
            payload = json.loads(text)
        except ValueError:
            payload = {"raw": text}
        if name == "ask_user":
            state["ask"] = payload
        if name == "wait_generation":
            state["wait"] = payload
        return text, images

    async def context_window(session, model):
        return 32000

    async def price_one(model, inputs):
        # The mock price table serves every model; no network. Same shape as LocalLlmProvider._price_one.
        price, _source = await wavespeed.quote(model, inputs)
        return price

    async def no_models(feature):
        return []

    def run_store():
        return None

    real_send = provider.send

    async def send_capture(turn, emit, handle):
        state["turn"] = turn
        state["chat"] = turn.chat_id
        token = BOT_CHAT_ID.set(turn.chat_id)
        guard_token = GUARD_CHAT_ID.set(turn.chat_id)
        try:
            res = await real_send(turn, emit, handle)
        finally:
            BOT_CHAT_ID.reset(token)
            GUARD_CHAT_ID.reset(guard_token)
        state["result"] = res
        return res

    monkeypatch.setattr(wavespeed, "catalog", _catalog_with_pins())
    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", real_mcp)
    monkeypatch.setattr(provider, "_context_window", context_window)
    monkeypatch.setattr(provider, "_price_one", price_one)
    monkeypatch.setattr(provider, "_models_for", no_models)
    # No over-quote card: the scripted runs stay under the mock's 5-USD run budget.
    monkeypatch.setattr(provider, "_threshold", lambda: 100.0)
    monkeypatch.setattr(provider, "_run_store", run_store)
    monkeypatch.setattr(provider, "send", send_capture)
    monkeypatch.setitem(providers._REGISTRY, "local-llm", provider)
    write_settings(**{
        "bot-provider": "local-llm", "bot-model-local-llm": "fake-911",
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


async def _open_skill(p, app_url, lang, sid, sockets, dialog_ref=None, dialog_text=None,
                      preset_id=None, composer_name=None):  # noqa: F811
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
    card = pg.locator(f'[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="{sid}"]')
    await card.scroll_into_view_if_needed()
    await card.hover()
    await card.get_by_test_id("skills-card-try").click()
    dlg = pg.locator(f'[data-testid="skill-run-dialog"][data-skill="{sid}"]')
    await dlg.wait_for(timeout=15000)
    if preset_id is not None:
        tile = dlg.locator(f'[data-testid="skill-run-preset"][data-preset="{preset_id}"]')
        await tile.scroll_into_view_if_needed()
        await tile.click()
    # Default input: the dialog's one upload field when the skill needs one base photo.
    if dialog_ref is not None:
        await dlg.locator('input[type="file"]').first.set_input_files(str(dialog_ref))
    if dialog_text is not None:
        await dlg.locator('textarea').first.fill(dialog_text)
    if dialog_ref is not None or dialog_text is not None:
        await pg.wait_for_function(
            "() => { const b = document.querySelector('[data-testid=skill-run-go]');"
            " return b && !b.disabled && !b.getAttribute('data-missing'); }"
        )
    await dlg.get_by_test_id("skill-run-go").click()
    await pg.locator(".ca-composer__input").wait_for(timeout=20000)
    label_key = {
        "clothing-swap": "skills.clothingSwap",
        "universal-multi-angle-grid": "skills.multiAngleImageGenerator",
        "logo-material-explorer": "skills.logoMaterialExplorer",
        "character-sheet-design": "skills.characterSheet",
        "poster-differentiated-compiler": "skills.posterDesign",
        "banner-design-director": "skills.bannerDesign",
        "meta-ads-creative-director": "skills.metaAdsCreative",
        "mobile-app-visual-design": "skills.mobileAppVisualDesign",
    }.get(sid, "skills.poseFission")
    chip = pg.locator('.ca-composer [data-testid="composer-skill-chip"]')
    await chip.wait_for(timeout=15000)
    label = composer_name or LOC[lang][label_key]
    await chip.get_by_text(label).first.wait_for(timeout=15000)
    # The Agent provider list must have arrived before the composer can send (#294).
    await pg.locator('.ca-composer__mode[data-agent="local-llm"]').wait_for(timeout=20000)
    await _bind_open_project(pg)
    return browser, pg


async def _send_default(pg):
    """Press send with the skill-link draft (the skill name, no extra typed text)."""
    box = pg.locator(".ca-composer__input")
    await box.click()
    await pg.wait_for_function(
        "() => { const b = document.querySelector('.ca-composer__slotwrap button[data-slot=send]');"
        " return b && !b.disabled; }",
        timeout=60000,
    )
    await box.press("Enter")


async def _submit_answer(pg):
    """Answer the docked question card: option A, then Submit."""
    await _submit_option(pg, 0)


async def _submit_option(pg, index: int):
    """Answer the docked question card with option #index (0=A, 1=B), then Submit."""
    card = pg.locator('[data-testid="question-dock"] .ca-q')
    await card.locator(".ca-q__opt").nth(index).click()
    await pg.wait_for_function(
        "() => { const b = document.querySelector('[data-testid=question-dock] .ca-q__submit');"
        " return b && !b.disabled; }",
        timeout=15000,
    )
    await card.locator(".ca-q__submit").click()


async def _skip_answer(pg):
    """Press 跳过 on the docked question card (the Full App sends empty per-question answers)."""
    await pg.locator('[data-testid="question-dock"] .ca-q .ca-q__skip').click()


def _plan_lines_now(pg):
    return pg.locator('[data-testid="question-dock"] .ca-q [data-testid="question-plan-line"]').all_inner_texts()


async def _wait_new_plan(pg, differ_from: list[str], timeout: float = 40.0) -> list[str]:
    """The regenerated (#710 B) card: four lines, all different from the previous plan."""
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    seen: list[str] = []
    while loop.time() < end:
        if await pg.locator('[data-testid="question-dock"] .ca-q').count():
            seen = [t.strip() for t in await _plan_lines_now(pg)]
            if len(seen) == 4 and seen != differ_from:
                return seen
        await asyncio.sleep(0.2)
    raise AssertionError(f"no regenerated plan card (still {seen!r})")


async def _asks_in_chat(chat_id: str) -> list[dict]:
    """Every persisted ask block of this chat, in message order (real chat store)."""
    from ComfyArt.api import chat_store
    out = []
    for msg in chat_store.list_messages(chat_id):
        out.extend(b for b in (msg.get("blocks") or [])
                   if isinstance(b, dict) and b.get("type") == "ask")
    return out


async def _canvas_images(chat_id: str) -> list[dict]:
    """The real get_canvas MCP tool, from the chat's project, at the current page."""
    from ComfyArt.api import chat_store, mcp
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID, GUARD_CHAT_ID, PROJECT
    row = chat_store.get_chat(chat_id) or {}
    token = BOT_CHAT_ID.set(chat_id)
    guard_token = GUARD_CHAT_ID.set(chat_id)
    project_token = PROJECT.set(str(row.get("project") or ""))
    try:
        out = await mcp._tools_call({"name": "get_canvas", "arguments": {}})
    finally:
        BOT_CHAT_ID.reset(token)
        GUARD_CHAT_ID.reset(guard_token)
        PROJECT.reset(project_token)
    text = next((b["text"] for b in out.get("content") or [] if b.get("type") == "text"), "{}")
    data = json.loads(text)
    return [s for s in data.get("shapes") or [] if s.get("type") == "image"]


async def _shot(pg, sid, name, lang):
    if not SHOTS:
        return
    out = Path(SHOTS) / sid
    out.mkdir(parents=True, exist_ok=True)
    await pg.wait_for_timeout(500)
    await pg.screenshot(path=str(out / f"{name}-{lang}.png"))


def _evidence(sid: str, name: str, data: dict) -> None:
    """$0 evidence next to the screenshots (only when EVIDENCE_911_SHOTS is set)."""
    if not SHOTS:
        return
    out = Path(SHOTS) / sid
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def _wait(predicate, timeout=60.0, interval=0.05):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        value = predicate()
        if value:
            return value
        await asyncio.sleep(interval)
    return predicate()


async def _assert_plan_card(card, lang):
    lines = [t.strip() for t in await card.locator('[data-testid="question-plan-line"]').all_inner_texts()]
    assert len(lines) == 4, lines
    for line in lines:
        for token in ("景别：", "角度：", "机位：", "姿态：", "构图：", "焦段：", "光：", "场景：", "°", "mm"):
            assert token in line, (token, line)
        assert "半身" not in line and "全身" not in line, line
    angles = [ln.split("角度：", 1)[1].split("；", 1)[0] for ln in lines]
    assert len(set(angles)) == 4, angles
    assert len([ln for ln in lines if "角度：0°" in ln]) <= 1, lines
    assert (await card.locator(".ca-q__prompt").inner_text()).strip() == "是否生成这 4 张？"
    labels = [t.strip() for t in await card.locator(".ca-q__opt .ca-q__text").all_inner_texts()]
    assert labels == ["开始生成", "换一组方案"], labels
    letters = [t.strip() for t in await card.locator(".ca-q__opt .ca-q__letter").all_inner_texts()]
    assert letters == ["A", "B", "C"], letters
    assert (await card.locator('.ca-q__opt[data-other] .ca-q__input').get_attribute("placeholder")
            ) == LOC[lang]["chatMessage.other"]
    assert await card.locator(".ca-q__skip").count() == 1
    assert await card.locator(".ca-q__opt[data-on]").count() == 0
    return lines


def _cancel_asks(chat_id: str) -> None:
    from ComfyArt.api import bot_asks
    if chat_id:
        bot_asks.cancel_chat_asks(chat_id)


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_clothing_swap_default_refs_card_one_sunburst_submit(
        app_url, mock_ws, local_agent, ws_forward, lang):  # noqa: F811
    """Two refs in order → ONE upper-body card → ONE Sunburst edit → 1 canvas image."""
    _provider, state = local_agent
    state["respond"] = _clothing_script(state, lang)

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, lang, "clothing-swap", ws_forward)
        try:
            # The skill needs person image 1 + garment image 2; the dialog field holds one file,
            # so both references are attached in the composer in that order.
            await pg.locator('.ca-composer__foot input[type="file"]').set_input_files([str(PERSON), str(GARMENT)])
            await pg.wait_for_function(
                "() => document.querySelectorAll('.ca-composer__chips [data-testid=user-ref-chip]').length === 2",
                timeout=30000,
            )
            chips = [t.strip() for t in await pg.locator(
                '.ca-composer__chips [data-testid="user-ref-chip"]').all_inner_texts()]
            assert chips == ["image-1", "image-2"], chips
            assert await pg.locator('[data-testid="composer-skill-chip"]').count() == 1

            await _send_default(pg)
            card = pg.locator('[data-testid="question-dock"] .ca-q')
            await card.wait_for(timeout=40000)
            # Nothing was generated while the question is open.
            assert mock_ws["submits"] == [], mock_ws["submits"]
            assert not [n for n, _a in state["mcp"] if n == "generate_image"], state["mcp"]

            assert await card.locator(".ca-q__page").count() == 0   # one question, one page
            prompts = [t.strip() for t in await card.locator(".ca-q__prompt").all_inner_texts()]
            assert prompts == [_clothing_card(lang)["questions"][0]["prompt"]], prompts
            options = _clothing_card(lang)["questions"][0]["options"]
            labels = [t.strip() for t in await card.locator(".ca-q__opt .ca-q__text").all_inner_texts()]
            assert labels == [o["label"] for o in options], labels
            letters = [t.strip() for t in await card.locator(".ca-q__opt .ca-q__letter").all_inner_texts()]
            assert letters == ["A", "B", "C", "D"], letters
            other = card.locator('.ca-q__opt[data-other]')
            assert await other.count() == 1
            assert await card.locator(".ca-q__opt[data-on]").count() == 0   # nothing preselected
            assert await card.locator(".ca-q__rec").count() == 0
            assert (await other.locator(".ca-q__input").get_attribute("placeholder")) == LOC[lang]["chatMessage.other"]
            # The user bubble carries the two uploaded images in upload order plus the skill chip.
            bubble = [t.strip() for t in await pg.locator(
                '.ca-chat__user [data-testid="user-ref-chip"]').all_inner_texts()]
            assert len(bubble) == 2, bubble
            assert bubble[0].endswith("person_911_3x4.jpg"), bubble
            assert bubble[1] == "garment_911.jpg", bubble
            assert await pg.locator('[data-testid="user-skill-chip"]').count() == 1
            await _shot(pg, "clothing-swap", "ask-card", lang)

            await _submit_answer(pg)
            answered = await _wait(lambda: state.get("ask"), timeout=30.0)
            assert answered.get("status") == "answered", answered
            assert answered.get("selected") == ["A"], answered
            assert answered["answers"]["upper_body_swap"]["selected"] == ["A"], answered

            await _wait(lambda: mock_ws["submits"], timeout=90.0)
            assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
            await _wait(lambda: state.get("wait"), timeout=90.0)
            rows = (state.get("wait") or {}).get("results") or []
            assert len(rows) == 1 and rows[0].get("status") == "done", rows
            assert rows[0].get("placed") is True and rows[0].get("shapes"), rows

            # The real call: one generate_image on the skill, refs [person, garment], server size lock.
            gens = [(n, a) for n, a in state["mcp"] if n == "generate_image"]
            assert len(gens) == 1, gens
            args = gens[0][1]
            assert args["skill"] == "clothing-swap" and args["count"] == 1, args
            assert args["refs"] == [row["id"] for row in state["attached"]], (args, state["attached"])
            assert (args["width"], args["height"], args["ratio"]) == (1536, 2048, "3:4"), args
            assert args.get("size_lock") is True, args
            names = [row["name"] for row in state["attached"]]
            assert names[0].endswith("person_911_3x4.jpg") and names[1] == "garment_911.jpg", names
            # What the supplier received (mock): one 3:4/2k edit with the two references.
            model, body = mock_ws["submits"][0]
            assert model == SUNBURST_EDIT, model
            assert body.get("aspect_ratio") == "3:4" and body.get("resolution") == "2k", body
            assert len(body.get("images") or []) == 2, body
            assert "width" not in body and "height" not in body, body

            # The canvas holds exactly one generated image shape (the two uploads are inputs).
            shapes = await _canvas_images(state["chat"])
            generated = set(rows[0].get("shapes") or [])
            assert len(generated) == 1, generated
            assert generated <= {s["id"] for s in shapes}, (generated, shapes)
            assert len([s for s in shapes if s["id"] in generated]) == 1
            _evidence("clothing-swap", f"evidence-{lang}.json", {
                "skill": "clothing-swap", "lang": lang, "paid": False,
                "ask": {"kind": "clothing-swap", "id": "upper_body_swap",
                        "question": _clothing_card(lang)["questions"][0]["prompt"],
                        "options": [o["label"] for o in _clothing_card(lang)["questions"][0]["options"]],
                        "allow_other": True, "page_count": 1},
                "answer": {"selected": answered.get("selected")},
                "attached": [{"n": r["n"], "name": r["name"], "id": r["id"]} for r in state["attached"]],
                "generate_image": {"count": len(gens), "calls": [
                    {"skill": a["skill"], "refs": a["refs"], "width": a["width"], "height": a["height"],
                     "ratio": a["ratio"], "count": a["count"], "size_lock": a.get("size_lock"),
                     "prompt": a["prompt"]} for _n, a in gens]},
                "submits": [{"model": m, "aspect_ratio": b.get("aspect_ratio"),
                             "resolution": b.get("resolution"), "images": len(b.get("images") or [])}
                            for m, b in mock_ws["submits"]],
                "canvas": {"generated_shapes": sorted(generated),
                           "image_shapes": len(shapes)},
            })
            await pg.mouse.click(1000, 500)
            await pg.keyboard.press("Shift+1")
            await pg.wait_for_timeout(600)
            await pg.keyboard.press("Escape")
            await _shot(pg, "clothing-swap", "result", lang)
        finally:
            await browser.close()


async def test_fullapp_clothing_swap_dialog_ref_then_composer_ref_keeps_person_first(
        app_url, mock_ws, local_agent, ws_forward):  # noqa: F811
    """Upload the person in the skill dialog, add the garment in the composer: person must stay image 1."""
    _provider, state = local_agent
    state["respond"] = _clothing_script(state, "zh")

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "zh", "clothing-swap", ws_forward, dialog_ref=PERSON)
        try:
            await pg.locator('.ca-composer__foot input[type="file"]').set_input_files(str(GARMENT))
            await pg.wait_for_function(
                "() => document.querySelectorAll('.ca-composer__chips [data-testid=user-ref-chip]').length === 2",
                timeout=30000,
            )
            chips = [t.strip() for t in await pg.locator(
                '.ca-composer__chips [data-testid="user-ref-chip"]').all_inner_texts()]
            assert chips == ["image-1", "image-2"], chips   # composer: image-1 is the dialog person
            await _send_default(pg)
            card = pg.locator('[data-testid="question-dock"] .ca-q')
            await card.wait_for(timeout=40000)
            await _shot(pg, "clothing-swap", "mixed-ref-order", "zh")
            bubble = [t.strip() for t in await pg.locator(
                '.ca-chat__user [data-testid="user-ref-chip"]').all_inner_texts()]
            _evidence("clothing-swap", "mixed-ref-order-zh.json", {
                "composer_chips": chips, "sent_user_bubble": bubble,
                "attached": [{"n": r["n"], "name": r["name"]} for r in _attached(state.get("messages") or [])],
            })
            # Loose (dialog) refs are numbered image-1 first, so they must be sent first too:
            # the person stays image 1, the garment image 2 (the skill's dual-ref order).
            assert len(bubble) == 2 and bubble[0].endswith("person_911_3x4.jpg"), bubble
            assert bubble[1] == "garment_911.jpg", bubble
            await _submit_answer(pg)
            answered = await _wait(lambda: state.get("ask"), timeout=30.0)
            assert answered.get("status") == "answered", answered
            assert answered["answers"]["upper_body_swap"]["selected"] == ["A"], answered
            await _wait(lambda: mock_ws["submits"], timeout=90.0)
            assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
            model, body = mock_ws["submits"][0]
            assert model == SUNBURST_EDIT, model
            # The model got the refs in the same order the composer numbered them.
            names = [row["name"] for row in state["attached"]]
            assert names[0].endswith("person_911_3x4.jpg") and names[1] == "garment_911.jpg", names
            assert len(body.get("images") or []) == 2, body
            await _wait(lambda: state.get("wait"), timeout=120.0)
            rows = (state.get("wait") or {}).get("results") or []
            assert len(rows) == 1 and rows[0].get("status") == "done" and rows[0].get("placed"), rows
            shapes = await _canvas_images(state["chat"])
            generated = set(rows[0].get("shapes") or [])
            assert len(generated) == 1 and generated <= {s["id"] for s in shapes}, (generated, shapes)
        finally:
            _cancel_asks(state.get("chat") or "")
            await browser.close()


async def test_fullapp_pose_fission_plan_card_ui_submit_starts_generation(
        app_url, mock_ws, local_agent, ws_forward):  # noqa: F811
    """Click 开始生成 on the real plan card: the real Submit confirms the plan and starts 4 jobs."""
    _provider, state = local_agent
    state["respond"] = _pose_script(state, "zh")

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "zh", "pose-fission", ws_forward, dialog_ref=PERSON)
        answer: dict = {}
        try:
            async def grab(response):
                if "/asks/" in response.url and response.request.method == "POST":
                    answer["status"] = response.status
                    try:
                        answer["body"] = await response.text()
                    except Exception:  # noqa: BLE001
                        answer["body"] = ""
            pg.on("response", lambda r: asyncio.create_task(grab(r)))

            await _send_default(pg)
            card = pg.locator('[data-testid="question-dock"] .ca-q')
            await card.wait_for(timeout=40000)
            await _assert_plan_card(card, "zh")
            await _submit_answer(pg)
            await _wait(lambda: answer.get("status"), timeout=15.0)
            await pg.wait_for_timeout(400)
            _evidence("pose-fission", "plan-card-submitted.json", {
                "answer_route": answer, "submits_after_submit": len(mock_ws["submits"]),
            })
            await _shot(pg, "pose-fission", "plan-card-submitted", "zh")
            # #971: the plan spec has questions[], so the Full App answers[] Submit is accepted.
            assert answer.get("status") == 202, answer
            assert "error" not in json.loads(answer.get("body") or "{}"), answer
            await _wait(lambda: len(mock_ws["submits"]) >= 4, timeout=150.0)
            assert len(mock_ws["submits"]) == 4, (answer, mock_ws["submits"])
        finally:
            _cancel_asks(state.get("chat") or "")
            await browser.close()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_pose_fission_plan_confirmed_four_bound_nano_pro_submits(
        app_url, mock_ws, local_agent, ws_forward, lang):  # noqa: F811
    """Plan card → click A + real Submit → 4 bound Nano Banana Pro submits (sha256 = plan) → 4 canvas images."""
    from ComfyArt.bot import shot_plan
    _provider, state = local_agent
    state["respond"] = _pose_script(state, lang)
    answer: dict = {}

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, lang, "pose-fission", ws_forward, dialog_ref=PERSON)
        try:
            async def grab(response):
                if "/asks/" in response.url and response.request.method == "POST":
                    answer["status"] = response.status
                    try:
                        answer["body"] = await response.text()
                    except Exception:  # noqa: BLE001
                        answer["body"] = ""
            pg.on("response", lambda r: asyncio.create_task(grab(r)))

            assert await pg.locator('[data-testid="composer-skill-chip"]').count() == 1
            chips = [t.strip() for t in await pg.locator(
                '.ca-composer__chips [data-testid="user-ref-chip"]').all_inner_texts()]
            assert chips == ["image-1"], chips
            await _send_default(pg)

            card = pg.locator('[data-testid="question-dock"] .ca-q')
            await card.wait_for(timeout=40000)
            # The plan card is server-side (#710): no model request and no submit before confirm.
            assert state["n"] == 0, state["n"]
            assert mock_ws["submits"] == [], mock_ws["submits"]
            lines = await _assert_plan_card(card, lang)
            await _shot(pg, "pose-fission", "ask-card-plan", lang)
            await card.locator(".ca-q__body").evaluate("el => { el.scrollTop = el.scrollHeight }")
            await pg.wait_for_timeout(300)
            await _shot(pg, "pose-fission", "ask-card", lang)

            # The real Full App path: option A + Submit posts answers[] for the questions spec.
            await _submit_answer(pg)
            await _wait(lambda: answer.get("status"), timeout=15.0)
            assert answer.get("status") == 202, answer
            assert "error" not in json.loads(answer.get("body") or "{}"), answer

            # The answered plan collapses into the right user bubble (a kind=question ask, #766).
            bubble = pg.locator('[data-testid="ask-answer-bubble"][data-ask="answer"]')
            await bubble.wait_for(timeout=20000)
            text = await bubble.inner_text()
            assert "是否生成这 4 张？" in text and "A: 开始生成" in text, text
            assert text.count("景别：") == 4, text

            await _wait(lambda: len(mock_ws["submits"]) >= 4, timeout=150.0)
            assert len(mock_ws["submits"]) == 4, mock_ws["submits"]
            await _wait(lambda: state.get("wait"), timeout=150.0)
            rows = (state.get("wait") or {}).get("results") or []
            assert len(rows) == 4 and all(r.get("status") == "done" and r.get("placed") for r in rows), rows

            gens = [(n, a) for n, a in state["mcp"] if n == "generate_image"]
            assert len(gens) == 4, gens
            expected = shot_plan.build_shots(4, 0, shot_plan.SCENE_DEFAULT)
            plan_prompts = [s.prompt_en for s in expected]
            # The plan the card showed is the plan that ran: sha256 equal, line by line.
            assert [_sha(line) for line in lines] == [_sha(s.zh()) for s in expected], lines
            assert [_sha(a["prompt"]) for _n, a in gens] == [_sha(p) for p in plan_prompts], \
                [a["prompt"] for _n, a in gens]
            assert [a["prompt"] for _n, a in gens] == plan_prompts
            assert [a["skill"] for _n, a in gens] == ["pose-fission"] * 4
            assert [a["count"] for _n, a in gens] == [1, 1, 1, 1]
            assert [(a["width"], a["height"], a["ratio"]) for _n, a in gens] == [(1536, 2048, "3:4")] * 4
            base_refs = [row["id"] for row in state["attached"]]
            assert base_refs, state["attached"]
            assert all(a["refs"] == base_refs for _n, a in gens), (base_refs, [a["refs"] for _n, a in gens])

            for model, body in mock_ws["submits"]:
                assert model == NANO_PRO_EDIT, model
                assert body.get("aspect_ratio") == "3:4" and body.get("resolution") == "2k", body
                assert len(body.get("images") or []) == 1, body
            prompts = [body.get("prompt") for _m, body in mock_ws["submits"]]
            assert len(set(prompts)) == 4, prompts
            # What reached the supplier is the same four prompts (sha256-equal, in order).
            assert [_sha(p) for p in prompts] == [_sha(a["prompt"]) for _n, a in gens], prompts
            # Each submitted prompt carries its own plan line (same fragments, same order).
            for shot, prompt in zip(expected, prompts):
                assert shot_plan.trace_ok(str(prompt or ""), shot), prompt

            shapes = await _canvas_images(state["chat"])
            generated = {sid for row in rows for sid in (row.get("shapes") or [])}
            assert len(generated) == 4, generated
            assert generated <= {s["id"] for s in shapes}, (generated, shapes)
            assert len([s for s in shapes if s["id"] in generated]) == 4, shapes
            _evidence("pose-fission", f"evidence-{lang}.json", {
                "skill": "pose-fission", "lang": lang, "paid": False,
                "ask": {"kind": "question", "id": "plan", "question": "是否生成这 4 张？",
                        "options": ["开始生成", "换一组方案", "其他（输入你的答案）…"], "lines": lines},
                "confirmed_via": "real Full App Submit: option A → POST /asks/{id}/answer {answers: {plan: ...}} → 202",
                "answer_route": answer,
                "generate_image": {"count": len(gens), "calls": [
                    {"skill": a["skill"], "refs": a["refs"], "width": a["width"], "height": a["height"],
                     "ratio": a["ratio"], "count": a["count"], "size_lock": a.get("size_lock"),
                     "prompt_sha256": _sha(a["prompt"]),
                     "prompt_head": a["prompt"][:120]} for _n, a in gens]},
                "submits": [{"model": m, "aspect_ratio": b.get("aspect_ratio"),
                             "resolution": b.get("resolution"), "images": len(b.get("images") or []),
                             "prompt_sha256": _sha(b.get("prompt"))}
                            for m, b in mock_ws["submits"]],
                "canvas": {"generated_shapes": sorted(generated), "image_shapes": len(shapes)},
            })
            await pg.mouse.click(1000, 500)
            await pg.keyboard.press("Shift+1")
            await pg.wait_for_timeout(600)
            await pg.keyboard.press("Escape")
            await _shot(pg, "pose-fission", "result", lang)
        finally:
            _cancel_asks(state.get("chat") or "")
            await browser.close()


async def test_fullapp_pose_fission_plan_skip_is_explicit_and_runs_the_shown_plan(
        app_url, mock_ws, local_agent, ws_forward):  # noqa: F811
    """跳过: 202 (no 422), recorded as a skip (empty answers), and the shown plan still runs."""
    from ComfyArt.bot import shot_plan
    _provider, state = local_agent
    state["respond"] = _pose_script(state, "zh")
    answer: dict = {}

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "zh", "pose-fission", ws_forward, dialog_ref=PERSON)
        try:
            async def grab(response):
                if "/asks/" in response.url and response.request.method == "POST":
                    answer["status"] = response.status
                    try:
                        answer["body"] = await response.text()
                    except Exception:  # noqa: BLE001
                        answer["body"] = ""
            pg.on("response", lambda r: asyncio.create_task(grab(r)))

            await _send_default(pg)
            card = pg.locator('[data-testid="question-dock"] .ca-q')
            await card.wait_for(timeout=40000)
            lines = await _assert_plan_card(card, "zh")
            await _skip_answer(pg)
            await _wait(lambda: answer.get("status"), timeout=15.0)
            await pg.wait_for_timeout(400)
            _evidence("pose-fission", "skip-plan-card.json", {
                "answer_route": answer, "plan_lines": lines, "paid": False,
            })
            assert answer.get("status") == 202, answer
            assert "error" not in json.loads(answer.get("body") or "{}"), answer

            # Explicit semantics: the answered bubble is a skip, never a chosen option.
            bubble = pg.locator('[data-testid="ask-answer-bubble"][data-ask="skip"]')
            await bubble.wait_for(timeout=20000)
            text = await bubble.inner_text()
            assert "开始生成" not in text and "换一组方案" not in text, text
            asks = await _asks_in_chat(state["chat"])
            row = [a for a in asks if a.get("status") == "answered"][-1]
            qid = row["questions"][0]["id"]
            assert row.get("answers") == {qid: {"selected": []}}, row.get("answers")
            assert not row.get("selected"), row.get("selected")

            await _wait(lambda: len(mock_ws["submits"]) >= 4, timeout=150.0)
            assert len(mock_ws["submits"]) == 4, mock_ws["submits"]
            await _wait(lambda: state.get("wait"), timeout=150.0)
            rows = (state.get("wait") or {}).get("results") or []
            assert len(rows) == 4 and all(r.get("status") == "done" and r.get("placed") for r in rows), rows

            # Skip keeps the plan the card showed; the prompts are still the four plan lines.
            gens = [(n, a) for n, a in state["mcp"] if n == "generate_image"]
            assert len(gens) == 4, gens
            expected = shot_plan.build_shots(4, 0, shot_plan.SCENE_DEFAULT)
            assert [_sha(line) for line in lines] == [_sha(s.zh()) for s in expected], lines
            assert [_sha(a["prompt"]) for _n, a in gens] == [_sha(s.prompt_en) for s in expected], \
                [a["prompt"] for _n, a in gens]
            # The supplier received exactly those four prompts (sha256-equal, in order).
            assert [_sha(b.get("prompt")) for _m, b in mock_ws["submits"]] == \
                [_sha(a["prompt"]) for _n, a in gens], mock_ws["submits"]
            # The model was told it was a skip, not that the user confirmed A.
            convo = _messages_text(state["messages"])
            assert "skipped the shot plan card" in convo
            assert "confirmed the shot plan" not in convo

            shapes = await _canvas_images(state["chat"])
            generated = {sid for row in rows for sid in (row.get("shapes") or [])}
            assert len(generated) == 4, generated
            assert generated <= {s["id"] for s in shapes}, (generated, shapes)
            assert len([s for s in shapes if s["id"] in generated]) == 4, shapes
            await _shot(pg, "pose-fission", "skip-result", "zh")
        finally:
            _cancel_asks(state.get("chat") or "")
            await browser.close()


async def test_fullapp_pose_fission_plan_regenerate_then_start_uses_the_new_plan(
        app_url, mock_ws, local_agent, ws_forward):  # noqa: F811
    """换一组方案: 202 (no 422), a new four-line plan, then A → four prompts bound to the new plan."""
    from ComfyArt.bot import shot_plan
    _provider, state = local_agent
    state["respond"] = _pose_script(state, "zh")
    statuses: list[dict] = []

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "zh", "pose-fission", ws_forward, dialog_ref=PERSON)
        try:
            async def grab(response):
                if "/asks/" in response.url and response.request.method == "POST":
                    entry = {"status": response.status}
                    try:
                        entry["body"] = await response.text()
                    except Exception:  # noqa: BLE001
                        entry["body"] = ""
                    statuses.append(entry)
            pg.on("response", lambda r: asyncio.create_task(grab(r)))

            await _send_default(pg)
            card = pg.locator('[data-testid="question-dock"] .ca-q')
            await card.wait_for(timeout=40000)
            first = await _assert_plan_card(card, "zh")
            assert state["n"] == 0 and mock_ws["submits"] == [], (state["n"], mock_ws["submits"])

            await _submit_option(pg, 1)          # B 换一组方案
            second = await _wait_new_plan(pg, first)
            await _wait(lambda: statuses, timeout=15.0)
            assert statuses[0].get("status") == 202, statuses
            assert "error" not in json.loads(statuses[0].get("body") or "{}"), statuses
            assert state["n"] == 0 and mock_ws["submits"] == [], (state["n"], mock_ws["submits"])
            await _assert_plan_card(card, "zh")  # still one card, same A/B/C actions
            _evidence("pose-fission", "regenerate-plan-card.json", {
                "answer_route": statuses[0], "first_plan": first, "second_plan": second, "paid": False,
            })
            await _shot(pg, "pose-fission", "regenerate-plan", "zh")

            await _submit_answer(pg)             # A on the regenerated plan
            await _wait(lambda: len(statuses) >= 2, timeout=15.0)
            assert [s.get("status") for s in statuses] == [202, 202], statuses
            await _wait(lambda: len(mock_ws["submits"]) >= 4, timeout=150.0)
            assert len(mock_ws["submits"]) == 4, mock_ws["submits"]
            await _wait(lambda: state.get("wait"), timeout=150.0)
            rows = (state.get("wait") or {}).get("results") or []
            assert len(rows) == 4 and all(r.get("status") == "done" and r.get("placed") for r in rows), rows

            expected = shot_plan.build_shots(4, 1, shot_plan.SCENE_DEFAULT)   # variant 1
            assert [_sha(line) for line in second] == [_sha(s.zh()) for s in expected], second
            assert [_sha(line) for line in second] != [_sha(line) for line in first], (first, second)
            gens = [(n, a) for n, a in state["mcp"] if n == "generate_image"]
            assert len(gens) == 4, gens
            assert [_sha(a["prompt"]) for _n, a in gens] == [_sha(s.prompt_en) for s in expected], \
                [a["prompt"] for _n, a in gens]
            assert [a["skill"] for _n, a in gens] == ["pose-fission"] * 4
            assert [_sha(b.get("prompt")) for _m, b in mock_ws["submits"]] == \
                [_sha(a["prompt"]) for _n, a in gens], mock_ws["submits"]

            shapes = await _canvas_images(state["chat"])
            generated = {sid for row in rows for sid in (row.get("shapes") or [])}
            assert len(generated) == 4, generated
            assert generated <= {s["id"] for s in shapes}, (generated, shapes)
            assert len([s for s in shapes if s["id"] in generated]) == 4, shapes
            await _shot(pg, "pose-fission", "regenerate-result", "zh")
        finally:
            _cancel_asks(state.get("chat") or "")
            await browser.close()
