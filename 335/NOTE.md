# #78 Question card assets for PR #336 · issue #335

- tip: `297cccb` (`fix/p1-335-question-other-scroll`)
- source: **tip-CSS harness live** — static HTML copies `QuestionCard` structure from tip `ChatMessage.tsx` + `.ca-q*` / tokens from tip `overlays.css` + `base.css`. Not a full ComfyUI/app runtime capture.
- badges in after/ PNGs: `tip-CSS harness · 297cccb`
- headed Chromium (classic scrollbar; headless overlay paints sw=0 / no thumb in PNG)
- no API keys; Chinese UI; 无「修改」

## Scrollbar fix (product re-review only)

Designer opacity: light `--ca-scroll-thumb: rgba(0,0,0,.36)` (was .22, invisible in prior #78); dark `.42`.
Thin ~5px webkit + subtle track; `overflow-y: scroll` + body max 272 so thumb always renders when options overflow.
Harness: scrollHeight 562 > clientHeight 272; scrollbarWidth 10 in headed shot.
Other expand + soft select unchanged (prior PASS).

## Design MVP (pixel target)

Spec: `QUESTION-CARD-MVP.md` + `question-card-comfyart-mvp.html`
Tokens: `--ca-opt-on` light `#ebebeb`; `--ca-letter-on`; `--ca-scroll-thumb`; `--ca-q-body-max: 272px`
Selected = soft fill, **NO** `--ca-strong` border. `--ca-strong` only for primary button.
Other = E selected → `[E] + inline input` placeholder「写下你的想法」.

## Required #78 states (tip after · Lovart side-by-side)

| file | shows |
|------|-------|
| after/light-scroll.png | Light · multi-q · **thin visible scrollbar** · soft select B |
| after/dark-scroll.png | Dark same |
| after/light-other.png | Light · **E 其他 inline expand** · `--ca-opt-on` |
| after/dark-other.png | Dark same |
| after/light-selected.png | Light · **轻选中** · no thick black border |
| after/dark-selected.png | Dark same |
| compare/lovart94-vs-comfy-scrollbar.png | Lovart RS/94 ‖ tip scrollbar |
| compare/lovart96-vs-comfy-other.png | Lovart RS/96 ‖ tip 其他展开 |
| compare/lovart95-vs-comfy-selected.png | Lovart RS/95 ‖ tip 轻选中 |
