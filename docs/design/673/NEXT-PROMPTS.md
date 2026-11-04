# #673 next round: generation specs (DRAFT, NOTHING generated, $0 spent)

Base SHA: `4451587222727a03fa603027215bb832705e3f5b`. Model for all rows: **WaveSpeed `google/nano-banana-2.1/edit`, 1K, ~$0.0378/img**. Masks are made locally (free) and sent as the edit mask. Output is upscaled locally (Lanczos + light unsharp, free) to the gold's size.

## Budget and rules
| group | approval | images | cap | retries |
|---|---|---|---|---|
| A: promo ex01 + ppt p07 | Angela OK (~$0.08) | 1 each | **$0.08 hard** (2 × $0.0378 = $0.0756) | **none**: if either fails, stop and report, no regeneration |
| B: taobao-product | 技术经理 separate cap | 1 | **$0.30** | stop after 2 consecutive fails; worst case 3 attempts = $0.1134 |

- **Balance log:** read the WaveSpeed balance before the first call and after the last call of each group, write to `docs/design/673/next/balance.log` (before, after, diff, per-call ids). Diff must equal the call count × $0.0378.
- **Shipping:** A goes in its **own small PR after the C-group swap PR merges** (not mixed into the swap PR or #726). B is tracked separately.
- **Pass check (all rows):** (1) at half-screen it is clearly a different image from the gold in the changed parts; (2) still reads as the same skill/layout; (3) OCR finds no gold copy; (4) faces are not lookalikes of the gold's people (design judgement).
- Prompt review by design + tech before any call.

## A1. promo-ecommerce ex01 (6-poster grid) re-wash
- **Gold/base:** `docs/design/673/gold/promo-ecommerce/ex01.webp` · 2560×2214 (≈7:6). 1K = **1184×1024** → upscale to 2560×2214.
- **Mask (local, per wash SOP, whole-head):** feathered ellipses (blur 35) over the full head + hair of the two models: poster 1 (trench woman, top-left) and poster 2 (denim man, top-centre). Per 技术经理 the paid call is **head-only**.
- **Products / brand / text (free, local, no extra call):** all gold text (VANT, LENO, glossa, LYSEN, LUMVEX, BONBUN, 双11, 天猫/淘宝 logos, prices, dates, APO-SUMMICRON, RESSE on the tube) is removed by local fill and retypeset with the C-PROMPTS #17 copy: ORVA · 秋序上新 · 10.08—10.31 / MIRO 轻衫季 · 预售 10.12 开启 / 付定立减 66 元 / velle velle · 限时立减 15 / 换个心情过冬！· 11 月 5 日 抢先购 / KORAX × 年终盛典 · 全画幅新旗舰 / 黄油小饼 · CRUMBO · 满 199 减 30. Product packaging marks (camera body, cookie box, lip tube) are cleaned locally.
- **Prompt:** "Inpaint only the masked heads. Poster 1: a completely different woman, at least as attractive, same three-quarter angle and wind-blown pose, sunglasses kept, dark straight shoulder-length hair. Poster 2: a completely different young man, at least as good-looking, same frontal angle and straight gaze, short black hair, no glasses. Keep each neck line, clothing collar, lighting direction, colour grade and grain exactly. Leave everything outside the mask unchanged. Generic generated people, not identifiable. No text."
- **Cost:** 1 × $0.0378. **Retry:** none.
- **Open point for 技术经理/设计:** head-only means the products themselves (trench, sofa, camera, cookie shapes) stay the gold's; only brand/text change. If design requires new products, that needs a wider mask or more calls and is **outside the $0.08** — needs a new OK.

## A2. ppt-visual ex01 p07 redo
- **Gold/base:** `ex01.jpg` crop y=6282–7329 · 1920×1047 (≈16:9). 1K = **1344×768** → upscale to width 1920, centre-crop 1920×1047.
- **Mask:** none for the scene (full-frame edit, gold as base so grade/grain carry over). After generation, the gold's left text column zone is overwritten locally with our text (free).
- **Prompt:** "Same dark cinematic slide, same muted olive-grey grade, film grain and low-key light as the reference. Replace the bedroom entirely with a quiet **study / tea room**: a low wooden tea table with a clay teapot and two cups, a bookshelf of linen-bound books on the left, tatami-like woven floor. A person **seen from behind**, sitting cross-legged at a large window, in a loose undyed linen robe, looking out at misty mountain ridges and bamboo (not pine forest, no bed, no stone wall). Leave the lower-left area dark and empty for text. No text, no page dots."
- **Local text (free):** small caps top-left "QUIET PRINCIPLES"; list 01–04 「静 / 茶 / 书 / 窗」 with short captions; page mark /07 and **5 dots** to match the 5-page deck.
- **Stitch:** long image back to **5 pages p01, p02, p07, p08, p10** → 1920×5235, re-run the C-PROMPTS seam check (target < 18/255 per join, 4 px dark divider), regenerate `ppt-visual-seams.jpg`.
- **Cost:** 1 × $0.0378. **Retry:** none (fail → keep the current 4-page deck).

**Group A total: $0.0756 ≤ $0.08.**

## B. taobao-product re-wash (true wash, same family)
- **Gold/base:** `docs/design/640/78/gold/taobao-product/cover.webp` · 1600×1198 (≈4:3). 1K = **1184×864** → upscale to 1600×1198. Earlier result was rejected as too different; composition lock per `docs/design/643/NOTES-COVER-FEEDBACK.md` (left thumbnail grid + right street hero).
- **Mask:** none (full-frame edit) so the 3+2 thumbnail grid, right hero and crosswalk/European street layout stay.
- **Prompt:** "Same e-commerce layout as the reference: a 3+2 grid of small product photos on light grey on the left, one large street hero photo on the right. Change the product and model: **a different woman with short dark bob hair**, at least as attractive, wearing a **cream knit polo top with a camel high-waist wide-leg trouser** and brown loafers, same poses per tile (standing studio, seated on a bench, standing, walking on a crosswalk, flat-lay of the trousers with a brown belt). Hero: she walks left-to-right across a crosswalk on a sunlit **stone-arcade street** (different buildings, warm late-afternoon light). Hero title, large white bold Chinese "**松弛一身**", subline "高腰阔腿西装裤 · 羊毛混纺". No other text, no logos, not identifiable."
- **Changes vs gold:** 廓形之选/高腰阔腿桶型裤·棉莫代尔混纺 → new copy; white trousers + black tank → camel trousers + cream knit; blonde bun → dark bob; street redrawn. Must still read as the same skill/composition.
- **Cost:** 1 × $0.0378, max 3 attempts ($0.1134) ≤ $0.30. **Retry:** stop after 2 consecutive fails and rewrite the prompt for review.

## Totals
A $0.0756 (cap $0.08, no retries) + B $0.0378–$0.1134 (cap $0.30). Current balance (end of C group): $44.285449.
