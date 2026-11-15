"""#994 HOLD: exact own-error localization, no arbitrary upstream pass-through."""
import json
from pathlib import Path
import pytest
from ComfyArt.bot.ratio_display import ratio_refusal_display
from ComfyArt.bot.skill_output import ratio_refusal_994

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('lang',['zh','en'])
def test_owned_packet_localizes_without_changing_machine_refusal(lang):
    packet=ratio_refusal_994('7:5');before=json.dumps(packet,sort_keys=True)
    copy=ratio_refusal_display(json.dumps(packet,ensure_ascii=False),lang)
    assert copy and '7:5' in copy and ('未提交' if lang=='zh' else 'Nothing submitted') in copy
    assert not any(word in copy for word in ['{','}', 'user_message','generation_succeeded','ValueError:'])
    assert json.dumps(packet,sort_keys=True)==before and packet['submitted'] is False

@pytest.mark.parametrize('lang',['zh','en'])
@pytest.mark.parametrize('source_lang',['zh','en'])
def test_known_page_refusal_strips_wrapper_and_uses_current_language(lang,source_lang):
    copies={lg:json.loads((ROOT/f'src/locales/{lg}.json').read_text())['wsErr.userRatioUnsupported'] for lg in ['zh','en']}
    assert ratio_refusal_display('ValueError: '+copies[source_lang],lang)==copies[lang]

@pytest.mark.parametrize('raw', ['ValueError: upstream secret raw body', '[object Object]',
    '{"kind":"userRatioUnsupported","user_message":"arbitrary upstream body"}',
    json.dumps({**ratio_refusal_994('7:5'), 'user_message':'arbitrary upstream body'})])
def test_unknown_raw_and_forged_ratio_packets_do_not_open_passthrough(raw):
    assert ratio_refusal_display(raw,'en') is None


@pytest.mark.parametrize('lang',['zh','en'])
def test_known_copy_plus_raw_upstream_suffix_does_not_pass(lang):
    copy=json.loads((ROOT/f'src/locales/{lang}.json').read_text())['wsErr.userRatioUnsupported']
    assert ratio_refusal_display('ValueError: '+copy+'\nupstream traceback or private body',lang) is None


@pytest.mark.parametrize('lang',['zh','en'])
async def test_real_normalizer_and_relay_display_seams_keep_machine_packet(lang):
    from ComfyArt.bot.local_llm import LocalLlmProvider, explain_unsubmitted
    from ComfyArt.bot.skill_output import RATIO_REFUSAL_994
    packet=ratio_refusal_994('7:5');before=json.dumps(packet,sort_keys=True)
    raw=json.dumps(packet,ensure_ascii=False);expected=ratio_refusal_display(raw,lang)
    assert explain_unsubmitted('generate_image',raw,lang)==(expected,'')
    events=[]
    async def emit(event):events.append(event)
    args={RATIO_REFUSAL_994:packet}
    result=await LocalLlmProvider(base_url=lambda:'http://127.0.0.1:1')._emit_result(
        {'name':'generate_image','args':args,'id':'refusal994','cached':False},raw,
        emit=emit,done=[],lang=lang,is_error=True,count_done=False)
    assert result[0]['content']==expected and events[-1].text==expected and events[-1].is_error
    assert events[0].input[RATIO_REFUSAL_994]['submitted'] is False
    assert json.dumps(packet,sort_keys=True)==before
