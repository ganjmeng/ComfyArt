# #348 process-timeline row kinds · #78 evidence

Honest label: tip CSS harness (`dist/assets/index-*.css` @ this PR) + static DOM matching `ProcessTimeline` / #325 `Thought` — NOT full Electron / not live LLM.

## Shots
| | light | dark |
|---|---|---|
| **before** (#325 Thought-only, no rail) | `before/light-{live,done}.png` | `before/dark-{live,done}.png` |
| **after** (Skill live primary) | `after/light-{live,done}.png` | `after/dark-{live,done}.png` |
| Skill live | `after/skill-light-live.png` | `after/skill-dark-live.png` |
| image/video live + model | `after/image-light-live.png` · `after/video-light-live.png` | (dark in review-assets) |
| Writing code ≥3 subs | `after/code-light-live.png` | `after/code-dark-live.png` |

## After vs #348 MUST + v3.4 lock
- Extended kinds: outputting · skill_file_read · search_pages · code · code_generated · code_updated · design_validated · preview_artifact
- Lucide FileSearch / SquareCode / FileCode / FilePenLine / ListChecks / Sparkles (stroke 2 · 16px · originals)
- Skill / skill_file_read live: title shimmer + status card outside rail
- image/video live + optional `…using {model}`
- Solid 1px spine · `--ca-process-step:30px` · done muted · no status
- Single Thought still #325 path (before/)

Harness: review-assets `348/sidebar-live/harness/` (not on tip `78/` tree)
