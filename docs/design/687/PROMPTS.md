# #687 Phase1 re-wash prompt pre-check (draft, no generation)

Base: origin/main `b47b6671368581f54d8a5c9e26fd0f3548010ffc`. Gold: `gold_lovart/<id>/` (box-local, `/workspace/qa687/gold_lovart`, not committed).
Model: WaveSpeed `google/nano-banana-2.1/edit`, 1K, ~$0.0378/img; free local upscale (Real-ESRGAN/Lanczos) to gold cover size.
Excluded: taobao-product (handled in its own PR, cap $0.3).

## Global rules (apply to every prompt)
- Person/photo slots: gold = base image; feathered mask (~24px) on head/face only; new person, no less attractive (campaign-grade, real skin texture), same head angle, gaze, light; 1–2 small scene tweaks. Keep gold pose, outfit, light, grade, grain.
- Non-portrait (product/illustration/anime) slots with soft-wash risk: gold = **style reference only**, new composition stated in prompt.
- Every prompt ends with: `No text, no letters, no logos, no numbers, no watermark anywhere in the image.` All text added locally (PIL), every gold brand/word/number replaced.
- One brand per slot (social = **LUMORA**); same character consistent across all views inside one sheet.
- Budget: social + character cap **$0.50**; stop after 2 consecutive fails on the same image; max 2 extra retries per batch. Log WaveSpeed balance before/after each batch.
- Local post (all): OCR check (no gold text survives), upscale to gold size, LANCZOS resize, webp q90.

## 1. social — re-wash, 5 examples (non-portrait product posts → style reference, new composition)
Gold family: "instagram Product Post" — one hero product in front of a giant headline word, small brand line top, CTA pill bottom. Gold brands ORGILEEN / DRAKON / AURA / MIRANO / VERDE and words VITAMIN / DRAGON / PULSE / CLASS / FRESH all replaced. Slot brand: **LUMORA** (one brand, five product lines).
Mask: none (style ref). Model/size: nano-banana-2.1/edit @1K, output aspect = gold; upscale to gold size. Cost: 5 × $0.0378 = **$0.189**.
Common local post: rembg product cutout → draw giant word behind product → paste product on top → brand line + 1-line claim + CTA pill (new copy) → OCR check.

**Rev (design review of `dc6b367c`):** each slot keeps its own gold's product category (no category drift, cf. #683 ex08); only brand, product shape, colours and composition change. Layout matches gold: small brand line top, giant word in the gold's own band (behind the product's top where the gold overlaps it), CTA pill bottom. The model renders the product and scene only; the band for the word is described per gold below.

| ex | gold size / category | new product / word (local) | big-type band (from gold) | prompt (after `Use the reference image only for colour palette, lighting and poster style; do not copy its exact product, layout or background objects.`) |
|---|---|---|---|---|
| ex01 | 1088×1920, supplement (vitamin oil) | LUMORA vitamin C capsules, amber jar; word BOOST; CTA "Try now" | y≈17–30%, above product, not overlapping | `A single squat amber glass supplement jar with a matte white lid, a few golden softgel capsules spilled beside it, standing on a cream stone plinth in the lower-middle of the frame; a large halved blood orange behind it and green leaves at the edges; warm peach-to-cream backdrop with soft sunlit haze; the upper third of the frame is clean plain backdrop. Studio product photography, 9:16.` |
| ex02 | 1088×1360, gaming controller | LUMORA wireless gamepad, white/teal; word SURGE; CTA "Pre-order" | y≈10–38%, behind controller top | `A single white wireless game controller with teal accents and translucent grips, shown front-on and slightly tilted, centred in the lower half on cracked dark basalt with drifting teal embers and smoke; deep charcoal backdrop with teal rim light; the upper third is dark smoky backdrop. Dramatic product shot, 4:5.` |
| ex03 | 1088×1360, over-ear headphones | LUMORA over-ear headphones, sand/rose-gold; word ECHO; CTA "Shop now" | y≈10–40%, behind headband | `A single pair of sand-beige over-ear headphones with rose-gold sliders, three-quarter view, centred slightly low, floating above a glossy pale surface; soft warm-white to blush gradient backdrop; the upper third is plain backdrop. Clean premium tech photography, 4:5.` |
| ex04 | 1088×1360, leather shoe | LUMORA suede chelsea boot, tan; word CRAFT; CTA "Discover" | y≈10–35%, behind boot top | `A single tan suede chelsea boot with dark elastic side panel, side view, in the lower half on a light travertine floor beside a folded olive wool cloth; soft window light from the left, warm grey plaster wall; the upper third is plain wall. Editorial luxury product photography, 4:5.` |
| ex05 | 1088×1456, fresh juice | LUMORA cold-pressed orange juice; word ZEST; CTA "Try now" | y≈8–38%, behind bottle top | `A hand entering from the right holding a clear glass bottle of orange cold-pressed juice, centred, halved oranges and mint leaves on a pale surface at the bottom; bright citrus-yellow backdrop with soft shadows; the upper third is plain backdrop. Fresh lifestyle product photography, 3:4.` |

All five end with the no-text line. Local post: rembg cutout of product → giant word in the band → product pasted over the word → LUMORA brand line top, 1-line claim, CTA pill bottom → OCR.

Cover (1088×1360): local only — reuse ex03 output with the cover copy layout, $0.

## 2. character — re-wash, 6 examples ("Character Sheet Design")
Each sheet = one character, identical across every view in that sheet. Keep each gold's ethnicity/age/style (diversity rule). Cost: 6 × $0.0378 = **$0.2268**.

| ex | gold size | route | mask plan | prompt | local post |
|---|---|---|---|---|---|
| ex01 real man turnaround (front/side/back) | 2048×1152 | gold base, head inpaint | feathered ellipse on the 2 visible heads (front, side); back head untouched except hair tone | `Replace only the masked heads with a different Caucasian man in his late 40s, short salt-and-pepper hair, trimmed beard, handsome, real skin texture. The same man in both views. Keep exact head angle, gaze, lighting, navy jacket, pose, white background and grain. Change the shoe colour to dark brown.` + no-text line | colour-match back-view hair; upscale 2048×1152 |
| ex02 anime schoolgirl sheet | 1536×1024 | style reference, new character | none | `Use the reference only for anime line style, colouring and sheet layout. New character: girl with a shoulder-length chestnut bob and green eyes, grey blazer school uniform with plaid green skirt and red ribbon, front/side/back full body on the left, six head expressions grid on the right, white background.` + no-text line | upscale 1536×1024 |
| ex03 businessman sheet + close-ups | 1536×2048 | gold base, head inpaint | feathered masks on every face (3 full-body + 3 portrait tiles), one person | `Replace only the masked faces with one different Caucasian man in his early 60s, neat silver side-parted hair, clean-shaven, distinguished and attractive, real skin texture, identical in every view. Keep exact head angles, gaze, light, black suit, poses, white background and grain. Change the tie from patterned to plain burgundy and the cufflinks to silver.` + no-text line | check tie tweak in close-up tiles too; upscale |
| ex04 cellist sheet | 2048×1152 | gold base, head inpaint | feathered masks on all faces (turnaround + playing shots); hands/cello untouched | `Replace only the masked faces with one different South Asian woman in her mid 20s, long dark hair in a low bun, beautiful, real skin texture, the same woman in every view. Keep exact head angles, downward gaze toward the cello, lighting, black dress, poses and grain. Change her earrings to small gold hoops.` + no-text line | upscale |
| ex05 hooded rogue sheet | 2048×1152 | style reference, new character (face hidden → soft-wash risk) | none | `Use the reference only for realistic concept-art rendering, sheet layout (front/side/back plus detail tiles) and muted earthy grade. New character: a desert ranger in a sand-coloured hooded cloak with a teal scarf over the face, leather bracers, curved short bow on the back; detail tiles of bracer, boots and quiver. Plain light background.` + no-text line | upscale |
| ex06 magical girls lineup | 2048×1152 | style reference, new characters | none | `Use the reference only for anime magical-girl style, pastel colouring and three-in-a-row lineup. New trio: the same new girl (short silver-lilac hair with a mint ribbon) in three stages left to right: casual school outfit, mint-and-white magical outfit with a star wand, dark navy-and-silver fallen form; identical face and hair in all three, full body, white background.` + no-text line | gold name plates replaced by new local labels (Mira / Lyra / Rinne) or removed |

Cover (1390×1040): local crop/collage of ex01+ex02+ex06 outputs, $0.

### Social + character subtotal
11 × $0.0378 = **$0.4158**; with the max 2 extra retries: $0.4914 ≤ $0.50 cap. Run as one batch; if any retry pushes the projection over $0.50, stop and re-review.

## 3. youtube-channel-banner — re-wash to mockup (cover)
Gold cover (`docs/design/640/78/gold/youtube-channel-banner/cover.webp`, 1600×1200) = tilted browser/phone mockups of YouTube channel pages on an orange backdrop. Our current cover is a flat banner floating on white and still carries the gold copy "FAMILY FIRST / PARENTING · KIDS · REAL LIFE" → must change.
Route: gold = style reference, new composition. Model: nano-banana-2.1/edit @1K, 4:3, upscale to 1600×1200.
Prompt: `Use the reference only for its colour, lighting and mockup style. New composition: three blank laptop and tablet screens showing empty video-channel page layouts (grey placeholder blocks, a wide empty banner strip at the top of each), fanned diagonally from lower left to upper right on a deep coral-to-magenta gradient backdrop, soft shadows, slight perspective, the banner strips left completely blank flat white.` + no-text line.
Mask: none. Local post: perspective-warp three of our own washed banners (new copy, e.g. "SLOW SUNDAYS", "CODE & COFFEE", "TRAIL NOTES" — no gold strings) into the blank strips; OCR check; upscale; webp.
Cost: 1 × $0.0378 = **$0.0378** (up to $0.1134 with 2 retries). Not part of the social+character cap — needs a cap from 技术经理 (suggest $0.12).

## 4. Fixes without generation ($0)
- clothing-swap: cover crop only — `object-position` so the face is not cut off.
- premium-website: cover crop only — `object-position` so the title is not clipped.
- Remaining #687 FIX cards (product, brand, logo-material, web-product, mobile-ui, banner) per audit rev 3: no prompts in this doc; scope to be confirmed.

## Totals
| item | images | base | worst case |
|---|---|---|---|
| social | 5 | $0.1890 | |
| character | 6 | $0.2268 | |
| social+character | 11 | $0.4158 | $0.4914 (cap $0.50) |
| youtube-channel-banner | 1 | $0.0378 | $0.1134 |
| clothing-swap, premium-website | 0 | $0 | $0 |
| **total** | **12** | **$0.4536** | **$0.6048** |

## 交接
- Done: prompt pre-check drafted for social (5), character (6), youtube-channel-banner (1); crop fixes listed. No generation run.
- Next: UIUX + 技术经理 review this file; confirm the "6 re-wash + 7 fix" list (only social, character, youtube-channel-banner and the 2 crops are pinned here) and a cap for youtube-channel-banner; then 1K pilot (1 per new slot to Angela), then batch.
- Spend: $0 in this task.
- Balance: WaveSpeed $44.285449 (last logged before the promo ex01 / p07 / taobao-product run; not re-queried, no paid calls here).

### character ex01 — rev 2 (design HOLD 22:56: pilot still read as the same man; NOT run, awaiting pre-review + smoke done)
Route: gold base → generate → `next/character/composite_head.py` pastes only head+hair ellipses (front/side/back) onto gold, so outfit/shoes/pose/bg stay gold pixels.
Prompt:
`Replace only the heads in all three views (front, side and back) with a clearly different Caucasian man in his early 40s: short dark brown, almost black hair with a straight, slightly higher squared-off hairline and a neat short side part, clean-shaven with a strong defined jawline, handsome and campaign-grade, real skin texture. He must not resemble the original man: no grey hair, no beard. The same new man in every view, including matching dark hair colour and cut on the back of the head in the back view. Keep exact head angles, gaze, lighting, neck position, navy jacket, trousers, shoes, pose, white background and grain unchanged. No text, no letters, no logos, no numbers, no watermark anywhere in the image.`
Cost if approved: 1 × $0.0378 (ar 16:9, 1K), local composite $0.
