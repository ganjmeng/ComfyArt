"""#940 second cut: mock DOM computed styles, no server or paid calls.

The shared icon factory emits an SVG stroke-width attribute (1.75). Styling
only the wrapper span does not override it. The dock header needs 1.5 directly
on the SVG per design numeric table 6857404832; other icons stay unchanged.
"""
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SVG_RULE = ".ca-chat__dock .ca-q__label .ca-icon svg { stroke-width: 1.5; }"
MOCK = """<style>.ca-icon { display:inline-flex }.ca-icon svg { width:100%;height:100% }</style>
<div class="ca-chat__dock"><div class="ca-q__label"><span class="ca-icon">
<svg viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><circle cx="12" cy="12" r="9"/></svg>
</span>Question</div></div>
<div id="outside"><svg stroke-width="1.75"></svg></div>"""


async def _measure(css):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(MOCK)
            await page.add_style_tag(content=css)
            return await page.evaluate("""() => {
                const svg = document.querySelector('.ca-q__label svg');
                const s = getComputedStyle(svg);
                return {stroke: s.strokeWidth, width: s.width, height: s.height,
                        color: s.color, outside: getComputedStyle(document.querySelector('#outside svg')).strokeWidth};
            }""")
        finally:
            await browser.close()


async def test_dock_question_svg_matches_940_numeric_table():
    got = await _measure((ROOT / "src/styles/shell.css").read_text())
    assert got == {"stroke": "1.5px", "width": "14px", "height": "14px",
                   "color": "rgb(115, 115, 115)", "outside": "1.75px"}


async def test_mutation_span_only_stroke_fails_the_940_lock():
    css = (ROOT / "src/styles/shell.css").read_text()
    assert SVG_RULE in css
    got = await _measure(css.replace(SVG_RULE, ""))
    # Reverting the SVG rule restores the wrong 1.75 stroke despite span=1.5.
    assert got["stroke"] == "1.75px"
    assert got["stroke"] != "1.5px"
