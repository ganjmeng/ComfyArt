# #371 P1-mascot · DNA A 画布 Agent 角标 + hover/click 「Arti 通知」 · #78 shots

**Branch:** `tip/371-arti-p1-mascot` · closes #371  
**AC:** box `ComfyArt-review-assets/arti/P1-MASCOT.md`（DNA A + hover/click）  
**Product ACK:** 2026-10-27 — Ashley **OK DNA A** cream dumpling + teal antenna（≠ Lovart 白幽灵）；hover 抬升+play；click 画布内通知浮层。

**Prior tip `d2f22a3` VOID** — CN/Lovart white-ghost developing sheet + provisional beret/brush deleted.

## Animation (MUST document)
| Item | Value |
|------|-------|
| Frames | **17** (`MASCOT_FRAMES`) |
| Frame ms | **250** (`--mascot-frame-ms`) |
| Duration | **≈4.25s** one-shot (`steps(17)`) |
| Idle | STATIC frame 0 — **no** infinite loop |
| Triggers | `.arti-mascot--play` · `.arti-mascot--typing` · `.arti-mascot--hover` |
| Hover | lift **~11px** (`translateY(-11px)`) + play sheet; leave → idle |
| Click | in-canvas **「Arti 通知」** popover (`data-testid=arti-notify`); **not** `/arti` |
| Empty copy | 「暂无新通知」+「使用 Agent 创作后，解锁巡检和调研功能」 |
| Reduced motion | → frame 0; **no** hover lift anim |
| Level stub | account level not ready → always Lv.1; mock `?artiLevel=` / `localStorage comfyart.arti.levelMock` |

## Level assets (final DNA A)
| Level | Asset | Status |
|-------|-------|--------|
| Lv.1 | `src/assets/arti/mascot-lv1-dna-a.png` | **Final DNA A** bare |
| Lv.2 | `src/assets/arti/mascot-lv2-dna-a.png` | **Final DNA A** pink upright ears + beret + scarf |
| Lv.3 | `src/assets/arti/mascot-lv3-dna-a.png` | **Final DNA A** gold crown + cape + brush |

Source: `locked-A/final-sheets/` · SHEETS-NOTES.md

## Honest source
Tip CSS harness + static DOM matching Composer mascot badge — NOT full Electron / NOT live account level. Persistence stub only.

## After (this tip)
| Shot | Theme | Shows | Priority |
|------|-------|-------|----------|
| `after/composer-mascot-idle-peek-dark.png` | dark | DNA A 左上 peek；半藏；50×50；frame 0 | **MUST** |
| `after/composer-mascot-idle-peek-light.png` | light | 同上浅色 | **MUST** |
| `after/composer-mascot-hover.png` | dark | hover 抬升 ~11px + play class | **MUST** |
| `after/composer-mascot-click-notify.png` | dark | 「Arti 通知」空态两句；非 /arti | **MUST** |
| `after/composer-mascot-typing.png` | dark | `--typing` | **MUST** |
| `after/composer-mascot-play.png` (+ `-frames`) | dark | play 多帧 | **MUST** |
| `after/mascot-sprite-sheet.png` | — | Lv.1/2/3 DNA A sheets · 250ms · ~4.25s | **MUST** |
| `after/mascot-lv1-dna.png` | — | DNA A cream dumpling + teal antenna | **MUST** |
| `after/mascot-level-ladder.png` | — | Lv.1+2+3 DNA A | **MUST** |
| `after/mascot-reduced-motion.png` | dark | reduce → 静止 frame 0、无抬升 | **SHOULD** |

## Evidence (box, not in tip)
`ComfyArt-review-assets/arti/p1-mascot-skins/locked-A/final-sheets/` · `P1-MASCOT.md` · Lovart CN only peek/timing ref

## Out of scope
P0-1/P0-2 rework · P0-3 evolution · P1-1 委托 · P2 巡检 feed · paid generation · Lv.4+ · claiming white ghost DNA
