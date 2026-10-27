"""Capture #399 #78 before/after + loader screenshots."""
from __future__ import annotations

import http.server
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[5]  # ComfyArt_399
OUT = Path(__file__).resolve().parents[1]
PORT = 8765


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def log_message(self, *args):
        pass


class ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def shot(page, path: Path, w: int, h: int):
    page.set_viewport_size({"width": w, "height": h})
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=False)
    print("wrote", path)


def main():
    httpd = ReuseTCPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{PORT}"
    demo = ROOT / "public" / "brand" / "_loader-demo.html"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            for theme in ("light", "dark"):
                for w, label in ((1440, "1440"), (390, "390")):
                    h = 900 if w == 1440 else 844
                    page.goto(f"{base}/docs/design/399/78/harness/before.html?theme={theme}", wait_until="networkidle")
                    shot(page, OUT / "before" / f"home-{theme}-{label}.png", w, h)

                    page.goto(f"{base}/docs/design/399/78/harness/index.html?theme={theme}", wait_until="networkidle")
                    shot(page, OUT / "after" / f"home-{theme}-{label}.png", w, h)

            demo.write_text("""<!doctype html><html><head><meta charset=utf-8>
<link rel=stylesheet href=loomi-loader.css>
<script src=brand.config.js></script>
<script src=loomi-loader.js></script>
<style>html,body{margin:0;height:100%;background:#888}</style>
</head><body>
<script>
const theme=new URLSearchParams(location.search).get('theme')||'light';
document.documentElement.dataset.theme=theme;
LoomiLoader.mount({size:64,theme,waitForReady:true,durationMs:1200});
</script></body></html>""")

            for theme in ("light", "dark"):
                page.goto(f"{base}/public/brand/_loader-demo.html?theme={theme}", wait_until="networkidle")
                page.wait_for_timeout(700)
                shot(page, OUT / "loader" / f"loader-{theme}-1440.png", 1440, 900)
                shot(page, OUT / "loader" / f"loader-{theme}-390.png", 390, 844)

            assets = Path("/workspace/ComfyArt-review-assets/logo-explore/loomic-loader-v2")
            for name in ("loomic-loader-v2-contact-sheet-light.png", "loomic-loader-v2-contact-sheet-dark.png"):
                src = assets / name
                if src.is_file():
                    dest = OUT / "loader" / name.replace("loomic-loader-v2-", "")
                    dest.write_bytes(src.read_bytes())
                    print("copied", dest.name)

            browser.close()
    finally:
        httpd.shutdown()
        demo.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
