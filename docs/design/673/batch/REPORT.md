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
| ppt cover | ppt-visual-cover.webp = **4:3 crop of p08** (3-panel grid, x262–1658 of 1920×1047, to 2048×1536, gold size; both gutters visible), darkened to 62%, plus our own big title **山野 / 栖居** in Noto Serif CJK (same thin serif as the p01 title 栖于云海之上), set large on the left like the PREMIUM SLIDES layout, with small VOL.02 and SLOW STAYS / IN THE WILD lines. No gold text; a clipped NATURAL RETREATS fragment at top left was patched out. Cover bottom rebuilt from the fixed p08 (clean captions, 4-dot pager), no garbled text (OCR-checked) | 44.9 | PASS* (design) |
| ppt p01 | ppt-p01.webp | 26.4 (was 6.1) | style-ref call: new cliff, sea and cloud scene; 栖于云海之上 | PASS* |
| ppt p02 | ppt-p02.webp | 26.3 | page number changed to **02/04**; pager redrawn as **4 dots** (2nd active) | PASS* |
| ppt p07 | moved to `pulled/ppt-p07.webp` | 26.5 | **design FAIL** (soft wash: same bed + forest-window theme as gold). Not in the long image this round | NEXT ROUND |
| ppt p08 | ppt-p08.webp | 23.7 | garbled small captions replaced with our own: 雪松温泉 / 露天汤池 · 户外平台 · 森林环绕; 灯光石径 / 石阶步道 · 暖光夜行 · 静谧探索; 晨雾湖畔 / 观景平台 · 晨曦微光 · 湖畔静居. Pager redrawn as **4 dots** (3rd active); no page number | PASS* |
| ppt p10 | ppt-p10.webp | 16.3 (was 2.0) | style-ref call: glass pavilion on a hill, navy dusk; 让风景留在窗里 / THANK YOU | PASS* |
| ppt stitched | ppt-visual-ex01-stitched.webp 1920×4188, **4 pages: p01, p02, p08, p10** | seams **8.6 / 5.8 / 2.4** (raw 69.7 / 4.6 / 2.3) | 96 px dark fade on both sides of the p01→p02 join, plus a 4 px dark divider at every join; `ppt-visual-seams.jpg` redone (3 joins) | PASS (design) |
| naive cover / ex02 / ex03 / ex04 | | 29.2 / 32.4 / 38.3 / 31.2 | unchanged | PASS* |
| promo cover (#16) | promo-cover.webp | 9.9 | see the root-cause section above | PASS (visual) |
| promo ex01 | moved to `pulled/` | – | pulled this round (models and products are the gold's) | NEXT ROUND |
| promo ex02 | promo-ex02.webp | 22.8 | every QA-CSV hit replaced locally (inpaint plus Noto CJK text in the sampled colour), see below; blank coupon filled with ¥180 / 满1599元可用. OCR round: coupon fine print fixed to 满2099元可用 / 满3999元可用 / 满2000可用, pill label → 限时专享券, red tab → 关注领取, 日策价 → 日常价, 镜头清洁券 confirmed | PASS* |
| photo-split cover | | 15.6 | unchanged (2026年 is a generic date stamp) | PASS* |
| photo-split ex01 | photo-split-ex01.webp | 22.4 | slogan 一茶一水，当思自然之恩 changed to **雾是山的被，茶是春的信。** (LXGW WenKai). That line was already in the top-left note, so I changed the top-left note to 采一芽新绿，寄一封春天。 to avoid a duplicate (design to confirm) | PASS* |

\* meanAbs < 40: the PASS relies on **design's half-screen visual check**, not on the 40 threshold.

### promo ex02 replacements (QA CSV list + REPORT)
官方立减15%/可叠加会员券 → 满额再享9折 / 新客专享 · 加入店铺会员… → 关注店铺 领取冬日好礼 >> · 官方立减15% → 新客满减 9折 · 199 → 229 · 秋冬新品 件低至85折 → 冬装上新 第二件88折 · 付定立减 → 预约优惠 · 全店6期免息 → 全店3期免息 · ¥400会员专属礼券 → ¥260新客礼券 · 单笔实付≥1000 赠礼品 → 满额≥1288 送围巾 · UP TO / OFF → SAVE / NOW · 现货速发 → 当天发货 · 人气爆款 (bag) → 冬季热卖 · 全画幅配件券 → 镜头清洁券 · 点击领取 → 立即抢券 · vertical 点击领取 → 马上领用 · 旗舰相机券 → 冬季焕新券 · 天然配方 → 臻选原料 · 人气爆款 (shield) → 冬日必入 · 品质保障 → 放心之选 · blank coupon → ¥180 满1599元可用.
Left as is: the CSV hits 200 / 300 / 1500 / 1200 / ¥300 (the gold's numbers; ours are 100 / 250 / 800 / 120 / 600, already different, and QA matched them only fuzzily), plus generic words like 爆款价/人气价. Small inpaint traces are visible at 100% zoom on the gradient badges.

## Design PASS (recorded)
#16 promo cover, ppt p01, ppt p10, the stitch seams, and the photo-split slogan/top-note change.

## OCR check (free, local)
tesseract was not installable (apt mirror down), so RapidOCR (chi_sim+eng models) was run on every changed page: ppt p01/p02/p08/p10, the cover and promo ex02. No garbled captions or coupon text remain. Known leftover: the tiny decorative circular rim text on the promo ex02 stamp badges (gold-style pseudo-English) is still unreadable; flag if design wants it cleared.

## Next round (to be quoted; no budget left in C)
1. promo ex01: pulled; needs new models and products (style-ref route).
2. ppt p07: design FAIL; redo with a style reference, subject: a study or tea room, person seen from behind sitting at the window. Then re-stitch to 5 pages (/05, 5 dots).
3. taobao-product.
(logo cover redo dropped: ex06 is final.)
