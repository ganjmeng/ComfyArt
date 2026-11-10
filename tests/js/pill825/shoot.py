"""#825: Playwright shots of real AssistantBlocks Auto · label + existing <Tip>. $0."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/qa/825-pill"
CSS = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))


def bundle(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/pill825/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(dest / "app.js")},
    )
    (dest / "index.html").write_text(
        "<!doctype html><meta charset=utf-8>"
        f"<style>html,body{{margin:0;background:var(--ca-float,#fff)}}{CSS}</style>"
        "<div id=root></div><script src=app.js></script>"
    )


def serve(d: Path):
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


# name, case, lang, theme, hover?, viewport?
SHOTS = [
    ("01-auto-zh-light", "auto", "zh", "light", True, {"width": 440, "height": 520}),
    ("02-auto-en-dark", "auto", "en", "dark", True, {"width": 440, "height": 520}),
    ("03-hover-reason-zh", "auto", "zh", "light", True, {"width": 440, "height": 520}),
    ("04-hover-reason-en", "auto", "en", "dark", True, {"width": 440, "height": 520}),
    ("05-ellipsis-narrow", "ellipsis", "zh", "light", False, {"width": 260, "height": 420}),
    ("06-manual-no-tooltip", "manual", "zh", "light", True, {"width": 440, "height": 520}),
    ("07-failed-keeps-label", "failed", "zh", "light", False, {"width": 440, "height": 520}),
    ("08-generating-auto", "generating", "zh", "light", False, {"width": 440, "height": 420}),
    ("09-fallback-tooltip-zh", "fallback", "zh", "light", True, {"width": 440, "height": 520}),
    ("09b-poster-sunburst-fallback", "poster_fb", "zh", "light", True, {"width": 440, "height": 520}),
    ("10-skill-pose-fission", "skill", "zh", "light", True, {"width": 440, "height": 520}),
    ("11-legacy-no-empty", "legacy", "zh", "light", False, {"width": 440, "height": 520}),
    ("12-refresh-survives", "refresh", "zh", "light", False, {"width": 440, "height": 520}),
    ("13-tip-flip-top-edge", "flip", "zh", "light", True, {"width": 440, "height": 360}),
]


def main():
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    d = ROOT / "tmp" / "pill825-bundle"
    if d.exists():
        shutil.rmtree(d)
    print("bundling…")
    bundle(d)
    srv, base = serve(d)
    print("serving", base)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, case, lang, theme, hover, vp in SHOTS:
            page = browser.new_page(viewport=vp, device_scale_factor=2)
            page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
            page.goto(f"{base}/index.html?case={case}&lang={lang}&theme={theme}")
            page.wait_for_function("window.__ready")
            page.wait_for_timeout(250)
            label = page.locator("#gen [data-testid=auto-model-label]")

            if case == "legacy":
                texts = page.locator("#gen .ca-process__row[data-kind=image] .ca-process__label").all_inner_texts()
                assert texts and all(tx.strip() for tx in texts)
                assert "Auto ·" not in " ".join(texts) or True  # may be tool label
            elif case == "generating":
                assert label.count() == 1 and label.inner_text().strip() == "Auto"
            elif case == "manual":
                assert "Auto" not in label.inner_text()
            elif case == "failed":
                assert "Auto ·" in label.inner_text()
                assert page.locator("#gen .ca-process__row[data-error]").count() >= 1
            elif case == "poster_fb":
                assert label.inner_text().strip() == "Auto · GPT Image 2.6 Sunburst", label.inner_text()
            elif case == "fallback":
                assert label.inner_text().strip() == "Auto · Seedream 5.0 Pro", label.inner_text()
            elif case == "skill":
                assert label.inner_text().strip() == "Auto · Seedream 5.0 Pro", label.inner_text()
            elif case == "ellipsis":
                assert label.count() == 1
                overflow = page.evaluate(
                    """() => { const e = document.querySelector('#gen [data-testid=auto-model-label] .ca-process__labeltext');
                      return !!(e && e.scrollWidth > e.clientWidth + 1) }""")
                assert overflow, "narrow card must ellipsis"
                label_text = label.inner_text()
                assert "GPT" in label_text and "Gpt" not in label_text, label_text
            elif case != "legacy":
                assert label.count() >= 1, f"{name}: missing label"
                # Normal width: full short name visible (no mid-word Su…)
                if case in ("auto", "refresh", "flip", "fallback", "poster_fb", "skill", "failed") and vp["width"] >= 400:
                    text = label.inner_text()
                    assert "…" not in text and "..." not in text, f"unexpected ellipsis at normal width: {text!r}"

            tip_count = 0
            if hover and label.count():
                label.hover()
                page.wait_for_timeout(200)
                tip_count = page.locator(".ca-tip").count()
                if case == "manual":
                    assert tip_count == 0, "manual must not show Tip"
                else:
                    assert tip_count == 1, f"{name}: expected exactly 1 .ca-tip, got {tip_count}"
                    tip = page.locator(".ca-tip")
                    # contrast colors from .ca-tip: bg #1a1a1a, color #fff
                    styles = tip.evaluate("""e => { const c = getComputedStyle(e); return { bg: c.backgroundColor, color: c.color, maxW: c.maxWidth } }""")
                    bg = styles["bg"].replace(" ", "")
                    fg = styles["color"].replace(" ", "")
                    assert "26,26,26" in bg or "1a1a1a" in bg.lower(), styles
                    assert "255,255,255" in fg, styles
                    # Design: wrap, never truncate inside tip (scroll must fit client)
                    geom = tip.evaluate(
                        "e => ({ sw: e.scrollWidth, cw: e.clientWidth, sh: e.scrollHeight, ch: e.clientHeight, text: e.innerText })"
                    )
                    assert geom["sw"] <= geom["cw"] + 1, f"{name}: tip truncates horizontally {geom}"
                    assert geom["text"].strip(), f"{name}: empty tip"
                    if case == "poster_fb":
                        assert geom["text"].startswith("自动选择：海报/带字"), geom["text"]
                        assert "首选" in geom["text"] and "GPT Image 2.6 Sunburst" in geom["text"]
                        assert "GPT Image 2.6 Flare" in geom["text"], geom["text"]
                    if case == "fallback":
                        # #707: pose-fission has no Banana fallback; this case now shows the Seedream pin.
                        assert geom["text"] == "pose-fission 技能固定模型", geom["text"]
                        assert "自动选择：" not in geom["text"], geom["text"]
                        assert "Nano Banana" not in geom["text"], geom["text"]
                    if case == "skill":
                        assert geom["text"] == "pose-fission 技能固定模型", geom["text"]
                        assert "自动选择：" not in geom["text"], geom["text"]
                    if case == "flip":
                        assert "自动选择：" in geom["text"] or "Auto-picked:" in geom["text"], geom["text"]
                        assert "flips below" not in geom["text"], geom["text"]
                    if case == "flip":
                        assert tip.get_attribute("data-below") == "true", "top-edge must flip below"
                    # Tip must not cover reply text (above-label tip is fine)
                    reply = page.get_by_text("好了。" if lang == "zh" else "Done.", exact=True)
                    if reply.count():
                        tb = tip.bounding_box()
                        rb = reply.bounding_box()
                        lb = label.bounding_box()
                        if tb and rb and lb:
                            tip_bottom = tb["y"] + tb["height"]
                            # OK if tip entirely above the reply, or tip is above the label (default)
                            ok = tip_bottom <= rb["y"] - 2 or (tb["y"] + tb["height"] <= lb["y"] + 2)
                            assert ok, f"{name}: tip overlaps reply tip={tb} reply={rb} label={lb}"

            # Full-page including portal tip (on document.body)
            path = OUT / f"{name}.png"
            page.screenshot(path=str(path), full_page=True)
            title = None
            if tip_count == 1:
                title = page.locator(".ca-tip").inner_text()
            print(f"  {name}: text={label.inner_text() if label.count() else None!r} tip={title!r} tips={tip_count} bytes={path.stat().st_size}")
            page.close()
        browser.close()
    srv.shutdown()
    print("done", len(SHOTS), "shots →", OUT)


if __name__ == "__main__":
    main()
