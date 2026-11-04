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

| ex | gold size | new product / word (local) | prompt (after `Use the reference image only for colour palette, lighting and poster style; do not copy its product, layout or background objects.`) |
|---|---|---|---|
| ex01 | 1088×1920 | serum dropper bottle, word GLOW, CTA "Shop now" | `A single amber glass serum bottle with gold dropper standing on a peach stone plinth, right of centre, low three-quarter angle; sliced grapefruit and white blossoms scattered at the base; warm peach-to-cream gradient backdrop with soft sunlit haze, large empty area in the upper half for a headline. Studio product photography, crisp reflections, 9:16.` + no-text line |
| ex02 | 1088×1360 | wireless gaming mouse, word SURGE, CTA "Pre-order" | `A matte black wireless gaming mouse with teal edge lighting, angled 30° from above, floating over cracked dark slate with drifting teal embers and smoke; deep charcoal backdrop with teal rim light, empty upper half for a headline. Dramatic product shot, 4:5.` + no-text line |
| ex03 | 1088×1360 | true-wireless earbuds + open case, word ECHO, CTA "Shop now" | `A pair of pearl-white wireless earbuds beside their open charging case, slightly tilted, on a glossy white surface with soft violet reflections; cool lilac-to-white gradient backdrop, empty upper half for a headline. Clean premium tech photography, 4:5.` + no-text line |
| ex04 | 1088×1360 | leather tote bag, word CRAFT, CTA "Discover" | `A cognac leather tote bag standing on a folded linen cloth atop a walnut table, three-quarter view, warm window light from the left, beige plaster wall, empty upper half for a headline. Editorial luxury product photography, 4:5.` + no-text line |
| ex05 | 1088×1456 | cold-pressed juice bottle (orange), word ZEST, CTA "Try now" | `A hand holding a clear glass bottle of orange cold-pressed juice from the lower right, halved oranges and mint leaves on a pale yellow surface below, bright citrus-yellow backdrop with soft shadows, empty upper half for a headline. Fresh lifestyle product photography, 3:4.` + no-text line |

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
| ex06 magical girls lineup | 2048×1152 | style reference, new characters | none | `Use the reference only for anime magical-girl style, pastel colouring and three-in-a-row lineup. New trio: a mint-haired girl in a white-and-teal sailor dress, a lavender-haired girl in a starry violet gown, a red-haired girl in a gold-trimmed crimson outfit, full body, white background.` + no-text line | gold name plates replaced by new local labels (Mira / Lyra / Rinne) or removed |

Cover (1390×1040): local crop/collage of ex01+ex02+ex06 outputs, $0.

### Social + character subtotal
11 × $0.0378 = **$0.4158**; with the max 2 extra retries: $0.4914 ≤ $0.50 cap. Run as one batch; if any retry pushes the projection over $0.50, stop and re-review.
