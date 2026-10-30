"""#410: agent-loop audit — every process kind live+done, inventory lock, optional harness shots.

Mocks only ($0). Set AUDIT410_SHOTS=docs/design/410/78/after to write PNGs.
Never spends WaveSpeed; real-call fallback counts stay on the EL-approved $5 budget list.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = (ROOT / "docs/design/410/78/AUDIT.md").read_text(encoding="utf-8")
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
HARNESS = (ROOT / "tests/js/process410/main.tsx").read_text(encoding="utf-8")

# ProcessKind union in ChatMessage.tsx — keep in sync with the audit table.
PROCESS_KINDS = [
    "thought",
    "outputting",
    "skill",
    "skill_file_read",
    "search",
    "search_pages",
    "image",
    "video",
    "code",
    "code_generated",
    "code_updated",
    "design_validated",
    "preview_artifact",
    "memory_retrieved",
    "memory_updating",
    "memory_updated",
    "tool",
]

# Scenes the harness must cover (live + done for the audit acceptance).
SCENES = [
    "no-tool-live", "no-tool-done",
    "thought-live", "thought-done",
    "skill-live", "skill-done",
    "skill-file-live", "skill-file-done", "skill-read-done",
    "search-live", "search-done",
    "image-live", "image-done",
    "video-live", "video-done",
    "memory-live", "memory-done",
    "code-live", "code-done",
    "tool-live", "tool-done",
    "outputting-live",
    "chain-live", "chain-done",
]

pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


def test_process_kind_union_matches_audit_inventory():
    for k in PROCESS_KINDS:
        assert f"'{k}'" in CHAT, f"ProcessKind missing {k}"
        assert f"`{k}`" in AUDIT or f"**{k}**" in AUDIT or f"| `{k}`" in AUDIT, f"AUDIT.md missing kind {k}"


def test_audit_uses_reference_not_brand_name():
    # PR / docs rule: never write the reference product brand in tip files.
    assert "lovart" not in AUDIT.lower()
    assert "「reference」" in AUDIT


def test_harness_covers_every_scene():
    for s in SCENES:
        assert f"'{s}'" in HARNESS or f'"{s}"' in HARNESS


def test_no_tool_turn_called_out():
    assert "no-tool" in AUDIT.lower() or "没调工具" in AUDIT or "无工具" in AUDIT


def test_fallback_count_deferred_to_budget():
    # Product item from #410 comments: real-call fallback stats need EL $5 budget approval.
    assert "fallback" in AUDIT.lower() or "兜底" in AUDIT
    assert "$5" in AUDIT or "预算" in AUDIT


def test_skills_create_deferred_to_411():
    assert "#411" in AUDIT


def test_arti_memory_module_deferred_to_430():
    assert "#430" in AUDIT


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("process410")
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/process410/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(d / "app.js")},
    )
    css = "\n".join(
        (ROOT / "src/styles" / f).read_text()
        for f in ("base.css", "canvas.css", "shell.css", "overlays.css")
    )
    (d / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><style>html,body{{margin:0;background:var(--ca-page,#f5f5f5)}}"
        f"{css}</style><div id=root></div><script src=app.js></script>",
        encoding="utf-8",
    )
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


def _open(browser, bundle, scene, lang, theme):
    page = browser.new_page(viewport={"width": 420, "height": 720}, device_scale_factor=2)
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
    page.goto(f"{bundle}/index.html?lang={lang}&theme={theme}&scene={scene}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(250)
    return page


def test_harness_renders_chain_done(browser, bundle):
    page = _open(browser, bundle, "chain-done", "zh", "light")
    assert page.locator(".ca-process").count() >= 1
    labels = page.locator(".ca-process__label").all_text_contents()
    assert any("思考完成" in x for x in labels)
    assert any("技能" in x for x in labels)
    page.close()


@pytest.mark.parametrize("lang,want_path,want_load", [("zh", "技能文件已读", "技能加载完成"), ("en", "Skill file read", "Skill ready")])
def test_harness_skill_read_path_vs_load(browser, bundle, lang, want_path, want_load):
    """#462: read WITH a path still renders the file-read row; read WITHOUT a path renders the skill-load row."""
    page = _open(browser, bundle, "skill-file-done", lang, "light")
    labels = page.locator(".ca-process__label").all_text_contents()
    assert any(want_path in x for x in labels) and not any(want_load in x for x in labels), labels
    page.close()
    page = _open(browser, bundle, "skill-read-done", lang, "light")
    labels = page.locator(".ca-process__label").all_text_contents()
    assert any(want_load in x for x in labels) and not any(want_path in x for x in labels), labels
    page.close()


def _user_skill(browser, bundle, lang, name, text=""):
    from urllib.parse import quote
    page = browser.new_page(viewport={"width": 420, "height": 720}, device_scale_factor=2)
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
    page.goto(f"{bundle}/index.html?lang={lang}&theme=light&scene=user-skill&name={quote(name)}&text={quote(text)}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(200)
    m = page.evaluate("""() => {
      const bub = document.querySelector('[data-testid=user-bubble]')
      const chip = bub.querySelector('[data-testid=user-skill-chip]')
      const nm = chip.querySelector('.ca-chip__name')
      const tx = bub.querySelector('[data-testid=user-bubble-text]')
      const lh = parseFloat(getComputedStyle(tx).lineHeight) || 20
      const c = chip.getBoundingClientRect(), t = tx.getBoundingClientRect()
      return { inBubble: chip.parentElement === bub, chipLeft: c.right <= t.left + 1, sameRow: Math.abs((c.top + c.bottom) - (t.top + t.bottom)) < 4,
               textLines: t.height < lh * 1.5 ? 1 : Math.round(t.height / lh), truncated: nm.scrollWidth > nm.clientWidth, chipW: c.width,
               ellipsis: getComputedStyle(nm).textOverflow, chipMin: parseFloat(getComputedStyle(chip).minWidth) }
    }""")
    page.close()
    return m


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_harness_user_skill_chip_shrinks_first_text_one_line(browser, bundle, lang):
    """#462: chip inside the bubble, left of the text, same row; a long name truncates with … and the text stays on one line."""
    short = _user_skill(browser, bundle, lang, "早安咖啡店海报生成器")
    assert short["inBubble"] and short["chipLeft"] and short["sameRow"] and short["textLines"] == 1, short
    long = _user_skill(browser, bundle, lang, "早安咖啡店海报生成器·门店社媒竖版暖色调超长名称版本二")
    assert long["inBubble"] and long["sameRow"] and long["textLines"] == 1, long
    assert long["truncated"] and long["ellipsis"] == "ellipsis" and long["chipW"] <= 160, long
    # a prompt too long for one line may wrap, but the chip keeps its minimum (icon + …) instead of vanishing
    para = _user_skill(browser, bundle, lang, "早安咖啡店海报生成器", "把标题改成「周末早安」，画幅改为 9:16，并在底部加上门店地址与营业时间，配色更暖一些")
    assert para["inBubble"] and para["textLines"] >= 2 and para["chipW"] >= para["chipMin"] - 0.5, para


def test_harness_renders_memory_done(browser, bundle):
    page = _open(browser, bundle, "memory-done", "zh", "light")
    assert page.locator("[data-testid=memory-updated-row]").count() >= 1
    page.close()


def test_harness_renders_no_tool_done(browser, bundle):
    page = _open(browser, bundle, "no-tool-done", "zh", "light")
    # single Thought path (#325) — no multi-step rail required
    assert page.locator(".ca-chat__thinklabel, .ca-process__label, .ca-chat__thinking").count() >= 1
    page.close()


def test_shoot_audit_shots(browser, bundle):
    out = os.environ.get("AUDIT410_SHOTS")
    if not out:
        pytest.skip("set AUDIT410_SHOTS to write PNGs")
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=True)
    # Representative matrix: zh/light + en/dark for each scene (acceptance: live+done, zh/en)
    matrix = [("zh", "light"), ("en", "dark")]
    written = []
    for scene in SCENES:
        for lang, theme in matrix:
            page = _open(browser, bundle, scene, lang, theme)
            path = dest / f"{scene}-{lang}-{theme}.png"
            page.locator("#scene").screenshot(path=str(path))
            written.append(path.name)
            page.close()
    manifest = dest / "manifest.json"
    manifest.write_text(json.dumps({"scenes": SCENES, "files": written}, indent=2) + "\n", encoding="utf-8")
    assert len(written) == len(SCENES) * len(matrix)
