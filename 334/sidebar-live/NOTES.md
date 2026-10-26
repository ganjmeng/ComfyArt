# #334 sidebar-live · #78 evidence

**Tip:** `71b8fb0` (`fix/p2-334-question-submit-clip-pager` · draft PR closes #334)  
**Baseline:** `main@9e5ac7e` (#339/#340 tip behavior)  
**Prior pin:** `6f50999` (tip `55b6035` · #340 letter-on + multicard)

## Honest source label

**Playwright Chromium + tip `dist` AgentPanel (production React `QuestionCard` / `.ca-q`) against stubbed ComfyArt aiohttp routes + seeded `bot_asks.create_ask` (`kind=question`, incl. `questions[]` multi-block + page_count=2).**

- Real left column chrome: `aside.ca-agent` (~400px product width), chat list, history open, composer, tip CSS/JS from tip dist.
- **NOT** full Electron desktop shell / **NOT** live LLM turn.
- Closer than chat-shell HTML harness; product accepted this gate for proofread.
- Do **not** claim Electron/ComfyUI desktop runtime.

Capture: `/workspace/comfyart-334-sidebar-live/capture.py` (copy in this folder / `334/sidebar-live/`).

## #334 Scope

| Item | Evidence |
|------|----------|
| **末页 提交↵** | `*-multicard-last-submit` · pager `2 of 2` · primary **提交 ↵** (enabled) |
| **末页 disabled 提交** | `*-multicard-last-disabled` · 提交↵ muted/`--ca-field` before page-2 answer |
| **开放文本行** | `*-multicard-opentext-empty` · `[A]+input` placeholder「例如：源野 / 户外背包品牌…」; filled in `*-multicard` |
| **开放文本裁切 fix** | tip: `textarea`→`<input type="text">` + `line-height:18` + ellipsis (void UA-pad glyph clip) |
| **body 末题脚裁切** | `*-multicard-scroll` · `.ca-q__body` max-h 240 + thin scroll (RS/94) |
| **中页 下一步→** | `*-multicard` · `1 of 2` + **下一步 →** |
| **pager 源断言** | `tests/test_question_pixel_337.py::test_pager_next_source_asserts_334` |

## States (light + dark)

| id | state |
|----|-------|
| opentext-empty | page1 · open-text placeholder · disabled Next |
| multicard | page1 filled · mid **下一步→** |
| multicard-scroll | body scrolled · 末题/多选 peek clip |
| last-disabled | page2 · **提交↵** disabled |
| last-submit | page2 · **提交↵** enabled |
| other / soft / multi / empty / keep | carry from #337/#340 harness |

## Vs Lovart / MVP

- RS/94: open-text + body clip + disabled primary — see `compare/334-light-opentext-vs-lovart94.png` · `334-light-bodyclip-vs-lovart94.png` · `334-light-submit-disabled-vs-lovart94.png`
- Product lock: mid **下一步→** / last **提交↵** (Lovart RS/94 page1 shows Submit on all pages — we keep product Next/Submit split)
- MVP: `QUESTION-CARD-MVP.md` · `question-card-comfyart-mvp.html`

## Tests

```
COMFYART_SKIP_NODE_TESTS=1 pytest tests/test_question_pixel_337.py tests/test_question_other_337.py
# 16 passed
```
