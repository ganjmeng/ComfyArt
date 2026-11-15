"""#992 Full App: example-card option chips reach mock generate_image payloads.

Real dist, real chat/LocalLlmProvider/MCP, local WaveSpeed mock. $0, no paid calls.
Meta's three ratio chips each force every image to that ratio even when the scripted
model still emits the old mixed pack. UGC is style only. Rollback of the production
preset→#994 mapping turns the same assertion red.
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


async def _shot(pg, name):
    """Viewport shot after the dialog open/select animation has gone opaque."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    await pg.wait_for_timeout(500)
    await pg.screenshot(path=str(SHOTS / name), full_page=False)
PACK = ((1024, 1024, "1:1"), (1638, 2048, "4:5"), (1152, 2048, "9:16"))
UNIFORM = {
    "feed1x1": ((1024, 1024, "1:1"),) * 3,
    "feed4x5": ((1638, 2048, "4:5"),) * 3,
    "story9x16": ((1152, 2048, "9:16"),) * 3,
}
CHIPS = ("feed1x1", "feed4x5", "story9x16", "ugc")


def _sizes(gens: list[dict]) -> list[tuple[int, int, str, int]]:
    return [(a.get("width"), a.get("height"), a.get("ratio"), a.get("count")) for a in gens]


async def _open_dialog(p, app_url, lang, sid):  # noqa: F811
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
    await pg.get_by_test_id("rail-skills").click()
    await pg.get_by_test_id("skills-wall").wait_for(timeout=20000)
    card = pg.locator(f'[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="{sid}"]')
    await card.scroll_into_view_if_needed()
    await card.hover()
    await card.get_by_test_id("skills-card-try").click()
    dlg = pg.locator(f'[data-testid="skill-run-dialog"][data-skill="{sid}"]')
    await dlg.wait_for(timeout=15000)
    return browser, pg, dlg


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_meta_dialog_shows_chips_and_keeps_examples(app_url, lang, built_dist, no_paid_keys):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg, dlg = await _open_dialog(p, app_url, lang, META)
        try:
            examples = dlg.get_by_test_id("skill-run-examples")
            await examples.wait_for()
            assert int(await examples.get_attribute("data-count") or "0") >= 1
            chips = dlg.locator('[data-testid="skill-run-preset-chip"]')
            assert await chips.count() == 4
            assert [await chips.nth(i).get_attribute("data-preset") for i in range(4)] == list(CHIPS)
            # None selected by default — typed three-ratio pack must stay.
            selected = [await chips.nth(i).get_attribute("data-on") for i in range(4)]
            assert all(not flag for flag in selected)
            # Left is examples, not a Lovart template grid.
            assert await dlg.locator('[data-testid="skill-run-presets"]').count() == 0
            if SHOTS:
                await _shot(pg, f"meta-dialog-unselected-{lang}.png")
                await chips.nth(0).click()
                await _shot(pg, f"meta-dialog-feed1x1-{lang}.png")
        finally:
            await browser.close()


@pytest.mark.parametrize("preset,lang", [
    ("feed1x1", "en"),
    ("feed4x5", "zh"),
    ("story9x16", "en"),
])
async def test_fullapp_meta_ratio_chip_submits_all_three_at_that_ratio(
        app_url, mock_ws, local_agent, ws_forward, monkeypatch, preset, lang):  # noqa: F811
    _add_flare_models(monkeypatch)
    _provider, state = local_agent
    # Script still emits the old mixed pack; the server must coerce from the chip.
    state["respond"] = _pack_script(state, META, ("1:1", "4:5", "9:16"))
    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, lang, META, ws_forward,
                                        dialog_ref=SUBJECT, dialog_text="a paid-social pack",
                                        preset_id=preset,
                                        composer_name="Meta广告创意" if lang == "zh" else None)
        try:
            await _send_default(pg)
            await _wait(lambda: len(mock_ws["submits"]) >= 3, timeout=150.0)
            await _wait(lambda: state.get("wait"), timeout=150.0)
            gens = _gen_args(state)
            want = [(w, h, r, 1) for w, h, r in UNIFORM[preset]]
            assert _sizes(gens) == want, gens
            assert all(a.get("size_lock") is True and a.get("skill") == META and a.get("refs") for a in gens)
            assert len(mock_ws["submits"]) == 3
            for body, (w, h, _r) in zip([b for _m, b in mock_ws["submits"]], UNIFORM[preset]):
                _assert_provider_canvas(body, w, h)
            if SHOTS:
                SHOTS.mkdir(parents=True, exist_ok=True)
                rec = {"preset": preset, "lang": lang, "sizes": _sizes(gens), "submits": len(mock_ws["submits"])}
                (SHOTS / f"meta-{preset}-{lang}.json").write_text(json.dumps(rec, indent=2) + "\n")
        finally:
            await browser.close()


async def test_fullapp_meta_ugc_chip_keeps_default_pack(
        app_url, mock_ws, local_agent, ws_forward, monkeypatch):  # noqa: F811
    _add_flare_models(monkeypatch)
    _provider, state = local_agent
    state["respond"] = _pack_script(state, META, ("1:1", "4:5", "9:16"))
    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "en", META, ws_forward,
                                        dialog_ref=SUBJECT, dialog_text="ugc talking-head pack",
                                        preset_id="ugc")
        try:
            await _send_default(pg)
            await _wait(lambda: len(mock_ws["submits"]) >= 3, timeout=150.0)
            await _wait(lambda: state.get("wait"), timeout=150.0)
            gens = _gen_args(state)
            assert _sizes(gens) == [(w, h, r, 1) for w, h, r in PACK], gens
        finally:
            await browser.close()


async def test_fullapp_meta_feed1x1_rollback_keeps_mixed_pack(
        app_url, mock_ws, local_agent, ws_forward, monkeypatch):  # noqa: F811
    from ComfyArt.bot import skill_output as so
    monkeypatch.setattr(so, "ratio_from_example_preset_992", lambda *a, **k: None)
    _add_flare_models(monkeypatch)
    _provider, state = local_agent
    state["respond"] = _pack_script(state, META, ("1:1", "4:5", "9:16"))
    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "en", META, ws_forward,
                                        dialog_ref=SUBJECT, dialog_text="a paid-social pack",
                                        preset_id="feed1x1")
        try:
            await _send_default(pg)
            await _wait(lambda: len(mock_ws["submits"]) >= 3, timeout=150.0)
            await _wait(lambda: state.get("wait"), timeout=150.0)
            gens = _gen_args(state)
            with pytest.raises(AssertionError):
                assert _sizes(gens) == [(1024, 1024, "1:1", 1)] * 3
            assert _sizes(gens) == [(w, h, r, 1) for w, h, r in PACK], gens
        finally:
            await browser.close()


async def test_fullapp_logo_has_no_template_chips(app_url, built_dist, no_paid_keys):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg, dlg = await _open_dialog(p, app_url, "en", "logo-material-explorer")
        try:
            await dlg.get_by_test_id("skill-run-examples").wait_for()
            assert await dlg.locator('[data-testid="skill-run-preset-chip"]').count() == 0
            assert await dlg.locator('[data-testid="skill-run-presets"]').count() == 0
            if SHOTS:
                await _shot(pg, "logo-dialog-no-templates-en.png")
        finally:
            await browser.close()


RESTORE_DIALOG = {
    "meta-ads-creative-director": ("feed1x1", "feed4x5", "story9x16", "ugc"),
    "rednote-cover-maker": ("ugc-feed", "ugc-story"),
    "mobile-app-visual-design": ("home", "detail", "checkout", "onboarding"),
    "web-product-visual-design": ("hero", "features", "pricing", "responsive"),
    "marketing-campaign-generator": ("kv", "rednote-cover-maker", "display", "ooh"),
}


@pytest.mark.parametrize("sid,lang", [(s, l) for s in RESTORE_DIALOG for l in ("zh", "en")])
async def test_fullapp_restored_dialogs_keep_examples_and_show_option_chips(
        app_url, sid, lang, built_dist, no_paid_keys):  # noqa: F811
    want = list(RESTORE_DIALOG[sid])
    async with pw.async_playwright() as p:
        browser, pg, dlg = await _open_dialog(p, app_url, lang, sid)
        try:
            examples = dlg.get_by_test_id("skill-run-examples")
            await examples.wait_for()
            assert int(await examples.get_attribute("data-count") or "0") >= 1
            chips = dlg.locator('[data-testid="skill-run-preset-chip"]')
            assert await chips.count() == len(want)
            assert [await chips.nth(i).get_attribute("data-preset") for i in range(len(want))] == want
            selected = [await chips.nth(i).get_attribute("data-on") for i in range(len(want))]
            assert all(not flag for flag in selected)
            assert await dlg.locator('[data-testid="skill-run-presets"]').count() == 0
            if SHOTS:
                await _shot(pg, f"{sid}-dialog-unselected-{lang}.png")
                await chips.nth(0).click()
                await _shot(pg, f"{sid}-dialog-{want[0]}-{lang}.png")
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
