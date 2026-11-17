# #911 / PR #1003 — 660c4026 PAID finals, cells 1/2/3 of preview 76db53c0 — FROZEN CASE

**Do not resubmit.** Tasks d4f382727c8548c6aba47bebb52cbb19 (cell 1), 7214347eecf84628a8415ad21071bbb0 (cell 2), e488752a4a794e8d92f141836a6b284b (cell 3) must never be resubmitted or reused. Written 2026-11-18 ~00:15 Asia/Shanghai.

## Route / inputs
- SHA `660c402678626972e5214119da0b0d0bfda6edeb` (branch and PR head both at it, `preflight/ls-remote-presubmit.txt` 00:01 +0800). Official gate on this SHA: GATE_EXIT=0 (`/workspace/qa1003-660c4026-evidence/gate.log`).
- Frozen code `frozen-660c4026/` (git archive). Isolated runtime `runtime/`, in-process aiohttp TestServer on 127.0.0.1 port 37451 (dry run) / ephemeral (paid), never 8916/8927. Scripted, no LLM, no default agent.
- State: copy of the frozen 5cf1a349 delivered-preview chat (`inputs/chat-after-deliver-preview.json`, unmodified on disk). In memory only, `preview.urls` was set to the real delivered file `ws_76db53c0764a_0.png` (sha bbfb2c13…). Compositions were answered 1/2/3, and panel_content was passed per Fullstack's candidate (`paid_finals_once.py` CONTENT).
- Script `paid_finals_once.py`. Guard: HTTP allowlist; at most 1 provider POST per cell and 3 in total; no retry; LLM and Flare/preview blocked; old task ids blocked.

## Pre-checks (all passed)
- Read-only `preflight/readonly-pre.json` (00:01:26) and `readonly-pre-paid.json` (00:03:03): balance 20.479508 (= expected, delta 0). 7 tasks today, newest 76db53c0 at 22:04:26 → nothing created since 22:05, none in flight.
- Assembly vs offline audit (`/workspace/qa1003-660c4026-evidence/finals-assembly`): prompts byte-equal (sha 26fc405a… / 00fe9638… / 02959840…, = Fullstack candidates), refs equal [ma_subject_691.png f92f6c3e…, ma-cellN crop], crop shas 58d79831… / e890528d… / f625742d…, crop boxes equal, 2048×2048 1:1, model google/nano-banana-2.1/edit, param guard + provider size OK.
- Live quote $0.0576 per cell (cell 1 live, cells 2/3 the same priced inputs from the 5-min cache) → total $0.1728 ≤ $0.20 and ≤ $0.4132.
- Dry run first (`dryrun/`, 00:02:36–00:02:52): 3 provider POSTs refused at the guard (`dryrun/http-blocked.jsonl`), balance unchanged.

## Submit / spend (`paid/`)
| cell | task | submit (+0800) | provider created | seen done | output |
|---|---|---|---|---|---|
| 1 | d4f382727c8548c6aba47bebb52cbb19 | 00:03:13 | 00:03:16 | 00:03:56 | 2048×2048, e2ed4235… |
| 2 | 7214347eecf84628a8415ad21071bbb0 | 00:03:17 | 00:03:19 | 00:05:05 | 2048×2048, 04de226c… |
| 3 | e488752a4a794e8d92f141836a6b284b | 00:03:19 | 00:03:21 | 00:05:10 | 2048×2048, 49bd246f… |
- Exactly 1 POST per cell (`paid/guard.json`, `paid/http-allowed.jsonl`). All completed, size_check match, no size notice.
- Balance 20.479508 (00:03:08) → 20.306708 (00:05:12): **delta $0.1728 = quoted 3 × $0.0576**. Post check `preflight/readonly-post-paid.json`: 10 tasks, the 3 new ones completed, none in flight.
- #911 ledger: $0.4833 + $0.1728 = **$0.6561**, remaining **$0.3439**. Conservative (195faab6 counted): $0.5868 + $0.1728 = **$0.7596**, remaining **$0.2404**.

## Outputs / review
- Finals: `downloads/final-cell{1,2,3}.png` (originals in `runtime/output/wavespeed/ws_<task12>_0.png`).
- Side by side (cell crop left, final right): `review/side-by-side-cell{1,2,3}.png`. Contact sheet (reference + 3 finals): `review/contact-sheet-finals.png`. Crops: `review/cell-crops/`. Measurements: `review/measurements.json`.

## Verdict (QA visual + measured; details in verdict.json)
| item | cell 1 | cell 2 | cell 3 |
|---|---|---|---|
| a orientation/form vs cell | PASS | PASS (left cup outer shell, right cup cushion, not mirrored) | PASS |
| b identity vs reference | PASS | PASS (small added hinge detail) | HOLD (headband ends in a short stub, inherited from the preview cell) |
| c framing | HOLD (enlarged 0.69→0.93 of height, bottom margin 2.6%) | HOLD (0.74→0.93, bottom 2.1%) | PASS |
| d background #FFFFFF | HOLD (off-white mean 253.6, 9% exactly 255) | HOLD (mean 254.3, ~50% exactly 255) | PASS (77–85% exactly 255, min 250) |
| e material/lighting (separate) | PASS | HOLD (reads near-black, darker than reference) | PASS (narrower tonal range) |
| overall | HOLD | HOLD | HOLD |

The left/right orientation fix works in all three cells; cell 2 is no longer mirrored. The remaining HOLDs are framing scale, an off-white background, cell 2 colour depth and the cell 3 headband stub. Stopped: no retry, no merge, no post.
