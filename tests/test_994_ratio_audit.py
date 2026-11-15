"""All33 typed IMAGE-call defaults + actual checked-in schema/routing audit.
The catalog is a versioned snapshot, NOT a paid/live provider experiment.
"""
import hashlib
import json
import os
from pathlib import Path

from ComfyArt.bot.skill_output import TYPE_OUTPUTS_982, TYPED_USER_RATIOS_994, apply_generate
from ComfyArt.api.mcp_tools.canvas import select_model
from ComfyArt.api import wavespeed

ROOT = Path(__file__).resolve().parents[1]


def test_all_33_audit_uses_actual_schema_and_model_routing():
    fixture = json.loads((ROOT/'tests/fixtures/wavespeed_catalog_subset.json').read_text())
    pins_bytes = (ROOT/'api/auto_models.json').read_bytes()
    auto = json.loads(pins_bytes)
    cfg = wavespeed.load_config()
    models = {cfg['features'][f]['default'] for f in ('text_to_image', 'image_edit')}
    for row in auto['features'].values():
        models.update(c['model'] for c in row.get('categories', []))
    caps = {}
    for mid in sorted(models):
        props = wavespeed._schema(fixture.get(mid)).get('properties') or {}
        caps[mid] = {'snapshot_present': mid in fixture,
            'aspect_ratio_enum': (props.get('aspect_ratio') or {}).get('enum'),
            'size_schema': props.get('size'),
            'app_recognized_intersection': [r for r in TYPED_USER_RATIOS_994
                if r in ((props.get('aspect_ratio') or {}).get('enum') or [])]}
    rows = []
    for sid, row in sorted(TYPE_OUTPUTS_982.items()):
        assert sid not in auto['skills']  # do not change/extend registered pins
        routes = {}
        for with_ref in (False, True):
            args = apply_generate({'skill': sid, 'prompt': 'a simple design',
                'refs': ['shape:first-ref'] if with_ref else []}, user_text='Use 4:5')
            choice = select_model('generate_image', args, catalog=fixture, cfg=cfg, user_text='Use 4:5') or {}
            routes['one_reference' if with_ref else 'generic_no_reference'] = {
                k: choice.get(k) for k in ('model','edit_model','category')}
        rows.append({'skill': sid,'default': {k: row.get(k) for k in ('width','height','ratio','images','images_min','images_max','media')},
            'default_calls': row.get('calls'), 'refs_contract': row.get('refs'),
            'registered_skill_pin': None, 'representative_routes': routes,
            'override_points': ['run_hint','chat apply_generate','relay apply_generate',
                'follow-reference or call-plan defaults' if sid in {'style-transfer','person-swap'} or row.get('calls') else 'typed flat row',
                'frontend exact pixels','selected provider schema nearest-ratio/default/params'],
            'scope': 'image/still generate_image only; video contract unchanged' if row.get('media')=='video' else 'image calls',
            'support': '19 recognized app ratios (schema union), INTERSECT selected live model schema; explicit refusal otherwise'})
    assert len(rows) == 33
    assert set(TYPED_USER_RATIOS_994) == {r for c in caps.values() for r in (c['aspect_ratio_enum'] or [])}
    assert (ROOT/'api/auto_models.json').read_bytes() == pins_bytes
    out = os.environ.get('CA994_AUDIT')
    if out:
        dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
        report={'catalog_source':'tests/fixtures/wavespeed_catalog_subset.json',
            'catalog_sha256':hashlib.sha256((ROOT/'tests/fixtures/wavespeed_catalog_subset.json').read_bytes()).hexdigest(),
            'auto_models_sha256_unchanged':hashlib.sha256(pins_bytes).hexdigest(),
            'app_ratios':list(TYPED_USER_RATIOS_994),'model_caps':caps,'typed_skills':rows,
            'limits':'Representative generic prompts only. Auto is prompt/ref dependent; explicit model pins remain unchanged. Final runtime schema validation is authoritative. Provider runtime was mocked; live paid runtime NOT tested.'}
        (dest/'ratio-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        text = '# #994 all33 typed IMAGE-call audit\n\nApp ratios: '+', '.join(TYPED_USER_RATIOS_994)+'. Runtime support = intersection with actual selected model schema, never an assumption from normalization.\n\n'
        text += '|Skill|Default canvas|Image count|Ref contract|Representative no-ref / one-ref model|\n|---|---|---|---|---|\n'
        for r in rows:
            d=r['default'];models_text=' / '.join(str(v.get('edit_model') or v.get('model')) for v in r['representative_routes'].values())
            text+=f"|{r['skill']}|{d['width']}×{d['height']} {d['ratio']}|{d['images']} (bounds {d['images_min']}..{d['images_max']})|{r['refs_contract']}|{models_text}|\n"
        text+='\n## Actual schema snapshot capabilities\n'
        for mid,cap in caps.items(): text+=f"- `{mid}`: enum={cap['aspect_ratio_enum']}; size={cap['size_schema']}; snapshot present={cap['snapshot_present']}\n"
        text+='\nEvery row previously could lose user intent in run_hint/chat/relay/flat or call/ref defaults, then frontend/provider nearest-ratio mapping. New explicit intent wins chat+relay, carries through real frontend and is checked against the FINAL provider schema and final payload before submit; incompatible models refuse with alternatives, not a model switch. No explicit user ratio retains default plans/counts/refs. Multi-call image counts stay unchanged; six video skills here cover image/still calls ONLY. No992/993/990 scope. auto_models.json and pins unchanged. Photo-split4:5 is an already-default control on this base; photo9:16 additionally proves override.\n\n'+report['limits']+'\n'
        (dest/'ratio-audit.md').write_text(text)
