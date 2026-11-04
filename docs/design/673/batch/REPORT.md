# #673 C wash: batch + round 2 (技术经理 / design / QA final decisions, 2026-11-04)
## Spend (cap $1, now used up; stop)
| step | before | after | cost |
|---|---|---|---|
| pilots v1+v2 | | | $0.0756 |
| batch, 20 rows (`balance.log`) | 45.192649 | 44.436649 | $0.7560 |
| round 2: p01, p07, p10, #16 (`balance-round2.log`) | 44.436649 | 44.285449 | $0.1512 |
| **C total** | | | **$0.9828** |
No more paid calls are possible under the cap. Before each round I checked the prediction history: nothing new after the batch's last job (13:20:37Z), so no duplicates. Round 2 was resumed after an interrupted shell; already-submitted ids were reused from `state2.json`, so nothing was paid twice.

## #16 root cause (diagnosed for free before the paid call)
- The mask was **applied correctly**: it was composited locally (the model has no mask input). The parameters were fine, and the model **did not** return the input unchanged: raw vs gold in the face area differed by 10.5.
- Cause 1: `cover.face-mask.png` was a small circle (eyes to mouth only, about 13% of the frame). The gold's blond hair, hairline, jaw, chin and ears stayed, so the new eyes and brows sat inside the old head, and it still read as the same man.
- Cause 2: the prompt kept "the same hair", so even the raw output kept a blond head.
- Cause 3: the 64×64 grey meanAbs metric cannot see an identity change in a same-pose B&W portrait (any face-only swap scores about 1–10), so 1.4 was misleading on its own.
- Fix: a whole-head feathered mask (`gold/promo-ecommerce/cover.head-mask-v2.png`, ellipse 315,135–795,800, blur 35) and the prompt "completely different man, short dark hair". Result: a clearly different dark-haired man. Shirt, both hands and fingers, slice offsets, white background and B&W look are kept. **PASS (visual)**, meanAbs 9.9.

## Rows (all L/R images in `lr/LR-<name>.jpg`; meanAbs in `meanabs.json`)
| row | file | meanAbs | what changed | status |
|---|---|---|---|---|
| logo cover | logo-abstract-cover.webp = **ex06 VERDANT** | 16.2 (vs old gold cover) | old ALCEDO cover dropped; logo examples are now 4 (ex02, ex06, ex09, ex10) | PASS* |
| logo ex02 / ex09 / ex06 / ex10 | | 5.3 / 19.0 / 13.6 / 10.2 | unchanged | PASS* |
| ppt cover | ppt-visual-cover.webp = **4:3 crop of p02** (x500–1833, y0–1000, to 2048×1536) | 44.9 | old cover with its gold text dropped; p02 picked over p08 (one clean fjord image, no captions); crop leaves out the page number, arrows and pager dots; no text at all | PASS |
| ppt p01 | ppt-p01.webp | 26.4 (was 6.1) | style-ref call: new cliff, sea and cloud scene; 栖于云海之上 | PASS* |
| ppt p02 | ppt-p02.webp | 26.3 | page number 02/10 changed to **02/05** locally | PASS* |
| ppt p07 | ppt-p07.webp | 26.5 (was 6.4) | style-ref call: new room and camera; gold label SPATIAL PRINCIPLES replaced locally with FOREST RETREAT. Still a bed facing a forest window, so the theme is close to gold | borderline, design to check |
| ppt p08 | ppt-p08.webp | 23.7 | unchanged; no page number | PASS* |
| ppt p10 | ppt-p10.webp | 16.3 (was 2.0) | style-ref call: glass pavilion on a hill, navy dusk; 让风景留在窗里 / THANK YOU | PASS* |
| ppt stitched | ppt-visual-ex01-stitched.webp 1920×5235 | seams **7.2 / 9.2 / 6.6 / 1.8** (raw 70.1 / 12.3 / 9.5 / 2.4) | 48 px dark fade at the p01→p02 join, plus a 4 px dark divider at every join; `ppt-visual-seams.jpg` redone | PASS |
| naive cover / ex02 / ex03 / ex04 | | 29.2 / 32.4 / 38.3 / 31.2 | unchanged | PASS* |
| promo cover (#16) | promo-cover.webp | 9.9 | see the root-cause section above | PASS (visual) |
| promo ex01 | moved to `pulled/` | – | pulled this round (models and products are the gold's) | NEXT ROUND |
| promo ex02 | promo-ex02.webp | 22.8 | every QA-CSV hit replaced locally (inpaint plus Noto CJK text in the sampled colour), see below; blank coupon filled with ¥180 / 满1599元可用 | PASS* |
| photo-split cover | | 15.6 | unchanged (2026年 is a generic date stamp) | PASS* |
| photo-split ex01 | photo-split-ex01.webp | 22.4 | slogan 一茶一水，当思自然之恩 changed to **雾是山的被，茶是春的信。** (LXGW WenKai). That line was already in the top-left note, so I changed the top-left note to 采一芽新绿，寄一封春天。 to avoid a duplicate (design to confirm) | PASS* |

\* meanAbs < 40: the PASS relies on **design's half-screen visual check**, not on the 40 threshold.

### promo ex02 replacements (QA CSV list + REPORT)
官方立减15%/可叠加会员券 → 满额再享9折 / 新客专享 · 加入店铺会员… → 关注店铺 领取冬日好礼 >> · 官方立减15% → 新客满减 9折 · 199 → 229 · 秋冬新品 件低至85折 → 冬装上新 第二件88折 · 付定立减 → 预约优惠 · 全店6期免息 → 全店3期免息 · ¥400会员专属礼券 → ¥260新客礼券 · 单笔实付≥1000 赠礼品 → 满额≥1288 送围巾 · UP TO / OFF → SAVE / NOW · 现货速发 → 当天发货 · 人气爆款 (bag) → 冬季热卖 · 全画幅配件券 → 镜头清洁券 · 点击领取 → 立即抢券 · vertical 点击领取 → 马上领用 · 旗舰相机券 → 冬季焕新券 · 天然配方 → 臻选原料 · 人气爆款 (shield) → 冬日必入 · 品质保障 → 放心之选 · blank coupon → ¥180 满1599元可用.
Left as is: the CSV hits 200 / 300 / 1500 / 1200 / ¥300 (the gold's numbers; ours are 100 / 250 / 800 / 120 / 600, already different, and QA matched them only fuzzily), plus generic words like 爆款价/人气价. Small inpaint traces are visible at 100% zoom on the gradient badges.

## Still not passing / next round (about $0.12, to be quoted with taobao-product; no budget left in C)
1. promo ex01: pulled; needs new models and products (style-ref route).
2. logo cover redo (optional; ex06 stands in for now).
3. ppt p07: borderline (same bed + forest-window theme as the gold); design to decide whether it needs a redo.
4. ppt p02/p08 still show a 10-dot pager under the image (only the numeric page label was changed); fix locally for free next time if design wants it.
