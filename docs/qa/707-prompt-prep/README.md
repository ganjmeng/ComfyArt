# #707 prompt prep ($0 — no paid API calls)

Prep only for the remaining [#707](https://github.com/ganjmeng/ComfyArt/issues/707) visual gate. Nothing in this folder was sent to WaveSpeed, kie, Replicate, or DeepSeek. No gold cover was modified. `docs/qa/707-local-canvas` was clean and was left untouched. Dist was not rebuilt.

Design should check these prompts against the gold images, then Angela confirms, before any money is spent. Cap for the later paid run is **$3** including a 1k pilot, the four-skill set, and LLM if the run goes through the skill agent.

Branch: `docs/707-prompt-prep`, based on main `2e1ad04c9978dca315e2b5a04980f479f61e6023`.

Raw GitHub URLs below are pinned to this tip's full SHA:

`TIP_SHA`

---

## 1. Scope

[#707](https://github.com/ganjmeng/ComfyArt/issues/707) (child of #704) still needs a current-main, WaveSpeed-only, full-pipeline run of **four skills**, one set each, with layout in the gold family and the sizes already declared on main:

| Skill | Declared size / ratio (product AC, 2026-11-10) | Layout family |
| --- | --- | --- |
| before-after | one still, 1024×1280, 4:5 | One left/right (or stacked) comparison card, same person and light, readable Before / After labels. Not 2–3 solo portraits, not a copy of the ref. |
| pose-fission | four stills, each 1536×2048, 3:4 | Same person, outfit, scene and light as the base photo; change only camera angle and framing. Four separate stills, not a grid. |
| game-art | one still, 1024×1824, 9:16 | Vertical mobile game UI (title bar, list or cards, a button, bottom nav). Theme follows the user; a character or poster request still has to live inside a UI slot. |
| linkedin-banner | one still, 1584×396 | Professional personal banner; readable type; headline in the right two thirds (left quarter is the avatar safe area). ≤10 steps, ≤3 minutes to done, one `generate_image`. |

Source-of-truth images (from `docs/qa/704/tip-lr/NOTES.md`, not the discarded Qwen rights):

- before-after: `docs/design/640/78/gold/before-after/cover.webp` (the card with clear type). The 643 wash cover is a dropped-text right and is **not** tip SoT.
- pose-fission: gold cover plus `643/wash/pose-fission/examples/01.webp`–`04.webp` (and the posepro stills). Gold ex01 is a single street photo; the cover itself is a 5-up collage and is not the output shape.
- game-art: `643/wash/game-art/examples/01.webp` (奔秋围棋 list UI). The anime poster on `docs/design/640/78/gold/game-art/cover.webp` is **rejected** as the typifying gold for this card.
- linkedin-banner: size and safe-area proof is `704-lr/linkedin-banner/fixed-input-v1/RIGHT.png` (1584×396). The typifying cover family is the personal banner on `docs/design/640/78/gold/linkedin-banner/cover.webp`.

Original Lovart user-input strings for these four golds were not in the repo. The Chinese skill inputs below are drafted to ask for the gold layout family with new faces and new marketing copy. Design should confirm them before the paid run.

---

## 2. Routing and known prices

Team routing used here (after #883 on main `2e1ad04c`):

- Realistic people: `bytedance/seedream-v5.0-pro` or `bytedance/seedream-v5.0-pro/edit`
- Poster / text: `openai/gpt-image-2.6-flare/text-to-image` or `.../edit`
- Masked / local API inpaint: `openai/gpt-image-2.6-sunburst/edit`
- Anime: `midjourney/text-to-image`
- Product / generic keep edits: `google/nano-banana-2.1/edit`

Person slots that only need a new face use **Seedream 5.0 Pro edit**, then a $0 local feathered-mask composite (WASH-SOP), so clothing, pose, light, grade and grain stay gold pixels. The alternate API-side masked path is Sunburst edit; it is listed, not used as the default.

Prices are from the repo only. Unknowns are marked unknown. Nothing was invented.

| Model id | Known USD | What is unknown | Source |
| --- | --- | --- | --- |
| `bytedance/seedream-v5.0-pro/edit` | **$0.0405** actual debit (list $0.045, discounted quote $0.0405) | Whether 2k or 4k costs more than this debit | `docs/qa/825-keepface/SPEND.md`, catalog list `tests/fixtures/wavespeed_catalog_subset.json` `base_price` 0.045 |
| `bytedance/seedream-v5.0-pro` (t2i) | **$0.0405** actual debit | Same size question | `docs/qa/825/SPEND.md` row D2 |
| `google/nano-banana-2.1/edit` | **$0.0378** actual debit (list $0.040, discounted quote $0.036) | — | `docs/qa/825-keepface/SPEND.md` |
| `google/nano-banana-2.1/text-to-image` | **$0.036** actual debit | — | `docs/qa/825/SPEND.md` row D1 |
| `openai/gpt-image-2.6-flare/text-to-image` and `...-sunburst/text-to-image` | Documented medium **1k $0.05 / 2k $0.10 / 4k $0.18**. Catalog `base_price` 0.05. Live debits in #825 were $0.09 and $0.045, so the bill follows quality and resolution. | Exact band for 1024×1824 and 1584×396 until a live `/model/price` quote | `api/gif_image.py` (`GPT26_STILL_USD`), fixture `base_price` |
| `openai/gpt-image-2.6-flare/edit` and `...-sunburst/edit` | Catalog `base_price` **$0.065**. Live 2.6 Sunburst edit debits **$0.0585–$0.072** | Exact 1k medium debit | fixture + `docs/qa/825/SPEND.md` B2/C3 |
| `openai/gpt-image-2.5-flare/text-to-image` | Documented medium 1k **$0.024** | Not used in this plan | `api/gif_image.py` |
| `midjourney/text-to-image` | Catalog `base_price` **$0.10** | No live debit in the repo | fixture |
| DeepSeek / skill-agent LLM | Not a WaveSpeed image price. #704 historically spent about **$0.009–$0.043 per skill** (balance residual) | Current per-skill LLM cost | #704 issue body |

Budget figures below use Seedream **$0.0405** per call, Flare t2i **$0.05** at 1k and a conservative **$0.10** when the long edge is over 1024 (2k documented). A live quote is required before submit.

---

## 3. Summary

| # | Slot | Base | Mask | Model | Pilot 1k (long edge 1024, same ratio) | Full / AC size | Est. / call | Copies to replace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P | before-after (pilot) | gold cover | faces + headline + disclaimer | `bytedance/seedream-v5.0-pro/edit` | 819×1024 (4:5) | — | $0.0405 | see §4 |
| 1 | before-after | gold cover | same | same | — | 1024×1280 (4:5) | $0.0405 | see §4 |
| 2 | pose-fission ex01 | `643/wash/.../01.webp` | none for the pose run; face+scene mask is on disk if a re-wash is asked | `bytedance/seedream-v5.0-pro/edit` | 768×1024 (3:4) | 1536×2048 (3:4) | $0.0405 | no marketing type on the gold |
| 3 | pose-fission ex02 | same base as #2 | same policy | same | 768×1024 | 1536×2048 | $0.0405 | none |
| 4 | pose-fission ex03 | same base as #2 | same policy | same | 768×1024 | 1536×2048 | $0.0405 | none |
| 5 | pose-fission ex04 | same base as #2 | same policy | same | 768×1024 | 1536×2048 | $0.0405 | none |
| 6 | game-art | layout ref: 643 wash ex01 (not the poster cover) | none (t2i) | `openai/gpt-image-2.6-flare/text-to-image` | 576×1024 (9:16) | 1024×1824 (9:16) | $0.05 at 1k; **$0.10 conservative** at AC size | 奔秋围棋 / 云山棋梦 and all list titles, nicks, dates, move counts |
| 7 | linkedin-banner | family: gold cover banner; size proof: 704-lr RIGHT.png | none (t2i) | `openai/gpt-image-2.6-flare/text-to-image` | 1024×256 (4:1) | 1584×396 | $0.05 at 1k; $0.05–$0.10 at 1584×396 (unknown band) | see §7 |

Primary paid set after a passing pilot: items 1 and 2–7 at AC size (item P is the 1k pilot of the same before-after card). Pose-fission is four calls from one base photo, which is the skill AC. Items: **7 full stills + 1 pilot still** (the pilot can be skipped as a second before-after if Angela accepts the AC-size card as the 1k-class check).

The 643 pose-fission examples already have the #670 new face (dark-brown bob with bangs). This plan does **not** budget a second face swap. The four paid pose-fission calls change only camera and framing, from `examples/01.webp` as `baseImage`. Face-and-scene masks are committed in case design asks for another local re-wash; that would be extra Seedream calls and is called out under open questions.

---

## 4. before-after (pilot + full)

**Slot:** before-after, one comparison card.

**Gold base:** `docs/design/640/78/gold/before-after/cover.webp` (1600×1200, 4:3 plate; the cream card is 683×910 at x=459, y=145, about 3:4).

- Raw: `https://raw.githubusercontent.com/ganjmeng/ComfyArt/TIP_SHA/docs/design/640/78/gold/before-after/cover.webp`

**Mask** (feathered, $0, committed; white = composite in):

- Faces only: `docs/qa/707-prompt-prep/masks/before-after-cover-faces.png`
  - Raw: `https://raw.githubusercontent.com/ganjmeng/ComfyArt/TIP_SHA/docs/qa/707-prompt-prep/masks/before-after-cover-faces.png`
- Faces + headline + disclaimer (recommended): `docs/qa/707-prompt-prep/masks/before-after-cover-faces-and-copy.png`
  - Raw: `https://raw.githubusercontent.com/ganjmeng/ComfyArt/TIP_SHA/docs/qa/707-prompt-prep/masks/before-after-cover-faces-and-copy.png`
- Overlay: `docs/qa/707-prompt-prep/previews/before-after-cover-mask-overlay.jpg`

`BEFORE` / `AFTER` labels, the cream card, the 2px gutter, and the dark plate stay mask = 0 (gold pixels).

**Model:** `bytedance/seedream-v5.0-pro/edit`, then local composite with the faces-and-copy mask.

**Resolution:**

- Gold plate is 1600×1200; the typifying card inside it is 683×910 (~3:4), not 4:5. Open question, see §10.
- Pilot 1k, 4:5 (skill ratio): **819×1024**.
- Full AC: **1024×1280**, 4:5. Do not default to 1024×1024. Do not outpaint the dark plate into the card.

**User input (zh), for the skill dialog:**

> 做一张左右对比卡，同一人、同一机位、同一光线。左侧是明显干燥缺水的皮肤，右侧是补水后更平滑细腻的效果。上方要有两行可读标题，两侧要有 Before / After 标签。不要出成 2～3 张单人像，也不要只复制原图。

**Generation prompt (EN):**

> Edit this exact before/after card. Keep the cream rounded card, the left/right split, the thin white gutter, the soft even studio light, the tight three-quarter close-up, the camera height, the gaze (looking slightly toward camera-left), and the typography style, size and placement. Keep the printed labels "BEFORE" and "AFTER" unchanged. Replace the person on BOTH sides with the same new woman, clearly a different person at a glance, equally or more attractive, not older, photoreal commercial-beauty skin with visible pores, no AI smoothness. Match the gold's olive-to-tan complexion, dark brown eyes, dark hair pulled back, and refined natural makeup. Keep the same head angle and the same light direction on both sides. The left (Before) panel stays drier, more textured and slightly dull; the right (After) panel is the same woman after hydration: smoother, more even, a healthy sheen, same identity. Replace the headline "Visibly hydrated. Noticeably smoother." with "Gently replenished. Clearly more even." in the same serif, two centered lines, similar length and position, keep the lettering effects. Replace the tiny footer "Illustrative visualization." with "For illustration only." in the same small centered style. One small scene tweak: warm the plain backdrop a half-step toward cream on both panels, still a seamless studio wall. Do not add a logo, a brand name, a product bottle, a grey box, or a local text overlay. Photoreal, no beauty filter, no reshoot of the crop.

**Estimated cost:** $0.0405 per Seedream edit (known debit). Pilot + full = $0.081 if both run. Size surcharge is unknown.

**Copy map (must change in the model, not as a later overlay):**

| Gold text | Replacement | Keep? |
| --- | --- | --- |
| Visibly hydrated. | Gently replenished. | no — marketing headline, similar length |
| Noticeably smoother. | Clearly more even. | no — marketing headline, similar length |
| BEFORE / AFTER | BEFORE / AFTER | yes — functional labels |
| Illustrative visualization. | For illustration only. | no — disclaimer rewritten, same tiny centered style |

No brand name on this gold. The same new woman is used on both panels. Do not reuse the 643 wash headline "Quenches dryness. Reveals smoother, healthier skin."

---

## 5. pose-fission (four stills, one set)

**Slot:** pose-fission. Default plan of four 3:4 stills from one base photo.

**Gold / base:**

- Typifying single-frame gold family: `docs/design/640/78/gold/pose-fission/cover.webp` (1600×1200 collage; output is **not** a collage).
  - Raw: `https://raw.githubusercontent.com/ganjmeng/ComfyArt/TIP_SHA/docs/design/640/78/gold/pose-fission/cover.webp`
- Paid-run `baseImage` (already the #670 washed face, same camel belted blazer, black shorts, gold sandals, hard street sun): `643/wash/pose-fission/examples/01.webp` (1529×2048, 3:4).
  - Raw: `https://raw.githubusercontent.com/ganjmeng/ComfyArt/TIP_SHA/643/wash/pose-fission/examples/01.webp`

**Mask:** none on the pose-changing calls (full-frame Seedream edit; the skill must change pose). Optional face+scene masks, rebuilt $0 from the #670 coords with a tighter ex04 wall box so the left sleeve stays gold:

| File | Raw | Notes |
| --- | --- | --- |
| `docs/qa/707-prompt-prep/masks/pose-fission-ex01-face-scene.png` | `https://raw.githubusercontent.com/ganjmeng/ComfyArt/TIP_SHA/docs/qa/707-prompt-prep/masks/pose-fission-ex01-face-scene.png` | face ellipse + collar ramp + grate box; ~8.8% |
| `docs/qa/707-prompt-prep/masks/pose-fission-ex02-face-scene.png` | `https://raw.githubusercontent.com/ganjmeng/ComfyArt/TIP_SHA/docs/qa/707-prompt-prep/masks/pose-fission-ex02-face-scene.png` | ~7.3% |
| `docs/qa/707-prompt-prep/masks/pose-fission-ex03-face-scene.png` | `https://raw.githubusercontent.com/ganjmeng/ComfyArt/TIP_SHA/docs/qa/707-prompt-prep/masks/pose-fission-ex03-face-scene.png` | ~4.6% |
| `docs/qa/707-prompt-prep/masks/pose-fission-ex04-face-scene.png` | `https://raw.githubusercontent.com/ganjmeng/ComfyArt/TIP_SHA/docs/qa/707-prompt-prep/masks/pose-fission-ex04-face-scene.png` | face + upper-left wall/window only. The #670 `scene_rect [0,0,500,1450]` painted the left sleeve and was **not** reused. |

Overlays are under `docs/qa/707-prompt-prep/previews/`. Parameters are in `masks.json`.

**Model:** `bytedance/seedream-v5.0-pro/edit` (realistic person, keep identity). The skill instructions on main still say "Nano Banana Pro edit at 2K"; after #883, person/face keep routes to Seedream. Confirm before submit (open question). Do not use `google/nano-banana-pro/edit` unless told to — its catalog `base_price` is $0.14, still in cap, but it is not the current person route.

**Resolution:** pilot 1k 3:4 = **768×1024** (only if a 1k pose still is requested after the before-after pilot). Full AC: **1536×2048**, 3:4, four single stills. Never a grid, never 1024×1024, never a white backdrop.

**User input (zh):**

> 请根据上传的这张街拍，在同一地点、同一身衣服、同一光线下，只改变机位和姿态，生成 4 张互不重复的 3:4 单图，不要宫格，不要换人、换装或重打光。

**Shared prompt prefix (EN), then one plan line per still:**

> Edit the reference photo. Single 3:4 photorealistic editorial fashion photograph, one frame only, not a collage, grid or contact sheet. Same person, same identity, same outfit, same location and light as the reference; change ONLY camera angle and framing. Commercial fashion model, refined makeup and styling, as attractive as the reference. Keep the reference's hard directional sunlight from camera-right / slightly behind, the same contrast ratio and deep shadows; dappled light and cast shadows fall across the face and the clothing (保留金标的硬光方向和斑驳投影，落在脸部和衣服上). Editorial color grade, fine film grain. Natural skin texture, visible pores, real fabric wrinkles; realistic does not mean unattractive. No flat lighting, no white backdrop, no heavy filter or skin smoothing. No text, letters, logos or numbers.

Plan lines (four different cameras, at most one frontal, subject on a third):

1. **ex01 standing, full-length, 45°.** full-length framing: clear headroom above the top of the head, both feet fully inside the frame with floor visible below the soles. Head turned 45° from camera (three-quarter view), far eye still visible near the nose bridge. Camera at eye level, 35mm f/2.8, subject on the left third, sidewalk and yellow curb still in frame. (Closest to the typifying street still.)
2. **ex02 walk, look-back.** full-length framing as above. Body facing away down the street, mid-stride, head turned 90° back over the shoulder, chin passes beyond the shoulder line, looking back toward camera. Camera at eye level, 35mm f/2.8.
3. **ex03 lean, 90° profile.** full-length framing as above. Strict 90° side profile: nose, lips and chin in silhouette, the far eye is NOT visible. Body leaning on the dark pole, hands relaxed, one foot on the yellow curb. Camera at eye level, 35mm f/2.8.
4. **ex04 close, hand in hair.** framing crops at the waistline / navel: bottom edge of the frame cuts exactly at the navel, nothing below the navel is in frame; the figure from top of head to navel fills the full frame height. Head slightly tilted, direct gaze, one hand in the hair at the side of the head. Camera slightly above eye level, 50mm f/2.

**Estimated cost:** 4 × $0.0405 = **$0.162**, plus $0.0405 if a 1k pose pilot is added. 2k surcharge is unknown. Same face across all four (the woman already on `01.webp`).

**Copy map:** no marketing type on these gold stills. Do not introduce letters or logos. Scene tweaks are optional and only if a local re-wash is requested (grate / wall), not on the primary pose run.

---

## 6. game-art

**Slot:** game-art, one vertical UI still.

**Gold base / layout ref:** `643/wash/game-art/examples/01.webp` (1536×2736, 9:16, 奔秋围棋 list). **Do not** use `docs/design/640/78/gold/game-art/cover.webp` or `643/wash/game-art/cover.webp` (anime posters; rejected as the typifying gold for #707).

- Raw: `https://raw.githubusercontent.com/ganjmeng/ComfyArt/TIP_SHA/643/wash/game-art/examples/01.webp`

The pre-wash dialog gold used the brand 云山棋梦. The 643 wash locked 奔秋围棋 across the twenty examples. This paid run invents a **third** consistent brand, `听潮弈社`, same four-character length, same ink-wash / maple-and-indigo family.

**Mask:** none. Text-to-image at the UI size. No local type overlay and no grey boxes.

**Model:** `openai/gpt-image-2.6-flare/text-to-image` (poster/text, readable UI type). Midjourney is the anime route and is reserved for the poster cover, which is out of scope.

**Resolution:**

- Gold example is 1536×2736 (9:16, larger than AC).
- Pilot 1k 9:16: **576×1024**.
- Full AC: **1024×1824**, 9:16. Never 1024×1024.

**User input (zh):**

> 做一张竖屏手机游戏 UI 截图，题材是围棋对局列表页，要有标题栏、分类标签、带棋盘缩略图的列表卡片、播放按钮和底部导航。风格可以是水墨秋意，但必须是界面，不要角色立绘，也不要宣传海报。

**Generation prompt (EN):**

> A single 9:16 mobile-game UI screenshot, not key art, not a character splash, not a store-cover poster. Portrait phone screen with: a top title bar, three text tabs, a vertically scrolling list of four rounded match cards, a primary play button on each row, and a four-item bottom navigation bar. Style family matches a Chinese ink-wash Go app: indigo night sky, maple leaves, cream paper cards, vermilion accents, readable calligraphy-inspired UI type. Brand name, used once in the title bar and nowhere else as a different spelling: "听潮弈社". Tabs (functional, short): "我的对局", "名家复盘", "珍藏棋谱". Bottom nav (functional): "棋谱", "棋院", "商城", "我的". Replace every marketing title, player nickname, date and move count with new copy of similar length, in the same placement and type style. Card titles, top to bottom: "潮声布局·三间低夹", "晚枫星位起手", "中盘转换要点", "官子收束专题". Black-player nicks and move counts: "黑：青渚樵客 198手", "黑：望海弈真 226手", "黑：素纸闲子 164手", "黑：听雨棋心 241手". Dates: "2026年4月03日", "2026年4月09日", "2026年4月18日", "2026年4月26日". Keep a small back chevron and a search icon in the title bar. Each card has a small Go-board thumbnail on the left and a circular play glyph on the right. Sharp, legible Chinese, no gibberish, no Latin placeholder, no watermark. Do not write 奔秋围棋, 云山棋梦, 云山棋客, 以棋会友, 小飞挂角, or 枫叶定式.

**Estimated cost:** $0.05 at 1k (documented medium). AC 1024×1824 may bill as 1k or 2k — **unknown until quoted**; budget **$0.10** conservative.

**Copy map (in-model only):**

| Gold / prior wash | Replacement | Keep? |
| --- | --- | --- |
| 云山棋梦 (pre-wash dialog gold) | 听潮弈社 | no — brand |
| 奔秋围棋 (643 wash, current example 01) | 听潮弈社 | no — do not reuse the wash brand |
| 枫叶定式·二间高夹, 开局星位布局, 中盘转换精要, 收官细算专题 | 潮声布局·三间低夹, 晚枫星位起手, 中盘转换要点, 官子收束专题 | no — list titles, similar length |
| 丹枫弈士, 霜叶知秋, 朱砂落子, 金桂棋心 and their 手 counts | 青渚樵客 198手, 望海弈真 226手, 素纸闲子 164手, 听雨棋心 241手 | no — nicks and numbers |
| 2025年3月12 / 16 / 21 / 27日 | 2026年4月03 / 09 / 18 / 26日 | no — dates |
| 我的对局, 名家复盘, 珍藏棋谱, 棋谱, 棋院, 商城, 我的, back, search, play | same or equally short functional labels | yes — functional UI |

Same brand `听潮弈社` on this still and on any later example in the slot.

---

## 7. linkedin-banner

**Slot:** linkedin-banner, one 1584×396 personal banner. The skill output is the banner itself, not the LinkedIn page chrome on the 4:3 gold cover.

**Gold base / family:**

- Cover (page mockup, typifying family): `docs/design/640/78/gold/linkedin-banner/cover.webp` (1440×1080). Headline lives in the right two thirds; a grey avatar sits in the left quarter.
  - Raw: `https://raw.githubusercontent.com/ganjmeng/ComfyArt/TIP_SHA/docs/design/640/78/gold/linkedin-banner/cover.webp`
- Size / safe-area proof: `704-lr/linkedin-banner/fixed-input-v1/RIGHT.png` (1584×396). Visual family is different (Product Designer / mint cubes). Used for pixels and safe area, not as copy to clone.
  - Raw: `https://raw.githubusercontent.com/ganjmeng/ComfyArt/TIP_SHA/704-lr/linkedin-banner/fixed-input-v1/RIGHT.png`

**Mask:** none. Text-to-image at banner size. No local type overlay.

**Model:** `openai/gpt-image-2.6-flare/text-to-image` (poster/text, readable headline).

**Resolution:** pilot 1k, same 4:1 ratio: **1024×256**. Full AC: **1584×396**. Do not pass 1:1 or 16:9. Do not outpaint or build a page frame around the banner.

**User input (zh):**

> 做一张 1584×396 的 LinkedIn 个人横幅，标题放在右侧约三分之二，左侧留给头像安全区，文字要大、对比强、能读清。不要做成 YouTube 频道图，也不要再拼一页主页。

**Generation prompt (EN):**

> One professional LinkedIn personal banner, exactly 1584 by 396, not a LinkedIn page mockup, not YouTube channel art, not a square post, not a second thumbnail. Dark navy field. A glowing teal-and-green node network and soft particle trails occupy the right third, similar in density and depth to a data-science banner but a new graph, not a copy. Leave the left quarter visually quieter as an avatar safe area; put the headline and subline in the right two thirds, large, high contrast, real words, no gibberish. Replace the gold headline "Turning Data Into Decisions" with "Shaping Signals Into Action", same weight, similar length, keep the lettering effects. Replace the subline "Data Scientist · Machine Learning · AI Research" with "Analytics Lead · Applied Models · Decision Science", same size and placement. If small icon tiles are used on the far right, label them "Sources", "System", "Patterns", "Action" (not Features, Model, Insights, Decisions). If a faint code whisper appears in the lower field, use "score = rank(signals)" and "action = policy(score)", not model.fit or model.predict. No face, no logo lockup, no company name, no "500+" claim, no "THE FUTURE ENTERPRISE", no "Signals to Strategy", no "PRODUCT DESIGNER", no grey box, no later text overlay.

**Estimated cost:** $0.05 at 1k documented. 1584×396 long edge is 1584 (between 1k and 2k) — **unknown band**; budget $0.05–$0.10.

**Copy map:**

| Gold / other existing | Replacement | Keep? |
| --- | --- | --- |
| Turning Data Into Decisions | Shaping Signals Into Action | no — headline, similar length |
| Data Scientist · Machine Learning · AI Research | Analytics Lead · Applied Models · Decision Science | no — subline |
| FEATURES, MODEL, INSIGHTS, DECISIONS | Sources, System, Patterns, Action | no — tile labels |
| model.fit / model.predict / decisions = insights.value | score = rank(signals) / action = policy(score) | no — code whisper |
| THE FUTURE ENTERPRISE, Powering 500+ Comp… (secondary card on the cover) | not generated (one banner only) | out of frame |
| Signals to Strategy (643 wash cover) | do not reuse | — |
| PRODUCT DESIGNER / Clarity · Craft · Collaboration (704-lr RIGHT) | do not reuse | — |

Functional LinkedIn chrome (avatar circle, name row) is not part of the 1584×396 canvas.

---

## 8. Pilot plan

1. Log the WaveSpeed balance before anything is submitted. Call `GET /api/v3/model/price` for the exact model and size; if the quote would break the remaining cap, stop.
2. Run **one 1k still first**: before-after, `bytedance/seedream-v5.0-pro/edit`, **819×1024**, 4:5, gold cover as the edit base, composite with `before-after-cover-faces-and-copy.png`. Cost estimate **$0.0405** (size variance unknown).
3. Serial only. One image at a time. Do not start the next skill while a call is in flight. Do not overlap with anyone else's pytest or paid run.
4. On failure of the same image: retry at most once. After **two failures on that image**, stop that image, keep the balance log, and do not spend more on it. Do not retry a third time.
5. Design checks the pilot against the gold card (new face both sides, same crop and light, headline replaced in-model, BEFORE/AFTER still readable). Then Angela confirms. No further spend until both pass.
6. After OK, run items 1 and 2–7 at AC size, still serial, same failure rule, live-quote before each submit. Log balance before and after every call, plus prediction id, model, size, and USD debit.
7. Do not call paid APIs in this prep. Do not start the pilot until Angela has confirmed and #884 is no longer blocking the queue (Ready order: chip fix #885, then #884, then this #707 run).

Suggested ledger columns: `slot`, `size`, `model`, `prediction_id`, `balance_before`, `balance_after`, `debit`, `status`, `notes`.

---

## 9. Total vs the $3 cap

Happy path (pilot + AC set, one success each, Seedream at the known $0.0405, Flare at $0.05 for 1k and $0.10 conservative for AC game-art and linkedin):

| Call | Est. USD |
| --- | --- |
| Pilot before-after 819×1024 Seedream edit | 0.0405 |
| Full before-after 1024×1280 Seedream edit | 0.0405 |
| pose-fission ×4 at 1536×2048 Seedream edit | 0.1620 |
| game-art 1024×1824 Flare t2i | 0.10 conservative (0.05 if billed 1k) |
| linkedin-banner 1584×396 Flare t2i | 0.10 conservative (0.05 if billed 1k) |
| **Image subtotal** | **~0.443** (about 0.343 if both Flare calls bill 1k) |
| Skill-agent LLM, if the run goes through the agent (historical #704 residual) | ~0.08–0.16 (not a catalog price) |
| **Happy-path total** | **~$0.52–0.60** |

Headroom to $3 is about **$2.40**.

Conservative envelope, still under the cap: treat every Flare call as $0.10, allow two attempts on every still (stop after the second failure), and add historical LLM at the high end.

| Envelope | Est. USD |
| --- | --- |
| 8 image attempts in the happy path × ~$0.10 ceiling, or 8 stills × 2 attempts if each fails once | ~0.44–1.18 |
| + LLM | ~0.16 |
| **Envelope** | **~$0.60–1.34** |
| **Cap** | **$3.00** |

A second face-wash of the four pose-fission stills (if design asks) would add about 4 × $0.0405 = $0.162 and still fit. Using `google/nano-banana-pro/edit` at catalog $0.14 × 4 = $0.56 would also fit, but it is not the planned route.

Stop if a live quote would take the running total over $3. Do not recharge. Do not switch accounts.

---

## 10. Open questions

1. **game-art cover vs example 01.** The 640 gold *cover* is an anime poster ("游戏美术与运营视觉设计 SKILL"). #707, the product AC, and `docs/qa/704/tip-lr/NOTES.md` all take the typifying gold to be the vertical Go UI (`643/wash/game-art/examples/01.webp`; pre-wash dialog brand 云山棋梦). This plan follows the UI, not the poster. Please confirm. The poster, if ever washed, would route to Midjourney (`midjourney/text-to-image`, catalog $0.10, no live debit in repo).
2. **before-after ratio.** The gold *plate* is 1600×1200 (4:3); the cream card inside it is 683×910 (~3:4). The skill AC is 1024×1280 (4:5). This plan generates the card at the AC 4:5 size, not a 4:3 plate with a dark margin. Confirm.
3. **pose-fission second face swap.** `643/wash/pose-fission/examples/01.webp`–`04.webp` already use the #670 new face. The paid plan changes only camera and framing from ex01. Confirm we should not pay for another face inpaint. Masks are on disk if that changes.
4. **Seedream vs the skill text.** pose-fission instructions on main still say Nano Banana Pro edit at 2K. #883 routing for realistic people / keep-face is Seedream 5.0 Pro. This plan uses Seedream. Confirm.
5. **Seedream size price.** The only live debit in repo is $0.0405, size not broken out. 1536×2048 and 1024×1280 may differ; quote before submit.
6. **Flare size band.** Documented table is 1k / 2k / 4k. It is unknown whether 1024×1824 and 1584×396 bill as 1k ($0.05) or 2k ($0.10). Quote before submit. Midjourney is unused; its catalog price is $0.10 with no live debit.
7. **linkedin family.** 640 gold cover is a data-network personal banner on a page mockup. 704-lr RIGHT is a Product Designer banner with mint cubes, already accepted as a historical 1584×396 right. This plan matches the **640 gold family** at **1584×396**, and does not clone 704-lr copy. Confirm.
8. **Lovart original user inputs** for these four golds were not found in the repo. The Chinese dialog lines above are drafted. Design should confirm or replace them.
9. **Direct WaveSpeed vs skill agent.** A direct edit/t2i submit has no LLM line. The #707 AC is a current-main full pipeline run (agent writes the prompt, one generate, done). This prep gives the exact prompts the agent should land on. If the agent is used, include historical LLM in the cap and still log balance before and after.
10. **Sunburst alternative.** If design wants the mask sent into the API instead of a local composite, use `openai/gpt-image-2.6-sunburst/edit` (catalog $0.065; live $0.0585–$0.072; exact 1k unknown). Not the default for person slots.

---

## 11. Files in this folder

```
docs/qa/707-prompt-prep/
  README.md                 this document
  make_masks.py             $0 mask builder (reproducible)
  masks.json                coordinates and notes
  masks/                    L-mode PNGs, 255 = edit region
  previews/                 red overlays for design review
```

No issue comment and no pull request are part of this prep.
