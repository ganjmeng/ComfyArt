"""#610 tip CSS-class harness — zh-light starter matrix + Close restores pills."""
from __future__ import annotations

import http.server
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parents[1] / "left-ours"
PORT = 8710
HARNESS = "/docs/design/610/78/harness/mock.html"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def log_message(self, *args):
        pass


class ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


SHOTS = [
    ("social", "AFTER-starter-social.png"),
    ("brand", "AFTER-starter-brand.png"),
    ("creative", "AFTER-starter-creative.png"),
    ("website", "AFTER-starter-website.png"),
    ("close", "AFTER-starter-close-pills.png"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    httpd = ReuseTCPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{PORT}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 880, "height": 720}, device_scale_factor=2)
            for scene, name in SHOTS:
                page.goto(f"{base}{HARNESS}?scene={scene}", wait_until="networkidle")
                page.wait_for_selector("#shot")
                if scene == "close":
                    page.wait_for_selector('[data-testid="home-v3-hero-chip-e_commerce"]')
                else:
                    page.wait_for_selector('[data-testid="ca-home-starter"]')
                    page.wait_for_selector(f'[data-testid="home-v3-starter-icon-{ {"social":"social_media","brand":"branding","creative":"ads_creative","website":"website"}[scene] }"][aria-pressed="true"]')
                page.locator("#shot").screenshot(path=str(OUT / name))
                print("wrote", OUT / name)
            browser.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
