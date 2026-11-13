"""#940 first cut: inline skill + reference chips in the user bubble.

Source locks plus Full App zh-light / en-dark shots. $0 — seeded chat, no model calls.
Set CA_940_SHOTS=<dir> to choose the screenshot directory (defaults to tmp-940-shots/).
"""
from __future__ import annotations

import io
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
SHELL = (ROOT / "src/styles/shell.css").read_text(encoding="utf-8")
SHOT_DIR = Path(os.environ.get("CA_940_SHOTS", str(ROOT / "tmp-940-shots")))

LONG_ZH = (
    "请根据频道定位做一张 YouTube 频道横幅，标题要能在电视、桌面和手机上都能读清，"
    "左侧留出安全区给文字，右侧放主视觉，整体偏亮、留白多一些，不要假界面。"
)
LONG_EN = (
    "Please make a YouTube channel banner that stays readable on TV, desktop and phone, "
    "with a safe area on the left for the copy, the main visual on the right, "
    "and a bright, generous layout with no fake UI."
)


def test_src_only_touches_shell_and_chat_message_for_chips():
    """First cut lives in the existing bubble + chip files; no parallel chip component."""
    assert "function UserRefChip" in CHAT
    assert "function refChipLabel" in CHAT
    assert '<SkillChip key={b.name} name={b.name ?? ""} testId="user-skill-chip" />' in CHAT
    assert "onError={() => setFailed(true)}" in CHAT
    assert "className=\"ca-chip__thumb\"" in CHAT
    assert "Lovart" not in CHAT and "Lovart" not in SHELL


def test_inline_chip_css_locks():
    assert re.search(r"\.ca-chat__bubble--skill \{[^}]*display: block", SHELL)
    skill = re.search(r"\.ca-chat__bubble--skill > \.ca-chip--skill \{([^}]*)\}", SHELL)
    assert skill and "display: inline-flex" in skill.group(1) and "max-width: 160px" in skill.group(1)
    assert "flex: 0 999 auto" not in SHELL
    text = re.search(r"\.ca-chat__bubble--skill > \.ca-chat__text \{([^}]*)\}", SHELL)
    assert text and "display: inline" in text.group(1) and "max-width: none" in text.group(1)
    ref = re.search(r"(?m)^\.ca-chip--ref \{([^}]*)\}", SHELL)
    assert ref and "max-width: 120px" in ref.group(1)
    thumb = re.search(r"\.ca-chip--ref \.ca-chip__thumb \{([^}]*)\}", SHELL)
    assert thumb and "width: 16px" in thumb.group(1) and "height: 16px" in thumb.group(1)
    assert "object-fit: cover" in thumb.group(1) and "border-radius: 4px" in thumb.group(1)
    # #491 creator chip still never truncates
    assert '.ca-chip--skill:is([title="技能创建器"], [title="Skill Creator"]) { flex-shrink: 0; max-width: none; }' in SHELL


def test_ref_chip_falls_back_to_filename_or_image_n():
    assert "refFromUrl(src).filename" in CHAT
    assert "return `image-${index + 1}`" in CHAT
    assert "if (named) return named" in CHAT


def _png(rgb: tuple[int, int, int], size: tuple[int, int] = (48, 48)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, rgb).save(buf, "PNG")
    return buf.getvalue()


def _write_refs() -> tuple[str, str]:
    import folder_paths
    base = Path(folder_paths.STATE["base"])
    inp = base / "input"
    inp.mkdir(parents=True, exist_ok=True)
    a, b = "product-input.png", "packing-shot.png"
    (inp / a).write_bytes(_png((220, 90, 60)))
    (inp / b).write_bytes(_png((60, 120, 200)))
    return (
        f"/api/view?filename={a}&subfolder=&type=input",
        f"/api/view?filename={b}&subfolder=&type=input",
    )


async def _seed(pg, lang: str) -> None:
    from ComfyArt.api import chat_store

    user = await pg.evaluate("async()=>(await (await fetch('/api/comfyart/bot/status')).json()).user")
    proj = await pg.evaluate(
        r"()=>{for (const e of performance.getEntriesByType('resource')){"
        r"const m=e.name.match(/bot\/chats\?project=([^&]+)/); if(m) return decodeURIComponent(m[1])}"
        r" return null}"
    )
    assert proj
    url_a, url_b = _write_refs()
    skill = "YouTube频道横幅" if lang == "zh" else "YouTube Channel Banner"
    long = LONG_ZH if lang == "zh" else LONG_EN
    short = "请按这两张参考图出包装主视觉。" if lang == "zh" else "Use these two references for the pack shot."
    title = "940-cut1-zh" if lang == "zh" else "940-cut1-en"
    c = chat_store.create_chat(user=user, project=proj, provider="local-llm", title=title)
    chat_store.create_message(chat_id=c["id"], role="user", blocks=[
        {"type": "skill", "name": skill},
        {"type": "text", "text": long},
    ])
    chat_store.create_message(chat_id=c["id"], role="user", blocks=[
        {"type": "skill", "name": skill},
        {"type": "image", "url": url_a, "name": "product-input.png"},
        {"type": "image", "url": url_b},  # filename comes from the existing view URL
        {"type": "text", "text": short},
    ])
    # broken url: filename only, no empty thumb (assert after reload, not in the shot if we scroll? keep in same chat, last)
    chat_store.create_message(chat_id=c["id"], role="user", blocks=[
        {"type": "skill", "name": skill},
        {"type": "image", "url": "/api/view?filename=missing-ref.png&subfolder=&type=input", "name": "missing-ref.png"},
        {"type": "text", "text": "broken" if lang == "en" else "坏图"},
    ])
    await pg.reload()
    await pg.locator(".ca-split__chev").first.click(timeout=8000)
    await pg.locator(".ca-history__item", has_text=title).first.click(timeout=8000)
    await pg.locator('[data-testid="user-bubble"]').first.wait_for(timeout=10000)
    await pg.mouse.move(5, 790)
    await pg.wait_for_timeout(400)


@pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_full_app_inline_chips_940(app_url, fake_tools, lang, theme):  # noqa: F811
    pw = pytest.importorskip("playwright.async_api")
    from test_e2e_default_agent import _page

    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, lang, theme)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"chromium/full app boot failed: {e}")
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(100)
        await _seed(pg, lang)
        bubbles = pg.locator('[data-testid="user-bubble"]')
        assert await bubbles.count() == 3
        long_b, refs_b, broken_b = bubbles.nth(0), bubbles.nth(1), bubbles.nth(2)

        long_m = await long_b.evaluate("""el => {
          const chip = el.querySelector('[data-testid=user-skill-chip]')
          const tx = el.querySelector('[data-testid=user-bubble-text]')
          const cs = getComputedStyle(el)
          const padL = parseFloat(cs.paddingLeft) || 0
          const b = el.getBoundingClientRect(), c = chip.getBoundingClientRect(), t = tx.getBoundingClientRect()
          const lh = parseFloat(getComputedStyle(tx).lineHeight) || 24
          return {
            display: cs.display,
            chipDisplay: getComputedStyle(chip).display,
            chipW: c.width,
            textLines: t.height < lh * 1.5 ? 1 : Math.round(t.height / lh),
            wrapFromLeft: t.left <= b.left + padL + 2,
            firstLine: Math.abs(c.top - t.top) < 8,
          }
        }""")
        assert long_m["display"] == "block" and long_m["chipDisplay"] == "inline-flex", long_m
        assert 90 <= long_m["chipW"] <= 160, long_m
        assert long_m["textLines"] >= 2 and long_m["wrapFromLeft"] and long_m["firstLine"], long_m

        refs_m = await refs_b.evaluate("""el => {
          const refs = [...el.querySelectorAll('[data-testid=user-ref-chip]')]
          return refs.map((r) => {
            const img = r.querySelector('img')
            const name = (r.querySelector('.ca-chip__name') || r).textContent
            const cs = img ? getComputedStyle(img) : null
            return {
              name,
              w: r.getBoundingClientRect().width,
              max: getComputedStyle(r).maxWidth,
              hasThumb: !!img,
              thumbW: img ? img.getBoundingClientRect().width : 0,
              thumbH: img ? img.getBoundingClientRect().height : 0,
              fit: cs && cs.objectFit,
              radius: cs && cs.borderRadius,
            }
          })
        }""")
        assert [r["name"] for r in refs_m] == ["product-input.png", "packing-shot.png"], refs_m
        for r in refs_m:
            assert r["hasThumb"] and 15 <= r["thumbW"] <= 17 and 15 <= r["thumbH"] <= 17, r
            assert r["fit"] == "cover" and r["w"] <= 120, r

        # broken image: wait until the thumb is gone, label remains
        await broken_b.locator('[data-testid=user-ref-chip]').wait_for()
        await pg.wait_for_function(
            """() => {
              const b = document.querySelectorAll('[data-testid=user-bubble]')[2]
              const chip = b && b.querySelector('[data-testid=user-ref-chip]')
              return chip && chip.textContent.includes('missing-ref.png') && !chip.querySelector('img')
            }"""
        )
        broken_m = await broken_b.locator('[data-testid=user-ref-chip]').evaluate(
            "el => ({ text: (el.querySelector('.ca-chip__name')||el).textContent, imgs: el.querySelectorAll('img').length })"
        )
        assert broken_m["text"] == "missing-ref.png" and broken_m["imgs"] == 0, broken_m

        # Screenshot the two acceptance bubbles (long text + two refs), not the error-fallback row.
        await broken_b.evaluate("el => { el.closest('.ca-chat__user').style.display = 'none' }")
        await pg.wait_for_timeout(200)
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        await pg.locator(".ca-root").screenshot(path=str(SHOT_DIR / f"inline-chips-{lang}-{theme}.png"))
        await browser.close()


# Imported fixtures (app_url, fake_tools, mock_ws) are requested by name from the modules below.
from test_e2e_comment_edit import app_url, mock_ws  # noqa: E402,F401
from test_e2e_default_agent import fake_tools  # noqa: E402,F401
