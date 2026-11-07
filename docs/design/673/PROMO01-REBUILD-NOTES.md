# PROMO01-REPLACE rebuild notes

**When:** 2026-11-07 Asia/Shanghai  
**Why:** Original `/workspace/promo01/PROMO01-REPLACE.md` (Jingmeng 2026-11-05) is missing from workspace, `docs/design/673/`, and #745. User asked to rebuild from gold + documented rules — **no freeform inventing**.

## Method

1. **Gold image source:** lovart promo-ecommerce **ex02** gold, recovered as the **left panel** of  
   `docs/design/673/next/lr/LR-promo-ex02-platform.jpg` (金标｜main｜tip).  
   Note: `673/wash/promo-ecommerce/examples/01.webp` on main is the **washed tip** (already partially winterized), **not** the gold. Featured `01.webp` is a 1024² crop of the wash. Rebuild before-column is gold, not wash.
2. **OCR engine:** `rapidocr-onnxruntime` (same family as repo `docs/design/673/next/ocr.py`). Tesseract packages were unavailable in apt on this box; RapidOCR is the project-standard path.
3. **OCR procedure:** upscale gold panel ×3 + 4×4 tiled crops; dedupe by approx bbox+text. Also OCR `docs/qa/736/dropped.jpg` (gold crops) and merge string lists from:
   - `docs/design/673/next/lr736/ocr2way-nb21.json` → `g_promo.png`
   - `docs/qa/736/drops.json` (12 QA spots + bboxes)
   - `docs/design/673/next/MODEL-EDIT-PROMPTS-736.md` (12 agreed brand/copy rows)
   - Issue #745 body (winter map + KEEP list + 105/78/27 + A–E/F–H)
4. **Normalization:** OCR typos fixed when a documented source had the canonical gold string (e.g. `LYSENDOUBLEELEVEN` → `LYSEN DOUBLE ELEVEN`, `一热销推荐一` → `—热销推荐—`, `BONBUN镇店`).
5. **After column:** only from #745 hard map + #736×12 + KEEP list. Numeric coupon faces / secondary badge English / some winter synonyms not in those docs were filled to stay consistent with the existing wash tip (`ocr_promo_ex02.txt`) and marked **product sign** in notes — product must nail or reject those.
6. **No commit / no PR / $0 WaveSpeed.** Files only under `/workspace/promo01/`.

## Row counts

| | this rebuild | issue #745 target | gap |
|---|---:|---:|---:|
| total | 106 | 105 | +1 |
| replace | 78 | 78 | +0 |
| keep | 28 | 27 | +1 |
| A–E replaces | 39 | 31 | +8 |
| F–H replaces | 39 | 47 | -8 |

OCR under-count vs 105 is expected: dense RapidOCR on a **downscaled** LR gold panel (~851×1280) misses some micro labels; compounds may be 1 block on gold but 2–3 OCR pieces (and vice versa). Do **not** pad with invented strings to force 105 — product/design should add/merge rows against a full-res gold when signing.

## Zone map used

Approximate on the 2×3 sheet (full ~1690×2560):

| zone | region |
|:----:|---|
| A | top-left price banners |
| B | top-right tickers |
| C | second price row / mid shared |
| D | mid-left shopping bags + barcode |
| E | mid-right coupons (upper) |
| F | mid-right coupons (lower) |
| G | bottom-left feature badges |
| H | bottom-right seals + sale tag |

Pass 1 = A–E, Pass 2 = F–H (per #745 EL). Zone letters may not match Jingmeng’s lost original bucketing; L/R sign-off should re-bucket if needed.

## Top uncertainties (product must sign)

1. **Coupon face values & thresholds** not in #745 hard map (`¥200/300/1200/1500/500`, `满1999/2999/5999…`, `预估到手￥599→459`, `全店6期→3期`, `日常价 199→179`, `169→139`): inferred from current wash tip — **confirm or rewrite**.
2. **`不敏感` → `暖意足`** and other badge pairs around `敏感肌→怕冷星`: only `敏感肌` is hard-mapped; pair text is proposed.
3. **EN badge afters** (`CARE/GOOD/RAW/SALON/SOFT TOUCH/LEVEL CARE/TRAVEL CARE` → `PURE/PICKS/…`): gold fragments are noisy in OCR; afters follow wash tip style — design should lock.
4. **`爆款价→人气价`, `付定立减→预约优惠`, `加入店铺会员…→关注店铺领取冬日好礼>>`**: winter CTAs from wash tip, not #745 body.
5. **`夹克…7折` kept 7折** (only leading 夹克→冬装): confirm whether jacket 7折 also becomes 8折/78折.
6. **Zone A–E / F–H replace counts ≠ 31/47**: rebuild gap from OCR under-count + bucketing; do not treat as EL budget change until design re-buckets.
7. **Full-res gold file** (`g_promo.png`) was not in the workspace — only LR left panel + dropped crops. A higher-res gold OCR may surface the missing ~rows to hit 105 exactly.

## OCR failures / noise

- Vertical `LYSEN DOUBLE ELEVEN` often read as `LYSENDOUBLEELEVEN` (normalized).
- `双11专享` sometimes `双1专享` / `双Ⅱ专享`.
- Ornate seal `—热销推荐—` → `一热销推荐` / `一热销推荐一`.
- Tiny EN stamps (`SALON`, `SOFT TOUCH`, `SAAD`/`GOOD`) low confidence; some g_promo tokens (`GO`,`OD`,`SAAS`,`TEAET`) treated as garbage and omitted.
- Currency-only digits (`200`,`300`,`1500`…) ambiguous without bbox→coupon binding; notes point to parent coupon name.
- Tesseract not installed (apt packages missing on box); relied on RapidOCR only.

## Outputs

- `/workspace/promo01/PROMO01-REPLACE.md` — the table
- `/workspace/promo01/REBUILD-NOTES.md` — this file
- `/workspace/promo01/ocr_work/` — intermediate OCR JSON + gold panel PNG (scratch; not for docs commit unless asked)
