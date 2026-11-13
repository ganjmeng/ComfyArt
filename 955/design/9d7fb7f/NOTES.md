# #955 design evidence — same-id manual pick after Auto (new tip, merge-only)

- PR: #955 (Closes #953, Refs #911)
- Tip (frozen for this sign): `9d7fb7f17e97744ce145cd7be5df8e0187e043a2`
  - merge commit: parents `160be75d39be73edb7c4949e81e1dd805379f312` + main `b101419eb6739092ac0cdb11e858f80f672820e3` (#958 squash merge)
  - `git diff --stat 160be75d 9d7fb7f1` = only #958's 8 files under `api/`, `bot/`, `tests/`; **no `src/`, no `dist/`** → UI identical to the previous signed tip.
- Base: `b101419eb6739092ac0cdb11e858f80f672820e3` (current main)
- Captured: 2026-11-13 23:58 +08 (Asia/Singapore)
- Scenario: Studio new Image Generator → prompt "a cup of coffee on a table" → wait Auto estimate (GPT Image 2.6 Flare) → switch Auto off → explicitly check the **same** `openai/gpt-image-2.6-flare/text-to-image` row → menu still shows Auto off + Flare checked → Generate.
- Language: zh (`comfyart.lang=zh`) and en; viewport 1600×1000; native Full App UI.

## Tool / method (disclosed per #78)
- python-playwright 1.65 (Chromium; Firefox not installed on this box), repo harness `tests/test_e2e_953_studio_quote.py::test_studio_manual_pick_of_the_same_model_after_auto_is_manual[zh|en]`, committed `dist/` of this tip served by the repo's in-process mock host (real HTTP MCP / quote / submit / canvas-place chain).
- `$0`: WaveSpeed base URL and keys are local mocks; no paid or official LLM, no external supplier calls (GATE=1, `no_proxy='*'`, keys unset). The green image is a local mock PNG.
- Fresh checkout state: worktree reset to `9d7fb7f17e97744ce145cd7be5df8e0187e043a2` before the run; command:
  `python -m pytest tests/test_e2e_953_studio_quote.py -k "manual_pick_of_the_same_model" -q`
  → **2 passed, 6 deselected in 20.12s**.

## What the e2e asserts (not just screenshots)
1. First estimate is Auto (`model_choice.auto=true`) before the user acts.
2. After Auto off + same-id pick, a later estimate carries `model_choice.auto=false`, `model=openai/gpt-image-2.6-flare/text-to-image`; label text is exactly `GPT Image 2.6 Flare` (no `Auto`).
3. Submitted model unchanged: exactly **1** mock submit, model `openai/gpt-image-2.6-flare/text-to-image`; result label again no `Auto`, no `aria-label` reason / no `.ca-tip` hover reason. Display fix and actual route are separate assertions.
4. Cross-ref (fullstack, same tip lineage): `955/160be75d/same-id-estimate-before-after.json` shows estimate request+response `model_choice = {auto:false, category:"user", reason:{zh:"你指定了这个模型", en:"you named this model"}}`.

## Files (sha256)
| file | pixels | sha256 |
|---|---|---|
| studio-same-manual-selected-zh.png | 1600×1000 | fa184b313acc0d4deaba166e036e3e5ff39e7e368d120d6e4b47fdfab619a357 |
| studio-same-submitted-zh.png | 1600×1000 | a1ce486080ec0a9e09008d52140fe76668dc029892feba9d8ffd72ff89c031fa |
| studio-same-manual-selected-en.png | 1600×1000 | 6ff6dd27ff61a1bee97f1543976bc43f30d48e83e6f4fc11b104b80310d1d8c6 |
| studio-same-submitted-en.png | 1600×1000 | 24f2eab8f5b4ccae06c506411486fb2f47f306b8be604836613c7bb70610ea57 |
| before-after-same-id-en.png | 2328×764 | composite: left = QA capture at buggy tip `a43ad880` (RA `9feeda04.../955/qa/a43ad880/studio-same-manual-selected-en.png`, unmodified), right = this tip |

**Determinism / tip-equivalence check**: these four PNGs are **byte-identical (same sha256) to the RA `955/design/160be75d/` set**, which matches the verified `src/`/`dist/` no-op between the two tips.

## No-Lovart-counterpart note (per #78)
Internal model-source attribution / task-history display (Auto vs user pick in the Studio model pill and result title). Lovart has no equivalent attribution UI → evidence is **before/after** (buggy tip `a43ad880` → this tip), rationale stated for the PR body.

## Limitations
- Mock-only, $0: proves UI/attribution and the single-submit route, not paid-route quality or live WaveSpeed availability.
- Firefox path unavailable on this machine; Chromium run only.
- Design review scope = display/attribution UI. QA's independent unit/E2E gate and dist checks remain authoritative; this capture set does not replace them.
