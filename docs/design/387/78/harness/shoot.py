"""#387 #78: pending ask card survives refresh — before/after light+dark."""
from __future__ import annotations

import http.server
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[5]  # ComfyArt
OUT = Path(__file__).resolve().parents[1]
PORT = 8797


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def log_message(self, *args):
        pass


class ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def shot(page, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    el = page.locator("#shot")
    el.screenshot(path=str(path))
    print("wrote", path, path.stat().st_size)


def main():
    httpd = ReuseTCPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{PORT}/docs/design/387/78/harness"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 420, "height": 520})
            for theme in ("light", "dark"):
                page.goto(f"{base}/ask-persist-before.html?theme={theme}", wait_until="networkidle")
                shot(page, OUT / "before" / f"ask-persist-{theme}.png")
                page.goto(f"{base}/ask-persist-after.html?theme={theme}", wait_until="networkidle")
                shot(page, OUT / "after" / f"ask-persist-{theme}.png")
            browser.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
