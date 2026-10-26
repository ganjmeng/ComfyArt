# #348 process-timeline row kinds · review-assets

**Code tip:** `81f7292a3e7b7726a7c7e13a2c6a19603552458d` · branch `fix/p1-348-process-row-kinds` · closes #348.  
**#78 review-assets SHA:** 
**#78 tip path:** `docs/design/348/78/` on branch `fix/p1-348-process-row-kinds`.

## Honest source
Tip CSS harness (`dist/assets/index-*.css`) + static DOM matching ProcessTimeline / #325 Thought — NOT full Electron / NOT live LLM.

## Inventory
| Path | Contents |
|------|----------|
| `before/light|dark-{live,done}.png` | #325 Thought-only baseline |
| `after/light|dark-{live,done}.png` | Skill live primary + full done muted |
| `sidebar-live/after/skill-*-live.png` | Skill live 高亮 + FileSearch |
| `sidebar-live/after/image|video-*-live.png` | image/video live + model suffix |
| `sidebar-live/after/code-*-live.png` | Writing code ≥3 sub-kinds |
| `sidebar-live/harness/` | HTML + tip.css capture kit |

## Checklist
- [x] Light required (+ dark recommended) before/after
- [x] Skill live shimmer + status
- [x] image/video live + using {model}
- [x] Writing code ≥3 subs on spine
- [x] done muted · no status · icons static
- [x] No Lovart-cropped icons
