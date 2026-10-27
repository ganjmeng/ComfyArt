# Arti mascot v6 sheets + peek top -29px · #78

Real composer (canvas Agent panel, `?project=v6shot&new=1&artiLevel=N`), built `dist` served by `vite preview`, headless Chrome, DPR 2, 1280×900, zh. No backend (API 502s; UI-only).
- **before/** = `origin/main` 3eddf03 build (old sheets, `top:-22px`)
- **after/** = this tip (v6 sheets, `top:-29px`)
- States per level Lv.1/2/3 × dark/light: `idle` (frame 0), `hover`, `f12`/`f13`/`f14` (lowest bob; frame forced via `background-position`, animation off).
- `geometry.json`: `peekPx` = composer top − mascot top. before 21px (hover 32), after 28px (hover 39) in every frame.
- `zoom-mascot-{before,after}.png`: rows dark Lv1-3, light Lv1-3; cols idle, hover, f12, f13, f14.

Result: after — mouth visible above composer edge in all 30 frames. before — mouth hidden in idle and f12-14 (eyes also hidden in bob frames).

## Lovart CN reference + panel-open (#378)
- `lovart/` = Lovart CN refs (Lv.1 only, 1x CSS) `composer-pixel-corner-{idle,hover}-{dark,light}.png`.
- `side-by-side-{dark,light}.png` now: Lovart CN same-theme | before | after (Lovart column only for idle/hover; upscaled 2x nearest, composer-top aligned; Lv.1 ref used for all levels).
- `side-by-side-lovart-{dark,light}.png`: Lovart CN (left) vs after (right), Lv.1-3 × idle/hover.
- `after/composer-lv1-panelopen-{dark,light}.png`: notify panel open → corner mascot `visibility:hidden; opacity:0`, top element at its spot is `.arti-notify`.
- Re-verified (headless Chrome, all Lv × theme): idle — mascot top hits mascot, its bottom hits `.ca-composer__input` (behind surface, head only peeks); hover lifts −11px.
