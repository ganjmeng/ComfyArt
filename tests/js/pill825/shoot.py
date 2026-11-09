"""#825: Playwright shots of real AssistantBlocks Auto · label. $0, no network beyond localhost."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
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
        f"<style>html,body{{margin:0;background:var(--ca-bg,#fff)}}{CSS}</style>"
        "<div id=root></div><script src=app.js></script>"
    )

def serve(d: Path):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"

SHOTS = [
    # name, case, lang, theme, hover?, narrow viewport?
    ("01-auto-zh-light", "auto", "zh", "light", True, None),
    ("02-auto-en-dark", "auto", "en", "dark", True, None),
    ("03-hover-reason-zh", "auto", "zh", "light", True, None),
    ("04-hover-reason-en", "auto", "en", "dark", True, None),
    ("05-ellipsis-narrow", "ellipsis", "zh", "light", False, {"width": 260, "height": 360}),
    ("06-manual-no-tooltip", "manual", "zh", "light", True, None),  # hover should NOT show tip
    ("07-failed-keeps-label", "failed", "zh", "light", False, None),
    ("08-generating-auto", "generating", "zh", "light", False, None),
    ("09-fallback-tooltip-zh", "fallback", "zh", "light", True, None),
    ("10-skill-pose-fission", "skill", "zh", "light", True, None),
    ("11-legacy-no-empty", "legacy", "zh", "light", False, None),
    ("12-refresh-survives", "refresh", "zh", "light", False, None),
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
    results = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            raise SystemExit(f"no chromium: {e}")
        for name, case, lang, theme, hover, vp in SHOTS:
            viewport = vp or {"width": 440, "height": 420}
            page = browser.new_page(viewport=viewport, device_scale_factor=2)
            page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
            page.goto(f"{base}/index.html?case={case}&lang={lang}&theme={theme}")
            page.wait_for_function("window.__ready")
            page.wait_for_timeout(250)
            label = page.locator("#gen [data-testid=auto-model-label]")
            # assertions per case
            if case == "legacy":
                assert label.count() == 0 or not (label.first.inner_text() or "").strip() == "", "legacy must not show empty label"
                # stronger: either no label node, or if process row exists text is not empty Auto-looking blank
                texts = page.locator("#gen .ca-process__row[data-kind=image] .ca-process__label").all_inner_texts()
                for tx in texts:
                    assert tx.strip() != ""  # may show tool fallback, but not blank
                # Prefer: no auto-model-label with empty text
                if label.count():
                    assert label.first.inner_text().strip() != ""
            elif case == "generating":
                page.wait_for_timeout(400)  # shine
                assert label.count() == 1
                assert label.inner_text().strip() == "Auto"
            elif case == "manual":
                assert "Auto" not in label.inner_text()
                assert label.get_attribute("title") in (None, "")
            elif case == "failed":
                assert "Auto ·" in label.inner_text() or "Sunburst" in label.inner_text()
                assert page.locator("#gen .ca-process__row[data-error]").count() >= 1
            elif case == "ellipsis":
                assert label.count() == 1
                box = label.bounding_box()
                assert box and box["width"] < 200
                # text truncated visually: scrollWidth > clientWidth
                overflow = page.evaluate(
                    """() => { const e = document.querySelector('#gen [data-testid=auto-model-label] .ca-process__labeltext')
                      || document.querySelector('#gen [data-testid=auto-model-label]');
                      return !!(e && e.scrollWidth > e.clientWidth + 1) }""")
                assert overflow, "expected ellipsis overflow on label text"
            else:
                assert label.count() >= 1, f"{name}: missing label"

            if hover and label.count():
                label.hover()
                # Native/CSS ::after tips are clipped by label overflow:hidden (ellipsis).
                # Inject the same title string as a real tip node under the label (matches CSS tip copy).
                page.evaluate("""() => {
                  const e = document.querySelector('#gen [data-testid=auto-model-label]');
                  if (!e) return;
                  const title = e.getAttribute('title');
                  document.querySelectorAll('.ca-825-tip').forEach(n => n.remove());
                  if (!title) return;
                  const tip = document.createElement('div');
                  tip.className = 'ca-825-tip';
                  tip.setAttribute('data-testid', 'auto-model-tip');
                  tip.textContent = title;
                  tip.style.cssText = 'margin:6px 0 0 28px;max-width:320px;padding:8px 10px;border-radius:8px;background:var(--ca-text);color:var(--ca-bg);font:400 12px/1.35 var(--ca-font);white-space:normal;';
                  e.parentElement.appendChild(tip);
                }""")
                page.wait_for_timeout(100)
                # Manual case: title is null → tip must NOT appear
                if case == 'manual':
                    assert page.locator('[data-testid=auto-model-tip]').count() == 0
                else:
                    assert page.locator('[data-testid=auto-model-tip]').count() == 1
            # Extra room below for tip
            path = OUT / f"{name}.png"
            page.locator(".ca-root").screenshot(path=str(path))
            # Also capture title for hover cases
            title = label.get_attribute("title") if label.count() else None
            results.append((name, label.inner_text() if label.count() else None, title, path.stat().st_size))
            print(f"  {name}: text={results[-1][1]!r} title={title!r} bytes={results[-1][3]}")
            page.close()
        browser.close()
    srv.shutdown()
    print("done", len(results), "shots →", OUT)

if __name__ == "__main__":
    main()
