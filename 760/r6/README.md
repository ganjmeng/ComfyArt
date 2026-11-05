#760 / #761 r6 — portrait Master frame + multi-SKU height-fill + dialog 1112→1200 (tip ComfyArt `6a1b9ee7`)

## Product HOLD (this tip)
1. **主款/Master Packaging** — single image, natural 3:4 frame **181.5×242** centered, **NO stack** (`media.length=1` + `mediaOrient=portrait` for ratio≈0.75).
2. **Multi-SKU static** — portrait vert path: layers **181.5×242** (height贴满 inset), left 22.332% (=translateX 73.25), scale **.8057**, rot 5/−5/10; rest `object-fit: cover` so landscape wash fills the portrait frame (not landscape over-shrink letterbox). Focus stay contain; 2×2 hover unchanged.
3. **sbs-01/02 LEFT** — Lovart **same modal same card** (`lovart-1280x1072-static/hover.masked.png` + modal-crop `stack-static/expanded.modal.masked.png`). Not Skills wall `stack-1`/`stack-zoom`.
4. **Dialog scale** — @1280 → **1112×820** / cards **344×288** (well **344×258**); @1920 → **1200×820** / **388×321**. Right pane locked **360**. Width scales with viewport between 1112 and 1200.

Motion 首尾帧 + multi-SKU 2×2 hover: unchanged / passed (contain letterbox @9:16).

## Measured @1280 (dialog 1112×820, left 752 / right 360)
| card | media→layers | rest | notes |
|------|--------------|------|-------|
| t1 主款 | 1 → **nLayers 0** | cover box **181.48×242** centered (left 81.23, top 8); `data-orient=portrait` on presetimg | no CSS stack |
| t2 视觉方向 | 3 → data-n=3 landscape | pile ~78% path `.757178` | focus one-row contain |
| t3 多SKU | 4 → data-n=4 portrait; L3 opacity 0 | stack inset **328×242**; layers cover + scale .8057 | focus 2×2 contain; 4th opacity 0 |
| motion t2 | 1 → no stack | contain **144×258** (9:16 full-well) | no mediaOrient; never cover |

## Measured @1920 (dialog 1200×820, left 840 / right 360)
| card | well | rest |
|------|------|------|
| t1 主款 | 388×291 (outer 388×321) | portrait frame **205.84×275** |
| t3 多SKU | 388×291 | inset 372×275; cover + .8057 |
| motion t2 | 388×291 | contain **162.41×291** natural 1536×2752 |

## SBS
- `sbs-01-stack-rest.png` / `sbs-02-stack-expanded.png` — LEFT=lovart-1280x1072-static/hover (same modal); RIGHT=ours @1280 packaging Visual Direction
- `sbs-01b-modal-crop-rest.png` / `sbs-02b-modal-crop-hover.png` — LEFT=stack-static/expanded.modal (1200×820); RIGHT=ours dialog crop @1280
- `sbs-multisku-static.png` / `sbs-multisku-hover.png` — LEFT=ca67e71c multisku-1280-*; RIGHT=ours @1280
- `sbs-04-motion.png` — LEFT=463267c8 motion-modal.masked; RIGHT=ours @1920

## Crop method
@1280 RIGHT = full viewport 1280×1072 with dialog open (matches Lovart LEFT viewport). Modal-crop SBS uses white-dialog 1112×820 crop at ~(84,126). @1920 motion RIGHT = full 1920×1072.
