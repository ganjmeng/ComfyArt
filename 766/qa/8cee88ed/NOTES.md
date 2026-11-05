# QA #766 tip 8cee88ed — PASS

Tip: `8cee88ed98bf7207d328c30f0a5b4748e0151528` (PR #767)
How: real full App `http://127.0.0.1:8199/comfyart/` + canvas + composer; ComfyUI `--cpu --listen 127.0.0.1 --port 8199`; Playwright Firefox; natural-language user seed (**no** `ask_user` in typed prompt). Independent retest of tip after HOLD on `ce422970`.

## Product lock (Jingmeng / product / EL / design)

| Surface | `ask_user` |
|---------|------------|
| COLLAPSED Thought preview (`ca-chat__arg`) | ❌ must hide (正文) |
| EXPANDED thinking body (`ca-chat__thoughttext`) | ✅ KEEP |
| User bubbles / docked card / answer·skip / left agent prose / process labels | ❌ |

## Checklist

| Item | Result |
|------|--------|
| Right `ca-chat__user` bubble | ✅ |
| zh `问:` / `答:` · en `Q:` / `A:` | ✅ |
| Skip `Skip this question` / `跳过这个问题` | ✅ |
| No left grey `ca-qmemo` | ✅ |
| Full App (not test harness) | ✅ |
| Collapsed tip no `ask_user` | ✅ tip: `Note memory says they prefer minimal line style, but they asked to ask. So ask.` |
| Expanded may contain `ask_user` | ✅ e.g. `So call ask_user with one question…` / `Just ask_user.` |
| NL seed has no `ask_user` | ✅ |
| Follow-up prose after wait | ✅ appears (generation/审图 OK; not blocking) |

## Coverage

Settled chats on tip App: submit zh/en + skip zh (+ leak-proof en) all PASS; fresh skip en PASS. See `assert.json`.
