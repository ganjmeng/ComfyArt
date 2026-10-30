"""#387 #78: shoot pending ask card with tip base.css + overlays.css (real CSS/DOM).

Mirrors QuestionCard from ChatMessage.tsx. No reinvented tip.css chrome / harness labels in crop.
"""
from __future__ import annotations

import http.server
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parents[1] / "after"
PORT = 8798
HARNESS = "/docs/design/387/78/harness/ask-persist-live.html"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def log_message(self, *args):
        pass


class ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    httpd = ReuseTCPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{PORT}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 480, "height": 640}, device_scale_factor=2)
            for theme, name in (("light", "ask-persist-light.png"), ("dark", "ask-persist-dark.png")):
                page.goto(f"{base}{HARNESS}?theme={theme}", wait_until="networkidle")
                page.wait_for_selector('[data-testid="pending-ask-card"]')
                box = page.locator("#shot").bounding_box()
                assert box
                page.screenshot(
                    path=str(OUT / name),
                    clip={
                        "x": max(0, box["x"] - 8),
                        "y": max(0, box["y"] - 8),
                        "width": box["width"] + 16,
                        "height": box["height"] + 16,
                    },
                )
                print("wrote", OUT / name, (OUT / name).stat().st_size)
            browser.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
