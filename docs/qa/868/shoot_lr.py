#!/usr/bin/env python3
"""#868 $0 mocked L/R shots. Left = main 058e8447, right = this PR.

01: expand scale slider at 1× / 2× / 3× (three rows). Main recomputes panel
position as pads grow (the jump). PR holds left/top while the pointer is down.
02: model dropdown at Midjourney → (Krea 2 Turbo on the PR) → Ideogram, with
the Krea row hovered on the right. Main shows the same slice without Krea.

No network, no paid calls. Requires a built dist in both worktrees.
"""
from __future__ import annotations

import io
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Page, sync_playwright

HERE = Path(__file__).resolve().parent
PR_ROOT = HERE.parents[2]
MAIN_ROOT = Path(os.environ.get("MAIN_ROOT", "/tmp/wt887-main"))
OUT = HERE
PY = os.environ.get("GATE_PY", "/workspace/ca-venv/bin/python")
MAIN_SHA = "058e8447"
PR_SHA = "262deebd"
FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
MAIN_PORT, PR_PORT = 8871, 8872
VP = {"width": 1440, "height": 900}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REG
    try:
        return ImageFont.truetype(path, size=size, index=0)
    except TypeError:
        return ImageFont.truetype(path, size=size)


def make_src() -> Path:
    im = Image.new("RGB", (360, 480), (232, 222, 205))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((50, 60, 310, 420), radius=32, fill=(80, 130, 200))
    d.ellipse((120, 100, 240, 220), fill=(250, 236, 214))
    d.rectangle((0, 0, 359, 479), outline=(40, 40, 40), width=2)
    path = Path("/tmp/ca868-src.png")
    im.save(path)
    return path


def boot(root: Path, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env.pop("WAVESPEED_API_KEY", None)
    env.pop("KIE_API_KEY", None)
    env["GATE"] = "1"
    proc = subprocess.Popen(
        [PY, str(HERE / "boot_app.py"), "--root", str(root), "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        start_new_session=True,
    )
    lines = []
    t0 = time.time()
    while time.time() - t0 < 60:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line and proc.poll() is not None:
            break
        if line:
            lines.append(line.rstrip())
            if line.startswith("READY "):
                return proc
    dump = "\n".join(lines[-40:])
    raise SystemExit(f"boot failed for {root} :{port}\n{dump}")


def stop(proc: subprocess.Popen | None) -> None:
    if not proc or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)


def new_page(browser, url: str) -> Page:
    page = browser.new_page(viewport=VP, device_scale_factor=2)
    page.add_init_script(
        "localStorage.setItem('comfyart.lang','zh');"
        "localStorage.setItem('comfyart.theme','light');"
    )
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    # dismiss any first-run / key modal
    modal = page.locator(".ca-modal button")
    if modal.count():
        try:
            modal.nth(-2).click(timeout=1500)
            page.wait_for_timeout(200)
        except Exception:
            pass
    return page


def open_project(page: Page, src: Path) -> None:
    if page.locator(".tl-canvas").count() == 0:
        rail = page.locator("[data-testid=rail-new]")
        if rail.count():
            rail.click()
        else:
            page.mouse.click(28, 83)
        page.locator(".tl-canvas").wait_for(timeout=15000)
        page.wait_for_timeout(800)
        if page.locator(".ca-modal").count():
            try:
                page.locator(".ca-modal button").nth(-2).click(timeout=1500)
            except Exception:
                pass
    page.locator("input[type=file][accept*=image]").first.set_input_files(str(src))
    page.locator(".tl-image").first.wait_for(timeout=15000)
    page.wait_for_timeout(600)
    page.keyboard.press("Escape")
    page.locator(".tl-image").first.click()
    page.wait_for_timeout(300)
    zoom_to(page, 50)


def zoom_to(page: Page, pct: int) -> None:
    """Drop the camera so 3× pads still fit and the panel is not already clamped to EDGE."""
    btn = page.locator(".ca-zoom__btn")
    btn.wait_for(timeout=8000)
    if btn.inner_text().strip().rstrip("%") == str(pct):
        return
    btn.click()
    page.locator(".ca-menu__item", has_text=f"缩放至 {pct}%").click()
    page.wait_for_timeout(450)


def open_expand(page: Page) -> None:
    # pinned toolbar or the 更多 menu
    btn = page.get_by_role("button", name="扩展")
    if btn.count():
        btn.first.click()
    else:
        more = page.get_by_role("button", name="更多")
        if more.count():
            more.first.click()
            page.wait_for_timeout(200)
            page.get_by_role("menuitem", name="扩展").click() if page.get_by_role("menuitem", name="扩展").count() else page.locator(".ca-menu__item", has_text="扩展").click()
        else:
            # last resort: visible toolbar text
            page.locator(".ca-toolbar--image button", has_text="扩展").click()
    page.locator(".ca-panel").wait_for(timeout=8000)
    page.wait_for_timeout(200)


def crop_expand(page: Page) -> Image.Image:
    """Same canvas frame for every scale so the panel jump/hold is comparable."""
    el = page.locator(".tl-canvas")
    b = el.bounding_box()
    assert b
    vw, vh = VP["width"], VP["height"]
    x, y = max(0, b["x"]), max(0, b["y"])
    w, h = min(vw - x, b["width"]), min(vh - y, b["height"])
    raw = page.screenshot(clip={"x": x, "y": y, "width": w, "height": h})
    return Image.open(io.BytesIO(raw)).convert("RGB")


def set_scale_js(page: Page, value: float) -> None:
    page.evaluate(
        """(v) => {
          const input = document.querySelector('.ca-panel input[type=range]');
          if (!input) throw new Error('no scale slider');
          const proto = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
          proto.set.call(input, String(v));
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        value,
    )
    page.wait_for_timeout(150)


def panel_geom(page: Page) -> dict:
    return page.evaluate(
        """() => {
          const p = document.querySelector('.ca-panel');
          const i = document.querySelector('.ca-panel input[type=range]');
          if (!p || !i) return {};
          const r = p.getBoundingClientRect();
          return { left: p.style.left, top: p.style.top, x: Math.round(r.x), y: Math.round(r.y), value: i.value };
        }"""
    )


def hold_slider(page: Page) -> None:
    """Fire pointerdown on the range input so ModePanel sets `held` (PR) via setPointerCapture."""
    slider = page.locator(".ca-panel input[type=range]").first
    slider.wait_for()
    box = slider.bounding_box()
    assert box
    page.mouse.move(box["x"] + 6, box["y"] + box["height"] / 2)
    slider.dispatch_event(
        "pointerdown",
        {"button": 0, "buttons": 1, "pointerId": 1, "pointerType": "mouse", "isPrimary": True, "bubbles": True, "composed": True},
    )
    page.wait_for_timeout(80)


def drag_scale(page: Page, values: list[float]) -> dict[float, Image.Image]:
    """Keep the slider captured and step through values, shooting mid-hold."""
    hold_slider(page)
    shots: dict[float, Image.Image] = {}
    for v in values:
        set_scale_js(page, v)
        print("  hold", v, panel_geom(page), flush=True)
        shots[v] = crop_expand(page)
    return shots


def shoot_slider(page: Page, *, hold: bool) -> dict[float, Image.Image]:
    open_expand(page)
    values = [1.0, 2.0, 3.0]
    if hold:
        shots = drag_scale(page, values)
        page.mouse.up()
        return shots
    # main: show the jump as three settled positions
    out = {}
    for v in values:
        set_scale_js(page, v)
        print("  settled", v, panel_geom(page), flush=True)
        out[v] = crop_expand(page)
    return out


def ensure_image_mode(page: Page) -> None:
    """Home defaults to Agent; the model dropdown lives on 图像 / 视频 (DirectPills)."""
    page.locator(".ca-landing, .ca-composer, .tl-canvas").first.wait_for(timeout=15000)
    if page.locator("[data-pill=model]").count():
        return
    mode_btn = page.locator(".ca-landing__mode")
    if mode_btn.count():
        mode_btn.click()
        page.wait_for_timeout(200)
        item = page.locator(".ca-menu__item", has_text="图像")
        if item.count():
            item.first.click()
            page.wait_for_timeout(300)
    if page.locator("[data-pill=model]").count() == 0:
        # canvas project: the generate composer is at the bottom
        gen = page.get_by_role("button", name="图像生成")
        if gen.count():
            pass
        page.locator(".ca-composer, .ca-landing__foot").first.wait_for(timeout=8000)


def open_model_menu(page: Page) -> None:
    ensure_image_mode(page)
    pill = page.locator("[data-pill=model]").first
    pill.wait_for(timeout=10000)
    pill.click()
    menu = page.locator("[data-testid=model-menu]")
    menu.wait_for(timeout=8000)
    # Auto off so rows are not greyed
    sw = menu.locator("button.ca-switch")
    if sw.count() and sw.get_attribute("data-on"):
        sw.click()
        page.wait_for_timeout(200)
    menu.locator(".ca-modelprefs__row", has_text="Midjourney").wait_for(timeout=10000)


def shoot_dropdown(page: Page, *, want_krea: bool) -> Image.Image:
    open_model_menu(page)
    menu = page.locator("[data-testid=model-menu]")
    mid = menu.locator(".ca-modelprefs__row", has_text="Midjourney")
    mid.scroll_into_view_if_needed()
    page.wait_for_timeout(150)
    krea = menu.locator(".ca-modelprefs__row", has_text="Krea 2 Turbo")
    if want_krea:
        if krea.count() == 0:
            raise SystemExit("PR dropdown is missing Krea 2 Turbo")
        krea.scroll_into_view_if_needed()
        krea.hover()
        page.wait_for_timeout(250)
    else:
        if krea.count():
            raise SystemExit("main dropdown unexpectedly lists Krea 2 Turbo")
        # hover Midjourney so :hover styling matches the right side's treatment
        mid.hover()
        page.wait_for_timeout(250)
    box = menu.bounding_box()
    assert box
    pad = 24
    vw, vh = VP["width"], VP["height"]
    x, y = max(0, box["x"] - pad), max(0, box["y"] - pad)
    w = min(vw - x, box["width"] + pad * 2)
    h = min(vh - y, box["height"] + pad * 2)
    # If the menu is very tall, clip to a window around Midjourney (± a few rows)
    mid_box = mid.bounding_box()
    if mid_box and box["height"] > 520:
        y = max(0, mid_box["y"] - 80)
        h = min(vh - y, 560)
        x = max(0, box["x"] - pad)
        w = min(vw - x, box["width"] + pad * 2)
    raw = page.screenshot(clip={"x": x, "y": y, "width": w, "height": h})
    return Image.open(io.BytesIO(raw)).convert("RGB")


def same_size(images: list[Image.Image], fill="#e8e9ed") -> list[Image.Image]:
    w = max(im.width for im in images)
    h = max(im.height for im in images)
    out = []
    for im in images:
        if im.size == (w, h):
            out.append(im)
            continue
        canvas = Image.new("RGB", (w, h), fill)
        canvas.paste(im, (0, 0))
        out.append(canvas)
    return out


def label_bar(width: int, title: str, sub: str) -> Image.Image:
    h = 56
    im = Image.new("RGB", (width, h), "#f3f4f6")
    d = ImageDraw.Draw(im)
    d.text((16, 8), title, fill="#111111", font=font(20, True))
    d.text((16, 32), sub, fill="#4b5563", font=font(14))
    return im


def row_label(width: int, text: str) -> Image.Image:
    h = 36
    im = Image.new("RGB", (width, h), "#111111")
    d = ImageDraw.Draw(im)
    d.text((16, 8), text, fill="#ffffff", font=font(16, True))
    return im


def compose_slider(left: dict[float, Image.Image], right: dict[float, Image.Image], path: Path) -> None:
    labels = {1.0: "缩放 1×（起点）", 2.0: "缩放 2×（中间）", 3.0: "缩放 3×（终点）"}
    pairs = [same_size([left[v], right[v]]) for v in (1.0, 2.0, 3.0)]
    tw = max(a.width for a, _ in pairs)
    # pad pairs to a shared width so columns line up; keep each row's own height
    aligned = []
    for a, b in pairs:
        if a.width != tw:
            a, b = same_size([a, b])  # already same as each other
            ca = Image.new("RGB", (tw, a.height), "#e8e9ed")
            cb = Image.new("RGB", (tw, b.height), "#e8e9ed")
            ca.paste(a, (0, 0)); cb.paste(b, (0, 0))
            a, b = ca, cb
        aligned.append((a, b))
    gap, cap, rh, top = 16, 56, 36, 48
    w = tw * 2 + gap
    h = top + cap + sum(rh + a.height for a, _ in aligned)
    out = Image.new("RGB", (w, h), "#e8e9ed")
    header = Image.new("RGB", (w, top), "#111111")
    ImageDraw.Draw(header).text(
        (16, 12),
        "扩图缩放滑块：拖到两端和中间。左 = 面板随 pads 重算（跳动），右 = 拖动中钉住位置",
        fill="#ffffff",
        font=font(16, True),
    )
    out.paste(header, (0, 0))
    out.paste(label_bar(tw, "左 · main", MAIN_SHA), (0, top))
    out.paste(label_bar(tw, "右 · #887", PR_SHA), (tw + gap, top))
    y = top + cap
    for (text, (a, b)) in zip((labels[v] for v in (1.0, 2.0, 3.0)), aligned):
        out.paste(row_label(w, text), (0, y))
        y += rh
        out.paste(a, (0, y))
        out.paste(b, (tw + gap, y))
        y += a.height
    out.save(path, optimize=True)
    print("wrote", path, out.size, path.stat().st_size)


def compose_lr(left: Image.Image, right: Image.Image, title: str, path: Path) -> None:
    left, right = same_size([left, right])
    gap, cap, top = 16, 56, 48
    w = left.width + gap + right.width
    h = top + cap + left.height
    out = Image.new("RGB", (w, h), "#e8e9ed")
    header = Image.new("RGB", (w, top), "#111111")
    ImageDraw.Draw(header).text((16, 12), title, fill="#ffffff", font=font(16, True))
    out.paste(header, (0, 0))
    out.paste(label_bar(left.width, "左 · main", MAIN_SHA), (0, top))
    out.paste(label_bar(right.width, "右 · #887", PR_SHA), (left.width + gap, top))
    out.paste(left, (0, top + cap))
    out.paste(right, (left.width + gap, top + cap))
    out.save(path, optimize=True)
    print("wrote", path, out.size, path.stat().st_size)


def main() -> None:
    if not (MAIN_ROOT / "dist/index.html").is_file():
        raise SystemExit(f"main dist missing in {MAIN_ROOT}")
    if not (PR_ROOT / "dist/index.html").is_file():
        raise SystemExit(f"PR dist missing in {PR_ROOT}")
    OUT.mkdir(parents=True, exist_ok=True)
    src = make_src()
    main_p = pr_p = None
    try:
        main_p = boot(MAIN_ROOT, MAIN_PORT)
        pr_p = boot(PR_ROOT, PR_PORT)
        main_url = f"http://127.0.0.1:{MAIN_PORT}/comfyart/"
        pr_url = f"http://127.0.0.1:{PR_PORT}/comfyart/"
        with sync_playwright() as p:
            browser = p.chromium.launch()
            # --- slider ---
            lm = new_page(browser, main_url)
            open_project(lm, src)
            left_slider = shoot_slider(lm, hold=False)
            for v, im in left_slider.items():
                im.save(OUT / f"01-slider-{int(v)}x-before-main.png")
            lm.close()

            rp = new_page(browser, pr_url)
            open_project(rp, src)
            right_slider = shoot_slider(rp, hold=True)
            for v, im in right_slider.items():
                im.save(OUT / f"01-slider-{int(v)}x-after-pr.png")
            rp.close()
            compose_slider(left_slider, right_slider, OUT / "01-slider-lr.png")

            # --- dropdown: home, switch to 图像, open model prefs ---
            ld = new_page(browser, main_url)
            ld.locator(".ca-landing").wait_for(timeout=15000)
            left_dd = shoot_dropdown(ld, want_krea=False)
            left_dd.save(OUT / "02-krea-dropdown-before-main.png")
            ld.close()

            rd = new_page(browser, pr_url)
            rd.locator(".ca-landing").wait_for(timeout=15000)
            right_dd = shoot_dropdown(rd, want_krea=True)
            right_dd.save(OUT / "02-krea-dropdown-after-pr.png")
            rd.close()
            compose_lr(
                left_dd,
                right_dd,
                "模型下拉：Krea 2 Turbo 只出现在右侧，位于 Midjourney 与 Ideogram 之间",
                OUT / "02-krea-dropdown-lr.png",
            )
            browser.close()
    finally:
        stop(pr_p)
        stop(main_p)
    print("done", OUT)


if __name__ == "__main__":
    main()
