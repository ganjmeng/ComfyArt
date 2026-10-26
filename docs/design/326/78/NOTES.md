# #326 process-timeline · #78 evidence

Honest label: tip CSS harness (`dist/assets/index-*.css` @ this PR) + static DOM matching `ProcessTimeline` / #325 `Thought` — NOT full Electron / not live LLM.

## Shots
| | light | dark |
|---|---|---|
| **before** (#325 Thought-only, no rail) | `before/light-{live,done}.png` | `before/dark-{live,done}.png` |
| **after** (#326 v3.4 ProcessTimeline) | `after/light-{live,done}.png` | `after/dark-{live,done}.png` |

## After vs design lock v3.4
- Solid 1px spine on icon-column center (first→last icon cy)
- Lucide Brain · ScrollText · Globe · Image · Video · stroke 2 · ~16px · static (no spinner/check/breath/halo)
- Equal step spacing; labels vertically centered with icons
- Only ACTIVE title uses `ca-process__label--active` / ca-shine; done rows muted static
- Status = wide rounded card under live row, sibling outside rail
- Light + Dark

Harness: `harness/after-*.html`, `harness/before-*.html` + `harness/tip.css`
