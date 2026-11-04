# #687 social + character pilot — 交接
- Done: social ex01-05 all generated (ex01 regen ok via base64) + local text/OCR + L/R in `social/`; character ex01 PILOT (head swap, brown shoes) in `character/`. OCR: 0 verbatim gold strings on all 5.
- CTAs changed off gold ("TRY NOW"/"SHOP NOW" are gold copy): GET YOURS / LISTEN IN / DISCOVER / GRAB A BOTTLE.
- gen.py: pre-check $0.0378, resumes a `.pending.json` prediction instead of resubmitting.
- Next: design review of social ex01/03/04/05 + character ex01 pilot; on PASS run `jobs/c_ex02..06.json` (runner /workspace/g687, `set -a; . secrets env`).
- Spend: $0.2646 / $0.50 actual (7 calls). Balance: $43.907449.
- Accounting (tech lead 22:53): per-call cost attributed by prediction id (7 ids in calls.jsonl, `attributed` 0.0378 each = $0.2646). The prediction result record has no charge field, so attribution = per-call balance delta, each exactly $0.0378. Reconciliation: balance 44.172049 → 43.907449 = $0.2646, diff vs attributed $0.0000 (≤ $0.01 OK). All calls done before the smoke started spending.
- 22:58 CST character ex01 redone per SOP, $0, no generation: `character/composite_head.py` pastes only head+hair ellipses (front/side/back) from the pilot output onto gold, 22px feather, LAB colour match on the neck ring, white bg untouched. Outside the masks = gold (mean abs diff ≈ webp noise). Shoes/jacket/pose stay gold (so the "brown shoes" tweak is dropped). OCR: no text. ex02-06 HELD until tester smoke done + design PASS. Spend unchanged $0.2646; balance $43.907449.
- 23:03 CST character ex01 rev2: 1 call `ee20445d…` $0.0378 (attributed; balance delta exactly 0.0378). Composited heads onto gold with composite_head.py, ellipses `[[412,98,88,112],[1015,90,92,105],[968,150,50,45],[1620,85,82,98]]` feather 22 (extra side-chin ellipse removes gold beard ghost). Zoom-checked: no grey left at back hairline / behind ear. OCR no text. Spend $0.3024/0.50; balance $43.862706. Next: design review; ex02-06 still HELD.
- 23:30 CST character ex02–06 (design PASS on ex01 rev2 @88c25eed): 5 calls $0.189 (ids cddacd24, a23c7cca, 7769d4d8, df31f6ab, aebb21d6; each balance delta exactly 0.0378). Prompts in `character/c_ex0N.json`; ellipses + feather in `character/comp5.py`. composite_head.py gained `COLOR_MATCH=0` (used for anime ex02/ex06: navy-jacket ring stats greyed the skin). ex04 close-ups needed extra ellipses for gold bun ghost + loose strands. ex05 back view hood-only (no face) left gold. RapidOCR (/workspace/ocrv): ex02–05 no text; ex06 keeps the gold's generic stage labels (STAGE 1/2/3, BEFORE TRANSFORMATION, MAGICAL GIRL FORM, DARK FALLEN FORM) as gold pixels — not brand, flag for design/tech call. Known: ex06 stage-2 face has eyes closed (gold: open), ex02 hair now shoulder-length chestnut.
- Spend $0.4914/0.50 (13 calls). Balance $43.673706.

## 交接
- Tip: see `git log -1` on docs/687-prompts.
- Done: character ex01–06 generated+composited, L/R `character/lr_c_ex0N.jpg`.
- Next: design review ex02–06; #687 cap nearly used ($0.0086 left) — any redo needs a new budget from 技术经理/Angela.
- Spend $0.4914 / $0.50; balance $43.673706.
