"""Prefer shoot-live.py (real app). This harness shoot is VOID for product review after Agent/发送 HOLD."""
"""#461 tip CSS/DOM conversational Skill Creator — zh light/dark."""
from __future__ import annotations
import http.server, socketserver, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parents[1] / "after"
PORT = 8768
HARNESS = "/docs/design/461/78/harness/creator.html"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)
    def log_message(self, *args): pass

class ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    httpd = ReuseTCPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{PORT}"
    shots = [
        ("process", "light", "creator-process-zh-light.png"),
        ("process", "dark", "creator-process-zh-dark.png"),
        ("prefill", "light", "creator-prefill-zh-light.png"),
        ("prefill", "dark", "creator-prefill-zh-dark.png"),
    ]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 480, "height": 720}, device_scale_factor=2)
            for scene, theme, name in shots:
                page.goto(f"{base}{HARNESS}?theme={theme}&scene={scene}", wait_until="networkidle")
                page.wait_for_selector('[data-testid="skill-creator-chip"]')
                page.locator("#shot").screenshot(path=str(OUT / name))
                print("wrote", OUT / name)
            browser.close()
    finally:
        httpd.shutdown()

if __name__ == "__main__":
    main()
