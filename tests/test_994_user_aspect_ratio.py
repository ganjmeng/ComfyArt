"""#994 first-phase RED reproduction: typed defaults must yield to user ratio.

Pure production normalizer calls (chat then relay), $0/no provider or model.
These ordinary assertions failed on the assigned main before #994; they now
lock the implementation. photo-split4:5 is an honest already-working control on this base;
Actual Full App/provider submission and rollback coverage: test_skill_e2e_994_user_ratio.py.
"""
import pytest

from ComfyArt.bot.skill_output import OUTPUTS, apply_generate


@pytest.mark.parametrize('skill,requested,user_text', [
    ('banner-design-director', '21:9', '请做21:9横幅，保留参考图内容。'),
    ('logo-abstract', '4:5', 'Use 4:5, not a square. Keep the reference.'),
    ('naive-illustration', '9:16', '请按9:16竖版绘制，保留参考图。'),
    # Already4:5 in current typed table; do not fabricate this as a failing case.
    ('photo-split-poster', '4:5', '照片分割海报要4:5，保留参考图。'),
])
def test_explicit_user_ratio_survives_typed_chat_and_relay(skill, requested, user_text):
    row = OUTPUTS[skill]
    refs = ['shape:994-first-reference', 'shape:994-second-reference']
    args = {'skill': skill, 'prompt': 'Local ratio regression; never submit',
            'ratio': requested, 'width': row['width'], 'height': row['height'],
            'count': 1, 'refs': refs, 'model': 'mock-994-preserve-model-pin'}
    chat = apply_generate(args, skill, user_text=user_text)
    relay = apply_generate(chat, skill)
    for stage, result in [('chat', chat), ('relay', relay)]:
        assert result['count'] == 1, (stage, result)
        assert result['refs'] == refs, (stage, result)
        assert result['model'] == args['model'], (stage, result)
    observed = {stage: {key: result.get(key) for key in ('ratio', 'width', 'height', 'count')}
                for stage, result in [('chat', chat), ('relay', relay)]}
    assert [chat.get('ratio'), relay.get('ratio')] == [requested, requested], (
        f'{skill}: user explicitly requested {requested}; typed default overrode it: {observed}')


from copy import deepcopy
from pathlib import Path
import json
from ComfyArt.bot.skill_output import (
    TYPE_OUTPUTS_982, USER_RATIOS, TYPED_USER_RATIOS_994, RATIO_REFUSAL_994,
    STRICT_RATIO_994, run_hint, accepted_image_counts,
)


@pytest.mark.parametrize('sid', sorted(TYPE_OUTPUTS_982))
@pytest.mark.parametrize('ratio,text', [('4:5', '请使用４：５比例。'), ('9:16', 'Use 9:16, not 16:9.')])
def test_all_33_typed_overrides_preserve_counts_refs_and_relay(sid, ratio, text):
    refs = ['shape:reference-one', 'shape:reference-two']
    before = deepcopy(TYPE_OUTPUTS_982[sid])
    counts = accepted_image_counts(sid)
    out = apply_generate({'skill': sid, 'refs': refs, 'edit_model': 'preserve-existing-pin'}, user_text=text)
    assert (out['ratio'], out['width'], out['height']) == (ratio, *TYPED_USER_RATIOS_994[ratio])
    assert out['count'] == 1 and out['refs'] == refs and out['edit_model'] == 'preserve-existing-pin'
    assert out[STRICT_RATIO_994] == ratio and out['size_lock_mode']=='ratio'
    assert apply_generate(out) == out
    assert TYPE_OUTPUTS_982[sid] == before and accepted_image_counts(sid) == counts
    assert f'ratio {ratio}' in run_hint(sid, text)


@pytest.mark.parametrize('sid', sorted(TYPE_OUTPUTS_982))
def test_no_explicit_ratio_defaults_are_unchanged(sid):
    # Calling the user's turn versus relay-only must retain the same typed or
    # follow-reference fallback, counts and hints when no ratio was requested.
    args = {'skill': sid, 'refs': ['shape:kept'], 'ratio': '4:5'}
    assert apply_generate(args, user_text='Create the design') == apply_generate(args)
    assert STRICT_RATIO_994 not in apply_generate(args, user_text='Create the design')


@pytest.mark.parametrize('text', ['Use 7:5', '要9:19.5', '比例0:5'])
def test_unsupported_numeric_ratio_has_explicit_bilingual_refusal(text):
    out = apply_generate({'skill': 'banner-design-director'}, user_text=text)
    refusal = out[RATIO_REFUSAL_994]
    assert refusal['submitted'] is False and refusal['kind'] == 'userRatioUnsupported'
    assert '未提交' in refusal['error'] and 'nothing submitted' in refusal['error']
    assert '4:5' in refusal['error'] and '21:9' in refusal['error']
    assert 'Do not generate' in run_hint('banner-design-director', text)
    assert apply_generate(out)[RATIO_REFUSAL_994] == refusal
    # New authoritative user turn clears a stale refusal/marker.
    assert RATIO_REFUSAL_994 not in apply_generate(out, user_text='Use 4:5')


def test_typed_explicit_ratio_beats_reference_but_default_still_follows_it():
    import io
    from PIL import Image
    data = io.BytesIO(); Image.new('RGB', (800, 600)).save(data, format='PNG')
    args = {'skill': 'style-transfer', 'refs': ['shape:first']}
    default = apply_generate(args, user_text='Apply style', ref_image=data.getvalue())
    assert default['ratio'] == '4:3'
    explicit = apply_generate(args, user_text='Use 9:16', ref_image=data.getvalue())
    assert explicit['ratio'] == '9:16' and apply_generate(explicit)['ratio'] == '9:16'


@pytest.mark.parametrize('text,expected', [('不要16:9，要21:9', '21:9'), ('not 16:9, use 4:5', '4:5'),
    ('Use square format', '1:1'), ('portrait orientation please', '9:16'), ('横版', '16:9'), ('Use 8:10', '4:5')])
def test_cn_en_ratio_recognition(text, expected):
    assert apply_generate({'skill': 'banner-design-director'}, user_text=text)['ratio'] == expected


CATALOG = json.loads((Path(__file__).parent / 'fixtures/wavespeed_catalog_subset.json').read_text())

def schema(mid):
    return CATALOG[mid]['api_schema']['api_schemas'][0]['request_schema']


@pytest.mark.parametrize('ratio', list(CATALOG['openai/gpt-image-2.6-flare/text-to-image']['api_schema']['api_schemas'][0]['request_schema']['properties']['aspect_ratio']['enum']))
async def test_real_flare_schema_final_payload_honors_each_recognized_ratio(ratio):
    from ComfyArt.api.wavespeed import build_payload
    w, h = TYPED_USER_RATIOS_994[ratio]
    mid = 'openai/gpt-image-2.6-flare/text-to-image'
    body = await build_payload(None, schema(mid), {'prompt': 'mock', 'width': w, 'height': h, 'user_ratio': ratio}, mid)
    assert body['aspect_ratio'] == ratio


@pytest.mark.parametrize('mid', ['recraft-ai/recraft-v3', 'midjourney/text-to-image'])
async def test_actual_restricted_model_refuses_instead_of_snapping_4to5(mid):
    from ComfyArt.api.wavespeed import build_payload, WaveSpeedError
    with pytest.raises(WaveSpeedError, match='Requested ratio 4:5'):
        await build_payload(None, schema(mid), {'width': 1638, 'height': 2048, 'user_ratio': '4:5'}, mid)


async def test_final_params_cannot_override_user_ratio_and_legacy_snap_unchanged():
    from ComfyArt.api.wavespeed import build_payload, WaveSpeedError
    mid = 'openai/gpt-image-2.6-flare/text-to-image'
    args = {'width': 1638, 'height': 2048, 'user_ratio': '4:5', 'params': {'aspect_ratio': '16:9'}}
    with pytest.raises(WaveSpeedError, match='final payload would override'):
        await build_payload(None, schema(mid), args, mid)
    legacy = await build_payload(None, schema('recraft-ai/recraft-v3'), {'width': 1638, 'height': 2048})
    assert legacy['aspect_ratio'] != '4:5'  # unchanged for unmarked/default callers


@pytest.mark.parametrize('ratio', ['1:4', '4:1', '1:8', '8:1'])
async def test_other_provider_supported_extreme_ratios_are_not_blanket_rejected(ratio):
    from ComfyArt.api.wavespeed import build_payload, WaveSpeedError
    w,h = TYPED_USER_RATIOS_994[ratio]
    inp={'width':w,'height':h,'user_ratio':ratio}
    body=await build_payload(None,schema('google/nano-banana-2.1/text-to-image'),inp)
    assert body['aspect_ratio']==ratio
    with pytest.raises(WaveSpeedError,match='unsupported aspect_ratio'):
        await build_payload(None,schema('openai/gpt-image-2.6-flare/text-to-image'),inp)


def test_orientation_subject_nouns_are_not_explicit_ratio_requests():
    args={'skill':'banner-design-director'}
    assert apply_generate(args,user_text='A portrait photo with squares in a landscape')['ratio']=='16:9'
