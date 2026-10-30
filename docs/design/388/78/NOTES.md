# #388 P1-3 · 定时任务无人值守遇报价确认：跳过 + 通知 + 不扣费 · #78 shots

**Closes #388.** 超阈值确认 → 跳过本次 + kind=schedule「已跳过」通知 + 0 扣费；跨标签 Web Lock。

## After（real CSS/DOM — tip `base.css` + `shell.css` + ArtiMascot DOM；composer child；mock 跳过卡）
| Shot | Theme | Shows |
|------|-------|-------|
| `after/schedule-skip-light.png` | light zh | Arti 通知 ⚡ + 定时任务「…」已跳过卡 above composer |
| `after/schedule-skip-dark.png` | dark zh | 同上 |

Harness: `harness/schedule-skip-notify.html` (+ `shoot.py`). Title/body = `schedules.skippedOverQuote` / `schedules.skippedOverQuoteReason`. Not harness-only product chrome (#404/#474).

## Tokens used
`--ca-text` / `--ca-text-2` / `--ca-muted` / `--ca-border` / `--ca-field` / `--ca-float` / `--ca-block-gap` / `--ca-notify-close-hover` — no hard-coded hex in product CSS.
