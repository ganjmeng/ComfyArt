# #386 P1-1 · 巡检事件触发 + 状态机 · #78 shots

**Closes #386.** CN Lv.1 巡检空态文案锁定（不改）；本卡新增「巡检结果卡」进真实 ArtiMascot 通知面板（token only）。

## After（real CSS/DOM — tip `base.css` + `shell.css` + ArtiMascot DOM；composer child；mock 巡检卡）
| Shot | Theme | Shows |
|------|-------|-------|
| `after/review-notify-light.png` | light zh | Arti 通知 ⚡ + 画布体检卡 above composer |
| `after/review-notify-dark.png` | dark zh | 同上 |

Harness: `harness/review-notify.html` (+ `shoot.py`). No standalone reinvented chrome; title uses `proactive.reviewTitle`「画布体检」.

## Tokens used
`--ca-text` / `--ca-text-2` / `--ca-muted` / `--ca-border` / `--ca-field` / `--ca-float` / `--ca-block-gap` / `--ca-notify-close-hover` — no hard-coded hex in product CSS.
