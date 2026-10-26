# #337 sidebar-live · #78 evidence (remaining 1:1 pixel P0)

**Tip:** `eeb485a` (`fix/p1-337-question-pixel-1to1` · draft PR #339)  
**Baseline:** `main@8675819` (#338 tip behavior)  
**Prior pin:** `b9066ee` (tip `fb56d4f` · single-select only)

## Honest source label

**Playwright Chromium + tip `dist` AgentPanel (production React `QuestionCard` / `.ca-q`) against stubbed ComfyArt aiohttp routes + seeded `bot_asks.create_ask` (`kind=question`, incl. `max_selections>1` multi).**

- Real left column chrome: `aside.ca-agent` (~400px product width), chat list, history open, composer, tip CSS/JS from tip dist.
- **NOT** full Electron desktop shell / **NOT** live LLM turn.
- Closer than chat-shell HTML harness; product accepted this gate for proofread.
- Do **not** claim Electron/ComfyUI desktop runtime.

Capture: `/workspace/comfyart-337-sidebar-live/capture.py` (copy in this folder).

## States (light + dark)

| id | state |
|----|--------|
| `*-empty` | empty other · flat unselected · submit disabled |
| `*-other` | filled other soft-on · A–D cleared |
| `*-keep` | A soft-on · other text **kept** after A click |
| `*-soft` | B soft-select · other empty |
| `*-multi` | **RS/105** · `（多选）` hint · ≥2 soft-selects + Other 末字母 |

`shots/*-col.png` = full `aside.ca-agent` column; `shots/*-card.png` = card crop; `shots/*.png` = agent + canvas edge.

## compare/

- `sidebar-empty-vs-lovart01.png` / `sidebar-empty-vs-lovart94.png`
- `sidebar-other-vs-lovart04.png` / `sidebar-other-vs-lovart96.png`
- `sidebar-keep-vs-lovart06.png` / `sidebar-soft-vs-lovart03.png`
- `sidebar-multi-vs-lovart105.png` — multi ‖ Lovart RS/105
- `sidebar-*-light-vs-dark.png` — empty / other / multi theme pairs

## Tip P0 locks visible in shots

- Local light `--ca-q-shadow` (not global float)
- Header quieter (12/500 · icon 13@.65 · chev 18/12)
- Footer gap 6 · Skip 400 · Submit 600 + `↵`
- `--ca-block-gap:8` · flat unselected (no `--ca-field` pill)
- Multi `（多选）` + stacked soft-select
- No entrance animation

## #78 / sign-off

**NOT product PASS · NOT formal Ashley #78 sign-off · do not request signs / DM.**  
Ready for **product proofread**. Remaining gap for true Electron claim: launch ComfyArt Electron with this tip dist and inject the same pending ask in a live desktop session.
