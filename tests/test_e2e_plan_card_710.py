"""#710 UI e2e: real QuestionCard / user chips / composer Stop. $0, no network.

F.2 F.3 F.9 F.10 F.12 render the real components. F.13 writes L/R shots when
COMFYART_SHOT_710=1 (left = pinned Lovart gold, or GOLD MISSING for the selected state).
Agent-loop points F.1 F.4–F.8 F.11 live in test_shot_plan_710.py.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ComfyArt.bot.shot_plan import ask_spec, build_shots

ROOT = Path(__file__).resolve().parent.parent
pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)
SHOT = os.environ.get("COMFYART_SHOT_710") == "1"
OUT = ROOT / "docs" / "qa" / "710"
LOVART = "821762885248abef007feb308e09d5132ade7fe1"


def _prompt(scene="同参考图街景，背景压暗"):
    return ask_spec(build_shots(4, 0, scene))["prompt"]


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    d = tmp_path_factory.mktemp("plan710")
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/plan710/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(d / "app.js")},
    )
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    # CSS stays in its own file: @property syntax: '<number>' would close an inline <style>.
    (d / "app.css").write_text(
        "html,body{margin:0;background:#fff}\n" + css + "\n.ca-q__body{max-height:none!important}\n",
        encoding="utf-8",
    )
    (d / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><link rel=stylesheet href=app.css>"
        "<div id=root></div>"
        # Chrome 156 rejects tiptap's unicode whitespace RegExp; the card does not use it.
        "<script>window.WebSocket = class { constructor() {} send() {} close() {} addEventListener() {} };"
        "const __OrigRegExp = RegExp; function __SafeRegExp(p, f){ try { return new __OrigRegExp(p, f) } catch (e) { return new __OrigRegExp('\\\\s', f) } }"
        "__SafeRegExp.prototype = __OrigRegExp.prototype; window.RegExp = __SafeRegExp;</script>"
        "<script src=app.js></script>",
        encoding="utf-8",
    )
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        pg = browser.new_page(viewport={"width": 520, "height": 1800}, device_scale_factor=2)
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append((getattr(e, "stack", None) or str(e))[:800]))
        pg.goto((d / "index.html").as_uri())
        try:
            pg.wait_for_function("() => typeof window.__render === 'function'", timeout=8000)
        except Exception:
            kind = pg.evaluate("() => typeof window.__render")
            raise AssertionError(kind + " :: " + " | ".join(errors[:1]))
        yield pg
        browser.close()


def _show(page, **state):
    page.evaluate("s => window.__render(s)", state)
    page.wait_for_timeout(50)


def _lines(page):
    return page.locator('[data-testid="question-plan-line"]')


def test_plan_lines_are_separate_and_pre_line(page):
    prompt = _prompt()
    _show(page, lang="zh", theme="light", prompt=prompt, status="pending",
          skill="电商同场景角色姿势裂变", images=2, userText="同参考图街景", running=True)
    lines = _lines(page)
    assert lines.count() == 4
    body = page.locator('[data-testid="question-plan-body"]')
    assert body.evaluate("el => getComputedStyle(el).whiteSpace") == "pre-line"
    text = body.inner_text()
    assert len([ln for ln in text.splitlines() if ln.strip()]) >= 4
    joined = text.replace("\n", "")
    # not one collapsed paragraph: each line element owns its own text
    assert lines.nth(0).inner_text() != text
    for i in range(4):
        line = lines.nth(i).inner_text()
        for token in ("景别：", "角度：", "机位：", "姿态：", "构图：", "焦段：", "光：", "场景：", "°", "mm", "三分", "不居中"):
            assert token in line, (i, token, line)
        assert "半身" not in line and "全身" not in line
    angles = []
    for i in range(4):
        bit = lines.nth(i).inner_text().split("角度：", 1)[1].split("；", 1)[0]
        angles.append(bit)
    assert len(set(angles)) == 4
    fronts = [lines.nth(i).inner_text() for i in range(4) if "角度：0°" in lines.nth(i).inner_text()]
    assert len(fronts) <= 1 and fronts and "三分" in fronts[0] and "不居中" in fronts[0]
    assert page.locator(".ca-q__prompt").inner_text().strip() == "是否生成这 4 张？"
    assert page.locator(".ca-q__submit").is_disabled()
    # question open: primary is not Stop (#763/#764)
    assert page.locator('[data-testid="composer-stop"]').count() == 0
    chips = page.locator('[data-testid="user-ref-chip"]')
    assert chips.count() == 2
    assert chips.nth(0).inner_text() == "image-1" and chips.nth(1).inner_text() == "image-2"
    assert page.locator('[data-testid="user-skill-chip"]').inner_text()
    if SHOT:
        OUT.mkdir(parents=True, exist_ok=True)
        page.locator('[data-testid="plan-harness"]').screenshot(path=str(OUT / "right-4plans-zh-light.png"))


def test_select_a_then_folded_bubble(page):
    prompt = _prompt()
    _show(page, lang="zh", theme="light", prompt=prompt, status="pending", running=False)
    page.locator(".ca-q__opt").nth(0).click()
    assert page.locator(".ca-q__opt").nth(0).get_attribute("data-on") is not None
    assert page.locator(".ca-q__submit").is_enabled()
    if SHOT:
        page.locator('[data-testid="plan-harness"]').screenshot(path=str(OUT / "right-selected-zh-light.png"))
    _show(page, lang="zh", theme="light", prompt=prompt, status="answered", selected=["generate"])
    assert _lines(page).count() == 0
    assert page.locator(".ca-q").count() == 0
    bubble = page.locator('[data-testid="ask-answer-bubble"]')
    text = bubble.inner_text()
    assert "是否生成这 4 张？" in text and "A: 开始生成" in text
    assert text.count("景别：") == 4
    assert page.locator('[data-testid="ask-answer-copy"]').count() == 1
    if SHOT:
        page.locator('[data-testid="plan-harness"]').screenshot(path=str(OUT / "right-submitted-zh-light.png"))


def test_running_stop_and_en_dark(page):
    _show(page, lang="zh", theme="light", prompt="普通问题？", status="answered", running=True, selected=["generate"])
    stop = page.locator('[data-testid="composer-stop"]')
    assert stop.count() == 1
    assert stop.get_attribute("aria-label") == "停止"
    stop.click()
    assert page.locator('[data-testid="plan-harness"]').get_attribute("data-run") == "aborted"
    prompt = _prompt()
    _show(page, lang="en", theme="dark", prompt=prompt, status="pending",
          skill="Same-Scene Pose Fission", images=2, userText="street", running=True)
    assert _lines(page).count() == 4
    assert page.locator('[data-testid="composer-stop"]').count() == 0
    assert page.locator('[data-testid="user-ref-chip"]').nth(1).inner_text() == "image-2"
    if SHOT:
        page.locator('[data-testid="plan-harness"]').screenshot(path=str(OUT / "right-4plans-en-dark.png"))
    _show(page, lang="en", theme="dark", prompt=prompt, status="pending", running=False)
    page.locator(".ca-q__opt").nth(0).click()
    if SHOT:
        page.locator('[data-testid="plan-harness"]').screenshot(path=str(OUT / "right-selected-en-dark.png"))
    _show(page, lang="en", theme="dark", prompt=prompt, status="answered", selected=["generate"])
    assert "A: 开始生成" in page.locator('[data-testid="ask-answer-bubble"]').inner_text()
    assert _lines(page).count() == 0
    if SHOT:
        page.locator('[data-testid="plan-harness"]').screenshot(path=str(OUT / "right-submitted-en-dark.png"))


def test_skip_bubble_keeps_plan_lines(page):
    prompt = _prompt()
    _show(page, lang="zh", theme="light", prompt=prompt, status="answered", selected=[])
    bubble = page.locator('[data-testid="ask-answer-bubble"]')
    assert bubble.get_attribute("data-ask") == "skip"
    text = bubble.inner_text()
    assert "是否生成这 4 张？" in text and "跳过这个问题" in text
    assert _lines(page).count() == 0
