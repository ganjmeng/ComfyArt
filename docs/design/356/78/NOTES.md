# #356 Generating media hero · #78 shots

**Branch:** `tip/356-media-hero` · closes #356  
**#78 tip path:** `docs/design/356/78/`  
**Acceptance:** issue comments 6417443450 + 6417654394 · MEDIA-HERO.md (video AR prefer tool/job else **1/1**)

## Honest source
Tip CSS harness (`dist/assets/index-*.css` → `harness/tip.css`) + static DOM matching ProcessTimeline / GeneratorShape — NOT full Electron / NOT live LLM.

## Inventory
| Path | Contents |
|------|----------|
| `before/chat-image-light-live.png` | #348 timeline-only (no media hero) |
| `after/chat-image-{light,dark}-live.png` | image live + grey hero |
| `after/chat-video-{light,dark}-live.png` | video live + grey hero AR 1/1 |
| `after/chat-done-light.png` | result thumbs, no grey hero |
| `after/canvas-generating-{light,dark}.png` | ca-gen-frame + Generating pill |
| `after/density-before-after-light.png` | before/after strip |
| `harness/` | HTML + tip.css capture kit |

## Checklist
- [x] Light required (+ dark recommended)
- [x] chat image/video live + hero
- [x] chat done no hero
- [x] canvas Generating + pill
- [x] density strip
- [x] Video default AR 1/1 (comment-6417654394)
