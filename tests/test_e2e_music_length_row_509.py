"""#509 PR1: the music length row (slider for ACE-Step, 「时长由歌词决定」 note for YuE2/MiniMax) keeps one height, so the
controls below never move when switching models; screenshots zh light / en dark. Mocks only (no real WaveSpeed calls).
Not run yet: the shared machine is reserved; run when cleared."""
from __future__ import annotations

from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

SHOTS = Path(__file__).resolve().parent.parent / "artifacts" / "509"
GEOM = """() => { const row = document.querySelector('[data-testid=music-length-row]'); const next = row.nextElementSibling;
  return { rowH: row.getBoundingClientRect().height, nextY: next.getBoundingClientRect().top,
    slider: !!row.querySelector('input[type=range]'), note: row.querySelector('[data-testid=music-duration-note] .ca-chat__hint')?.textContent ?? null } }"""


async def _pick(pg, label):
    await pg.locator(".ca-modal .ca-fieldselect").click()
    await pg.locator(".ca-fieldselect__menu .ca-menu__item", has_text=label).click()
    await pg.wait_for_timeout(200)


@pytest.mark.parametrize("lang,theme,note", [("zh", "light", "时长由歌词决定"), ("en", "dark", "Length follows the lyrics")])
async def test_music_length_row_does_not_shift(app_url, fake_tools, monkeypatch, lang, theme, note):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 900})).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
        await pg.goto(app_url + f"?project=e509{lang}&new=1")
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(1500)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        await pg.locator(".ca-split__chev").first.click()
        await pg.locator(".ca-menu__item", has_text="音频" if lang == "zh" else "audio").first.click()
        await pg.locator("[data-testid=music-length-row]").wait_for()
        SHOTS.mkdir(parents=True, exist_ok=True)
        await _pick(pg, "ACE-Step 1.5")
        ace = await pg.evaluate(GEOM)
        await pg.locator(".ca-modal").screenshot(path=str(SHOTS / f"{lang}-{theme}-ace-step.png"))
        await _pick(pg, "YuE2")
        yue = await pg.evaluate(GEOM)
        await pg.locator(".ca-modal").screenshot(path=str(SHOTS / f"{lang}-{theme}-yue2.png"))
        await _pick(pg, "MiniMax Music 3")
        mm = await pg.evaluate(GEOM)
        assert ace["slider"] and ace["note"] is None, ace
        assert not yue["slider"] and yue["note"] == note and mm["note"] == note, (yue, mm)
        assert ace["rowH"] == yue["rowH"] == mm["rowH"], (ace, yue, mm)
        assert ace["nextY"] == yue["nextY"] == mm["nextY"], (ace, yue, mm)
        await browser.close()
