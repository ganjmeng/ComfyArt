"""#979 Full App mock e2e ($0): the template selected in the skill dialog drives the
real generate_image count and pixels, end to end.

Real built app (dist/), real ComfyArt routes, real chat panel, real LocalLlmProvider
agent loop with a scripted LLM (no LLM call), real MCP dispatch and the real
generate_image handler. WaveSpeed is the local mock; nothing is paid.

The scripted model never passes width/height/ratio/count (except `stage=2` for the
second brand stage / the 4th multi-SKU image), exactly like a model that read the
Output lock: the server must fill the selected template's plan. Each call is checked
against the product ruling's literal numbers, so reverting a table row turns this red.

  brand-identity-director: 3×1024×1024 (1:1) → user picks a direction → 1×2048×1152 (16:9)
  packaging eco 1×1536×2048 · gold 3×2048×1152 · playful 3×1536×2048 + 1×2048×1152
            panels 1×2048×1152 · shelf 1×2048×1152
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (real routes + local mock WaveSpeed)
from test_skill_e2e_portrait_studio import ws_forward  # noqa: F401
from test_a_class_fullapp_e2e_911 import (  # noqa: F401  (shared Full App harness + autouse guards)
    _all_ids, _bind_open_project, _calls, _canvas_images, _reply, _wait,
    built_dist, local_agent, no_paid_keys,
)

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parents[1]
LOC = {lg: json.loads((ROOT / f"src/locales/{lg}.json").read_text(encoding="utf-8")) for lg in ("zh", "en")}
BRAND = "brand-identity-director"
PACKAGING = "packaging-design-director"
BRAND_LABEL = "skills.brandIdentity"
PACKAGING_LABEL = "skills.packagingDesign"

# Literal product ruling. Do not read these from the table under test.
PACKAGING_CASES = [
    # (tile index, preset id, expected calls as (width, height, ratio), field value)
    (0, "eco", [(1536, 2048, "3:4")], "AURELIA 30ml serum"),
    (1, "gold", [(2048, 1152, "16:9")] * 3, "AURELIA 30ml serum"),
    (2, "playful", [(1536, 2048, "3:4")] * 3 + [(2048, 1152, "16:9")], "AURELIA 30ml serum"),
    (3, "panels", [(2048, 1152, "16:9")], "AURELIA 30ml serum"),
    (4, "shelf", [(2048, 1152, "16:9")], "AURELIA 30ml serum"),
]


def _last_user(messages: list) -> str:
    for m in reversed(messages or []):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, list):
            c = " ".join(str(p.get("text") or "") for p in c if isinstance(p, dict))
        return str(c or "")
    return ""


async def _open_template(p, app_url, lang, sid, sockets, tile, field: str, value: str):
    """Open the skill dialog, pick a template tile, fill the required text, start the chat."""
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
    if tile is not None:
        tiles = dlg.locator('[data-testid="skill-run-preset"]')
        assert await tiles.count() >= tile + 1, (sid, await tiles.count())
        await tiles.nth(tile).click()
    field_el = dlg.locator(f'[data-testid="skill-run-field"][data-key="{field}"]')
    await field_el.fill(value)
    await dlg.get_by_test_id("skill-run-go").click()
    await pg.locator(".ca-composer__input").wait_for(timeout=20000)
    await pg.locator('.ca-composer__mode[data-agent="local-llm"]').wait_for(timeout=20000)
    await _bind_open_project(pg)
    return browser, pg


def _gen_args(state: dict) -> list[dict]:
    return [args for name, args in state["mcp"] if name == "generate_image"]


async def _wait_shapes(chat_id: str, n: int, timeout: float = 120.0) -> list[dict]:
    """Poll the real get_canvas tool until at least n image shapes are placed."""
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    shapes: list[dict] = []
    while loop.time() < end:
        shapes = await _canvas_images(chat_id)
        if len(shapes) >= n:
            return shapes
        await asyncio.sleep(0.2)
    return shapes


def _assert_calls(state: dict, expected: list[tuple[int, int, str]]) -> None:
    gens = _gen_args(state)
    assert [(a.get("width"), a.get("height"), a.get("ratio"), a.get("count")) for a in gens] == \
        [(w, h, r, 1) for w, h, r in expected], gens
    assert all(a.get("size_lock") is True for a in gens), gens


def _packaging_script(state: dict, expected: list[tuple[int, int, str]], preset: str):
    """k-th step: read once, then one generate per expected image, then wait, then reply."""
    calls = len(expected)

    def respond(messages: list, n: int):
        state["messages"] = messages
        last = _last_user(messages)
        if state.get("last_user") != last:
            state["last_user"] = last
            state["turn_n"] = 0
        k = state["turn_n"]
        state["turn_n"] = k + 1
        if k == 0:
            return _calls(("skill", {"action": "read", "name": PACKAGING}))
        if 1 <= k <= calls:
            args = {"prompt": f"template {preset}, image {k}", "skill": PACKAGING}
            # The model passes the stage it is on (t3 stage 2 = the range shot); sizes are omitted.
            if preset == "playful" and k == calls:
                args["stage"] = 2
            return _calls(("generate_image", args))
        if k == calls + 1:
            return _calls(("wait_generation", {"ids": _all_ids(messages)}))
        return _reply("已按模板交付。" if state.get("lang") == "zh" else "Template delivery done.")

    return respond


def _brand_script(state: dict):
    """Turn 1: read + 3 direction proposals + stop for the pick. Turn 2: stage 2 = 1 board."""
    def respond(messages: list, n: int):
        state["messages"] = messages
        last = _last_user(messages)
        if state.get("last_user") != last:
            state["last_user"] = last
            state["turn_n"] = 0
        k = state["turn_n"]
        state["turn_n"] = k + 1
        stage2 = "选第一个方向" in last or "pick the first" in last.lower()
        if stage2:
            if k == 0:
                # No preset: the brand default template (geometric) is the same staged plan.
                return _calls(("generate_image", {
                    "prompt": "guideline board for the chosen direction", "skill": BRAND, "stage": 2}))
            if k == 1:
                return _calls(("wait_generation", {"ids": _all_ids(messages)}))
            return _reply("规范板已生成。" if state.get("lang") == "zh" else "The guideline board is ready.")
        if k == 0:
            return _calls(("skill", {"action": "read", "name": BRAND}))
        if 1 <= k <= 3:
            return _calls(("generate_image", {"prompt": f"logo direction {k}", "skill": BRAND}))
        if k == 4:
            return _reply("三个方向已出，选一个方向，我再出规范板。")
        return _reply("ok")

    return respond


@pytest.mark.parametrize("tile,preset,calls,value", PACKAGING_CASES)
async def test_fullapp_packaging_template_count_and_size(
        app_url, mock_ws, local_agent, ws_forward, monkeypatch, tile, preset, calls, value):  # noqa: F811
    """Each packaging template: exactly its own number of calls, each at its own pixels."""
    _provider, state = local_agent
    state["lang"] = "en"
    state["respond"] = _packaging_script(state, calls, preset)

    async with pw.async_playwright() as p:
        browser, pg = await _open_template(p, app_url, "en", PACKAGING, ws_forward, tile, "product_info", value)
        try:
            await pg.locator(".ca-composer__input").click()
            await pg.wait_for_function(
                "() => { const b = document.querySelector('.ca-composer__slotwrap button[data-slot=send]');"
                " return b && !b.disabled; }", timeout=60000)
            await pg.locator(".ca-composer__input").press("Enter")
            await _wait(lambda: len(mock_ws["submits"]) >= len(calls), timeout=180.0)
            assert len(mock_ws["submits"]) == len(calls), (preset, mock_ws["submits"])
            # No extra call: a template plan is exact, not a prompt hint.
            await asyncio.sleep(1.0)
            assert len(mock_ws["submits"]) == len(calls), (preset, len(mock_ws["submits"]))
            await _wait(lambda: state.get("wait"), timeout=120.0)
            _assert_calls(state, calls)
            gens = _gen_args(state)
            assert all(a.get("preset") == preset for a in gens), (preset, gens)
            # The lock the agent saw names the selected template and its plan.
            provider_text = state["turn"].user_text
            assert f"template={preset}" in provider_text, provider_text
            assert f"exactly {len(calls)} separate images" in provider_text or \
                (len(calls) == 1 and "exactly once" in provider_text), provider_text
            # Every planned image landed on the canvas.
            shapes = await _wait_shapes(state["chat"], len(calls))
            assert len(shapes) == len(calls), (preset, shapes)
            rows = (state.get("wait") or {}).get("results") or []
            placed = {sid for row in rows for sid in (row.get("shapes") or [])}
            assert placed <= {s["id"] for s in shapes}, (preset, placed, shapes)
        finally:
            await browser.close()


async def test_fullapp_packaging_no_template_uses_the_default_master(
        app_url, mock_ws, local_agent, ws_forward, monkeypatch):  # noqa: F811
    """No template tile clicked → the skill's documented default: 主款 1×1536×2048 (3:4)."""
    _provider, state = local_agent
    state["lang"] = "en"
    calls = [(1536, 2048, "3:4")]
    state["respond"] = _packaging_script(state, calls, "eco")

    async with pw.async_playwright() as p:
        browser, pg = await _open_template(p, app_url, "en", PACKAGING, ws_forward, None,
                                           "product_info", "AURELIA 30ml serum")
        try:
            await pg.locator(".ca-composer__input").click()
            await pg.wait_for_function(
                "() => { const b = document.querySelector('.ca-composer__slotwrap button[data-slot=send]');"
                " return b && !b.disabled; }", timeout=60000)
            await pg.locator(".ca-composer__input").press("Enter")
            await _wait(lambda: len(mock_ws["submits"]) >= 1, timeout=180.0)
            assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
            _assert_calls(state, calls)
            assert _gen_args(state)[0].get("preset") == "eco"
            provider_text = state["turn"].user_text
            # The dialog's default template is 主款 (eco); the lock names it and its plan.
            assert "template=eco" in provider_text, provider_text
            assert "width=1536 height=2048 ratio=3:4" in provider_text, provider_text
            shapes = await _wait_shapes(state["chat"], 1)
            assert len(shapes) == 1, shapes
        finally:
            await browser.close()


async def test_fullapp_brand_three_direction_proposals_then_one_guideline_board(
        app_url, mock_ws, local_agent, ws_forward, monkeypatch):  # noqa: F811
    """Brand: exactly 3×1:1, then (only after the user picks) exactly 1×16:9. Never a landscape single board."""
    _provider, state = local_agent
    state["lang"] = "zh"
    state["respond"] = _brand_script(state)

    async with pw.async_playwright() as p:
        browser, pg = await _open_template(p, app_url, "zh", BRAND, ws_forward, 0, "brand_info", "Wildpeak Coffee")
        try:
            await pg.locator(".ca-composer__input").click()
            await pg.wait_for_function(
                "() => { const b = document.querySelector('.ca-composer__slotwrap button[data-slot=send]');"
                " return b && !b.disabled; }", timeout=60000)
            await pg.locator(".ca-composer__input").press("Enter")
            # Stage 1: three 1:1 proposals, and nothing else before the user picks.
            await _wait(lambda: len(mock_ws["submits"]) >= 3, timeout=180.0)
            assert len(mock_ws["submits"]) == 3, mock_ws["submits"]
            await asyncio.sleep(1.2)
            assert len(mock_ws["submits"]) == 3, ("stage 2 ran before the pick", len(mock_ws["submits"]))
            _assert_calls(state, [(1024, 1024, "1:1")] * 3)
            provider_text = state["turn"].user_text
            assert "template=geometric" in provider_text
            assert "3 separate images" in provider_text and "2048" in provider_text and "16:9" in provider_text
            shapes1 = await _wait_shapes(state["chat"], 3)
            assert len(shapes1) == 3, shapes1
            await _wait(lambda: state.get("result") is not None, timeout=120.0)

            # The user picks a direction. The app clears the skill chip after a send, so this
            # follow-up is text-only, exactly like a real second turn.
            await pg.locator(".ca-composer__input").fill("选第一个方向，直接出规范板")
            await pg.wait_for_function(
                "() => { const b = document.querySelector('.ca-composer__slotwrap button[data-slot=send]');"
                " return b && !b.disabled; }", timeout=120000)
            await pg.locator(".ca-composer__input").press("Enter")
            # Stage 2: exactly one 16:9 guideline board; no repeat of stage 1, no 5th image.
            await _wait(lambda: len(mock_ws["submits"]) >= 4, timeout=180.0)
            assert len(mock_ws["submits"]) == 4, mock_ws["submits"]
            await asyncio.sleep(1.0)
            assert len(mock_ws["submits"]) == 4, ("unexpected extra image", len(mock_ws["submits"]))
            gens = _gen_args(state)
            assert [(a.get("width"), a.get("height"), a.get("ratio"), a.get("stage"), a.get("count"))
                    for a in gens] == [
                (1024, 1024, "1:1", 1, 1),
                (1024, 1024, "1:1", 1, 1),
                (1024, 1024, "1:1", 1, 1),
                (2048, 1152, "16:9", 2, 1),
            ], gens
            assert all(a.get("size_lock") is True and a.get("skill") == BRAND for a in gens), gens
            # Four images on the canvas (three proposals + one guideline board).
            shapes = await _wait_shapes(state["chat"], 4)
            assert len(shapes) == 4, shapes
            rows = (state.get("wait") or {}).get("results") or []
            placed = {sid for row in rows for sid in (row.get("shapes") or [])}
            assert placed <= {s["id"] for s in shapes}, (placed, shapes)
        finally:
            await browser.close()
