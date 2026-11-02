# #590 wash-v1 STATUS — featured rewash (kie nano-banana-2-1)

**When:** 2026-11-02 ~11:24–11:30 Asia/Shanghai (CST, UTC+8)  
**Issue:** #590 (spend authorized; Ashley kie key on box)  
**Source:** `/workspace/594w/review-assets/580/featured-v1/` · FEED_V1=`98a34727037f806895a4baed34dd2a498cb9baa2`  
**Out:** `/workspace/ComfyArt-review-assets/590/wash-v1/`  
**Helper:** `590/prep/wash_kie_590.py` · ledger `590/prep/ledger.jsonl` (no secrets)  
**GitHub/room/commit:** none (local only)

## Credits

| | value |
|---|---|
| before | **3353.4** |
| after | **3329.4** |
| spent | **24.0** (8 × 3.0) |
| garbled extras | skipped (must 8/8 green; credits still healthy for later) |

## Must slots — result

| # | slot | brand | taskId | state | w×h | full bytes | thumb bytes |
|---|---|---|---|---|---|---|---|
| 1 | brand/01 | ARC RIDE | `22a3baab855fa6faea3d21539f9bb0c5` | OK | 1200×900 | 62358 | 17820 |
| 2 | poster/01 | HALCYON | `e1e2e8a878cb33d6d89f8eaca65a148e` | OK | 1200×900 | 110694 | 18454 |
| 3 | poster/03 | Daylight Notes | `4ea327f39f1e32aca8b7c5a8271a3df9` | OK | 1200×900 | 116976 | 31040 |
| 4 | product/01 | NODAL | `03931cb67b4ac42e532c1032ac793f1c` | OK | 1200×900 | 132270 | 30686 |
| 5 | banner/02 | HELIO | `12465d376d9df39d68cc8a34a58e225d` | OK | 1200×900 | 72318 | 23952 |
| 6 | interior/02 | HALCYON | `5dad170858f9d1bc7a7b728d2ad48919` | OK | 900×1200 | 108270 | 20774 |
| 7 | social/02 | Tide Ledger | `4267d6c7b98b4740780eb62e9b8e2cd2` | OK | 1200×900 | 232812 | 35782 |
| 8 | packaging/01 | HELIO | `aa619ff07e1abbb46c6458b687c3b3b7` | OK | 1200×900 | 256282 | 26016 |

**Score: 8/8 must saved as webp + thumbs. Failures: none.**

## Deliverables

- Fulls + thumbs under `wash-v1/{brand,poster,product,banner,interior,social,packaging}/NN.webp` + `@thumb.webp`
- Slice manifest: `wash-v1/manifest-slice.json` (paths, w×h, taskIds, brands)
- SBS (L=old featured-v1 thumb · R=new wash thumb): `prep/sbs/*_sbs.webp` (8 pairs)
- Raw PNG downloads: `prep/raw/` (scratch; not for ship)

## L/R design notes (executor eye — soft PASS lean)

SBS pairs: left = `580/featured-v1` old · right = `590/wash-v1` new.

| slot | L (old) | R (new) | note for design |
|---|---|---|---|
| brand/01 | VOLTA billboard + dense specs/UI tiles | ARC RIDE single ¾ e-bike hero + tote/cards/mark; lime/black kept | Name+composition break clear. Soft: tile count ≈3 collateral + wordmark strip (still far from specs/highway). **PASS lean** |
| poster/01 | equinox cairn poster-in-interior | HALCYON fern + terracotta sun-arc; “atelier open studio · spring” | Cairn gone; large type clean. **PASS** |
| poster/03 | Golden Hours triptych / scrapbook | Daylight Notes one framed print + ceramic cup + pampas | One poster only; no Golden*. **PASS** |
| product/01 | 5-up silver headphone masonry | NODAL single open-back round cups on warm concrete | Silhouette + layout diverge. **PASS** |
| banner/02 | SOLARIS aerosol · copy left / product right | HELIO tube+roll-on left · HELIO / SPF50+PA chips / SHOP NOW right | Layout mirrored; large chips only. **PASS** |
| interior/02 | SOLSTICE book + cairn | HALCYON book + ceramic vessel; sage + bouclé kept | Name+cairn hit cleared. **PASS** |
| social/02 | Golden Hours / Summer Notes 3-card scrapbook | Tide Ledger 2 cards + polaroid strip; large title | Micro body gone. Soft: companion card mostly blank (OK). **PASS** |
| packaging/01 | SOLA spray on driftwood sand | HELIO bottle+stick linen overhead flat-lay; SPF50 chip | Soft: “STICK SUNSCREEN STICK” mild redundancy — not garbled fine print. **PASS lean** |

**Executor recommendation:** ready for design eye → fullstack handoff. Prefer leave files local; do **not** push review-assets until design PASS and parent documents commit sha.

## Skipped

Garbled-only extras (`brand/03–04`, `packaging/03`, `banner/04`, `poster/02`, `social/03–04`, `character/01`, optional `motion/01`) — not run; credits remain ~3329 for a follow-up if design wants.

## Hygiene check

- No API key in ledger/STATUS/manifest/log
- No GitHub post / room post / git commit
