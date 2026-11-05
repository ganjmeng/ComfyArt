#760 / #761 r5 — all-media stack + contain letterbox (tip ComfyArt `68a36d25`)

## Locked rules (this tip)
- Render ALL `media[]` (no `slice(0,3)`); indices ≥3 `opacity:0` (max 3 visible at rest)
- No pad-with-last; no `[data-on]` sticky expand (hover / focus-visible only)
- Layout by count: 1 = single centered contain; 2–3 = stack → one-row focus; ≥4 = 2×2 focus (161×118 gap 6, 4th empty opacity 0)
- Rest aspect-aware into inset ~328×242: landscape 100%×76.03% + translateY(15.75%) scale(.757178); portrait 55.335%×100% (181.5×242) left 22.332% + scale(.8057); rot 5/−5/10
- Covers: `object-fit: contain` ONLY — never cover. Letterbox on `#f4f4f4`
- media URLs = raw originals (real w/h), not `@thumb`
- Dialog @1920: **1200×820** / cards well **388×291** (title row → ≈388×321); modal open **200ms**; chips 200ms; pill/zoom 100ms; stack 400ms; pile ~**78%** AABB locked

## Motion 「首尾帧动画」
- src = raw `02-first-to-last-frame-animation.webp` **1536×2752** (same 9:16 as 1080×1920; not 357×640 thumb)
- Computed @1920 dialog: well 388×291, img box **162.4×291**, `object-fit: contain`, natural 1536×2752
- SBS LEFT = `lovart-raw/2026-11-05/stack-shots/motion-modal.masked.png` (463267c8) — NOT Jingmeng phone shot
- SBS RIGHT = ours same 1920×1072 modal crop (`ours-motion-modal-1920.png`)

## Packaging metrics @1280/1920 dialog
| card | media→layers | rest | focus |
|------|--------------|------|-------|
| t1 主款 | 1 → no stack | single contain | — |
| t2 视觉方向 | 3 → data-n=3 landscape | pileW ≈78.6% | one-row |
| t3 多SKU | 4 → data-n=4 portrait; L3 opacity 0 | portrait .8057 path | 2×2; 4th opacity 0 |
| t4 面板 | 1 → no stack | single contain | — |

## SBS (LEFT\|RIGHT, both 1920×1072)
- `sbs-01-stack-rest.png` — packaging rest
- `sbs-02-stack-expanded.png` — packaging t2 hover row
- `sbs-02b-multi-sku-2x2.png` — packaging t3 hover 2×2
- `sbs-04-motion-card2.png` — motion 首尾帧 contain letterbox

## Crop method
RIGHT = full viewport screenshot @1920×1072 with dialog open (same frame as LEFT masked refs).

## Multi-SKU SBS (LEFT = ca67e71c @1280×1072)
- LEFT static: `lovart-raw/2026-11-05/anim/multisku-1280-static.masked.png`
- LEFT hover: `lovart-raw/2026-11-05/anim/multisku-1280-hover.masked.png`
- RIGHT: `ours-multisku-static-1280.png` / `ours-multisku-hover-1280.png` (same 1280×1072 viewport)
- Composites: `sbs-multisku-static.png` / `sbs-multisku-hover.png`
- Hover 2×2 measured: cells ≈182.6×134.1 gap ~6 (49.085%/48.76% of inset at 388×291 well); 4th opacity 0
