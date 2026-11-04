# #673 C batch (20 rows, prompts v4 @ 7a5dc5a6) — google/nano-banana-2.1/edit, 1K, gold as base
Balance 45.192649 → 44.436649 = **$0.756** (20 calls, 0 retries). C total incl. pilots = **$0.8316** ≤ $1. 1 batch retry still unused.
Duplicate check: prediction history before the run had only the 2 pilot jobs.
Outputs `batch/<name>.webp` (upscaled to gold size, Lanczos+unsharp), L/R `batch/lr/LR-<name>.jpg`, meanAbs `meanabs.json`.

| # | name | meanAbs | half-screen self-check | verdict |
|---|---|---|---|---|
| 1 | logo-abstract-cover | 8.3 | ALCEDO wordmark; mirrored birds redrawn but read as herons more than kingfishers | PASS? design call |
| 2 | logo-abstract-ex02 | 5.3 | fictional lattice mast + single pod, LUMEN SPIRE/HARBOR CITY; no spheres | PASS |
| 3 | logo-abstract-ex09 | 19.0 | terracotta stacked slabs, STRATA | PASS |
| 4 | logo-abstract-ex06 | 13.6 | ochre gecko on fern, VERDANT | PASS |
| 5 | logo-abstract-ex10 | 10.2 | drinking fawn + teal pond/lily, STILL POND | PASS |
| 6 | ppt-visual-cover | 17.3 | ELEGANT DECKS, new props/columns | PASS |
| 6a | ppt-p01 | 6.1 | only title changed (栖于云海之上); same scene | **FAIL → style-ref** |
| 7 | ppt-p02 | 26.4 | fjord coastline, no towers | PASS |
| 8 | ppt-p07 | 6.4 | same bedroom; only side text changed | **FAIL → style-ref** |
| 9 | ppt-p08 | 23.7 | hot tub / lantern path / misty lake | PASS |
| 10 | ppt-p10 | 2.0 | same house/scene; only title changed | **FAIL → style-ref** |
| 11 | naive-cover | 29.2 | fox / hippo / girl + kite; skill title kept | PASS |
| 13 | naive-ex02 | 32.4 | braided girl jumping, yellow raincoat | PASS |
| 14 | naive-ex03 | 38.3 | pink ostrich at standing desk | PASS |
| 15 | naive-ex04 | 31.2 | fox / hippo / girl trio | PASS |
| 16 | promo-cover | 1.4 | face inpaint returned essentially the same man | **FAIL → style-ref (face ref)** |
| 17 | promo-ex01 | 38.9 | brands mostly changed, but gold text left: LUMVEX on camera, 丽森家居/…EN, 定格光影, 水润丰唇/持久显色, cookie bullets 1盒解锁6款口味/进口黄油香浓酥脆/买2盒加赠新品试吃; same models | **FAIL (gold text)** |
| 18 | promo-ex02 | 22.3 | numbers changed, but gold copy left: 官方立减15%, 全店6期免息/¥400会员专属礼券, 单笔实付≥1000, 现货速发, coupon sublines; one coupon blank | **FAIL (gold text)** |
| 21 | photo-split-cover | 15.6 | river path, 出发 sign, kite, new notes | PASS |
| 22 | photo-split-ex01 | 22.4 | tea-tin character, tea terraces, new title | PASS |

## ppt stitched
`ppt-visual-ex01-stitched.webp` 1920×5235 (p01,p02,p07,p08,p10), `ppt-visual-seams.jpg`. Join lum diff (8px rows): 73.6 / 12.6 / 7.0 / 9.1; gold's own joins range 3.4–63.6. Join 1 is the dark title → aerial page change; no white/black line. Stitch should be redone after 6a/8/10 are fixed.

## Not spent (per rule)
Last retry kept. Proposed style-reference route for 6a, 8, 10, 16: same model, gold passed only as style reference, new composition from prompt, $0.04 each = $0.16 → total $0.99 (just under cap; leaves no margin). #17/#18: local text fix (free) or style-ref. Needs design + 技术经理 OK.
