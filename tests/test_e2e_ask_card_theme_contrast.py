"""Dark-theme ask card: question text and an unselected option stay >= 4.5:1 on the card.

The docked multi-angle setup card reads `--ca-text` / `--ca-opt-on` from
`<html data-theme>`. Light theme is the same check in the other direction.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CSS = "\n".join((ROOT / "src/styles" / name).read_text() for name in ("base.css", "overlays.css", "shell.css"))
CARD = """
<div class="ca-chat__dock" data-testid="question-dock">
  <div class="ca-q">
    <div class="ca-q__head">
      <div class="ca-q__page">1 / 2</div>
      <button type="button" class="ca-q__chev">‹</button>
      <button type="button" class="ca-q__chev" disabled>›</button>
    </div>
    <div class="ca-q__body">
      <div class="ca-q__block">
        <div class="ca-q__prompt">产品参考图怎么提供？</div>
        <div class="ca-q__opts">
          <button type="button" class="ca-q__opt" data-on=""><span class="ca-q__letter">A</span><span class="ca-q__text">上传多角度产品图</span></button>
          <button type="button" class="ca-q__opt"><span class="ca-q__letter">B</span><span class="ca-q__text">只上传 1 张正面主图</span></button>
          <button type="button" class="ca-q__opt"><span class="ca-q__letter">C</span><span class="ca-q__text">暂无实拍图，先做产品示意</span></button>
        </div>
      </div>
      <div class="ca-q__block">
        <div class="ca-q__prompt">详情页主画幅用哪个？</div>
        <div class="ca-q__opts">
          <button type="button" class="ca-q__opt"><span class="ca-q__letter">A</span><span class="ca-q__text">1:1 方图（推荐）</span></button>
          <button type="button" class="ca-q__opt"><span class="ca-q__letter">B</span><span class="ca-q__text">3:4 竖图</span></button>
          <button type="button" class="ca-q__opt"><span class="ca-q__letter">C</span><span class="ca-q__text">4:3 横图</span></button>
        </div>
      </div>
    </div>
  </div>
</div>
"""


def _channels(value):
    inner = value[value.find("(") + 1:value.rfind(")")]
    parts = [float(p.strip()) for p in inner.split(",")]
    rgb = tuple(parts[:3])
    alpha = parts[3] if len(parts) > 3 else 1.0
    return rgb, alpha


def _composite(fg, fg_a, bg):
    return tuple(fg_a * c + (1 - fg_a) * b for c, b in zip(fg, bg))


def _contrast(fg, bg):
    def lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def lum(rgb):
        r, g, b = rgb
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

    lighter, darker = sorted((lum(fg), lum(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _measure(theme):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(f'<html data-theme="{theme}"><body>{CARD}</body></html>')
            page.add_style_tag(content=CSS)
            return page.evaluate("""() => {
                const card = document.querySelector('.ca-q');
                const prompt = document.querySelector('.ca-q__prompt');
                const option = document.querySelector('.ca-q__opt:not([data-on]) .ca-q__text');
                const cs = (el) => getComputedStyle(el);
                const row = document.querySelector('.ca-q__opt[data-on]');
                const badge = row.querySelector('.ca-q__letter');
                const page = document.querySelector('.ca-q__page');
                const enabled = document.querySelector('.ca-q__chev:not([disabled])');
                const disabled = document.querySelector('.ca-q__chev[disabled]');
                return {
                    theme: document.documentElement.dataset.theme,
                    token: cs(prompt).getPropertyValue('--ca-text').trim(),
                    bg: cs(card).backgroundColor,
                    prompt: cs(prompt).color,
                    option: cs(option).color,
                    row: cs(row).backgroundColor,
                    badge: cs(badge).backgroundColor,
                    badgeText: cs(badge).color,
                    page: cs(page).color,
                    enabled: cs(enabled).color,
                    disabled: cs(disabled).color,
                };
            }""")
        finally:
            browser.close()


def _paint(value, onto):
    rgb, alpha = _channels(value)
    return _composite(rgb, alpha, onto)


def _chrome(got):
    bg, bg_a = _channels(got["bg"])
    assert bg_a == 1, got
    row = _paint(got["row"], bg)
    badge = _paint(got["badge"], row)
    ink = _paint(got["badgeText"], badge)
    return {
        "badge_row": _contrast(badge, row),
        "badge_ink": _contrast(ink, badge),
        "page": _contrast(_paint(got["page"], bg), bg),
        "enabled": _contrast(_paint(got["enabled"], bg), bg),
        "disabled": _contrast(_paint(got["disabled"], bg), bg),
    }


def _ratios(got):
    bg, bg_a = _channels(got["bg"])
    assert bg_a == 1, got
    prompt, prompt_a = _channels(got["prompt"])
    option, option_a = _channels(got["option"])
    return (
        _contrast(_composite(prompt, prompt_a, bg), bg),
        _contrast(_composite(option, option_a, bg), bg),
    )


def test_dark_setup_ask_card_text_contrast():
    got = _measure("dark")
    prompt_ratio, option_ratio = _ratios(got)
    assert got["theme"] == "dark"
    assert got["token"] == "rgba(255,255,255,.9)", got
    assert prompt_ratio >= 4.5, (got, prompt_ratio)
    assert option_ratio >= 4.5, (got, option_ratio)
    chrome = _chrome(got)
    assert chrome["badge_row"] >= 4.5, (got, chrome)
    assert chrome["badge_ink"] >= 4.5, (got, chrome)
    assert chrome["page"] >= 4.5 and chrome["enabled"] >= 4.5, (got, chrome)
    assert chrome["disabled"] < chrome["enabled"], (got, chrome)


def test_light_setup_ask_card_text_contrast():
    got = _measure("light")
    prompt_ratio, option_ratio = _ratios(got)
    assert got["theme"] == "light"
    assert got["token"] == "rgba(0,0,0,.9)", got
    assert prompt_ratio >= 4.5, (got, prompt_ratio)
    assert option_ratio >= 4.5, (got, option_ratio)
    chrome = _chrome(got)
    assert chrome["badge_row"] >= 4.5, (got, chrome)
    assert chrome["badge_ink"] >= 4.5, (got, chrome)
    assert chrome["page"] >= 4.5 and chrome["enabled"] >= 4.5, (got, chrome)
    assert chrome["disabled"] < chrome["enabled"], (got, chrome)
