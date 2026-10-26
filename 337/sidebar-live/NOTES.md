# #337 sidebar-live · #78 evidence (closer than chat-shell)

**Tip:** `fb56d4f` (`fix/p1-337-question-other-input`; product behavior from `54baf74`)

## Honest source label

**Playwright Chromium + tip `dist` AgentPanel (production React `QuestionCard` / `.ca-q`) against stubbed ComfyArt aiohttp routes + seeded `bot_asks.create_ask` (`kind=question`, `allow_other`).**

- Real left column chrome: `aside.ca-agent` (~400px product width), chat list, history open, composer, tip CSS/JS from tip dist.
- **NOT** full Electron desktop shell / **NOT** live LLM turn.
- **Closer than** rejected `337/after-live/` chat-shell HTML harness (~300 tip-CSS column) @ `83cc4ea`.
- Do **not** claim Electron/ComfyUI desktop runtime.

Capture: `/workspace/comfyart-337-sidebar-live/capture.py` (copy in this folder).

## States (light + dark)

| id | state |
|----|--------|
| `*-empty` | empty other · flat · submit disabled |
| `*-other` | filled other soft-on (`包装袋`) · A–D cleared |
| `*-keep` | A soft-on · other text **kept** after A click |
| `*-soft` | B soft-select · other empty |

`shots/*-col.png` = full `aside.ca-agent` column; `shots/*.png` = agent + canvas edge.

## compare/

- `sidebar-*-vs-lovart0*.png` — sidebar-live ‖ Lovart live (empty / filled / keep / soft)
- `sidebar-other-light-vs-dark.png` — filled other light ‖ dark

Lovart refs: `337/lovart-live/` (RS notes in that NOTES.md).

## #78 / sign-off

**NOT product PASS · NOT formal #78 sign-off · do not request signs.**  
Product must proofread before Ashley DM. Remaining gap for true Electron claim: launch ComfyArt Electron (or ComfyUI linked to this tip dist) and inject the same pending ask in a live desktop session.
