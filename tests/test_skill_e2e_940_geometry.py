"""#940 HOLD geometry: actual Full App native scrollbar + raster ink anchors.

No new images/model calls; screenshots are browser captures, not fake markup.
CA940_GEOMETRY keeps original-CSS captures separate from track-paint diagnostics.
The proposed ink/THUMB anchors are measured, not a declaration of design approval.
"""
import io
import json
import os
from pathlib import Path

import pytest
from PIL import Image
from playwright.async_api import async_playwright

from test_skill_e2e_934_youtube_banner_card2 import (
    app_url, mock_ws, agent, ws_forward, no_paid_keys, CARD1, _open_youtube,
)
from test_skill_param_guard_e2e_956_957 import _call
from ask_card_pages import wait_dock

MEASURE = 'el => {\n const r=n=>{let b=n.getBoundingClientRect();return {x:b.x,y:b.y,left:b.left,top:b.top,right:b.right,bottom:b.bottom,width:b.width,height:b.height}};\n const st=n=>{let s=getComputedStyle(n);return Object.fromEntries([\'borderTopWidth\',\'borderRightWidth\',\'borderBottomWidth\',\'borderLeftWidth\',\'paddingTop\',\'paddingRight\',\'paddingBottom\',\'paddingLeft\',\'gap\',\'lineHeight\',\'fontSize\',\'height\',\'overflowY\',\'scrollbarWidth\',\'scrollbarColor\'].map(k=>[k,s[k]]))};\n const glyph=n=>{let range=document.createRange();range.selectNodeContents(n);return [...range.getClientRects()].map(b=>({left:b.left,top:b.top,right:b.right,bottom:b.bottom,width:b.width,height:b.height}))};\n const body=el.querySelector(\'.ca-q__body\');\n const blocks=[...el.querySelectorAll(\'.ca-q__block\')].map(n=>{const opts=[...n.querySelectorAll(\'.ca-q__opt\')];const last=opts.at(-1);const descs=[...n.querySelectorAll(\'.ca-q__desc\')];return {outer:r(n),outerStyle:st(n),prompt:r(n.querySelector(\'.ca-q__prompt\')),promptStyle:st(n.querySelector(\'.ca-q__prompt\')),promptTextRanges:glyph(n.querySelector(\'.ca-q__prompt\')),input:r(last.querySelector("input")),lastOption:r(last),lastOptionStyle:st(last),lastOptionKind:last.hasAttribute(\'data-other\')?\'input/Other\':\'choice\',lastChoice:r(n.querySelectorAll(\'button.ca-q__opt\')[n.querySelectorAll(\'button.ca-q__opt\').length-1]),descriptions:descs.map(d=>({text:d.textContent,rect:r(d),ranges:glyph(d)})),options:opts.map(o=>({rect:r(o),style:st(o),text:o.textContent}))}});\n const bs=getComputedStyle(body);const cs=getComputedStyle(el);\n return {head:r(el.querySelector(".ca-q__head")),foot:r(el.querySelector(".ca-q__foot")),card:r(el),cardStyle:st(el),body:r(body),bodyStyle:st(body),scrollTop:body.scrollTop,scrollHeight:body.scrollHeight,clientHeight:body.clientHeight,offsetWidth:body.offsetWidth,clientWidth:body.clientWidth,clientLeft:body.clientLeft,trackGutter:body.offsetWidth-body.clientWidth-parseFloat(bs.borderLeftWidth)-parseFloat(bs.borderRightWidth),cardRightInnerEdge:el.getBoundingClientRect().right-parseFloat(cs.borderRightWidth),bodyRightInnerEdge:body.getBoundingClientRect().right-parseFloat(bs.borderRightWidth),pseudoScrollbarWidth:getComputedStyle(body,\'::-webkit-scrollbar\').width,blocks,pairs:blocks.slice(0,-1).map((b,i)=>({from:i+1,to:i+2,lastOptionTop_to_promptTop:blocks[i+1].prompt.top-b.lastOption.top,lastOptionBottom_to_promptTop:blocks[i+1].prompt.top-b.lastOption.bottom,lastChoiceTop_to_promptTop:blocks[i+1].prompt.top-b.lastChoice.top,lastChoiceBottom_to_promptTop:blocks[i+1].prompt.top-b.lastChoice.bottom,outerBottom_to_nextPromptTop:blocks[i+1].prompt.top-b.outer.bottom}))};\n}'


def ink_top(image, rect, threshold, inset=0):
    """Raster INK, not DOM Range or line box; exclude borders and badge."""
    x0, x1 = int(rect['left']) + inset, int(rect['right']) - inset
    y0, y1 = int(rect['top']) + inset, int(rect['bottom']) - inset
    pixels = image.load()
    ys = [y for y in range(y0, y1)
          if sum(min(pixels[x, y][:3]) < threshold for x in range(x0, x1)) > 2]
    assert ys, ('no ink', rect)
    return min(ys)


def raster_metrics(png, m, pair):
    image = Image.open(io.BytesIO(png)).convert('RGB')
    assert image.size == (1280, 900)
    b, n = m['blocks'][pair], m['blocks'][pair + 1]
    last_ink = ink_top(image, b['input'], 240, inset=2)
    prompt_ink = ink_top(image, n['prompt'], 170)
    # Native thumb color in the reserved gutter, excluding arrow-button areas.
    gutter_left = int(m['bodyRightInnerEdge'] - m['trackGutter'])
    track_right = int(m['bodyRightInnerEdge'])
    px = image.load()
    hits = [(x, y) for y in range(int(m['body']['top']) + 20, int(m['body']['bottom']) - 20)
            for x in range(gutter_left, track_right)
            if px[x, y] == (223, 224, 226)]
    assert len(hits) > 100, ('native thumb must really be visible', len(hits))
    thumb_right = max(x for x, y in hits) + 1  # half-open boundary
    return {'lastPlaceholderInkTop': last_ink, 'nextPromptInkTop': prompt_ink,
            'inkPitch': prompt_ink - last_ink, 'trackRight': track_right,
            'thumbRight': thumb_right, 'thumbPaintWidth': len({x for x, y in hits}),
            'cardRightInner': m['cardRightInnerEdge'],
            'trackOffset': m['cardRightInnerEdge'] - track_right,
            'thumbOffset': m['cardRightInnerEdge'] - thumb_right}


def assert_ink_pitch(r):
    assert abs(r['inkPitch'] - 36) <= 2, r


def assert_thumb_offset(r):
    assert 2 <= r['thumbOffset'] <= 3, r


def numeric_geometry(value):
    """Ignore paint/style strings when proving a color-only diagnostic."""
    if isinstance(value, dict):
        return {k: numeric_geometry(v) for k, v in value.items()
                if isinstance(v, (dict, list, int, float))}
    if isinstance(value, list):
        return [numeric_geometry(v) for v in value]
    return value


def assert_unclipped(m):
    for b in m['blocks']:
        assert b['options'][0]['rect']['top'] - b['prompt']['bottom'] == 16
        assert b['lastOption']['bottom'] == b['outer']['bottom']
        for desc in b['descriptions']:
            host = next(o['rect'] for o in b['options']
                        if o['rect']['top'] <= desc['rect']['top'] < o['rect']['bottom'])
            assert desc['rect']['bottom'] <= host['bottom'] - 8
            for line in desc['ranges']:
                assert line['left'] >= desc['rect']['left'] - 1
                assert line['right'] <= desc['rect']['right'] + 1
                assert line['bottom'] <= desc['rect']['bottom'] + 1
    for p in m['pairs']:
        assert p['lastOptionBottom_to_promptTop'] == 9
        assert p['lastOptionTop_to_promptTop'] == 45
    assert m['body']['right'] <= m['cardRightInnerEdge']
    assert m['blocks'][0]['outer']['left'] >= m['card']['left'] + 1
    assert m['blocks'][0]['outer']['right'] < m['bodyRightInnerEdge']


@pytest.mark.parametrize('lang', ['zh', 'en'])
async def test_fullapp_940_cross_question_ink_and_native_thumb(
    app_url, mock_ws, agent, ws_forward, monkeypatch, lang,
):
    async def steps(a, turn, emit):
        a.asked = await _call(a, emit, 'ask_user', CARD1[lang], 1)
    agent.steps = steps
    out = Path(os.environ['CA940_GEOMETRY']) if os.environ.get('CA940_GEOMETRY') else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    records = []
    async with async_playwright() as p:
        launch = p.chromium.launch
        async def visible_launch(**kw):
            return await launch(ignore_default_args=['--hide-scrollbars'],
                args=['--disable-features=OverlayScrollbar,OverlayScrollbars'], **kw)
        monkeypatch.setattr(p.chromium, 'launch', visible_launch)
        browser, pg = await _open_youtube(p, app_url, lang, ws_forward)
        try:
            await pg.set_viewport_size({'width': 1280, 'height': 900})
            card = await wait_dock(pg)
            await pg.wait_for_timeout(300)
            assert await card.locator('.ca-q__block').count() == 3
            assert await pg.evaluate('devicePixelRatio') == 1
            body = card.locator('.ca-q__body')
            async def capture(name, pair):
                # Align both anchors visibly in this SAME snapshot, preserving
                # the recorded numeric scrollTop rather than mixing frames.
                offset = await card.evaluate("""(el,i) => {
                    const body=el.querySelector('.ca-q__body');
                    const b=el.querySelectorAll('.ca-q__block')[i];
                    const d=b.querySelector('.ca-q__opt:last-child');
                    return Math.max(0,body.scrollTop+d.getBoundingClientRect().top-body.getBoundingClientRect().top-70);
                }""", pair)
                await body.evaluate('(el,v)=>{el.scrollTop=v;el.dispatchEvent(new Event("scroll"))}', offset)
                await pg.wait_for_timeout(120)
                m = await card.evaluate(MEASURE)
                png = await pg.screenshot()
                r = raster_metrics(png, m, pair)
                b, n = m['blocks'][pair], m['blocks'][pair + 1]
                assert b['lastOption']['top'] >= m['body']['top']
                assert n['prompt']['bottom'] <= m['body']['bottom']
                if out:
                    (out / f'{lang}-{name}.png').write_bytes(png)
                record = {'name': name, 'pair': pair, 'geometry': m, 'raster': r}
                records.append(record)
                return m, r
            for state in ('unselected', 'selected'):
                if state == 'selected':
                    for b in await card.locator('.ca-q__block').all():
                        await b.locator('button.ca-q__opt').first.click()
                    assert await card.locator('button.ca-q__opt[data-on]').count() == 3
                for pair in (0, 1):
                    m, r = await capture(f'{state}-q{pair+1}-q{pair+2}', pair)
                    assert_unclipped(m)
                    assert_ink_pitch(r)
                    assert_thumb_offset(r)
                    assert r['trackOffset'] == 0
                    assert r['thumbPaintWidth'] == 6
                    assert m['bodyStyle']['gap'] == '9px'
                    assert m['blocks'][0]['outerStyle']['gap'] == '16px'
            for pair in (0, 1):
                assert numeric_geometry(records[pair]['geometry']) == numeric_geometry(records[2 + pair]['geometry'])
                assert records[pair]['raster'] == records[2 + pair]['raster']
            fixed, _ = await capture('before-mutations', 0)
            # Roll back only BODY inter-question gap. The actual same-anchor
            # raster assertion must go red; within-question spacing stays16.
            mutation = await pg.add_style_tag(content='.ca-chat__dock .ca-q__body {gap:16px !important}')
            old, old_r = await capture('mutation-old-body-gap', 0)
            assert old['pairs'][0]['lastOptionBottom_to_promptTop'] == 16
            with pytest.raises(AssertionError):
                assert_ink_pitch(old_r)
            assert old_r['inkPitch'] - records[-2]['raster']['inkPitch'] == 7
            await mutation.evaluate('el=>el.remove()')
            # Roll back scrollbar compensation: preserve width/typography,
            # but make the actual RASTER thumb offset wrong again.
            mutation = await pg.add_style_tag(content='.ca-chat__dock .ca-q__body {margin-right:0 !important;padding-right:8px !important}')
            old, old_r = await capture('mutation-old-scrollbar-position', 0)
            with pytest.raises(AssertionError):
                assert_thumb_offset(old_r)
            assert old_r['thumbOffset'] == 14
            assert old_r['trackOffset'] == 12
            # Negative-margin compensation must not resize content, change
            # wrapping, or move header/footer. Compare real DOM before/rollback.
            assert old['head'] == fixed['head'] and old['foot'] == fixed['foot']
            for b, prev in zip(old['blocks'], fixed['blocks']):
                assert b['outer']['width'] == prev['outer']['width']
                assert b['outer']['height'] == prev['outer']['height']
                assert [d['rect']['height'] for d in b['descriptions']] == [d['rect']['height'] for d in prev['descriptions']]
            await mutation.evaluate('el=>el.remove()')
            fixed, r = await capture('restored', 0)
            # Separate optional PAINT diagnostic; original-CSS captures above
            # are unmodified. Native track paint only, no fake scrollbar.
            diagnostic = await pg.add_style_tag(content='.ca-chat__dock .ca-q__body {scrollbar-color:#DFE0E2 #dceeff !important}')
            await pg.wait_for_timeout(120)
            diag = await card.evaluate(MEASURE)
            assert diag['body'] == fixed['body']
            assert numeric_geometry(diag) == numeric_geometry(fixed)
            if out:
                await pg.screenshot(path=str(out / f'{lang}-diagnostic-native-track.png'))
            await diagnostic.evaluate('el=>el.remove()')
            assert mock_ws['submits'] == [] and mock_ws['quotes'] == []
        finally:
            if out:
                (out / f'measurements-{lang}.json').write_text(json.dumps({
                    'viewport': [1280, 900], 'deviceScaleFactor': 1,
                    'launch': {'ignore_default_args': ['--hide-scrollbars'],
                               'args': ['--disable-features=OverlayScrollbar,OverlayScrollbars']},
                    'records': records}, indent=2, ensure_ascii=False))
            await browser.close()
