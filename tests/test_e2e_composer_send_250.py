"""#250: in image / video mode the composer bar folds (settings text → short → icon, model icon, mode icon last)
so +, voice and send always stay inside the bar and send is clickable. 1280 and 360 wide, zh and en. Mocks only ($0)."""
from __future__ import annotations

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import fake_tools  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

SHORT = {"image": "1K · 1:1", "video": "16:9 · 5s"}
LABEL = {"image": {"zh": "图像", "en": "Image"}, "video": {"zh": "视频", "en": "Video"}, "agent": {"zh": "Agent", "en": "Agent"}}


async def _pick_mode(pg, mode: str, lang: str) -> None:
    """Open composer mode menu and choose image / video / Loomi Agent.

    #505: Popover portals the menu at left:-9999 until useLayoutEffect places it
    (Popover.tsx). Under full-suite load, Playwright can start clicking Video while
    the portal is still off-screen and time out scrolling it into view. Wait until
    the .ca-pop that owns .ca-agentpick is on-screen, then click. No product change.
    """
    trigger = pg.locator(".ca-composer__mode").first
    await trigger.wait_for()
    menu = pg.locator(".ca-agentpick")
    for _ in range(3):
        if await menu.count() and await menu.is_visible():
            break
        await trigger.click()
        try:
            await menu.wait_for(state="visible", timeout=5000)
            break
        except Exception:
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(200)
    else:
        await menu.wait_for(state="visible", timeout=10000)
    # Portal starts at (-9999,-9999); only then is the Video row actionable.
    await pg.wait_for_function(
        """() => {
          const pick = document.querySelector('.ca-agentpick');
          if (!pick) return false;
          const pop = pick.closest('.ca-pop');
          if (!pop) return false;
          const r = pop.getBoundingClientRect();
          return r.left >= -1 && r.top >= -1 && r.width > 8 && r.height > 8;
        }""",
        timeout=15000,
    )
    if mode == "agent":
        item = menu.locator(".ca-menu__item").filter(has_text="Loomi Agent").first  # #399
    else:
        item = menu.locator(".ca-menu__item:not(.ca-agentpick__row)").filter(has_text=LABEL[mode][lang]).first
    await item.wait_for(state="visible")
    await item.click()


FOOT = """() => {
  const c = document.querySelector('.ca-composer').getBoundingClientRect()
  const foot = document.querySelector('.ca-composer__foot'); const fr = foot.getBoundingClientRect()
  const r = (s) => foot.querySelector(s).getBoundingClientRect()
  const inside = (b) => b.width > 0 && b.left >= fr.left - 0.5 && b.right <= fr.right + 0.5 && b.right <= Math.min(c.right, innerWidth) + 0.5
  const s = r('.ca-composer__slotwrap > :not([hidden])'); const hit = document.elementFromPoint(s.left + s.width / 2, s.top + s.height / 2)
  const vis = (e) => !!e && e.getBoundingClientRect().width > 0
  return {
    send: inside(s), plus: inside(r('.ca-bar__btn--icon')), hit: !!hit && foot.querySelector('.ca-composer__slotwrap').contains(hit),
    fixed: [...foot.querySelectorAll(':scope > .ca-pop-anchor > .ca-bar__btn--icon, :scope > .ca-composer__slotwrap > :not([hidden])')].every((e) => e.getBoundingClientRect().width >= 31.5),
    pills: [...foot.querySelectorAll('.ca-composer__mode, [data-pill]')].map((e) => ({ pill: e.dataset.pill || 'mode', text: e.innerText.trim(), title: e.title, aria: e.getAttribute('aria-label') || '', icon: vis(e.querySelector('.ca-gen__pillicon, .ca-icon')) })),
    settingsCut: (() => { const t = foot.querySelector("[data-pill=settings] > .ca-gen__pilltext"); return vis(t) && t.scrollWidth > t.clientWidth })(),
    midCut: (() => { const m = foot.querySelector(".ca-composer__mid"); return m.scrollWidth > m.clientWidth })(),
    agentFull: (() => { const t = foot.querySelector('.ca-composer__mode[data-agent] > .ca-menu__grow'); return !t || t.scrollWidth <= t.clientWidth + 0.5 })(),
    chevSame: (() => { const a = foot.querySelector('.ca-composer__mode > .ca-icon:last-child'), b = foot.querySelector('[data-pill] .ca-gen__chev'); const ra = a.getBoundingClientRect(); const sz = Math.abs(ra.width - 16) < 0.5 && Math.abs(ra.height - 16) < 0.5; const bs = [...foot.querySelectorAll('[data-pill] .ca-gen__chev')].every((e) => { const r = e.getBoundingClientRect(); return r.width === 0 || (Math.abs(r.width - 16) < 0.5 && Math.abs(r.height - 16) < 0.5) }); return sz && bs && (!b || getComputedStyle(a).color === getComputedStyle(b).color) })(),
    slot: foot.querySelector('.ca-composer__slotwrap').dataset.slot, slots: foot.querySelectorAll('.ca-composer__slotwrap > :not([hidden])').length, mics: foot.querySelectorAll('.ca-bar__btn.ca-voice').length,
    order: (() => { const q = (x) => foot.querySelector(x); const md = q('.ca-composer__mode'), m = q('[data-pill=model]'), st = q('[data-pill=settings]'), sl = q('.ca-composer__slotwrap'); if (!m || !st) return true; const [a, b, c, d] = [md, m, st, sl].map((e) => e.getBoundingClientRect()); const ok = a.right <= b.left + 0.5 && b.right <= c.left + 0.5 && c.right <= d.left + 0.5 && d.left - c.right <= 12 && c.left - b.right <= 12; return ok || [a.left, a.right, b.left, b.right, c.left, c.right, d.left].map(Math.round).join(",") })(),
    modelW: (foot.querySelector('[data-pill=model]') || { getBoundingClientRect: () => ({ width: 0 }) }).getBoundingClientRect().width,
    modeText: (() => { const t = foot.querySelector('.ca-composer__mode > .ca-composer__modetext, .ca-composer__mode > .ca-menu__grow'); return t ? { text: t.textContent.trim(), w: t.getBoundingClientRect().width } : null })(),
    modeChev: (() => { const m = foot.querySelector('.ca-composer__mode'); const c = m.querySelector(':scope > .ca-icon:last-child'); const a = c.getBoundingClientRect(), b = m.getBoundingClientRect(); return a.width >= 10 && a.right <= b.right + 0.5 })(),
  }
}"""


@pytest.mark.parametrize("mode", ["image", "video", "agent"])
@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("width", [1280, 1100, 900, 360])
async def test_send_stays_in_bar(app_url, fake_tools, monkeypatch, width, lang, mode):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        ctx = await browser.new_context(viewport={"width": width, "height": 800})
        pg = await ctx.new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
        await pg.goto(app_url + "?project=e250&new=1")
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(1500)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        await _pick_mode(pg, mode, lang)
        await pg.wait_for_timeout(300)
        if await pg.locator(".ca-agentpick").count():
            await pg.keyboard.press("Escape")
        await pg.locator(".ca-composer__input").fill("a cat")
        await pg.wait_for_timeout(400)
        bar = await pg.evaluate(FOOT)
        assert bar["slot"] == "send" and bar["slots"] == 1 and bar["mics"] == 0, bar  # typed -> send; no separate mic
        assert bar["send"] and bar["plus"] and bar["hit"] and bar["fixed"], bar
        # the mode button always shows its text (never icon only), and its arrow stays visible even if the text ellipsizes
        assert bar["modeText"] and bar["modeText"]["text"] and bar["modeText"]["w"] >= 12, bar
        assert bar["modeChev"], bar
        assert bar["chevSame"], bar  # mode arrow same colour and 16x16 size as settings / model arrows
        if mode == "agent":
            assert bar["agentFull"], bar  # "Loomi" (#399) shows in full when the bar has room (incl. 360)
            await browser.close()
            return
        assert [x["pill"] for x in bar["pills"]] == ["mode", "model", "settings"], bar  # #268 final: mode left; model, settings right
        assert bar["order"] is True, bar["order"]  # #268: mode < model < settings < voice/send, model+settings grouped right next to the slot
        assert len(bar["pills"]) == 3, bar  # mode, settings and model are all kept, none hidden
        assert all((x["aria"] if x["pill"] == "model" else x["title"]) for x in bar["pills"]), bar  # full text on hover (model: icon button, Tip + aria-label only, #287)
        assert not bar["settingsCut"] and not bar["midCut"], bar  # folded or iconised, never cut mid-text
        assert bar["modelW"] <= 120.5, bar
        if width >= 900:  # v2: room for the middle tier, so settings must not jump straight to the icon
            # #287: the model is now a 32px icon button, so settings may show in full; never jumps to icon only
            assert next(x for x in bar["pills"] if x["pill"] == "settings")["text"].startswith(SHORT[mode]), bar
        if width == 360:
            assert all(x["text"] == "" and x["icon"] for x in bar["pills"][1:]), bar  # phone: settings and model icon only
            assert bar["pills"][0]["text"], bar  # mode keeps its text
        await browser.close()


SLOT = """() => { const w = document.querySelector('.ca-composer__slotwrap'); const b = w.querySelector(':scope > :not([hidden])').getBoundingClientRect();
  const fr = document.querySelector('.ca-composer__foot').getBoundingClientRect();
  return { slot: w.dataset.slot, n: w.querySelectorAll(':scope > :not([hidden])').length, w: b.width, h: b.height, x: Math.round(b.left), inside: b.left >= fr.left - 0.5 && b.right <= fr.right + 0.5 } }"""


@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("width", [1280, 360])
async def test_voice_send_one_slot(app_url, fake_tools, monkeypatch, width, lang):  # noqa: F811
    """#250 v2: empty -> voice, typed -> send, cleared -> voice; whitespace-only stays voice; same 32px spot; inside the bar at 360."""
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pg = await (await browser.new_context(viewport={"width": width, "height": 800})).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
        await pg.goto(app_url + "?project=e250s&new=1")
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(1500)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        inp = pg.locator(".ca-composer__input")
        empty = await pg.evaluate(SLOT)
        assert empty["slot"] == "voice" and empty["n"] == 1 and empty["w"] == 32 and empty["h"] == 32 and empty["inside"], empty
        await inp.fill("   ")
        assert (await pg.evaluate(SLOT))["slot"] == "voice"
        await inp.fill("a cat")
        typed = await pg.evaluate(SLOT)
        assert typed["slot"] == "send" and typed["n"] == 1 and typed["w"] == 32 and typed["x"] == empty["x"] and typed["inside"], (empty, typed)
        await inp.fill("")
        assert (await pg.evaluate(SLOT))["slot"] == "voice"
        await browser.close()
