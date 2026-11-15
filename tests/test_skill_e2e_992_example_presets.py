"""#992 Full App: default homepage/Skills dialog has no option chips for the five example cards.

Real dist, real chat/LocalLlmProvider/MCP, local WaveSpeed mock. $0, no paid calls.
Default surface keeps Examples and does not accept chip clicks as this card's pass
condition. Explicit #994 text ratios still force every image to that ratio; no
named ratio keeps the typed mixed pack. Rollback of production user-ratio
precedence is covered in unit tests, not by clicking chips.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_skill_e2e_portrait_studio import ws_forward  # noqa: F401
from test_a_class_fullapp_e2e_911 import (  # noqa: F401
    _all_ids, _attached, _bind_open_project, _calls, _open_skill, _refs, _reply,
    _send_default, _wait, built_dist, local_agent, no_paid_keys,
)
from test_e2e_fullapp_982 import (
    META, SUBJECT, _add_flare_models, _assert_provider_canvas, _gen_args, _pack_script,
)

pw = pytest.importorskip("playwright.async_api")

SHOTS = Path(os.environ["CA992_SHOTS"]) if os.environ.get("CA992_SHOTS") else None

FIVE = (
    "meta-ads-creative-director",
    "rednote-cover-maker",
    "mobile-app-visual-design",
    "web-product-visual-design",
    "marketing-campaign-generator",
)
PACK = ((1024, 1024, "1:1"), (1638, 2048, "4:5"), (1152, 2048, "9:16"))


async def _shot(pg, name):
    """Viewport shot after the dialog open animation has gone opaque."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    await pg.wait_for_timeout(500)
    await pg.screenshot(path=str(SHOTS / name), full_page=False)


def _sizes(gens: list[dict]) -> list[tuple[int, int, str, int]]:
    return [(a.get("width"), a.get("height"), a.get("ratio"), a.get("count")) for a in gens]


async def _open_dialog(p, app_url, lang, sid, *, via="skills"):  # noqa: F811
    try:
        browser = await p.chromium.launch()
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"chromium not available, this e2e must not skip: {e}")
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900},
                                    locale="zh-CN" if lang == "zh" else "en-US")
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','light')")
    await pg.goto(app_url)
    if via == "home":
        # Same SkillRunDialog as Skills; open from the home skills surface when present.
        await pg.get_by_test_id("rail-home").click()
        card = pg.locator(f'[data-testid="skills-wall-card"][data-skill="{sid}"], [data-skill="{sid}"]').first
        await card.scroll_into_view_if_needed()
        try_btn = card.get_by_test_id("skills-card-try")
        if await try_btn.count():
            await try_btn.click()
        else:
            await card.click()
    else:
        await pg.get_by_test_id("rail-skills").click()
        await pg.get_by_test_id("skills-wall").wait_for(timeout=20000)
        card = pg.locator(f'[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="{sid}"]')
        await card.scroll_into_view_if_needed()
        await card.hover()
        await card.get_by_test_id("skills-card-try").click()
    dlg = pg.locator(f'[data-testid="skill-run-dialog"][data-skill="{sid}"]')
    await dlg.wait_for(timeout=15000)
    return browser, pg, dlg


@pytest.mark.parametrize("sid,lang", [(s, l) for s in FIVE for l in ("zh", "en")])
async def test_fullapp_default_dialogs_keep_examples_and_have_no_option_chips(
        app_url, sid, lang, built_dist, no_paid_keys):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg, dlg = await _open_dialog(p, app_url, lang, sid)
        try:
            examples = dlg.get_by_test_id("skill-run-examples")
            await examples.wait_for()
            assert int(await examples.get_attribute("data-count") or "0") >= 1
            assert await dlg.locator('[data-testid="skill-run-preset-chip"]').count() == 0
            assert await dlg.locator('[data-testid="skill-run-presets"]').count() == 0
            if SHOTS:
                await _shot(pg, f"{sid}-dialog-no-chips-{lang}.png")
        finally:
            await browser.close()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_logo_dialog_has_no_template_chips(app_url, lang, built_dist, no_paid_keys):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg, dlg = await _open_dialog(p, app_url, lang, "logo-material-explorer")
        try:
            await dlg.get_by_test_id("skill-run-examples").wait_for()
            assert await dlg.locator('[data-testid="skill-run-preset-chip"]').count() == 0
            assert await dlg.locator('[data-testid="skill-run-presets"]').count() == 0
            if SHOTS:
                await _shot(pg, f"logo-dialog-no-templates-{lang}.png")
        finally:
            await browser.close()


async def test_fullapp_home_and_skills_share_dialog_without_chips(
        app_url, built_dist, no_paid_keys):  # noqa: F811
    """Home and Skills open the same dialog; neither default surface shows chips."""
    async with pw.async_playwright() as p:
        browser, pg, dlg = await _open_dialog(p, app_url, "en", META, via="skills")
        try:
            assert await dlg.locator('[data-testid="skill-run-preset-chip"]').count() == 0
            await dlg.locator('[data-testid="skill-run-dialog-close"], button').first  # dialog is up
        finally:
            await browser.close()
        browser, pg, dlg = await _open_dialog(p, app_url, "en", META, via="home")
        try:
            await dlg.wait_for(timeout=15000)
            assert await dlg.locator('[data-testid="skill-run-preset-chip"]').count() == 0
        finally:
            await browser.close()


async def test_fullapp_meta_explicit_text_ratio_submits_all_three_at_that_ratio(
        app_url, mock_ws, local_agent, ws_forward, monkeypatch):  # noqa: F811
    """#994 text path, not a default chip click."""
    _add_flare_models(monkeypatch)
    _provider, state = local_agent
    state["respond"] = _pack_script(state, META, ("1:1", "4:5", "9:16"))
    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "en", META, ws_forward,
                                        dialog_ref=SUBJECT,
                                        dialog_text="请全部做成 1:1，不要改张数。")
        try:
            await _send_default(pg)
            await _wait(lambda: len(mock_ws["submits"]) >= 3, timeout=150.0)
            await _wait(lambda: state.get("wait"), timeout=150.0)
            gens = _gen_args(state)
            want = [(1024, 1024, "1:1", 1)] * 3
            assert _sizes(gens) == want, gens
            assert all(a.get("size_lock") is True and a.get("skill") == META and a.get("refs") for a in gens)
            assert len(mock_ws["submits"]) == 3
            for body in [b for _m, b in mock_ws["submits"]]:
                _assert_provider_canvas(body, 1024, 1024)
            if SHOTS:
                SHOTS.mkdir(parents=True, exist_ok=True)
                rec = {"path": "text-994", "sizes": _sizes(gens), "submits": len(mock_ws["submits"])}
                (SHOTS / "meta-text-1x1-en.json").write_text(json.dumps(rec, indent=2) + "\n")
        finally:
            await browser.close()


async def test_fullapp_meta_no_named_ratio_keeps_default_pack(
        app_url, mock_ws, local_agent, ws_forward, monkeypatch):  # noqa: F811
    _add_flare_models(monkeypatch)
    _provider, state = local_agent
    state["respond"] = _pack_script(state, META, ("1:1", "4:5", "9:16"))
    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "en", META, ws_forward,
                                        dialog_ref=SUBJECT, dialog_text="a paid-social pack")
        try:
            await _send_default(pg)
            await _wait(lambda: len(mock_ws["submits"]) >= 3, timeout=150.0)
            await _wait(lambda: state.get("wait"), timeout=150.0)
            gens = _gen_args(state)
            assert _sizes(gens) == [(w, h, r, 1) for w, h, r in PACK], gens
        finally:
            await browser.close()
