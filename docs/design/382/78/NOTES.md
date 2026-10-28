# #382 → #78 visual review

Mocks only (no paid calls). After shots are HTML harness screenshots of the process-rail row 「记忆已更新 ›」 between 思考完成 and the reply, matching CN `memory-updated-row-in-chat-light`. Dark has no CN reference — token check only.

Tip SHA: `bf0d775b1d3b54d87e1acd355fc7c7b09e3c6ba2`

Raw (must HTTP 200):
- after light: https://raw.githubusercontent.com/ganjmeng/ComfyArt/4df85f7bfc09570dcea42db9f5b38b5e9e813985/docs/design/382/78/after/memory-updated-row-light.png
- after dark: https://raw.githubusercontent.com/ganjmeng/ComfyArt/4df85f7bfc09570dcea42db9f5b38b5e9e813985/docs/design/382/78/after/memory-updated-row-dark.png
- before light: https://raw.githubusercontent.com/ganjmeng/ComfyArt/4df85f7bfc09570dcea42db9f5b38b5e9e813985/docs/design/382/78/before/memory-updated-row-light.png
- before dark: https://raw.githubusercontent.com/ganjmeng/ComfyArt/4df85f7bfc09570dcea42db9f5b38b5e9e813985/docs/design/382/78/before/memory-updated-row-dark.png
- CN light: https://raw.githubusercontent.com/ganjmeng/ComfyArt/4df85f7bfc09570dcea42db9f5b38b5e9e813985/docs/design/382/78/lovart/memory-updated-row-in-chat-light.png

| Lovart CN reference | before (main, no row) | after (this PR) |
|---|---|---|
| lovart/memory-updated-row-in-chat-light.png (.webp source) | before/memory-updated-row-light.png | after/memory-updated-row-light.png |
| CN 无深色 | before/memory-updated-row-dark.png | after/memory-updated-row-dark.png |

Notes
- Placement AC5: types order is `[thinking, memory_updated, text]` (see `insertMemoryUpdatedBlock` / `memoryUpdatedPlacementOk`).
- Click row → `memoryFocusAtom` opens Memory dialog scrolled to that id; Undo calls `undoMemoryUpdated` → `removeMemory` + log entry.
- Harness: `docs/design/382/78/harness/memory-updated-row.html` (+ `-before.html`).
- Budget / log / inject behaviour is covered by `tests/test_memory_budget_382.py` (12 cases), not by these shots.
