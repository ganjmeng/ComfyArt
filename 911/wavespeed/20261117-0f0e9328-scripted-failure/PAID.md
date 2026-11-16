# Scripted tool-only paid QA — frozen 0f0e9328

Times below are Asia/Shanghai (UTC+8).

This run is **SCRIPTED TOOL-ONLY**, not the real default-agent / DeepSeek 1017 loop. The default agent was not started: a default loop cannot be safely bounded (multiple completions; one maxed 2x official-tariff call ≈ $0.67) and `submit_command` requires a ComfyArt page (browser blocked). Images went through frozen `prepare` / `validate_plan` / `validate_provider_size` / `reserve`, then in-process TestClient `POST /comfyart/wavespeed/run` → `wavespeed.submit` / `poll`. No production code was changed. No GitHub post. 8916 and the engineer worktree were not written. Left baseline `44b6ab3756a96f82ec85e31525a31c07728d690d` was not rerun. This is **not** a UI PASS and **not** a Lovart L/R PASS.

Exact SHA: `0f0e9328934e3d35e95f5993c6cfc91b08815e0f`  
Frozen tree: `/workspace/qa1002-0f0e9328-evidence/frozen-0f0e9328`  
Evidence: `/workspace/qa1002-0f0e9328-appstack-paid/`  
Fixture `ma_subject_691.png` sha256 `f92f6c3eb265a1421003a4682d21c3e472450eb084ef027ab0290b6e2d550b5e` (match).  
DESC `商品详情页，纯白无缝背景`; source `single_front`; selected compositions 1/2/3; final 1:1.

## Attempt 1 (no charge) — 00:28:48–00:28:57

Harness HTTP allowlist blocked the in-process TestClient `POST 127.0.0.1/comfyart/wavespeed/run` before any WaveSpeed model POST. No task id. Balance unchanged at $21.066308. Archived at `paid/attempt1-selfblock/`.

## Attempt 2 (paid, completed) — 00:29:41–00:34:10

Loopback TestClient routes were allowlisted. Same frozen app path. 4 image submits, 0 LLM calls, 0 blocked HTTP after the fix.

Quoted spend $0.2763. Shared balance $21.066308 → $20.790008, delta $0.2763 (equals the four live quotes; shared-account delta is still not exclusive unless proved). Hard cap $1 not exceeded.

| Stage | Task ID | Model | Quote | Balance after | Output |
|---|---|---|---:|---:|---|
| preview | `47890f21db9045429e6a958a63bae52b` | `openai/gpt-image-2.6-flare/edit` 2k+9:16, 1 ref | $0.1035 | $20.962808 | 1440×2560 |
| final 1 正面全景 | `926f8a55ce184a71b2bc8f95d94670a7` | `google/nano-banana-2.1/edit` 2k+1:1, 2 refs | $0.0576 | $20.905208 | 2048×2048 exact |
| final 2 四分之三全景 | `9232393db2414c0596c7f5bf16dba699` | same, 2 refs (same subject + preview) | $0.0576 | $20.847608 | 2048×2048 exact |
| final 3 90°侧面轮廓 | `69d2d600171f4169b0b240a4a1fb6713` | same, 2 refs (same subject + preview) | $0.0576 | $20.790008 | 2048×2048 exact |

Composition card used the frozen 9-item scripted plan (subject-aware for this fixture; not a production default table). Plan persisted on preview reserve before submit; finals used the same plan and the same subject ref plus the delivered preview.

## Output paths for independent visual review

- `/workspace/qa1002-0f0e9328-appstack-paid/downloads/preview-9x16-lineart.png` sha256 `f4ee76543809a66306f5ef554227068c83e8ff4711974263b536c1ff073f798c`
- `/workspace/qa1002-0f0e9328-appstack-paid/downloads/final-1-front.png` sha256 `a72951f85847d69e3e30ba5d92f408cfa02cf960382147bfd2158414181cd2e3`
- `/workspace/qa1002-0f0e9328-appstack-paid/downloads/final-2-three-quarter.png` sha256 `d9c57a85620c63ae88a36b22c69d80ea32b5cf2469eb903a939d5126e017def1`
- `/workspace/qa1002-0f0e9328-appstack-paid/downloads/final-3-side.png` sha256 `09ef97b5c7cb0a13b9eb127448ece43073c4fec3e04318a834fc26b263761a3c`

Originals under `runtime/output/wavespeed/`. Machine result: `paid/run-result.json`. Transcript: `transcript/workflow.jsonl`. Redacted submit bodies: `paid/submit-body-*.json`. Task ids: `go/*.task.json`.

## Product observation (preview size lock)

Preview was reserved at policy 1152×2048 (9:16, 2k+ratio). Flare returned 1440×2560 (same 9:16, long edge 2560). Because `apply_generate` for this skill does not set `size_lock_mode=ratio`, the app audited **exact** pixels, recorded a P1 size notice, and still delivered the file (no resubmit). The notice text says “smaller than expected” even though 1440×2560 is larger than 1152×2048. Finals 2048×2048 matched exactly.

## Machine checks vs visual

Machine path: plan freeze, same ref across stages, 2-ref finals, live quotes, WaveSpeed through frozen app, spend within cap — completed. Visual quality of the nine-grid and compositions 1/2/3 is for parent review; no UI/Lovart L/R verdict is claimed.

## Independent parent visual review — HOLD (2026-11-17 00:39 Asia/Shanghai)

Parent independently viewed the delivered preview and the left/right contact `/workspace/qa1002-0f0e9328-appstack-paid/paid-effects-left-right-contact.png` (sha256 `2592e42356108433d41154409dc94d2db14405528cbf790c27466d1f941920b3`, 1000×1560, written 00:37 Asia/Shanghai; left Lovart front/three-quarter/side, right this scripted-tool WaveSpeed run). Existing task IDs, images, and quotes were not retried. No new paid calls. This remains **scripted tools, zero LLM**; it is **not** a completed default-agent test.

HOLD findings (visual quality / effect — not relabeled as PASS):

1. **Preview is not lineart.** The reserved prompt in `paid/submit-body-preview.json` (built from frozen `api/multi_angle.py` line 426) is explicit: `Produce ONE lineart preview image: a numbered 3x3 nine-panel composition grid, labels 1..9. Not final photographs.` The delivered file `/workspace/qa1002-0f0e9328-appstack-paid/downloads/preview-9x16-lineart.png` is shaded photographic product renders, not the requested lineart.
2. **Panel 7 is not top-down.** The same submit body asked `7: 顶部头梁 — top-down view of the headband arc and spacing between cups, proportions from the reference, white seamless`. Parent review: that panel visually repeats a front view rather than a top-down view.
3. **Finals follow the broad angles but identity / Lovart effect are not PASS.** Compositions 1/2/3 are broadly front / three-quarter / side, but yokes and cups differ visibly from the reference and from the Lovart left column on the contact. Reference-identity fidelity and Lovart effect comparison are **not PASS**. No UI or Lovart L/R PASS is claimed.

Machine-readable copy: `paid/parent-hold-review.json`.

## Verified: false “smaller than expected” size notice (local $0 replay)

Records (task `47890f21db9045429e6a958a63bae52b`, `paid/run-result.json`): requested **1152×2048**, provider/delivered **1440×2560**, `size_check.match=false`, `size_check.mode=exact`, notice `出图尺寸低于预期（实际 1440×2560），已按原图交付。` / `Output is smaller than expected (1440×2560). Delivered as generated.` Submit body had `size_lock: true` and `user_ratio: 9:16` and **no** `size_lock_mode`. File pixels re-read from the saved PNG match 1440×2560. Both edges and area are larger (2,359,296 → 3,686,400 px). 9:16 is exact (ratio error 0.0%); long edge 2560 ≥ 2048.

Local $0 replay of frozen `audit_file` on that PNG, no network: exact mode still mismatches and still emits the “smaller” notice; if `size_lock_mode=ratio` had been set, `ratio_ok` would be **true** and there would be no notice. Result: `paid/size-notice-false-smaller-replay.json`.

Frozen source (SHA `0f0e9328934e3d35e95f5993c6cfc91b08815e0f`, tree `/workspace/qa1002-0f0e9328-evidence/frozen-0f0e9328`):

- `api/skill_size.py` **65–75** — exact `reconcile` is `got == req` only.
- `api/skill_size.py` **97–103** — `ratio_ok`: ratio error ≤ 1% and long side ≥ target.
- `api/skill_size.py` **118–124** — `size_notice()` ignores whether the file is smaller or larger; any mismatch uses the hardcoded “低于预期 / smaller than expected” copy (comment at **116–117** says this is the same as the page).
- `src/locales/en.json` **898** and `src/locales/zh.json` **898** — `jobs.sizeNotice` strings; applied in `src/jobs.ts` **321**.
- `bot/skill_output.py` **808–813** — `apply_generate` returns early for `MULTI_ANGLE` (pixels owned by the stage guard) **before** `size_lock_mode=ratio` would be set at **915**.
- `src/botCommands.ts` **228** — the page sets `sizeLockMode: 'ratio'` only if `args.size_lock_mode === 'ratio'`.
- `api/wavespeed.py` **2072–2075** — job `size_mode` becomes ratio only when `inputs.size_lock_mode == RATIO_MODE` (and the model is Sunburst or tier-only).
- `api/wavespeed.py` **2716–2734** — after a charged complete, a failed size check is logged and the file is delivered as returned (no resubmit). This run used exact mode, so the false “smaller” wording fired even though 1440×2560 is larger.

This is a copy/audit defect plus a missing ratio-mode lock on this skill’s generate path. It does not change the HOLD visual findings above.

## $0 replay recommendations (no paid calls, no resubmit)

Do not POST `/api/v3/{model}`, do not start a new poll as a new job, and do not reuse the four task IDs for another generate.

- Re-open the four downloads and the contact sheet above; compare the preview against `paid/submit-body-preview.json` (lineart clause + panel 7 top-down line).
- Re-run the local size-notice replay: `paid/size-notice-false-smaller-replay.json` was produced by frozen `ComfyArt.api.skill_size.audit_file` on the saved preview PNG.
- Optional mock replay already on disk: `/workspace/qa1002-0f0e9328-evidence/` 504 + 17 pytest logs (no keys, no WaveSpeed generate).
- Re-read the frozen line refs listed in the size-notice section.

## Additional independent composition check (2026-11-17 00:42 Asia/Shanghai)

Design flagged mirrored direction between preview panel 2 and final 2. QA independently confirms from the archived originals: preview panel 2 presents the outer cup on image-right, while final-2-three-quarter.png presents the outer cup on image-left. Both are three-quarter, but the selected preview composition direction is not retained. This is an output-fidelity HOLD, not a reproduced ID-storage/mapping bug, and does not require matching Lovart direction. No additional paid request.
