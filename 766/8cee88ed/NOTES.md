# #766 tip 8cee88ed — collapsed Thought tip hides ask_user

Tip: `8cee88ed98bf7207d328c30f0a5b4748e0151528` (PR #767)
How: full App `http://127.0.0.1:8199/comfyart/` + canvas + composer; ComfyUI `--cpu --listen 127.0.0.1 --port 8199`; Playwright Firefox; natural-language user seed (**no** `ask_user` in typed prompt).

## Product lock (YohakuX / Jingmeng / QA / design / EL / PM)

| Surface | `ask_user` |
|---------|------------|
| COLLAPSED Thought preview (`ca-chat__arg` / live-thought-inline) | ❌ must hide (正文) |
| EXPANDED thinking body (`ca-chat__thoughttext`) | ✅ KEEP |
| User bubbles / docked card / answer·skip bubble / left agent prose / process labels | ❌ |

## Checklist

| Item | Result |
|------|--------|
| Right `ca-chat__user` bubble (`ask-answer-bubble`) | ✅ |
| zh `问:` / `答:` · en `Q:` / `A:` | ✅ |
| Skip `Skip this question` / `跳过这个问题` | ✅ |
| No left grey `ca-qmemo` | ✅ |
| Full App (not ask763 harness) | ✅ |
| Collapsed tip no `ask_user` (walks prior clean line) | ✅ tip: `Note memory says they prefer minimal line style, but they asked to ask. So ask.` |
| Expanded thinking may contain `ask_user` | ✅ `Let me call ask_user with one multiple-choice question.` |
| NL seed has no `ask_user` | ✅ |
| Follow-up capture-as-is (no Got it I'll wait rewrite) | ✅ not blocking |

## Code

`thoughtCollapsedTip()` in `src/ui/ChatMessage.tsx` — reverse-walk lines, skip `/\bask_user\b/i`; Thought collapsed + ProcessTimeline live-thought-inline use tip; expanded stays `text.trim()`.

## Assert

See `assert.json` — `ok: true`, `leak_proof: true`, coverage submit/skip × zh/en complete.
