"""$0 mocked L/R of the keep-face Auto edit card header, plus hover shots for
keep_identity (person) and keep_product. No network, no paid calls.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests/js/pill825"))
import shoot as pill  # noqa: E402

OUT = ROOT / "docs/qa/825-keepface-route"
FONT = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 22)
FONT_B = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 22)
VP = {"width": 440, "height": 520}
HOVER_VP = {"width": 480, "height": 560}


def _shot(browser, base, name, case, expected, *, hover=False, vp=None, expected_tip=None):
    page = browser.new_page(viewport=vp or VP, device_scale_factor=2)
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
    page.goto(f"{base}/index.html?case={case}&lang=zh&theme=light")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(250)
    if hover:
        # Give the wrapped reason tip room above the Auto label.
        page.evaluate(
            """() => {
              const root = document.querySelector('.ca-root');
              if (root) root.style.paddingTop = '40px';
              // Hide the harness case caption so it doesn't peek out behind the tip.
              const cap = root && root.firstElementChild;
              if (cap && cap.style && cap.textContent.includes('·')) cap.style.visibility = 'hidden';
            }"""
        )
        page.wait_for_timeout(50)
    label = page.locator("#gen [data-testid=auto-model-label]")
    text = label.inner_text().strip()
    assert text == expected, f"{case}: got {text!r}, expected {expected!r}"
    tip_text = None
    if hover:
        label.hover()
        page.wait_for_timeout(200)
        tip = page.locator(".ca-tip")
        assert tip.count() == 1, f"{case}: expected 1 .ca-tip, got {tip.count()}"
        tip_text = tip.inner_text().strip()
        assert expected_tip, f"{case}: hover shot needs expected_tip"
        assert tip_text == expected_tip, f"{case}: tip {tip_text!r}"
        geom = tip.evaluate(
            "e => ({ sw: e.scrollWidth, cw: e.clientWidth, sh: e.scrollHeight, ch: e.clientHeight })"
        )
        assert geom["sw"] <= geom["cw"] + 1, f"{case}: tip truncates horizontally {geom}"
        box = tip.bounding_box()
        assert box and box["y"] >= 0, f"{case}: tip clipped at top {box}"
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  {name}: {text!r} tip={tip_text!r} {path.stat().st_size} bytes {Image.open(path).size}")
    page.close()
    return path


def _lr(left_path, right_path, out_name, left_caption, right_caption):
    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")
    assert left.size == right.size, (left.size, right.size)
    w, h = left.size
    gap, bar = 8, 44
    canvas = Image.new("RGB", (w * 2 + gap, h + bar), (255, 255, 255))
    canvas.paste(left, (0, bar))
    canvas.paste(right, (w + gap, bar))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((w, 0, w + gap - 1, h + bar), fill=(220, 220, 220))
    draw.rectangle((0, 0, w * 2 + gap, bar - 1), fill=(245, 245, 245))
    draw.line((0, bar - 1, w * 2 + gap, bar - 1), fill=(220, 220, 220))
    captions = (
        (w // 2, left_caption),
        (w + gap + w // 2, right_caption),
    )
    for cx, text in captions:
        bbox = draw.textbbox((0, 0), text, font=FONT_B)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, 10), text, font=FONT_B, fill=(30, 30, 30))
    out = OUT / out_name
    canvas.save(out)
    print("lr", out, canvas.size, out.stat().st_size)
    return out


def main() -> None:
    from playwright.sync_api import sync_playwright
    import shutil

    OUT.mkdir(parents=True, exist_ok=True)
    d = ROOT / "tmp" / "pill825-keepface-bundle"
    if d.exists():
        shutil.rmtree(d)
    print("bundling…")
    pill.bundle(d)
    srv, base = pill.serve(d)
    print("serving", base)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        before = _shot(browser, base, "01-header-before-main", "keepface_main", "Auto · Nano Banana 2.1")
        after = _shot(browser, base, "01-header-after-pr", "keepface", "Auto · Seedream 5.0 Pro")
        ident = _shot(
            browser, base, "02-hover-keep-identity", "keepface",
            "Auto · Seedream 5.0 Pro", hover=True, vp=HOVER_VP,
            expected_tip="自动选择：保留同一人物",
        )
        product = _shot(
            browser, base, "03-hover-keep-product", "keepproduct",
            "Auto · Nano Banana 2.1", hover=True, vp=HOVER_VP,
            expected_tip="自动选择：保留商品不变",
        )
        browser.close()
    srv.shutdown()
    _lr(
        before, after, "01-header-lr.png",
        "前 · 保留同一个人改图 (main)",
        "后 · 保留同一个人改图 (本 PR)",
    )
    print("hover identity", ident)
    print("hover product", product)
    print("done")


if __name__ == "__main__":
    main()
