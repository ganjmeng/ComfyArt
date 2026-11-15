# #994 real Full App evidence — mock $0 only

Base: 41ec2b8a0d946372f286602c7d648eceac5eca10
Tip: 05eea0a5818ced781c7a1ca9868c999255c5344d

Actual built app: Skills wall → Try → required upload + CN/EN Additional Details → chat send → real LocalLlmProvider production normalization → real MCP relay → actual frontend → actual schema/payload builder → local mock provider POST. No static/example markup, paid runtime, or fabricated Lovart comparison.

Raw PNGs in raw/ are unaltered 1280×900 device-scale=1. Comparison captions are outside app images: LEFT actual production user_ratio recognizer rolled back; RIGHT fix. These are both OUR app, not Lovart. The mocked output dimensions follow the actual submitted default under rollback too; plain pixels are deterministic fixtures, not generated artwork. The actual provider POST, not mock image pixels, is the assertion oracle.

Five cases × fixed/rollback: banner21:9 CN, photo-split4:5 EN, logo4:5 CN, naive9:16 EN, photo-split9:16 CN. Each keeps count1 and one ref. Photo-split4:5 is already the base default and stays a passing control; it is not fabricated as a reproduced failure. Three-call meta-ad pack additionally keeps all three calls and refs. Rollback disables the REAL production user_ratio recognizer for typed skills; the SAME actual provider-payload assertion fails for each non-default case. Original main reproduction: 3 failed, 1 passed (log retained).

Unsupported7:5: actual visible normalizer refusal and zero submits. App-recognized1:2 on actual Nano2.1 schema: HTTP400, visible localized refusal and zero submits. That negative test explicitly asks not to use its uploaded file as reference, exercising existing t2i routing without changing model pins or Auto/edit routing. Successful cases keep all references.

All33 typed image/still contracts and actual snapshot model capability/routing matrix: ratio-audit.md/json. Six video-skill rows cover image/still calls only. api/auto_models.json, model pins, counts, refs and no-explicit-ratio defaults are unchanged. Recognition of19 ratios is NOT live runtime support: final actual selected model schema and final payload are checked; incompatible ratios refuse instead of silently snapping. Live/paid provider execution, image quality, video delivery, presets and wider mock-fidelity scope are untested or outside this card.

Reproduce with existing main node dependencies and matching built dist:

```
npm run typecheck && npm run build
CA994_AUDIT=/path/evidence /workspace/ca-venv/bin/python -m pytest -q tests/test_994_user_aspect_ratio.py tests/test_994_ratio_audit.py
CA994_SHOTS=/path/evidence/raw /workspace/ca-venv/bin/python -m pytest -q tests/test_skill_e2e_994_user_ratio.py
GATE_ROOT=/workspace/comfyart GATE_MAIN=/workspace/comfyart/src GATE_PY=/workspace/ca-venv/bin/python scripts/gate.sh 994
```

No overlapping pytest/gate. Gate logs are attached after completion. No credentials or paid calls.

Raw application captures were taken on implementation commit `fddcf8df09117bd0f1d67f3322882e72864d25ea`; final head `05eea0a5818ced781c7a1ca9868c999255c5344d` differs ONLY in two historical snapshot guard tests, with byte-identical src/bot/api/dist trees. See production-tree-integrity.json.

Final gate on final head: GATE_EXIT=0; UNIT4869 passed,25 skipped; E2E208 passed; typecheck/build passed. First gate exit1 with four historical snapshot guards remains attached (4865 unit passed,25 skipped,208 e2e passed); exact guard follow-up passed91 tests before successful full rerun. Related297 and final targeted Full App14 passed. Mock$0; no real paid provider/LLM runtime.
