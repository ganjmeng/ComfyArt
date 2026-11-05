# QA #766 tip ce422970 — HOLD (not merge-ready)

Tip: `ce422970ac1c345ee155b2482eb2904211a2dd9e`
How: full App `http://127.0.0.1:8199/comfyart/` + canvas + composer; ComfyUI `--cpu --listen 127.0.0.1 --port 8199`; Playwright Firefox; natural-language user seed (no `ask_user` in prompt).

## Bubble chrome (#766 checklist) — PASS

| Item | Result |
|------|--------|
| Right `ca-chat__user` bubble (`data-testid=ask-answer-bubble`) | ✅ |
| zh `问:` / `答:` | ✅ |
| en `Q:` / `A:` | ✅ |
| Skip `Skip this question` / `跳过这个问题` | ✅ |
| No left grey `ca-qmemo` | ✅ |
| Full App (composer + canvas), not ask763 harness | ✅ |

## Residual / HOLD reasons (product lock: tip not merge-ready)

### 1. Follow-up prose after submit
- Immediate after submit: often **only** Thought + Q/A bubble (matches Jingmeng SBS crop).
- After waiting ~up to 120s in real App: left unbubbled agent prose **does appear** (not swallowed).
- Content is usually generation/审图 prose, not Lovart-style "Got it — I'll wait…". Agent also often generates despite "do not generate".
- Conclusion: **not HOLD for swallowed output**; behavior residual for product/engineer in same PR if they want Lovart wait wording.

### 2. `ask_user` string in visible UI
- Natural seed used (Lovart-like). User bubble has **no** `ask_user`.
- Agent body text / process **labels**: no raw `ask_user` (ask row suppressed; labels mapped).
- Lone Thought tip always shows thinking **last line** collapsed (`ca-chat__arg`). On fresh en submit chat `c9bb0d52`, last line was: `Let me call ask_user with one multiple-choice question.` → **user-visible tool-name leak before ask** → **HOLD**.
- Full thinking bodies often mention `ask_user` even when last line is clean (`Let me ask.`); expanding Thought would also expose it.

## Evidence files
- `ours/01-full-submit-en-immediate.png` — bubble, no follow yet
- `ours/02-full-submit-en-after-wait.png` / `03-agent-…` — follow-up after wait
- `ours/05-agent-skip-zh-after-wait.png` — skip + follow-up wait prose
- `sbs/*.png` — Lovart vs ours
- `assert.json` — measured checklist

