# #387 → #78 visual review

**Closes #387.** Pending ask card (待答卡) survives refresh — tip CSS/DOM shots.

## After（real tip CSS/DOM — `base.css` + `overlays.css` + QuestionCard DOM from ChatMessage.tsx；zh × light/dark）
| Shot | Theme | Shows |
|------|-------|-------|
| `after/ask-persist-light.png` | light zh | 待答卡 above bubble · 问题 · 1 of 2 · Aurora/Nova · 跳过/下一步 |
| `after/ask-persist-dark.png` | dark zh | 同上 |

Harness: `harness/ask-persist-live.html` (+ `shoot-live.py`) loads tip stylesheets and mirrors QuestionCard DOM (not reinvented tip.css chrome). Before harness (`ask-persist-before.html` / tip.css) kept for historical contrast only — design/QA sign after/ live pair.

## Tokens used
`--ca-text` / `--ca-muted` / `--ca-float` / `--ca-field` / `--ca-hover` / `--ca-opt-on` / `--ca-q-shadow` / `--ca-q-body-max` / `--ca-border` — no hard-coded product hex beyond stage backdrop.

PR tip-pins absolute `raw.githubusercontent.com/.../<tip-sha>/docs/design/387/78/after/...` URLs (must HTTP 200). Do not embed tip SHA in this NOTES file.
