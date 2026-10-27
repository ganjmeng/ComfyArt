# #381 → #78 visual review

| Lovart CN reference | before (main 3eddf03) | after (this PR) |
|---|---|---|
| lovart/memory-delete-confirm-dialog-light.png | before/delete-confirm-light.png | after/delete-confirm-light.png |
| lovart/memory-deleted-toast-light.png | before/delete-toast-light.png (no toast on main) | after/delete-toast-light.png |
| lovart/memory-modal-after-delete-dark.png | before/after-delete-dark.png | after/after-delete-dark.png |
| CN 无深色 | before/delete-confirm-dark.png | after/delete-confirm-dark.png |
| CN 无深色 | before/delete-toast-dark.png | after/delete-toast-dark.png |
| — (new: empty state) | before/empty-*.png (demo seeds appear) | after/empty-*.png (4 headings + guide line) |
| — (new: chooser) | n/a | after/chooser-*-{light,dark}.png |
| — (/arti toggles) | before/arti-toggles-*.png | after/arti-toggles-*.png |

Notes
- Live shots come from the home Arti page (`?view=arti`, 1440×900, mock server, no paid calls). The CN refs show the canvas memory modal; it uses the same confirm + toast components.
- The chooser shots come from static harness pages (`harness/*.html`, same DOM/classes as `src/ui/MemoryChooser.tsx`, linked to built `dist` CSS). A live chooser needs a multi-match from the agent, so it is not shot live.
- Lovart has no dark CN shots for the confirm or the toast. Those are marked "CN 无深色".
