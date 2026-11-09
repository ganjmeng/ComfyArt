"""#870: when a gen card has no output, the DOM must not paint a broken <img>.

Covers failed (job stub + error), recovering/null-job (job cleared + error), and
size-lock refused. Mock WaveSpeed only, $0. Asserts: no <img> with empty/missing
src inside .ca-gen-card, and no img alt contains the model short name.
"""
from __future__ import annotations

import asyncio
import os

import pytest

from test_e2e_skill_canvas_707 import QWEN, _png, app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("index.html")), reason="needs built dist/")

W, H, WRONG = 1024, 1280, (2048, 682)
MODEL_FRAG = "Qwen"  # short_name fragment from Auto · Qwen Image 2.0


async def _open_gen(page, app_url):
    await page.add_init_script(
        "localStorage.setItem('comfyart.lang','zh'); localStorage.setItem('comfyart.e2e','1')"
    )
    await page.goto(app_url)
    await page.wait_for_timeout(1000)
    await page.mouse.click(28, 83)
    await page.locator(".tl-canvas").wait_for(timeout=60000)
    await page.wait_for_timeout(600)
    if await page.locator(".ca-modal").count():
        await page.locator(".ca-modal button").nth(-2).click()
    await page.wait_for_function("() => window.__caEditor")
    await page.get_by_role("button", name="图像生成").first.click()
    await page.locator(".ca-gen__prompt").wait_for()
    await page.evaluate(
        """([w, h, model]) => {
          const ed = window.__caEditor
          const id = ed.getSelectedShapeIds()[0]
          const shape = ed.getShape(id)
          ed.updateShape({
            id, type: 'generator',
            props: { ...shape.props, prompt: 'no-output-img', resolution: 'custom', ratio: '4:5', cw: w, ch: h, w, h },
            meta: { ...shape.meta, pixelSize: [w, h], sizeLockModel: model, quiet: false,
              modelChoice: { auto: true, model, category: 'poster_text',
                reason: { zh: '自动选择：海报/带字', en: 'Auto-picked: poster/text' } } },
          })
        }""",
        [W, H, QWEN],
    )


async def _assert_no_output_img_leak(page, label: str):
    info = await page.evaluate(
        """(frag) => {
          const card = document.querySelector('.ca-gen-card')
          if (!card) return { err: 'no-card' }
          const imgs = [...card.querySelectorAll('img')]
          const empty = imgs.filter((i) => {
            const s = i.getAttribute('src')
            return s == null || !String(s).trim()
          }).map((i) => i.outerHTML.slice(0, 160))
          const named = imgs.filter((i) => {
            const a = i.getAttribute('alt') || ''
            return a.includes(frag) || /Auto\\s*·/.test(a)
          }).map((i) => ({ alt: i.getAttribute('alt'), src: i.getAttribute('src') }))
          const model = card.querySelector('[data-testid=auto-model-label]')
          const modelPos = model ? getComputedStyle(model).position : null
          return {
            imgCount: imgs.length, empty, named, modelPos,
            hasError: !!card.querySelector('.ca-gen-card__error'),
            modelText: model ? (model.textContent || '').trim() : null,
          }
        }""",
        MODEL_FRAG,
    )
    assert info.get("err") is None, (label, info)
    assert info["empty"] == [], (label, info)
    assert info["named"] == [], (label, info)
    # after #870 CSS fix the Auto row stays absolute (not in-flow "alt" next to the icon)
    if info.get("modelText"):
        assert info["modelPos"] == "absolute", (label, info)


@pytest.mark.asyncio
async def test_no_output_states_have_no_broken_img_or_model_alt(app_url, mock_ws):  # noqa: F811
    mock_ws["png"] = _png(*WRONG, (20, 20, 20), "wrong")
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await _open_gen(page, app_url)

        # --- refused (real size-lock path → job null + error) ---
        before = len(mock_ws["submits"])
        await page.locator(".ca-gen__send").click()
        for _ in range(300):
            if len(mock_ws["submits"]) > before and await page.locator(".ca-gen-card__error").count():
                break
            await asyncio.sleep(0.1)
        assert await page.locator(".ca-gen-card__error").count() >= 1
        text = await page.locator(".ca-gen-card__error").inner_text()
        assert "没有通过" in text
        await _assert_no_output_img_leak(page, "refused")

        # --- recovering / null-job (explicit clear; size-lock already cleared job) ---
        await page.evaluate(
            """() => {
              const ed = window.__caEditor
              const id = [...ed.getCurrentPageShapes()].find((s) => s.type === 'generator').id
              const shape = ed.getShape(id)
              ed.updateShape({ id, type: 'generator', meta: { ...shape.meta, job: null } })
              const atom = window.__caResultsAtom
              if (atom) {
                const cur = atom.get()[id] || { srcs: [] }
                atom.update((r) => ({ ...r, [id]: { ...cur, srcs: [], error: cur.error || 'recovering probe' } }))
              }
            }"""
        )
        await page.wait_for_timeout(200)
        await _assert_no_output_img_leak(page, "recovering-null-job")

        # --- failed (job stub re-attached + error, still no output) ---
        await page.evaluate(
            """() => {
              const ed = window.__caEditor
              const id = [...ed.getCurrentPageShapes()].find((s) => s.type === 'generator').id
              const shape = ed.getShape(id)
              ed.updateShape({
                id, type: 'generator',
                meta: { ...shape.meta, job: { id: 'fail-probe', phase: 'running' } },
              })
              const atom = window.__caResultsAtom
              if (atom) {
                atom.update((r) => ({ ...r, [id]: { srcs: [], error: '生成失败 / Generation failed' } }))
              }
            }"""
        )
        await page.wait_for_timeout(200)
        # with job running, icon may hide; error must still not introduce a broken img
        await _assert_no_output_img_leak(page, "failed")
        await browser.close()
