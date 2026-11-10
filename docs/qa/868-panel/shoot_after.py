#!/usr/bin/env python3
"""#868 panel avoidance: $0 local shots after the expand scale slider is released.

1x / 2x / 3x at 1440x900, plus 3x at a 1280px-wide viewport. Localhost only.
Requires a built dist in this worktree (do not commit it).

By default this retakes the 3x / 3x@1280 cropped shots (handle + panel edge)
and the uncropped 1280 full-viewport frame (05).
Pass --all to also reshoot the full-canvas 1x / 2x frames.
Pass --full-only to take only the uncropped 1280 full-viewport shot.
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, sync_playwright

HERE = Path(__file__).resolve().parent
PR_ROOT = HERE.parents[2]
SYS868 = HERE.parent / "868"
sys.path.insert(0, str(SYS868))
from shoot_lr import (  # noqa: E402
    boot,
    make_src,
    open_expand,
    open_project,
    set_scale_js,
    stop,
)

OUT = HERE
PORT = 8868
CLEAR = 12


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


def geom(page: Page, gap: int = CLEAR) -> dict:
    return page.evaluate(
        """(gap) => {
          const panel = document.querySelector('.ca-panel');
          const gen = document.querySelector('.ca-panel__primary');
          const tools = document.querySelector('.ca-tools');
          const dock = document.querySelector('.ca-dock');
          const box = document.querySelector('.ca-expand');
          const handle = document.querySelector('.ca-expand__handle[data-side=r]');
          if (!panel || !gen || !tools || !dock) return { ok: false, reason: 'missing el' };
          const r = (el) => {
            const b = el.getBoundingClientRect();
            return { l: b.left, t: b.top, r: b.right, b: b.bottom, w: b.width, h: b.height };
          };
          const overlaps = (a, b, g) =>
            a.l < b.r + g && a.r > b.l - g && a.t < b.b + g && a.b > b.t - g;
          const p = r(panel), g = r(gen), t = r(tools), d = r(dock);
          const boxR = box ? r(box) : null;
          const handleR = handle ? r(handle) : null;
          const handleHit = !!(handleR && overlaps(p, handleR, gap));
          const narrow = panel.hasAttribute('data-narrow') || Math.abs(p.w - 220) < 1;
          const besideRight = !!(boxR && Math.abs(p.l - (boxR.r + 16)) <= 1.5);
          const besideLeft = !!(boxR && Math.abs(p.r - (boxR.l - 16)) <= 1.5);
          const docked = narrow && !besideRight && !besideLeft;
          const side = besideRight ? 'narrow-right' : besideLeft ? 'narrow-left' : (docked ? 'dock' : 'other');
          const ok = !overlaps(p, t, gap) && !overlaps(p, d, gap) && !overlaps(g, t, 0)
            && (docked || (!handleHit && !(boxR && overlaps(p, boxR, 16))));
          const row = panel.querySelector('.ca-panel__row');
          const hint = panel.querySelector('.ca-chat__hint');
          const foot = panel.querySelector('.ca-panel__foot');
          const btns = foot ? [...foot.querySelectorAll('button')] : [];
          const oneLine = (el) => !!el && el.scrollWidth <= el.clientWidth + 1;
          return {
            ok, narrow, docked, side, handleHit,
            panel: p, gen: g, tools: t, dock: d, box: boxR, handle: handleR,
            overlapTools: overlaps(p, t, gap),
            overlapDock: overlaps(p, d, gap),
            overlapBox: !!(boxR && overlaps(p, boxR, 16)),
            genCovered: overlaps(g, t, 0),
            scale: document.querySelector('.ca-panel input[type=range]')?.value,
            moving: panel.getAttribute('data-move'),
            style: { left: panel.style.left, top: panel.style.top },
            layout: narrow ? {
              rowOneLine: !!(row && oneLine(row) && row.getBoundingClientRect().height <= 36),
              hintOneLine: !hint || (oneLine(hint) && hint.getBoundingClientRect().height <= 28),
              footOneRow: btns.length === 2 && Math.abs(btns[0].getBoundingClientRect().top - btns[1].getBoundingClientRect().top) <= 2,
              btnNoEllipsis: btns.every((b) => oneLine(b) && getComputedStyle(b).textOverflow !== 'ellipsis'),
            } : null,
          };
        }""",
        gap,
    )


def assert_clear(page: Page, label: str) -> dict:
    data = geom(page)
    print(label, data, flush=True)
    if not data.get("ok"):
        raise SystemExit(f"clearance failed for {label}: {data}")
    if data.get("narrow") and data.get("layout"):
        lay = data["layout"]
        missing = [k for k, v in lay.items() if not v]
        if missing:
            raise SystemExit(f"220px layout failed for {label}: {missing} {lay}")
    return data



def axis_gaps(a: dict, b: dict) -> tuple[float, float]:
    """Signed CSS-px gaps. Positive = separated; negative = overlap depth."""
    if a["b"] <= b["t"]:
        v = b["t"] - a["b"]
    elif b["b"] <= a["t"]:
        v = a["t"] - b["b"]
    else:
        v = -min(a["b"] - b["t"], b["b"] - a["t"])
    if a["r"] <= b["l"]:
        h = b["l"] - a["r"]
    elif b["r"] <= a["l"]:
        h = a["l"] - b["r"]
    else:
        h = -min(a["r"] - b["l"], b["r"] - a["l"])
    return h, v


def measure_gaps(data: dict, vp: dict) -> dict:
    p = data["panel"]
    h_zoom, v_zoom = axis_gaps(p, data["tools"])
    h_dock, v_dock = axis_gaps(p, data["dock"])
    vw, vh = vp["width"], vp["height"]
    out = {
        "panel_to_zoom_bar_h": round(h_zoom, 2),
        "panel_to_zoom_bar_v": round(v_zoom, 2),
        "panel_to_toolbar_h": round(h_dock, 2),
        "panel_to_toolbar_v": round(v_dock, 2),
        "viewport": {
            "left": round(p["l"], 2),
            "top": round(p["t"], 2),
            "right": round(vw - p["r"], 2),
            "bottom": round(vh - p["b"], 2),
        },
        "panel": {k: round(p[k], 2) for k in ("l", "t", "r", "b", "w", "h")},
        "tools": {k: round(data["tools"][k], 2) for k in ("l", "t", "r", "b", "w", "h")},
        "dock": {k: round(data["dock"][k], 2) for k in ("l", "t", "r", "b", "w", "h")},
    }
    print("GAPS", out, flush=True)
    return out


def shoot_full_viewport(page: Page) -> Image.Image:
    raw = page.screenshot(type="png")
    return Image.open(io.BytesIO(raw)).convert("RGB")


def shoot_canvas(page: Page, vp: dict) -> Image.Image:
    el = page.locator(".tl-canvas")
    b = el.bounding_box()
    assert b
    vw, vh = vp["width"], vp["height"]
    x, y = max(0, b["x"]), max(0, b["y"])
    w, h = min(vw - x, b["width"]), min(vh - y, b["height"])
    raw = page.screenshot(clip={"x": x, "y": y, "width": w, "height": h})
    return Image.open(io.BytesIO(raw)).convert("RGB")


def shoot_handle_panel(page: Page, vp: dict, *, docked: bool = False) -> Image.Image:
    """Crop/zoom on the right drag handle and the adjacent panel edge."""
    info = page.evaluate(
        """() => {
          const panel = document.querySelector('.ca-panel');
          const handle = document.querySelector('.ca-expand__handle[data-side=r]');
          const box = document.querySelector('.ca-expand');
          if (!panel || !handle) return null;
          const p = panel.getBoundingClientRect();
          const h = handle.getBoundingClientRect();
          const b = box ? box.getBoundingClientRect() : h;
          return {
            p: { l: p.left, t: p.top, r: p.right, b: p.bottom },
            h: { l: h.left, t: h.top, r: h.right, b: h.bottom, cx: h.left + h.width / 2, cy: h.top + h.height / 2 },
            box: { l: b.left, t: b.top, r: b.right, b: b.bottom },
          };
        }"""
    )
    assert info, "missing panel or right handle"
    vw, vh = vp["width"], vp["height"]
    if docked:
        # Show the panel's left edge and the box edge where it exits below the panel,
        # so the covered handle location is in context.
        x = max(0, min(info["p"]["l"], info["h"]["l"]) - 80)
        y = max(0, info["h"]["t"] - 120)
        x1 = min(vw, max(info["p"]["l"] + 280, info["h"]["r"] + 80))
        y1 = min(vh, max(info["p"]["b"] + 80, info["h"]["b"] + 80))
        w, h = x1 - x, y1 - y
    else:
        nearer = info["p"]["l"] if abs(info["p"]["l"] - info["h"]["cx"]) <= abs(info["p"]["r"] - info["h"]["cx"]) else info["p"]["r"]
        cx = (info["h"]["cx"] + nearer) / 2
        cy = info["h"]["cy"]
        w, h = 480, 400
        x = min(max(0, cx - w / 2), max(0, vw - w))
        y = min(max(0, cy - h / 2), max(0, vh - h))
        w, h = min(w, vw - x), min(h, vh - y)
    raw = page.screenshot(clip={"x": x, "y": y, "width": w, "height": h})
    return Image.open(io.BytesIO(raw)).convert("RGB")


def setup_expand(page: Page, src, scale: float) -> None:
    open_project(page, src)
    open_expand(page)
    set_scale_js(page, scale)
    page.wait_for_timeout(300)


def main() -> None:
    only_3x = "--all" not in sys.argv
    full_only = "--full-only" in sys.argv
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
            if not only_3x and not full_only:
                page = new_page(browser, url, wide)
                open_project(page, src)
                open_expand(page)
                for v in (1.0, 2.0):
                    set_scale_js(page, v)
                    page.wait_for_timeout(250)
                    assert_clear(page, f"{int(v)}x")
                    im = shoot_canvas(page, wide)
                    path = OUT / f"0{int(v)}-after-release-{int(v)}x.png"
                    im.save(path, optimize=True)
                    print("wrote", path, im.size, path.stat().st_size, flush=True)
                page.close()

            if not full_only:
                page = new_page(browser, url, wide)
                setup_expand(page, src, 3.0)
                d3 = assert_clear(page, "3x")
                im = shoot_handle_panel(page, wide, docked=bool(d3.get('docked')))
                path = OUT / "03-after-release-3x.png"
                im.save(path, optimize=True)
                print("wrote", path, im.size, path.stat().st_size, "side", d3.get("side"), "handleHit", d3.get("handleHit"), flush=True)
                page.close()

            narrow = {"width": 1280, "height": 800}
            npage = new_page(browser, url, narrow)
            setup_expand(npage, src, 3.0)
            d4 = assert_clear(npage, "3x-1280")
            measure_gaps(d4, narrow)
            if not full_only:
                nim = shoot_handle_panel(npage, narrow, docked=bool(d4.get('docked')))
                npath = OUT / "04-after-release-3x-1280.png"
                nim.save(npath, optimize=True)
                print("wrote", npath, nim.size, npath.stat().st_size, "side", d4.get("side"), "handleHit", d4.get("handleHit"), flush=True)
            full = shoot_full_viewport(npage)
            fpath = OUT / "05-after-release-3x-1280-full.png"
            full.save(fpath, optimize=True)
            print(
                "wrote", fpath, full.size, fpath.stat().st_size,
                "side", d4.get("side"), "handleHit", d4.get("handleHit"),
                "full-viewport uncropped", flush=True,
            )
            npage.close()
            browser.close()
    finally:
        stop(proc)
    print("done", OUT)


if __name__ == "__main__":
    main()
