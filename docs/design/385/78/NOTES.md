# #385 → #78 visual review

All "after" shots are real-app screenshots taken by `tests/test_e2e_arti_385.py` (built `dist`, home Arti page `?view=arti`, 1440×900, mock server, LLM `/comfyart/llm/complete` stubbed, no paid calls). The same test asserts toggle persistence, chat composer open, and evolution log columns. Set `SHOT_OUT=<dir>` to regenerate them.

| Reference (CN) | before | after (this PR) |
|---|---|---|
| lovart/arti-page-top-toggles-dark.png | before/arti-toggles-dark.png (#381: state shown, switches disabled) | after/arti-toggles-dark.png (memory/skills switchable + persist) |
| CN 无浅色 | before/arti-toggles-light.png | after/arti-toggles-light.png |
| lovart/arti-memory-chat-edit-composer-light.png | before/arti-memory-chat-edit-composer-*.png | after/arti-memory-chat-edit-composer-*.png (add/correct/forget via intent) |
| lovart/arti-evolution-log-dark.png · arti-page-evolution-log-light.png | before/arti-evolution-log-*.png (placeholder 「进化日志即将开放」) | after/arti-evolution-log-*.png (时间 \| 操作 from memoryLog) |
| CN 无对照 (empty log) | n/a | after/arti-evolution-empty-*.png |

Notes
- #385 wires 「自动更新记忆」「自进化技能」 to real `proactive-memory` / `proactive-skills` via `saveSettings` + `loadSettings` on /arti mount (switchable; #381 only showed state + disabled).
- Chat composer distinguishes add / correct / forget via mockable LLM intent (`artiChatMemory.ts`).
- Evolution log: two columns 「时间 | 操作」, data from `memoryLogAtom` (newest first); empty state replaces placeholder.
- Ownership fields on memory records stay `owner_id` + `workspace_id` (SaaS-ready naming; no multi-tenant infra in this PR).
