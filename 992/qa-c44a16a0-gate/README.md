# QA independent final gate and rebuild evidence — PR1001 / #992

Tested commit: `c44a16a0fa142727c08c3e8ff0617382e97fae3e`, parent `1897e228e5a3469b0afbcb34434bd511063e99b4`.

QA personally reviewed the final local gate logs and independent build verification. This publication copies existing completed runs; it does not claim a new run or erase earlier red runs.

## Procedure and actual results

All times Asia/Shanghai (UTC+8). Final official gate: 2026-11-15 20:21:18–20:38:57. Independent rebuild: 20:42:05–20:42:08.

Run in independent worktree `wt_qa_673_ready`, `GATE_MAIN=<COMFYART_ROOT>/src GATE_PY=<QA_VENV>/bin/python GATE_WT=<COMFYART_ROOT>/wt_qa_673_ready GATE=1 DEBUG=pw:api bash scripts/gate.sh qa1001_c44a16a0`, paid provider keys unset, `no_proxy=*`, mock only, cost $0.

- Typecheck succeeded; its log is genuinely empty.
- UNIT: 4893 passed, 25 skipped, 625 deselected, exit 0. Collected 4918; node-unit bridge includes 464 tests.
- Official build succeeded, exit 0. Warnings retained in full.
- E2E: 229 passed, 5314 deselected, exit 0. Collection includes all four #673 nodes and fifteen #992 nodes; see collection log rather than infer individual test names from quiet progress dots.
- Complete gate and wrapper exit 0.
- Independent post-gate `npm run build` exit 0, then `git diff --exit-code -- dist` exit 0. This is a real rebuild, not relying on gate cleanup restoring committed dist. See npm_build.log and dist_verify.log.

## Boundaries and provenance

No production change or test weakening is included in this evidence commit. Generated #707 screenshots and temporary artifacts remain outside this publication. Old 59754e69 signoff is not carried forward. Earlier f447/1897 failed runs remain preserved locally; the old failures are not relabeled flaky or green.

Five canonical Home form pairs are separately pinned at evidence commit `970a3f026ccc422e3dd3365b29b3de437ed1b3fb`, directory `992/home-form-f4479456-to-c44a16a0`. These are f447 captures mapped by identical src/dist to c44, not c44 recaptures. Default Presets controls are absent; source definitions, backend capability and text-specified ratio remain. This package does not prove real-provider output, quality, Logo Home, all 49 skills, or #911 completion. Product/design signatures and PR description accuracy remain independent release requirements.

## Redaction and integrity

Only allowlisted text logs and bridge/collection metadata were copied. No environment dumps, credentials, DB, session state, screenshots or private inputs were copied. Sensitive credential/contact patterns were scanned before publication. Local workspace, venv and temp prefixes were normalized to placeholders; ANSI color escapes removed. Counts, failures/skips/warnings, tested commit and build hashes were not altered. SHA256-MANIFEST.json records both original and published hashes; empty tsc log is included intentionally.
