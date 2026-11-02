# #497 residual visual GAP — AFTER #539 vs Lovart M1/M2

**Date:** 2026-11-02 Asia/Shanghai  
**Product lock:** [6573000359](https://github.com/ganjmeng/ComfyArt/issues/497#issuecomment-6573000359) — soft residual **visual 1:1 only**  
**LEFT:** AFTER #539 detail shots (`539c-*` @ `8d1322d7` / `db3996b6`) — **not** main-66dbb4e KitEditor-as-only-surface  
**RIGHT:** Lovart page gold `M1-assets-zh.png` / `M2-assets-en.png` (495-498; no live re-scrape)  
**Scope In:** spacing / token / upload zone / bottom bar / list column width+color (+ title row)  
**Scope Out:** filter/search; preview/download unless L/R shows them on Lovart card「…」(not evidenced → out)

---

## Concrete deltas still off (tip AC candidates)

| # | Area | Lovart (M1/M2) | Ours AFTER #539 | Tip note |
|---|---|---|---|---|
| 1 | **List column width** | Divider ≈ **159px** from left @1280 (narrow secondary pane) | Divider ≈ **438–439px** @1280 / same @1920 (list much wider) | Match Lovart list proportion (narrower list, wider detail) |
| 2 | **List column bg** | Sustained **`#f5f5f5`** under tabs/empty list | Empty list area **`#ffffff`** (card cells `#f5f5f5`); weak separation from detail | List chrome → `#f5f5f5` (or token equiv) vs detail `#fff` |
| 3 | **Upload zone** | Solid light fill ≈`#f3f3f3`–`#f5f5f5`, rounded; copy 「拖拽或上传…或导入 URL」+ PNG/JPG/PDF·20MB; **no** extract subline in M1 | AFTER solid fill `#f5f5f5` (prior dashed residual in old sbs-c looks **P2-closed**); still has extra 「从文件中提取…」 subline; title→zone vertical rhythm differs (title y≈40 ours vs ≈76 Lovart) | Keep solid fill; tune height/padding/radius to M1; decide extract subline keep vs hide for 1:1 |
| 4 | **Title row** | Short default「未命名」/「Untitled」; compact top padding; `…` on EN | Longer「未命名品牌套件」/「Untitled Brand Kit」; more top air; `…` present | Align default name string + top spacing/token to Lovart |
| 5 | **Logo / Color / Font / Reference rows** | Tighter vertical rhythm; thin full-width rules;「+ 添加」/「+ Add」 | Rows taller / more whitespace between rules;「+ 添加」**already P2-fixed** (present + right-aligned) | Compress row height/gap to M1; **do not re-tip「添加」presence** |
| 6 | **Bottom bar / CTA** | Dark CTA bottom-right「使用此素材创建项目 →」 floating over white | Same copy; bar/button hit-area taller / wider span (dark bbox ~full width-ish) | Align bar height, side inset, button weight/radius to M1 |
| 7 | **Left「新建」chrome** | Dashed / dotted create control | Solid-border「+ 新建」+ yellow plus | Optional soft: dashed create affordance per M1/M2 |
| 8 | **Dark** | **No** Lovart Assets **page** dark in evidence | AFTER `539c-detail-p1-en-dark` (+ url-row en-dark) | Borrow AFTER en-dark tokens; **no** pixel-lock to missing Lovart page dark |

---

## Already closed by #539 / P2 (do not re-open as functional)

- Dedicated Assets page + rail entry + 4 kit tabs + KitEditor detail  
- Upload + URL import + 20MB copy/validation  
- 「+ 添加」on Logo/Color/Font/Reference (P2)  
- CTA → project with chip / no auto-send  
- Real local data, no demo  

---

## Out (per 6573000359) — do **not** invent into tip

| Item | Why out |
|---|---|
| **filter / 搜索** | Lovart page gold has none; prior ruling「没有搜索，也没有筛选」 |
| **preview / download** | M1/M2 + staged L/R do **not** open Lovart card「…」showing those actions → **out**; reopen only if later L/R measures them on Lovart menu |
| Character / Product / Custom body variants; role/product extensions | Not in soft residual lock |

---

## SBS index (`sbs/`)

| File | LEFT | RIGHT |
|---|---|---|
| `497-detail-zh-light.png` | `after/539c-detail-p1-zh-light.png` | `lovart/M1-assets-zh.png` |
| `497-detail-en-dark-vs-M2-light.png` | `after/539c-detail-p1-en-dark.png` | `lovart/M2-assets-en.png` (light; theme mismatch labeled) |
| `497-url-row-zh-light.png` | `after/539c-url-row-p2-zh-light.png` | `lovart/M1-assets-zh.png` |
| `497-detail-1920-zh-light.png` | `after/539c-detail-1920-p1-zh-light.png` | `lovart/M1-assets-zh.png` |
| `prior-539c-sbs-detail-*.png` | prior #539 pin composites (orientation Lovart\|Ours — reference only) | |

---

## Ready for product

Product: lock **tip AC** from rows 1–7 (soft visual only) → fullstack tip with `Closes #497`.  
Design: this pin is the L/R evidence; no PR tip from design.
