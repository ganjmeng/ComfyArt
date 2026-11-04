# #687 social + character pilot — 交接
- Done: social ex01-05 all generated (ex01 regen ok via base64) + local text/OCR + L/R in `social/`; character ex01 PILOT (head swap, brown shoes) in `character/`. OCR: 0 verbatim gold strings on all 5.
- CTAs changed off gold ("TRY NOW"/"SHOP NOW" are gold copy): GET YOURS / LISTEN IN / DISCOVER / GRAB A BOTTLE.
- gen.py: pre-check $0.0378, resumes a `.pending.json` prediction instead of resubmitting.
- Next: design review of social ex01/03/04/05 + character ex01 pilot; on PASS run `jobs/c_ex02..06.json` (runner /workspace/g687, `set -a; . secrets env`).
- Spend: $0.2646 / $0.50 actual (7 calls). Balance: $43.907449.
- Accounting (tech lead 22:53): per-call cost attributed by prediction id (7 ids in calls.jsonl, `attributed` 0.0378 each = $0.2646). The prediction result record has no charge field, so attribution = per-call balance delta, each exactly $0.0378. Reconciliation: balance 44.172049 → 43.907449 = $0.2646, diff vs attributed $0.0000 (≤ $0.01 OK). All calls done before the smoke started spending.
- 22:58 CST character ex01 redone per SOP, $0, no generation: `character/composite_head.py` pastes only head+hair ellipses (front/side/back) from the pilot output onto gold, 22px feather, LAB colour match on the neck ring, white bg untouched. Outside the masks = gold (mean abs diff ≈ webp noise). Shoes/jacket/pose stay gold (so the "brown shoes" tweak is dropped). OCR: no text. ex02-06 HELD until tester smoke done + design PASS. Spend unchanged $0.2646; balance $43.907449.
