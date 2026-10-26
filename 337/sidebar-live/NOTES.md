# #337/#340 sidebar-live · #78 evidence

**Tip:** `55b6035` (`fix/p1-337-question-pixel-1to1` · draft PR #339 · closes #340 Scope A/B)  
**Baseline:** `main@8675819` (#338 tip behavior)  
**Prior pin:** `2676d24` (tip `eeb485a` · pre-#340 letter correction)

## Honest source label

**Playwright Chromium + tip `dist` AgentPanel (production React `QuestionCard` / `.ca-q`) against stubbed ComfyArt aiohttp routes + seeded `bot_asks.create_ask` (`kind=question`, incl. `questions[]` multi-block + `max_selections>1`).**

- Real left column chrome: `aside.ca-agent` (~400px product width), chat list, history open, composer, tip CSS/JS from tip dist.
- **NOT** full Electron desktop shell / **NOT** live LLM turn.
- Closer than chat-shell HTML harness; product accepted this gate for proofread.
- Do **not** claim Electron/ComfyUI desktop runtime.

Capture: `/workspace/comfyart-340-sidebar-live/capture.py` (copy in this folder / `340/sidebar-live/`).

## #340 Scope A — letter-on lock (Ashley correction)

| Token | Value |
|-------|-------|
| `--ca-letter-on` | **`#2d2d2d`** (≈ rgba(0,0,0,.82); softer than tip `#1a1a1a`) |
| `--ca-letter-on-fg` | **`#fff`** near-white — **NOT** dark text / `var(--ca-text)` |
| `--ca-opt-on` | `#ebebeb` **only** on `[data-on]` |
| unselected letter | `--ca-letter: rgba(0,0,0,.06)` · `--ca-letter-fg: rgba(0,0,0,.45)` |
| unselected row | flat transparent — ban `--ca-field` full-row pill |
| **VOID** | mid-gray `.55` letter bg + dark fg (after-mock direction) |
| dark | `--ca-letter-on: #404040` · `--ca-letter-on-fg: #fff` · `--ca-opt-on: rgba(255,255,255,.12)` |

Ban `--ca-strong` as option stroke.

## #340 Scope B — multi-block page chrome

- `‹ n of N ›` pager + multiple `.ca-q__block` per page
- Mid-page primary **「下一步→」** / last **「提交↵」**
- #78 × Lovart RS/94 · RS/105 (scroll shots show second block / `（多选）`)

## States (light + dark)

| id | state |
|----|--------|
| `*-empty` | empty other · flat unselected · submit disabled |
| `*-other` | filled other soft-on · A–D cleared |
| `*-keep` | A soft-on · other text **kept** after A click |
| `*-soft` | B soft-select · letter-on `#2d2d2d`+#fff |
| `*-multi` | RS/105 · `（多选）` hint · ≥2 soft-selects + Other |
| `*-multicard` | **#340** multi `.ca-q__block` · `1 of 2` ·「下一步→」 |
| `*-multicard-scroll` | scrolled to second block / `（多选）` |

`shots/*-col.png` = full `aside.ca-agent` column; `shots/*-card.png` = card crop; `shots/*.png` = agent + canvas edge.

## compare/

- `sidebar-soft-vs-lovart03.png` / `sidebar-soft-light-vs-dark.png` — Scope A
- `sidebar-multicard-vs-lovart94.png` / `sidebar-multicard-vs-lovart105.png`
- `sidebar-multicard-light-vs-dark.png` / `sidebar-multicard-scroll-light-vs-dark.png`
- Prior empty/other/keep/multi compares retained from tip eeb485a refresh where still valid
- Also mirrored under `340/sidebar-live/compare/340-*.png`

## Tip P0 locks visible in shots

- Selected letter **`#2d2d2d` + white** (not `#1a1a1a`, not `.55`/dark-fg)
- Soft row `--ca-opt-on` only when selected; unselected flat
- Multi-block pager +「下一步→」/「提交↵」
- Local light `--ca-q-shadow` (not global float)

**NOT product PASS · NOT formal Ashley #78 sign-off · do not DM Ashley.**  
Ready for **product proofread**.
