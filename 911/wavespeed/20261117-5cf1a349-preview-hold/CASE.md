# #911 multi-angle — 5cf1a349 paid lineart preview (ONE submit) — FROZEN CASE

**Do not pay for this path again. Task 76db53c0764a4552a45fd7dbc3c1ee03 must never be resubmitted or reused.**
Written 2026-11-17 ~22:12 Asia/Shanghai (+0800).

## Route / inputs
- SHA `5cf1a349df79a1c2cbefcfdd9d170c4cabd1e234` (branch + refs/pull/1003/head both at it, ls-remote 22:04 +0800, `preflight/ls-remote-presubmit.txt`). Product code identical to 251d8c4c (only `tests/test_e2e_skill_hidden_notice_673.py` differs; `frozen.meta.txt`).
- Official gate on this SHA: GATE_EXIT=0 (`/workspace/qa1003-5cf1a349-evidence/gate.log`).
- Frozen code: `frozen-5cf1a349/` (git archive, committed tree only). Isolated runtime: `runtime/` (fresh input/output/user DB). Server: in-process aiohttp TestClient on an ephemeral 127.0.0.1 port (not 8916/8927). No other service touched.
- Method = same as 96259b9e run (`/workspace/qa1002-96259b9e-preview-preflight`): scripted 0-LLM, app `prepare → quote_route → quote_detail → reserve → POST /comfyart/wavespeed/run → poll history`. HTTP allowlist guard, max 1 provider image POST, finals model blocked, LLM blocked. Scripts: `harness_common.py`, `paid_preview_once.py` (adds prompt-sha gate, $0.11 quote ceiling, old-task-id check).
- Plan: independent new plan = reviewed candidate `structured-plan.json` (sha256 bf418e2b…, from 63e4a9d0 preflight; not the 96259 plan).
- Reference: `runtime/input/ma_subject_691.png` sha256 f92f6c3e… (same as earlier paid runs). DESC `商品详情页，纯白无缝背景`. Setup card: source single_front, aspect 1:1 (finals would be 2048², not run). Plan quote card answered Start.
- Dry run first (`/workspace/qa1003-5cf1a349-paid-preview-dryrun`, provider POST blocked at allowlist, $0).

## Pre-checks (all passed)
- Assembled preview prompt sha256 `afd3bfac32b92fa7dfb54476fb38ddf8e7ea14200cc7da7f9efffc3956bab678` == reviewed candidate, byte-identical (`paid/assembled-prompt.txt`, `preflight/quote-result.json`). Stage = preview (`key=preview`), LINEART ONLY, 1152×2048 9:16, size_lock_mode=ratio, exact_pixels=false, refs = fixture only, final ratio 1:1, 9 panels, DESC/purpose/appearance excluded.
- Live quote $0.1035 (`openai/gpt-image-2.6-flare/edit`, 2k, 9:16, 1 ref), ≤ $0.11.
- Balance + in-flight: see `preflight/BALANCE-TRACE.md` and `preflight/ws-predictions-today.json` (read-only provider history). 656362db fully accounted (20.790008 → 20.686508 at 08:35). Extra shared charge: task 195faab693874f86885b162148540324 (Flare edit, 12:01:49 +0800, 1:1 headphones nine-grid). Not from any QA/box evidence; owner unknown. Nothing created after 12:01:49 and nothing in progress; balance flat 14:55 → 22:04.

## Submit / spend
- Provider POST 22:04:26 +0800, exactly one (`paid/guard-one-post.json`, image_posts=1, uncertain=false, 0 blocked). Task `76db53c0764a4552a45fd7dbc3c1ee03` recorded before polling (`go/preview.task.json`). Completed 22:05:10.
- Balance 20.583008 (22:04:20) → 20.479508 (22:05:10): **delta $0.1035 = quote**.
- #911 ledger: $0.3798 + $0.1035 = **$0.4833**, remaining **$0.5167**. Worst case if 195faab6 is #911's too: $0.5868, remaining $0.4132.

## Output
- Original `runtime/output/wavespeed/ws_76db53c0764a_0.png`; copy `downloads/preview-9x16.png`, 1440×2560 PNG, sha256 `bbfb2c13705ea811eee65d15e6cf9b64bb23bef731a471891c36d15cadac9115`, ratio check match (0.0%), no size notice.
- Crops: `panel7-crop-native.png` (500×853), `panel7-crop-2x.png` (1000×1706), `panel7-detail-zoom.png`, `panel1-crop-native.png`, `row1/2/3-crop.png`.

## Verdict (details in `verdict.json`)
- 9:16 numbered nine-grid: PASS. Lineart only (no gray fill/shading/material): PASS. Panel 7 true top-down: **PASS** (fixes the 656362db HOLD).
- Plan conformance: panel 2 **HOLD**. Its handedness is mirrored: the near cup with outer shell is on screen-left, but the plan's camera is to the viewer's right with the subject's left cup closer. Panels 6/9 read as near-duplicate three-quarter views (noted, not failed).
- **Overall HOLD** under the room rule (any item fails → HOLD). Stopped: no finals, no retry, no merge, no GitHub post. Archived as a failure case (image + plan + prompt kept here).

Not a default-agent / UI / Lovart L/R PASS. Material and lighting not judged.
