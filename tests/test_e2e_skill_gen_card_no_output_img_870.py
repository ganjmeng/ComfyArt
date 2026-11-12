"""#870: Auto · model is header-only; gen-card frame never paints .ca-gen-frame__model.

Across data-running, data-pending, a size-lock mismatch (image delivered + notice,
no error card), and a failed stub: (1) no in-frame model row on a gen card,
(2) SelectionLabel header contains Auto · <model> when a card is present, (3) with no
output, no <img> with empty/missing src. Mock WaveSpeed, $0.
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
FLARE = "openai/gpt-image-2.6-flare/text-to-image"  # #871 09b poster_fb model


async def _open_gen(page, app_url, prompt="870-label", model=None):
    model = model or QWEN
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
        """([w, h, model, prompt]) => {
          const ed = window.__caEditor
          const id = ed.getSelectedShapeIds()[0]
          const shape = ed.getShape(id)
          ed.updateShape({
            id, type: 'generator',
            props: { ...shape.props, prompt, resolution: 'custom', ratio: '4:5', cw: w, ch: h, w, h },
            meta: { ...shape.meta, pixelSize: [w, h], sizeLockModel: model, quiet: false,
              modelChoice: { auto: true, model, category: 'poster_text',
                reason: { zh: '自动选择：海报/带字', en: 'Auto-picked: poster/text' } } },
          })
          ed.select(id)
        }""",
        [W, H, model, prompt],
    )


async def _assert_header_only(page, label: str, *, expect_error: bool):
    info = await page.evaluate(
        """() => {
          const card = document.querySelector('.ca-gen-card')
          const header = document.querySelector('.ca-label')
          if (!card) return { err: 'no-card' }
          const imgs = [...card.querySelectorAll('img')].map((i) => ({
            src: i.getAttribute('src'), alt: i.getAttribute('alt'),
          }))
          return {
            inFrameModel: !!card.querySelector('.ca-gen-frame__model'),
            inFrameTestId: !!card.querySelector('[data-testid=auto-model-label]'),
            headerText: header ? header.innerText : null,
            headerModel: header ? !!header.querySelector('[data-testid=auto-model-label], .ca-label__model') : false,
            hasError: !!card.querySelector('.ca-gen-card__error'),
            emptyImgs: imgs.filter((i) => i.src == null || !String(i.src).trim()),
            running: card.getAttribute('data-running'),
            pending: card.getAttribute('data-pending'),
          }
        }"""
    )
    assert info.get("err") is None, (label, info)
    assert info["inFrameModel"] is False and info["inFrameTestId"] is False, (label, info)
    assert info["headerText"] and "Auto ·" in info["headerText"], (label, info)
    assert info["headerModel"] is True, (label, info)
    if expect_error:
        assert info["hasError"] is True, (label, info)
        assert info["emptyImgs"] == [], (label, info)
    return info


@pytest.mark.asyncio
async def test_header_only_auto_label_running_pending_and_no_output(app_url, mock_ws):  # noqa: F811
    mock_ws["png"] = _png(*WRONG, (20, 20, 20), "wrong")
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await _open_gen(page, app_url, prompt="870 header-only", model=QWEN)

        # --- data-running ---
        await page.evaluate(
            """() => {
              const ed = window.__caEditor
              const id = [...ed.getCurrentPageShapes()].find((s) => s.type === 'generator').id
              const shape = ed.getShape(id)
              ed.updateShape({ id, type: 'generator', meta: { ...shape.meta, job: { id: 'run', phase: 'running' } } })
              ed.select(id)
              const atom = window.__caResultsAtom
              if (atom) atom.update((r) => { const n = { ...r }; delete n[id]; return n })
            }"""
        )
        await page.wait_for_timeout(200)
        await page.locator(".ca-label").wait_for()
        run = await _assert_header_only(page, "running", expect_error=False)
        assert run["running"] == "true", run

        # --- data-pending ---
        await page.evaluate(
            """() => {
              const ed = window.__caEditor
              const id = [...ed.getCurrentPageShapes()].find((s) => s.type === 'generator').id
              const shape = ed.getShape(id)
              ed.updateShape({ id, type: 'generator', meta: { ...shape.meta, job: { id: 'pend', uncertain: true } } })
              ed.select(id)
              const atom = window.__caResultsAtom
              if (atom) atom.update((r) => ({ ...r, [id]: { srcs: [], pending: true } }))
            }"""
        )
        await page.wait_for_timeout(200)
        pend = await _assert_header_only(page, "pending", expect_error=False)
        assert pend["pending"] == "true", pend

        # --- size-lock mismatch: charged image is delivered, info notice shown, no error card ---
        await page.evaluate(
            """() => {
              const ed = window.__caEditor
              const id = [...ed.getCurrentPageShapes()].find((s) => s.type === 'generator').id
              const shape = ed.getShape(id)
              ed.updateShape({ id, type: 'generator', meta: { ...shape.meta, job: null } })
            }"""
        )
        before = len(mock_ws["submits"])
        want = "出图尺寸低于预期（实际 2048×682），已按原图交付。"
        await page.locator(".ca-gen__send").click()
        delivered = False
        for _ in range(300):
            nimg = await page.evaluate(
                "() => window.__caEditor.getCurrentPageShapes().filter((s) => s.type === 'image').length"
            )
            if len(mock_ws["submits"]) > before and nimg >= 1:
                delivered = True
                break
            await asyncio.sleep(0.1)
        assert delivered, "size-lock mismatch must still place the charged image on the canvas"
        notice_shown = False
        for _ in range(100):
            titles = await page.locator(".tlui-toast__title").all_inner_texts()
            if any(want in t for t in titles):
                notice_shown = True
                break
            await asyncio.sleep(0.1)
        assert notice_shown, "expected the size-delivery info toast"
        assert await page.locator(".ca-gen-card__error").count() == 0
        toast = page.locator(".tlui-toast__container").filter(has_text=want)
        assert await toast.count() >= 1
        assert (await toast.first.get_attribute("data-severity")) == "info"

        # --- failed (job stub + error, still no in-frame model) ---
        # defaultPlacer removes the generator after a successful delivery; open a new one for this stub.
        await page.get_by_role("button", name="图像生成").first.click()
        await page.locator(".ca-gen__prompt").wait_for()
        await page.evaluate(
            """([w, h, model, prompt]) => {
              const ed = window.__caEditor
              const id = ed.getSelectedShapeIds()[0] || [...ed.getCurrentPageShapes()].find((s) => s.type === 'generator')?.id
              const shape = ed.getShape(id)
              ed.updateShape({
                id, type: 'generator',
                props: { ...shape.props, prompt, resolution: 'custom', ratio: '4:5', cw: w, ch: h, w, h },
                meta: { ...shape.meta, pixelSize: [w, h], sizeLockModel: model, quiet: false, job: { id: 'fail', phase: 'running' },
                  modelChoice: { auto: true, model, category: 'poster_text',
                    reason: { zh: '自动选择：海报/带字', en: 'Auto-picked: poster/text' } } },
              })
              ed.select(id)
              const atom = window.__caResultsAtom
              if (atom) atom.update((r) => ({ ...r, [id]: { srcs: [], error: '生成失败 / Generation failed' } }))
            }""",
            [W, H, QWEN, "870 failed stub"],
        )
        await page.wait_for_timeout(200)
        await page.locator(".ca-label").wait_for()
        await _assert_header_only(page, "failed", expect_error=True)
        await browser.close()
