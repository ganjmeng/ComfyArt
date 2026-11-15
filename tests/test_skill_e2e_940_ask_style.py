"""#940 second cut: real Full App mock measurements and selected/unselected evidence.
No external model, no new images. Reuses the official youtube-banner app fixtures.
"""
import json
import os
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from test_skill_e2e_934_youtube_banner_card2 import (
    app_url, mock_ws, agent, ws_forward, no_paid_keys, CARD1, _open_youtube,
)
from test_skill_param_guard_e2e_956_957 import _call
from ask_card_pages import wait_dock, inspect_scroll_card, answer_scroll_card

MEASURE = """el => {
 const style = (sel, props, pseudo) => {
   const node = sel ? el.querySelector(sel) : el;
   const s = getComputedStyle(node, pseudo);
   return Object.fromEntries(props.map(k => [k, s[k]]));
 };
 return {
   card: style(null,['maxHeight','minHeight','borderRadius','borderTopWidth','borderTopColor','backgroundColor','paddingLeft','paddingRight','paddingBottom','overflow']),
   body: style('.ca-q__body',['overflowY','minHeight','scrollbarWidth','scrollbarColor']),
   scrollbar: style('.ca-q__body',['width'],'::-webkit-scrollbar'),
   thumb: style('.ca-q__body',['backgroundColor','borderRadius'],'::-webkit-scrollbar-thumb'),
   label: style('.ca-q__label',['color','fontSize']),
   icon: style('.ca-q__label svg',['width','height','strokeWidth','color']),
   page: style('.ca-q__page',['color','fontSize']),
   disabledArrow: style('.ca-q__chev:disabled',['color','opacity']),
   prompt: style('.ca-q__prompt',['fontSize','lineHeight','color']),
   row: style('.ca-q__opt',['height','minHeight','paddingLeft','paddingRight','borderRadius','backgroundColor']),
   text: style('.ca-q__text',['fontSize','color']),
   badge: style('.ca-q__letter',['width','height','backgroundColor','color']),
   primary: style('.ca-q__submit',['height','minWidth','borderRadius','backgroundColor','color','fontSize','gap']),
   key: style('.ca-q__key',['width','height','fontSize']),
   skip: style('.ca-q__skip',['width','height','backgroundColor','borderTopColor','borderTopWidth','color']),
   footer: style('.ca-q__foot',['gap']),
   scroll: {height:el.querySelector('.ca-q__body').clientHeight, content:el.querySelector('.ca-q__body').scrollHeight},
 };
}"""


@pytest.mark.parametrize('lang', ['zh', 'en'])
async def test_fullapp_940_numeric_styles_and_selected_state(app_url, mock_ws, agent, ws_forward, lang):
    async def steps(a, turn, emit):
        a.asked = await _call(a, emit, 'ask_user', CARD1[lang], 1)
        a.asked2 = await _call(a, emit, 'ask_user', {
            'questions':[{'id':'numeric940', 'prompt':'Question / 问题',
                'options':[{'id':k,'label':k} for k in ('A','B','C')],
                'allow_other':True}], 'allow_skip':True, 'page_count':1}, 2)
    agent.steps = steps
    out = os.environ.get('CA940_EVIDENCE')
    async with async_playwright() as p:
        browser, pg = await _open_youtube(p, app_url, lang, ws_forward)
        try:
            await pg.set_viewport_size({'width':1280,'height':900})
            card = await wait_dock(pg)
            await inspect_scroll_card(pg, 3)
            await pg.wait_for_timeout(400)
            unselected = await card.evaluate(MEASURE)
            if out:
                Path(out).mkdir(parents=True,exist_ok=True)
                await pg.screenshot(path=str(Path(out)/f'unselected-{lang}.png'))
                await card.screenshot(path=str(Path(out)/f'unselected-card-{lang}.png'))
            await card.locator('button.ca-q__opt').first.click()
            selected = await card.locator('button.ca-q__opt[data-on]').first.evaluate("""el => {
                const b=getComputedStyle(el.querySelector('.ca-q__letter'));
                return {row:getComputedStyle(el).backgroundColor,bg:b.backgroundColor,fg:b.color};
            }""")
            if out:
                await pg.screenshot(path=str(Path(out)/f'selected-{lang}.png'))
                await card.screenshot(path=str(Path(out)/f'selected-card-{lang}.png'))
                (Path(out)/f'measured-{lang}.json').write_text(json.dumps({'unselected':unselected,'selected':selected},indent=2))
            assert selected == {'row':'rgb(235, 235, 235)','bg':'rgb(44, 44, 44)','fg':'rgb(255, 255, 255)'}
            assert_numeric_table(unselected)
            # Invert the old dock gray-badge regression on the real mounted app.
            mutation = await pg.add_style_tag(content='.ca-chat__dock .ca-q__opt[data-on] .ca-q__letter {background:#F5F5F5 !important;color:#6F6F6F !important}')
            mutated = await card.locator('button.ca-q__opt[data-on] .ca-q__letter').first.evaluate('el => getComputedStyle(el).backgroundColor')
            with pytest.raises(AssertionError):
                assert mutated == 'rgb(44, 44, 44)'
            await mutation.evaluate('el => el.remove()')
            # Still the same scrolling card; advance only by scrolling before final submit.
            await card.get_by_test_id('question-body').evaluate("el => {el.scrollTop=0;el.dispatchEvent(new Event('scroll'))}")
            await answer_scroll_card(pg, (0,0,0))
            await pg.wait_for_function("() => document.querySelector('.ca-chat__dock .ca-q__prompt')?.textContent === 'Question / 问题'")
            plain = await card.evaluate('''el => {
                const rows=[...el.querySelectorAll('button.ca-q__opt')];
                return {height:getComputedStyle(rows[0]).height,
                        pitch:rows[1].getBoundingClientRect().top-rows[0].getBoundingClientRect().top,
                        promptPitch:rows[0].getBoundingClientRect().top-el.querySelector('.ca-q__prompt').getBoundingClientRect().top,
                        cardHeight:el.getBoundingClientRect().height};
            }''')
            assert plain['height'] == '36px'
            assert plain['pitch'] == 40
            assert plain['promptPitch'] == 36
            assert plain['cardHeight'] < 442  # no forced min-height for a single question
            old_gap = await pg.add_style_tag(content='.ca-chat__dock .ca-q__block {gap:5px !important}')
            inverted_pitch = await card.evaluate("el => el.querySelector('.ca-q__opt').getBoundingClientRect().top-el.querySelector('.ca-q__prompt').getBoundingClientRect().top")
            with pytest.raises(AssertionError):
                assert inverted_pitch == 36
            assert inverted_pitch == 25
            await old_gap.evaluate('el => el.remove()')
            if out:
                (Path(out)/f'plain-{lang}.json').write_text(json.dumps(plain,indent=2))
            assert unselected['scroll']['content'] > unselected['scroll']['height']
            assert mock_ws['submits'] == [] and mock_ws['quotes'] == []
        finally:
            await browser.close()


def assert_numeric_table(m):
    """Table 6857404832; description rows grow naturally and do not clip text."""
    expected = {
        'card': {'maxHeight':'442px','minHeight':'0px','borderRadius':'18px',
                 'borderTopWidth':'1px','borderTopColor':'rgb(229, 229, 229)',
                 'backgroundColor':'rgb(255, 255, 255)','paddingLeft':'16px',
                 'paddingRight':'12px','paddingBottom':'14px','overflow':'hidden'},
        'body': {'overflowY':'auto'},
        'scrollbar': {'width':'6px'},
        'thumb': {'backgroundColor':'rgb(223, 224, 226)','borderRadius':'3px'},
        'label': {'color':'rgb(115, 115, 115)','fontSize':'14px'},
        'icon': {'width':'14px','height':'14px','strokeWidth':'1.5px','color':'rgb(115, 115, 115)'},
        'page': {'color':'rgb(115, 115, 115)','fontSize':'14px'},
        'disabledArrow': {'color':'rgb(197, 197, 197)','opacity':'1'},
        'prompt': {'fontSize':'14px','color':'rgb(25, 25, 25)'},
        'row': {'minHeight':'36px','paddingLeft':'9px','paddingRight':'9px','borderRadius':'8px'},
        'text': {'fontSize':'14px','color':'rgb(25, 25, 25)'},
        'badge': {'width':'20px','height':'20px','backgroundColor':'rgb(245, 245, 245)','color':'rgb(111, 111, 111)'},
        'primary': {'height':'32px','borderRadius':'10px','backgroundColor':'rgb(44, 44, 44)',
                    'color':'rgb(255, 255, 255)','fontSize':'14px','gap':'8px'},
        'key': {'width':'14px','height':'14px','fontSize':'14px'},
        'skip': {'width':'60px','height':'32px','backgroundColor':'rgb(255, 255, 255)',
                 'borderTopColor':'rgb(229, 229, 229)','borderTopWidth':'1px','color':'rgb(25, 25, 25)'},
        'footer': {'gap':'8px'},
    }
    for section,props in expected.items():
        for prop,value in props.items():
            assert m[section][prop] == value, (section,prop,m[section][prop],value)
