"""#460 tip CSS/DOM Skills Explore — zh light/dark."""
from __future__ import annotations
import http.server, socketserver, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parents[1] / "after"
PORT = 8767
HARNESS = "/docs/design/460/78/harness/explore.html"

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
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
            for theme, name in (("light", "explore-zh-light.png"), ("dark", "explore-zh-dark.png")):
                page.goto(f"{base}{HARNESS}?theme={theme}", wait_until="networkidle")
                page.wait_for_selector('[data-testid="skills-page"]')
                page.locator('[data-testid="home-shell"]').screenshot(path=str(OUT / name))
                print("wrote", OUT / name)
            browser.close()
    finally:
        httpd.shutdown()

if __name__ == "__main__":
    main()
