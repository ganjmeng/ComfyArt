"""#994 actual Full App, scripted real LocalLlmProvider+MCP+page+mock provider.

Assertions inspect real provider POST payload, not merely normalized tool args.
Rollback disables the real production user_ratio recognizer for typed skills;
the SAME submission assertion must fail (photo4:5 is honestly a default control).
CA994_SHOTS retains real app PNG/JSON; no fabricated Lovart comparison.
"""
import json
import os
import re
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from test_e2e_fullapp_982 import (
    app_url, mock_ws, ws_forward, built_dist, local_agent, no_paid_keys,
    SUBJECT, _add_flare_models, _png, _gen_args,
)
from test_a_class_fullapp_e2e_911 import (
    _open_skill, _send_default, _wait, _attached, _calls, _refs, _reply, _last_tool_json,
)

from test_skill_param_guard_e2e_956_957 import _bind_open_project


async def open_ratio_skill(p, app_url, lang, sid, sockets, text, reference=None):
    """Official actual app flow, supporting BOTH text and textarea skill notes.
    The older911 helper assumes textarea and its fixed skill-label map lacks
    these three typed skills; do not alter that unrelated shared fixture."""
    browser = await p.chromium.launch()
    try:
        ctx = await browser.new_context(viewport={'width':1280,'height':900}, locale='zh-CN' if lang=='zh' else 'en-US')
        await ctx.route_web_socket(re.compile(r'/ws(\?|$)'), lambda ws:sockets.append(ws))
        pg = await ctx.new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','light')")
        await pg.goto(app_url)
        await pg.get_by_test_id('rail-skills').click()
        await pg.get_by_test_id('skills-wall').wait_for(timeout=20000)
        tile = pg.locator(f'[data-testid="skills-wall-card"][data-skill="{sid}"]')
        await tile.scroll_into_view_if_needed(); await tile.hover()
        await tile.get_by_test_id('skills-card-try').click()
        dlg = pg.locator(f'[data-testid="skill-run-dialog"][data-skill="{sid}"]')
        await dlg.wait_for(timeout=15000)
        if reference:
            await dlg.locator('input[type=file]').first.set_input_files(str(reference))
        await dlg.locator('textarea, input[data-type="text"]').first.fill(text)
        await dlg.get_by_test_id('skill-run-go').click()
        await pg.locator('.ca-composer__input').wait_for(timeout=20000)
        await pg.get_by_test_id('composer-skill-chip').wait_for(timeout=15000)
        await pg.locator('.ca-composer__mode[data-agent="local-llm"]').wait_for(timeout=20000)
        await _bind_open_project(pg)
        return browser,pg
    except BaseException:
        await browser.close()
        raise


CASES = [
    ('banner-design-director', '21:9', 'zh', '请用21:9横幅，保留参考图'),
    ('photo-split-poster', '4:5', 'en', 'Use 4:5 for the photo split; keep the reference'),
    ('logo-abstract', '4:5', 'zh', '要4:5，不要默认方图；保留参考图'),
    ('naive-illustration', '9:16', 'en', 'Use 9:16, keep the reference'),
    ('photo-split-poster', '9:16', 'zh', '照片分割改用9:16，保留参考图'),
]


def assert_submitted_ratio(submit, ratio):
    body = submit[1]
    if 'aspect_ratio' in body:
        assert body['aspect_ratio'] == ratio, body
    else:
        from fractions import Fraction
        w, h = map(int, body['size'].replace('x', '*').split('*'))
        a, b = map(int, ratio.split(':'))
        assert abs(Fraction(w, h) / Fraction(a, b) - 1) < 0.01, body


def script(state, sid, model=None, refusal=False):
    def respond(messages, n):
        refs = _attached(messages)
        if refs:
            state['attached'] = refs
        if n == 0:
            return _calls(('skill', {'action': 'read', 'name': sid}))
        if n == 1:
            # Deliberately omit ratio and dimensions. Only the USER'S actual
            # turn, not the scripted model's guesses, can supply the override.
            return _calls(('generate_image', {'skill': sid, 'prompt': 'A local ratio test design',
                'refs': [] if model else _refs(state.get('attached') or []), **({'model': model} if model else {})}))
        if refusal:
            # Show the actual refusal/tool error, not an invented success reply.
            return _reply(str(messages[-1].get('content', '')))
        if n == 2:
            ids = (_last_tool_json(messages, 'ids') or {}).get('ids') or []
            return _calls(('wait_generation', {'ids': ids}))
        return _reply('Mock ratio test complete / 本地比例验证完成（非真实付费输出）')
    return respond


@pytest.mark.parametrize('rollback', [False, True], ids=['fixed', 'rollback-user-override'])
@pytest.mark.parametrize('sid,ratio,lang,text', CASES, ids=[f'{s}-{r}' for s,r,_,_ in CASES])
async def test_fullapp_994_user_ratio_reaches_real_provider_submit(
    app_url, mock_ws, local_agent, ws_forward, monkeypatch, sid, ratio, lang, text, rollback,
):
    from ComfyArt.bot import skill_output as so
    import test_e2e_comment_edit as ce
    _add_flare_models(monkeypatch)
    w, h = so.TYPED_USER_RATIOS_994[ratio]
    # Fake output follows the ACTUAL submitted default under rollback too;
    # never illustrate a successful requested ratio while the POST differs.
    output = so.OUTPUTS[sid] if rollback else {'width':w,'height':h}
    monkeypatch.setattr(ce, 'RESULT', _png(output['width'], output['height']))
    if rollback:
        real = so.user_ratio
        monkeypatch.setattr(so, 'user_ratio', lambda skill, value: None if skill in so.TYPE_OUTPUTS_982 else real(skill, value))
    _, state = local_agent
    state['respond'] = script(state, sid)
    out = Path(os.environ['CA994_SHOTS']) if os.environ.get('CA994_SHOTS') else None
    name = f'{sid}-{ratio.replace(":", "x")}-{lang}-' + ('rollback' if rollback else 'fixed')
    async with async_playwright() as p:
        browser, pg = await open_ratio_skill(p, app_url, lang, sid, ws_forward, text, SUBJECT)
        try:
            await pg.set_viewport_size({'width': 1280, 'height': 900})
            await _send_default(pg)
            await _wait(lambda: len(mock_ws['submits']) >= 1, timeout=60)
            await _wait(lambda: state.get('wait'), timeout=60)
            gens = _gen_args(state)
            assert len(gens) == 1 and len(mock_ws['submits']) == 1
            refs = _refs(state.get('attached') or [])
            assert refs and gens[0]['refs'] == refs and gens[0]['count'] == 1
            payload = mock_ws['submits'][0][1]
            submitted_refs = payload.get('images') or ([payload['image']] if payload.get('image') else [])
            assert len(submitted_refs) == len(refs) == 1, payload
            assert payload.get('num_images', 1) == 1
            # No pinned model table/routing mutation. Ref edits use the existing
            # production Auto edit selection; record exactly which model ran.
            assert mock_ws['submits'][0][0] in ce.FIXTURE
            control = so.OUTPUTS[sid]['ratio'] == ratio
            if rollback and not control:
                with pytest.raises(AssertionError):
                    assert_submitted_ratio(mock_ws['submits'][0], ratio)
                assert gens[0]['ratio'] == so.OUTPUTS[sid]['ratio']
            else:
                assert_submitted_ratio(mock_ws['submits'][0], ratio)
                assert (gens[0]['width'], gens[0]['height'], gens[0]['ratio']) == (w,h,ratio)
            if out:
                out.mkdir(parents=True,exist_ok=True)
                await pg.evaluate('() => { const ed=window.__caEditor; ed.selectNone(); ed.zoomToFit({animation:{duration:0}}) }')
                await pg.wait_for_timeout(200)
                await pg.screenshot(path=str(out/f'{name}.png'))
                (out/f'{name}.json').write_text(json.dumps({'skill':sid,'requested':ratio,'lang':lang,
                    'rollback':rollback,'already_default_control':control,'normalized':gens,
                    'actual_provider_posts':mock_ws['submits'],'mock_only':True,
                    'real_provider_runtime_tested':False},ensure_ascii=False,indent=2))
        finally:
            await browser.close()


def assert_clean_refusal_text(text, expected, lang):
    # Actual assistant node, not the entire chat/user bubble or mere keywords.
    assert text == expected
    assert not re.search(r'ValueError|TypeError|KeyError|\[object Object\]|generation_succeeded|user_message|\[tool error\]|[{}]|["\'](?:status|submitted|kind|error)["\']\s*:', text)
    if lang == 'en':
        assert not re.search(r'[\u4e00-\u9fff]', text)
    else:
        assert not re.search(r'[A-Za-z]{2,}', text)


@pytest.mark.parametrize('lang', ['zh', 'en'])
@pytest.mark.parametrize('rollback_display', [False, True], ids=['fixed-display', 'rollback-display-boundary'])
@pytest.mark.parametrize('unsupported_schema', [False, True], ids=['unrecognized-ratio', 'real-nano-schema'])
async def test_fullapp_994_explicit_refusal_no_silent_submit(
    app_url, mock_ws, local_agent, ws_forward, monkeypatch, unsupported_schema, lang, rollback_display,
):
    import test_e2e_comment_edit as ce
    from ComfyArt.bot import local_llm as llm
    from ComfyArt.bot.ratio_display import ratio_refusal_display
    from ComfyArt.bot.skill_output import ratio_refusal_994
    _add_flare_models(monkeypatch)
    model = 'google/nano-banana-2.1/text-to-image' if unsupported_schema else None
    if model and not any(m['model_id'] == model for m in ce.MODELS):
        monkeypatch.setattr(ce, 'MODELS', [*ce.MODELS, ce.FIXTURE[model]])
    if rollback_display:
        # Real old behavior: both production chat/relay display seams become
        # identity/no-op again. SAME DOM assertion below must turn red.
        monkeypatch.setattr(llm, 'ratio_refusal_display', lambda text, lang: None)
    _, state = local_agent
    state['respond'] = script(state, 'banner-design-director', model=model, refusal=True)
    if unsupported_schema:
        text = ('请用1:2，模型google/nano-banana-2.1/text-to-image；不要将上传图作为参考图。' if lang=='zh' else
                'Use 1:2 with google/nano-banana-2.1/text-to-image; do not use the uploaded image as a reference.')
    else:
        text = '请用7:5，不要静默改成默认比例' if lang=='zh' else 'Use 7:5; do not silently change to the default ratio.'
    if unsupported_schema:
        expected = json.loads((Path(__file__).resolve().parents[1]/f'src/locales/{lang}.json').read_text())['wsErr.userRatioUnsupported']
    else:
        expected = ratio_refusal_display(json.dumps(ratio_refusal_994('7:5'),ensure_ascii=False),lang)
    assert expected
    out = Path(os.environ['CA994_SHOTS']) if os.environ.get('CA994_SHOTS') else None
    async with async_playwright() as p:
        browser, pg = await open_ratio_skill(p, app_url, lang, 'banner-design-director', ws_forward, text, SUBJECT)
        try:
            responses = []
            async def record_response(response):
                if '/wavespeed/run' in response.url or '/wavespeed/quote' in response.url:
                    responses.append({'path':response.url.split('/comfyart/')[-1], 'status':response.status, 'body':await response.json()})
            pg.on('response',record_response)
            await _send_default(pg)
            await _wait(lambda: state.get('result') is not None, timeout=60)
            assert mock_ws['submits'] == []
            replies = pg.locator('.ca-chat .ca-md:visible')
            await replies.last.wait_for()
            actual = await replies.all_inner_texts()
            def check_visible():
                assert len(actual)==1, actual
                assert_clean_refusal_text(actual[0],expected,lang)
            if rollback_display:
                # Prove the real historic display defect, not a random/missing
                # node failure or an artificial forced assertion.
                assert len(actual)==1
                if unsupported_schema:
                    # Legacy CN takes the older agent-instruction wrapper;
                    # legacy EN retains ValueError. BOTH are display leaks.
                    assert actual[0].startswith(('ValueError: ', '[tool error] ')), actual
                else:
                    assert 'user_message' in actual[0] and 'generation_succeeded' in actual[0], actual
                    assert 'Requested ratio' in actual[0] and re.search(r'[\u4e00-\u9fff]',actual[0])
                with pytest.raises(AssertionError):
                    check_visible()
            else:
                check_visible()
                assert await pg.locator('.ca-chat__notice[data-level="error"]:visible').count()==0
            if out:
                out.mkdir(parents=True,exist_ok=True)
                label = ('unsupported-model-schema' if unsupported_schema else 'unsupported-app-ratio')+f'-{lang}-'+('rollback' if rollback_display else 'fixed')
                await pg.screenshot(path=str(out/f'{label}.png'))
                (out/f'{label}.json').write_text(json.dumps({'user_text':text,'model':model,'lang':lang,
                    'actual_visible_assistant':actual,'expected_user_copy':expected,'rollback_display':rollback_display,
                    'submits':mock_ws['submits'],'http_responses':responses,'mock_only':True},ensure_ascii=False,indent=2))
        finally:
            await browser.close()


@pytest.mark.parametrize('rollback', [False, True], ids=['fixed','rollback-user-override'])
async def test_fullapp_994_explicit_ratio_keeps_three_call_pack(
    app_url, mock_ws, local_agent, ws_forward, monkeypatch, rollback,
):
    from ComfyArt.bot import skill_output as so
    from test_e2e_fullapp_982 import _repeat_script
    import test_e2e_comment_edit as ce
    _add_flare_models(monkeypatch)
    monkeypatch.setattr(ce,'RESULT',_png(1024,1024) if rollback else _png(1638,2048))
    if rollback:
        real=so.user_ratio
        monkeypatch.setattr(so,'user_ratio',lambda skill,text: None if skill in so.TYPE_OUTPUTS_982 else real(skill,text))
    _,state=local_agent
    state['respond']=_repeat_script(state,'meta-ads-creative-director',3,'a distinct product creative')
    async with async_playwright() as p:
        browser,pg=await open_ratio_skill(p,app_url,'en','meta-ads-creative-director',ws_forward,'Use 4:5 for all three images, keep the reference',SUBJECT)
        try:
            await _send_default(pg)
            await _wait(lambda:len(mock_ws['submits'])==3,timeout=60)
            await _wait(lambda:state.get('wait'),timeout=60)
            gens=_gen_args(state);refs=_refs(state.get('attached') or [])
            assert len(gens)==3 and refs
            assert all(g['count']==1 and g['refs']==refs for g in gens)
            for post in mock_ws['submits']:
                assert len(post[1].get('images') or [post[1].get('image')])==len(refs)==1
                if rollback:
                    with pytest.raises(AssertionError):assert_submitted_ratio(post,'4:5')
                else:assert_submitted_ratio(post,'4:5')
            out=os.environ.get('CA994_SHOTS')
            if out:
                dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
                name='meta-pack-'+('rollback' if rollback else 'fixed')
                await pg.evaluate('() => { const ed=window.__caEditor; ed.selectNone(); ed.zoomToFit({animation:{duration:0}}) }')
                await pg.wait_for_timeout(200)
                await pg.screenshot(path=str(dest/f'{name}.png'))
                (dest/f'{name}.json').write_text(json.dumps({'normalized':gens,'actual_provider_posts':mock_ws['submits'],'rollback':rollback,'mock_only':True},indent=2))
        finally:await browser.close()
