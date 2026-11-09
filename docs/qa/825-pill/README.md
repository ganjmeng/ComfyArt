# #825 generation-card Auto · model label

## Finding (Lovart)
Lovart’s generation row above the thumbnail is a gray icon + **「图片模型」** only — **no model name, no hover tooltip** (existing history; no new generations / $0).

- `lovart-card-1.png` — chat crop, 「图片模型」 above result thumb
- `lovart-card-2-hover-label.png` — same row (no hover affordance)

## Ours (enhancement, not parity)
Process-rail / gen-card row reuses the same gray icon + muted 13px text placement as Lovart. Text is **`Auto · <short name>`** (manual = short name only). Auto hover/tap shows the table reason (zh/en by locale); **manual shows no reason UI**. Backend manual `reason` remains `你指定了这个模型` / `you named this model`.

- `ours-auto-label.png` / `ours-auto-label.html` — fixture: Auto done / Auto pending / manual
- `LR-lovart-vs-ours-auto-label.png` — L/R pair

PR must state this is an **enhancement beyond Lovart**, not parity.
