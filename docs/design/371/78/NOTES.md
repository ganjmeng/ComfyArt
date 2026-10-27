# #371 P1-mascot · 画布 Agent 角标像素 Arti + Lv.1–3 阶梯 · #78 shots

**Branch:** `tip/371-arti-p1-mascot` · closes #371  
**AC:** box `ComfyArt-review-assets/arti/P1-MASCOT.md`  
**Product ACK:** 2026-10-27 — Lv.1+2+3 MUST; stub Lv.1; play **and** typing animate; idle static; reduced-motion → frame 0.

**Base:** `origin/main` @ `fa919b2` (after #372 / #368)

## Animation (MUST document)
| Item | Value |
|------|-------|
| Frames | **17** (`MASCOT_FRAMES`) |
| Frame ms | **250** (`--mascot-frame-ms`) |
| Duration | **≈4.25s** one-shot (`steps(17)`) |
| Idle | STATIC frame 0 (open eyes) — **no** infinite loop |
| Triggers | `.arti-mascot--play` (busy) · `.arti-mascot--typing` (non-empty draft) |
| Reduced motion | `prefers-reduced-motion: reduce` → animation none, frame 0 |
| Level stub | account level not ready → always Lv.1; mock `?artiLevel=` / `localStorage comfyart.arti.levelMock` |

## Level assets
| Level | Asset | Status |
|-------|-------|--------|
| Lv.1 | `src/assets/arti/mascot-lv1-developing.png` | **CN gold** developing sheet 2176×128 |
| Lv.2 | `src/assets/arti/mascot-lv2-beret.png` | **Provisional original** — mini beret + lavender ribbon (design draft `p1-mascot-skins/lv2-beret.jpg`) |
| Lv.3 | `src/assets/arti/mascot-lv3-brush.png` | **Provisional original** — brush + Klein-blue dots; pink blush kept (`p1-mascot-skins/lv3-brush.jpg`) |

**Gate:** Lv.2/3 are **not** Ashley-approved final ladder yet. Tip ships provisional; merge waits Ashley OK + design final low-res sheets. Do **not** claim CN capture for Lv.2+.

## Honest source
Tip CSS harness + static DOM matching Composer mascot badge — NOT full Electron / NOT live account level. Persistence stub only.

## After (this tip)
| Shot | Theme | Shows | Priority |
|------|-------|-------|----------|
| `after/composer-mascot-idle-peek-dark.png` | dark | 左上 peek；半藏圆角；50×50；frame 0 睁眼 | **MUST** |
| `after/composer-mascot-idle-peek-light.png` | light | 同上浅色 | **MUST** |
| `after/composer-mascot-typing.png` | dark | `--typing` class | **MUST** |
| `after/composer-mascot-play.png` (+ `-frames`) | dark | play 多帧静帧 f0/f5/f8 + 时序说明 | **MUST** |
| `after/mascot-sprite-sheet.png` | — | 17 帧 sheet；250ms · ~4.25s 文档 | **MUST** |
| `after/mascot-lv1-dna.png` | — | vs CN crop：白/黑/粉腮/暗尾尖 | **MUST** |
| `after/mascot-level-ladder.png` | — | Lv.1+2+3 并排；Lv.2/3 labeled provisional | **MUST** |
| `after/mascot-reduced-motion.png` | dark | reduce → 静止 frame 0 | **SHOULD** |

## Evidence (box, not in tip)
`ComfyArt-review-assets/lovart-arti-pixel-20261027/` · `arti/P1-MASCOT.md` · `arti/p1-mascot-skins/` (design draft)

## Out of scope
P0-1/P0-2 rework · P0-3 evolution · P1-1 委托 · P2 巡检 · paid generation · claiming Ashley ladder OK · Lv.4+
