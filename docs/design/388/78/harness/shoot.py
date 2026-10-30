"""#388 #78: shoot real ArtiMascot notify panel (schedule skip card) light/dark zh.

Loads tip base.css + shell.css via schedule-skip-notify.html (real CSS/DOM, composer child).
Not a standalone reinvented chrome page (#404/#474 lesson).
"""
from __future__ import annotations

import http.server
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parents[1] / "after"
PORT = 8768
HARNESS = "/docs/design/388/78/harness/schedule-skip-notify.html"


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
            page = browser.new_page(viewport={"width": 520, "height": 700}, device_scale_factor=2)
            for theme, name in (("light", "schedule-skip-light.png"), ("dark", "schedule-skip-dark.png")):
                page.goto(f"{base}{HARNESS}?theme={theme}", wait_until="networkidle")
                page.wait_for_selector('[data-testid="arti-notify"]')
                page.wait_for_selector('[data-testid="arti-schedule-card"]')
                box = page.locator(".ca-composer").bounding_box()
                panel = page.locator('[data-testid="arti-notify"]').bounding_box()
                assert box and panel
                x = min(box["x"], panel["x"]) - 16
                y = min(box["y"], panel["y"]) - 16
                w = max(box["x"] + box["width"], panel["x"] + panel["width"]) - x + 16
                h = max(box["y"] + box["height"], panel["y"] + panel["height"]) - y + 16
                page.screenshot(
                    path=str(OUT / name),
                    clip={"x": max(0, x), "y": max(0, y), "width": w, "height": h},
                )
                print("wrote", OUT / name)
            browser.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
