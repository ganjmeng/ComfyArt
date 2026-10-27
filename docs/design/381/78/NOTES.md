# #381 → #78 visual review

All "after" shots are real-app screenshots taken by `tests/test_e2e_memory_381.py` (built `dist`, home Arti page `?view=arti`, 1440×900, mock server, no paid calls). The same test asserts the visual rules, so the shots and the assertions come from one run. Set `SHOT_OUT=<dir>` to regenerate them.

| Lovart CN reference | before (main 3eddf03) | after (this PR) |
|---|---|---|
| lovart/arti-page-top-toggles-dark.png | before/arti-toggles-dark.png | after/arti-toggles-dark.png |
| CN 无浅色 | before/arti-toggles-light.png | after/arti-toggles-light.png |
| lovart/arti-memory-list-hover-light.png | before/list-light.png | after/list-light.png |
| lovart/arti-page-memory-top-dark.png | before/list-dark.png | after/list-dark.png |
| lovart/memory-delete-confirm-dialog-light.png | before/delete-confirm-light.png | after/delete-confirm-light.png (no ✕: only 取消 / 删除) |
| CN 无深色 | before/delete-confirm-dark.png | after/delete-confirm-dark.png |
| lovart/memory-deleted-toast-light.png | before/delete-toast-light.png (main shows no toast) | after/delete-toast-light.png |
| CN 无深色 | before/delete-toast-dark.png | after/delete-toast-dark.png |
| lovart/memory-modal-after-delete-dark.png | before/after-delete-dark.png | after/after-delete-dark.png |
| CN 无浅色 | before/after-delete-light.png | after/after-delete-light.png (reshot) |
| CN 无对照 (empty state) | before/empty-*.png (demo seeds appear) | after/empty-{light,dark}.png |
| CN 无对照 (picker) | n/a | after/chooser-forget-selected-*, chooser-scrolled-bottom-*, chooser-correct-selected-* |
| CN 无对照 (new states) | n/a | after/read-error-*, after/save-failed-toast-* |

Notes
- Product confirmed that design signs off the empty state and the picker against tokens, because no CN reference exists for them ("CN 无对照").
- The CN references for the confirm, toast and after-delete come from the canvas memory modal. It uses the same Confirm and toast components.
- Picker: matching is exact full text, so every candidate in a multi-match carries the same text. The title reads 「找到 N 条相同记忆，要改哪一条？」. There are 6 rows, 5 visible, with a bottom fade and an always-visible scrollbar. `chooser-scrolled-bottom-*` shows row 6 with the fade gone.
- "Primary token" = `--ca-strong`, the token the primary buttons use. In dark mode the radio and the 更正 button are therefore near-white.
