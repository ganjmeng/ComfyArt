"""#994 first-phase RED reproduction: typed defaults must yield to user ratio.

Pure production normalizer calls (chat then relay), $0/no provider or model.
These ordinary assertions intentionally fail on the assigned main until #994
is implemented. photo-split4:5 is an honest already-working control on this base;
Full App/provider submission and rollback coverage belong to the next phase.
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
