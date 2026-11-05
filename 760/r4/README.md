#760 / #761 r4 — product-DOM stack @1280×1072 (tip ComfyArt `2db55473`)

## Timings (measurements.md @6aa4b6cd)
- Skills category chips (For you / E-commerce / …): **200ms**
- Card 「选择」pill / zoom icon: **100ms** (unchanged)
- Stack expand/collapse: **400ms** cubic-bezier(.25,.1,.25,1)

## Stack data
- Layers = real wash media only; pad to min(depth,3) by duplicating last real URL; never PENDING_WASH
- Focus cells = same raw layer URLs (packaging t2: gold / playful / panels)

## Geometry @1280
- Card well 344×258 (aspect 160/120), stack inset 8
- Rest: layer 100%×76.03%, translateY(15.75%) scale(.757178), rot 5/−5/10, transform-origin center, object-fit cover
- Measured rest pile AABB ≈ **78%** card width (scale box ≈72% before rotation; matches product scale .757178, not a separate 85% scale)
- Focus: cell 32.11% × 100%, pitch 33.94%, object-fit contain
- Motion card2: object-fit contain, object-position center, well bg #f4f4f4 (9:16 natural 357×640)

## SBS
- LEFT = anim pack masked ref (`lovart-raw/2026-11-05/anim/`, from c4934a8a)
- RIGHT = ours @ tip
- SBS-1 rest / SBS-2 expanded (modal + card crops) / SBS-3 frames 0/100/200/400 / SBS-4 motion ours tile
