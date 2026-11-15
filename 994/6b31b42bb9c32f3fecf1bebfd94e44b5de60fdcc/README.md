# #994 / PR1000 display-HOLD repair — actual app, mock $0

Design HOLD: https://github.com/ganjmeng/ComfyArt/pull/1000#issuecomment-6888523934

Source tip: 6b31b42bb9c32f3fecf1bebfd94e44b5de60fdcc
Base:41ec2b8a0d946372f286602c7d648eceac5eca10. Prior published tip:05eea0a5818ced781c7a1ca9868c999255c5344d.

Fix: keep the internal machine refusal packet unchanged and retain failed/zero-submit semantics, but map ONLY our exact own ratio packet / exact own localized model-refusal copy to the CURRENT turn/UI language before chat/LLM presentation. Remove ValueError or agent/protocol wrappers only at these owned-error seams; unknown/forged JSON or raw upstream bodies do not become passthrough. No screenshot/DOM-only substitution, no registry or frontend style changes. Backend-only follow-up; frontend src/dist were rebuilt and checked identical.

## Evidence
`raw/` contains unaltered 1280×900 scale1 real Full App captures and actual provider POST/refusal data. Four L/R comparisons (both error paths × CN/EN): LEFT actually disables the production display-boundary function, RIGHT fixed. Captions sit OUTSIDE unchanged app screenshots. Neither side is Lovart. The LEFT normalizer path really reproduces raw bilingual JSON. The LEFT provider EN path has ValueError; CN takes the real older [tool error] agent-instruction branch. All these fail the SAME strict visible-node assertion. Both rollback and fixed refusal paths retain ZERO provider submits.

The test drives Skills wall → Try → actual upload/details → actual chat → real LocalLlmProvider + actual MCP/page + provider-schema path; only LLM responses/provider endpoint are mocked. No static imitation markup, paid generation, external Lovart visits or real provider-runtime/quality claim. Machine JSON in offline evidence is intentionally retained for audit; it is NOT the visible chat body in fixed images.

Strict assertion: exact sole visible assistant Markdown text, current language only; no JSON braces/stringification, serialized protocol fields, exception prefixes or mixed-language leakage; no duplicated error notice. Unit checks cover original packet/error-state preservation, opposite-language incoming own copy, arbitrary raw suffixes/forged kind safety. Existing wide21:9/portrait4:5+9:16/square4:5+9:16 actual POST, count/refs/model and three-call-pack tests retained. All33 audit regenerated; auto_models.json unchanged.

## Executed tests
Existing contracts first:149 passed (8 new display cases deselected). Strict display/unit/actual rollback subset:22 passed. Final broad related suite:317 passed. Typecheck/build passed. GATE_EXIT=0; UNIT 4883 passed / 25 skipped / 610 deselected; E2E 214 passed / 5304 deselected; mock $0. Complete gate.log and gate-details/ attached; one full run, no retry needed. During E2E the gate-rebuilt dist was checked byte-identical to the committed tree (gate-built-dist-match.json).

Two test-development diagnostics are retained: a rollback assertion initially assumed EN ValueError also for CN, but the real legacy CN path emits [tool error] instructions; the oracle now locks BOTH real leaks, not a fabricated failure. A unit fixture initially omitted required base_url, then used a valid local callback. No final failed cases were skipped.

## Reproduce
Use built dist, existing main node dependencies, /workspace/ca-venv and no concurrent pytest/gates.
```
npm run typecheck && npm run build
CA994_SHOTS=/path/shots /workspace/ca-venv/bin/python -m pytest -q tests/test_994_refusal_display.py tests/test_skill_e2e_994_user_ratio.py -k refusal
GATE_ROOT=/workspace/comfyart GATE_MAIN=/workspace/comfyart/src GATE_PY=/workspace/ca-venv/bin/python scripts/gate.sh 994
```

No source for unrelated cards or QA/tmp artifacts is included. No role approval/HOLD removal/merge is claimed; new-tip product/design/QA review remains necessary. Live paid provider/LLM runtime and output quality remain untested. Entirely mock $0.
