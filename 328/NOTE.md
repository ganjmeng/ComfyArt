# #78 Question card assets for PR #333

- tip: `92cd335b9002fd80e3da4be475b387b3e38adaae` (fix/p1-328-question-card)
- source: **tip-CSS harness live** — static HTML copies `QuestionCard` / `QuestionAnswered` class structure from `src/ui/ChatMessage.tsx` + `.ca-q*` / tokens from tip `overlays.css` + `base.css` (Icons.question / Icons.next). Not a full ComfyUI/app runtime capture.
- replaces prior design-mock interim (`QUESTION-CARD-MVP` crops @526f8ef)
- badges in PNGs: `tip-CSS harness · 92cd335`
- no API keys in shots
- Chinese: 问题 / 跳过 / 下一步 / 提交; pageOf `{n} of {N}`; 问/答; 无「修改」

| file | shows |
|------|-------|
| after/light-pending.png | Light mid-page · ‹ 2 of 3 › · multi-q · 下一步 → |
| after/dark-pending.png | Dark same |
| after/light-answered.png | Light grey Q/A memo · no「修改」 |
| after/dark-answered.png | Dark same |
| after-live/* | Same PNGs (alias path) |
| before/ask-chips.png | main Ask chips (pre-QuestionCard) |
