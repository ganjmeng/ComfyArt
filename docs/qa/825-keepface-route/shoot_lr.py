"""$0 mocked L/R of the keep-face Auto edit card header. No network, no paid calls."""
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
    paths = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, case, expected in (
            ("01-header-before-main", "keepface_main", "Auto · Nano Banana 2.1"),
            ("01-header-after-pr", "keepface", "Auto · Seedream 5.0 Pro"),
        ):
            page = browser.new_page(viewport=VP, device_scale_factor=2)
            page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
            page.goto(f"{base}/index.html?case={case}&lang=zh&theme=light")
            page.wait_for_function("window.__ready")
            page.wait_for_timeout(250)
            label = page.locator("#gen [data-testid=auto-model-label]")
            text = label.inner_text().strip()
            assert text == expected, f"{case}: got {text!r}, expected {expected!r}"
            path = OUT / f"{name}.png"
            page.screenshot(path=str(path), full_page=True)
            print(f"  {name}: {text!r} {path.stat().st_size} bytes {Image.open(path).size}")
            paths[name] = path
            page.close()
        browser.close()
    srv.shutdown()

    left = Image.open(paths["01-header-before-main"]).convert("RGB")
    right = Image.open(paths["01-header-after-pr"]).convert("RGB")
    assert left.size == right.size, (left.size, right.size)
    w, h = left.size
    gap, bar = 8, 44
    canvas = Image.new("RGB", (w * 2 + gap, h + bar), (255, 255, 255))
    canvas.paste(left, (0, bar))
    canvas.paste(right, (w + gap, bar))
    draw = ImageDraw.Draw(canvas)
    # divider
    draw.rectangle((w, 0, w + gap - 1, h + bar), fill=(220, 220, 220))
    # top bar
    draw.rectangle((0, 0, w * 2 + gap, bar - 1), fill=(245, 245, 245))
    draw.line((0, bar - 1, w * 2 + gap, bar - 1), fill=(220, 220, 220))
    captions = (
        (w // 2, "前 · 保留同一个人改图 (main)"),
        (w + gap + w // 2, "后 · 保留同一个人改图 (本 PR)"),
    )
    for cx, text in captions:
        bbox = draw.textbbox((0, 0), text, font=FONT_B)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, 10), text, font=FONT_B, fill=(30, 30, 30))
    out = OUT / "01-header-lr.png"
    canvas.save(out)
    print("lr", out, canvas.size, out.stat().st_size)
    print("done")


if __name__ == "__main__":
    main()
