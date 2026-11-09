"""#870: when a gen card has no output, the DOM must not paint a broken <img>.

Covers failed (job stub + error), recovering/null-job (job cleared + error), and
size-lock refused. Mock WaveSpeed only, $0. Asserts: no <img> with empty/missing
src inside .ca-gen-card; no img alt contains the model short name; in-frame Auto
label does not intersect the error banner or placeholder (out of flow / absent).
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


def _overlap(a, b):
    return not (a["x2"] <= b["x1"] or b["x2"] <= a["x1"] or a["y2"] <= b["y1"] or b["y2"] <= a["y1"])


async def _assert_no_output_img_leak(page, label: str):
    info = await page.evaluate(
        """(frag) => {
          const card = document.querySelector('.ca-gen-card')
          if (!card) return { err: 'no-card' }
          const rect = (el) => {
            if (!el) return null
            const r = el.getBoundingClientRect()
            return { x1: r.left, y1: r.top, x2: r.right, y2: r.bottom, w: r.width, h: r.height }
          }
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
          const errEl = card.querySelector('.ca-gen-card__error')
          const icon = card.querySelector('.ca-gen-card__icon')
          const modelPos = model ? getComputedStyle(model).position : null
          const modelDisplay = model ? getComputedStyle(model).display : null
          return {
            imgCount: imgs.length, empty, named, modelPos, modelDisplay,
            hasError: !!errEl,
            modelText: model ? (model.textContent || '').trim() : null,
            modelRect: rect(model),
            errorRect: rect(errEl),
            iconRect: rect(icon),
            pending: card.getAttribute('data-pending'),
          }
        }""",
        MODEL_FRAG,
    )
    assert info.get("err") is None, (label, info)
    assert info["empty"] == [], (label, info)
    assert info["named"] == [], (label, info)
    assert info["hasError"], (label, info)
    # #870: settled no-output → no in-frame Auto row (SelectionLabel keeps it in the header)
    assert info["modelText"] is None and info["modelRect"] is None, (label, info)
    # if a future change reintroduces the node, it must stay out of flow and not intersect
    if info.get("modelRect"):
        assert info["modelPos"] == "absolute", (label, info)
        if info.get("errorRect"):
            assert not _overlap(info["modelRect"], info["errorRect"]), (label, info)
        if info.get("iconRect") and info["iconRect"]["w"] > 0:
            assert not _overlap(info["modelRect"], info["iconRect"]), (label, info)


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
        await _assert_no_output_img_leak(page, "failed")
        await browser.close()
