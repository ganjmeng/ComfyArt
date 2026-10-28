# #382 → #78 visual review

Mocks only (no paid calls). After shots are HTML harness screenshots of the process-rail row 「记忆已更新 ›」 between 思考完成 and the reply, matching CN `memory-updated-row-in-chat-light`. Dark has no CN reference — token check only.

## Shots (relative under `docs/design/382/78/`)
| Lovart CN reference | before (main, no row) | after (this PR) |
|---|---|---|
| `lovart/memory-updated-row-in-chat-light.png` (.webp source) | `before/memory-updated-row-light.png` | `after/memory-updated-row-light.png` |
| CN 无深色 | `before/memory-updated-row-dark.png` | `after/memory-updated-row-dark.png` |

PR body tip-pins absolute `raw.githubusercontent.com` URLs to **branch HEAD** (must HTTP 200). Do not embed a tip SHA in this NOTES file (avoids tip≠NOTES drift).

## Notes
- Placement AC5: types order is `[thinking, memory_updated, text]` (see `insertMemoryUpdatedBlock` / `memoryUpdatedPlacementOk`).
