# #78 Question card assets for PR #336 · issue #335

- tip: `453f498` (`fix/p1-335-question-other-scroll`)
- source: **tip-CSS harness live** — static HTML copies `QuestionCard` structure from tip `ChatMessage.tsx` + `.ca-q*` / tokens from tip `overlays.css` + `base.css`. Not a full ComfyUI/app runtime capture.
- badges in after/ PNGs: `tip-CSS harness · 453f498`
- no API keys; Chinese UI; 无「修改」

## Design MVP (pixel target)

Spec: `QUESTION-CARD-MVP.md` + `question-card-comfyart-mvp.html`
Tokens: `--ca-opt-on` light `#ebebeb`; `--ca-letter-on`; `--ca-scroll-thumb`; `--ca-q-body-max: 272px`
Selected = soft fill, **NO** `--ca-strong` border. `--ca-strong` only for primary button.
Other = E selected → `[E] + inline input` placeholder「写下你的想法」.

Design composites also copied under `design-mvp/` for product self-review (not tip shots).

## Required #78 states (tip after · Lovart side-by-side)

| file | shows |
|------|-------|
| after/light-scroll.png | Light · multi-q · **thin scrollbar** · soft select B · no black ring |
| after/dark-scroll.png | Dark same |
| after/light-other.png | Light · **E 其他 inline expand**「山野徒步、粗犷质感」· `--ca-opt-on` |
| after/dark-other.png | Dark same |
| after/light-selected.png | Light · **轻选中** C · `--ca-opt-on` / `--ca-letter-on` · **no thick black border** |
| after/dark-selected.png | Dark same |
| compare/lovart94-vs-comfy-scrollbar.png | Lovart RS/94 ‖ tip scrollbar |
| compare/lovart96-vs-comfy-other.png | Lovart RS/96 ‖ tip 其他展开 |
| compare/lovart95-vs-comfy-selected.png | Lovart RS/95 ‖ tip 轻选中 |
| design-mvp/question-card-335-*-2x.png | Design MVP Lovart 并排（产品自审） |
