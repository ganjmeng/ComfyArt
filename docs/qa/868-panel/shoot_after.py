#!/usr/bin/env python3
"""#868 panel avoidance: $0 local shots after the expand scale slider is released.

1x / 2x / 3x at 1440x900, plus 3x at a 1280px-wide viewport. Localhost only.
Requires a built dist in this worktree (do not commit it).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, sync_playwright

HERE = Path(__file__).resolve().parent
PR_ROOT = HERE.parents[2]
SYS868 = HERE.parent / "868"
sys.path.insert(0, str(SYS868))
from shoot_lr import (  # noqa: E402
    PY,
    boot,
    make_src,
    open_expand,
    open_project,
    set_scale_js,
    stop,
)

# Re-import Page helpers we wrap, because shoot_lr.new_page hardcodes 1440x900.
OUT = HERE
PORT = 8868
CLEAR = 12
CANVAS_ZOOM = 50


def new_page(browser, url: str, vp: dict) -> Page:
    page = browser.new_page(viewport=vp, device_scale_factor=2)
    page.add_init_script(
        "localStorage.setItem('comfyart.lang','zh');"
        "localStorage.setItem('comfyart.theme','light');"
    )
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    modal = page.locator(".ca-modal button")
    if modal.count():
        try:
            modal.nth(-2).click(timeout=1500)
            page.wait_for_timeout(200)
        except Exception:
            pass
    return page


def zoom_to(page: Page, pct: int) -> None:
    btn = page.locator(".ca-zoom__btn")
    btn.wait_for(timeout=8000)
    if btn.inner_text().strip().rstrip("%") == str(pct):
        return
    btn.click()
    page.locator(".ca-menu__item", has_text=f"缩放至 {pct}%").click()
    page.wait_for_timeout(450)


def hold_slider(page: Page) -> None:
    slider = page.locator(".ca-panel input[type=range]").first
    slider.wait_for()
    box = slider.bounding_box()
    assert box
    page.mouse.move(box["x"] + 6, box["y"] + box["height"] / 2)
    slider.dispatch_event(
        "pointerdown",
        {
            "button": 0,
            "buttons": 1,
            "pointerId": 1,
            "pointerType": "mouse",
            "isPrimary": True,
            "bubbles": True,
            "composed": True,
        },
    )
    page.wait_for_timeout(80)


def release_slider(page: Page) -> None:
    page.mouse.up()
    page.wait_for_timeout(250)  # 150ms move transition + settle


def clearance(page: Page, gap: int = CLEAR) -> dict:
    return page.evaluate(
        """(gap) => {
          const panel = document.querySelector('.ca-panel');
          const gen = document.querySelector('.ca-panel__primary');
          const tools = document.querySelector('.ca-tools');
          const dock = document.querySelector('.ca-dock');
          const box = document.querySelector('.ca-expand');
          if (!panel || !gen || !tools || !dock) return { ok: false, reason: 'missing el' };
          const r = (el) => {
            const b = el.getBoundingClientRect();
            return { l: b.left, t: b.top, r: b.right, b: b.bottom, w: b.width, h: b.height };
          };
          const overlaps = (a, b, g) =>
            a.l < b.r + g && a.r > b.l - g && a.t < b.b + g && a.b > b.t - g;
          const p = r(panel), g = r(gen), t = r(tools), d = r(dock);
          const handles = [...document.querySelectorAll('.ca-expand__handle')].map(r);
          const handleHit = handles.some((h) => overlaps(p, h, gap));
          const boxR = box ? r(box) : null;
          // Side placement must keep 16px from the expand box. Pin may overlap the interior
          // but must still clear handles, the dock, and the zoom bar.
          const scale = document.querySelector('.ca-panel input[type=range]')?.value;
          // Pin fallback (rule 2): panel is flush with the viewport right edge.
          // In that case the box may be too wide for a 16px side gap, so a handle
          // hit is accepted; toolbars and the Generate button must still stay clear.
          const pinned = Math.abs((window.innerWidth - 8) - p.r) <= 1;
          const ok = !overlaps(p, t, gap) && !overlaps(p, d, gap) && !overlaps(g, t, 0)
            && (pinned || (!handleHit && !overlaps(p, boxR || {l:0,t:0,r:0,b:0}, 16)));
          return {
            ok, pinned,
            panel: p, gen: g, tools: t, dock: d, box: boxR,
            overlapTools: overlaps(p, t, gap),
            overlapDock: overlaps(p, d, gap),
            overlapBox: !!(boxR && overlaps(p, boxR, 16)),
            handleHit,
            genCovered: overlaps(g, t, 0),
            scale,
            moving: panel.getAttribute('data-move'),
            style: { left: panel.style.left, top: panel.style.top },
          };
        }""",
        gap,
    )


def assert_clear(page: Page, label: str) -> dict:
    data = clearance(page)
    print(label, data, flush=True)
    if not data.get("ok"):
        raise SystemExit(f"clearance failed for {label}: {data}")
    return data


def shoot_canvas(page: Page, vp: dict) -> Image.Image:
    # Crop to the canvas, but keep the zoom bar and dock (they sit on the canvas).
    el = page.locator(".tl-canvas")
    b = el.bounding_box()
    assert b
    vw, vh = vp["width"], vp["height"]
    x, y = max(0, b["x"]), max(0, b["y"])
    w, h = min(vw - x, b["width"]), min(vh - y, b["height"])
    raw = page.screenshot(clip={"x": x, "y": y, "width": w, "height": h})
    import io
    return Image.open(io.BytesIO(raw)).convert("RGB")


def main() -> None:
    if not (PR_ROOT / "dist/index.html").is_file():
        raise SystemExit(f"dist missing in {PR_ROOT}; run npm run build first (do not commit dist)")
    OUT.mkdir(parents=True, exist_ok=True)
    src = make_src()
    url = f"http://127.0.0.1:{PORT}/comfyart/"
    proc = None
    try:
        proc = boot(PR_ROOT, PORT)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            wide = {"width": 1440, "height": 900}
            page = new_page(browser, url, wide)
            open_project(page, src)
            # open_project already zooms to 50%
            open_expand(page)
            shots = {}
            for v in (1.0, 2.0, 3.0):
                # Settled position after release (pads applied, held cleared).
                set_scale_js(page, v)
                page.wait_for_timeout(250)
                assert_clear(page, f"{int(v)}x")
                im = shoot_canvas(page, wide)
                path = OUT / f"0{int(v)}-after-release-{int(v)}x.png"
                im.save(path, optimize=True)
                print("wrote", path, im.size, path.stat().st_size, flush=True)
                shots[v] = im
            page.close()

            narrow = {"width": 1280, "height": 800}
            npage = new_page(browser, url, narrow)
            open_project(npage, src)
            open_expand(npage)
            set_scale_js(npage, 3.0)
            npage.wait_for_timeout(250)
            assert_clear(npage, "3x-1280")
            nim = shoot_canvas(npage, narrow)
            npath = OUT / "04-after-release-3x-1280.png"
            nim.save(npath, optimize=True)
            print("wrote", npath, nim.size, npath.stat().st_size, flush=True)
            npage.close()
            browser.close()
    finally:
        stop(proc)
    print("done", OUT)


if __name__ == "__main__":
    main()
