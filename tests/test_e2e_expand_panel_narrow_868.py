"""#868: at 220px the scale slider, size/price line, and 取消/生成 stay on one row.

$0 local Playwright against a stubbed app. Excluded from the unit gate by the
"e2e" name; not part of the skill/650/creator/712 E2E filter.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs/qa/868-panel"))
sys.path.insert(0, str(ROOT / "docs/qa/868"))

pytestmark = pytest.mark.skipif(
    not (ROOT / "dist/index.html").is_file() or not (ROOT / "node_modules").exists(),
    reason="needs a local npm run build (dist not committed) and node_modules",
)


def test_e2e_expand_panel_220_rows_do_not_wrap():
    from playwright.sync_api import sync_playwright
    import shoot_after as sa

    if not (ROOT / "dist/index.html").is_file():
        pytest.skip("dist missing")
    src = sa.make_src()
    url = f"http://127.0.0.1:{sa.PORT}/comfyart/"
    proc = None
    try:
        proc = sa.boot(ROOT, sa.PORT)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            # 1280 3x is the path most likely to go 220px (dock or narrow-left/right).
            page = sa.new_page(browser, url, {"width": 1280, "height": 800})
            sa.setup_expand(page, src, 3.0)
            data = sa.assert_clear(page, "e2e-3x-1280")
            assert data.get("narrow") is True
            assert data["layout"]["rowOneLine"]
            assert data["layout"]["hintOneLine"]
            assert data["layout"]["footOneRow"]
            assert data["layout"]["btnNoEllipsis"]
            assert data["overlapTools"] is False and data["genCovered"] is False
            page.close()
            browser.close()
    finally:
        sa.stop(proc)
