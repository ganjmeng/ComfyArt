# #825 generation-card Auto · model label (real app shots)

All UI shots below are **real `AssistantBlocks` + app CSS** via `tests/js/pill825/` (rolldown + Playwright Chromium). Mocked tool_use / tool_result / `model_choice` only — **$0**, no WaveSpeed, no network beyond localhost.

Static `ours-auto-label.html` is obsolete (fixture only); prefer the numbered PNGs.

## Lovart (existing history, $0)
| File | Notes |
|------|-------|
| `lovart-card-1.png` | Crop: 「图片模型」 only — no model name, no hover |
| `lovart-card-2-hover-label.png` | Same row, no hover affordance |

## Before / after (main `f22b1ff0` vs tip)
| File | Notes |
|------|-------|
| `00-before-main-f22b1ff0.png` | Same mock payload on main — ignores `model_choice`, no `Auto ·` |
| `01-auto-zh-light.png` | Tip: `Auto · GPT Image 2.6 Sunburst` + tip `海报/带字` |
| `LR-before-after-gen-card.png` | L/R collage |

## Tip cases (real app)
| # | File | Case |
|---|------|------|
| 01 | `01-auto-zh-light.png` | Auto done, zh light + reason tip |
| 02 | `02-auto-en-dark.png` | Auto done, en dark + reason tip |
| 03 | `03-hover-reason-zh.png` | Desktop hover reason (zh) |
| 04 | `04-hover-reason-en.png` | Desktop hover reason (en) |
| 05 | `05-ellipsis-narrow.png` | Narrow card, long name ellipsis |
| 06 | `06-manual-no-tooltip.png` | Manual: name only, **no** tip |
| 07 | `07-failed-keeps-label.png` | Failed row keeps `Auto ·` label |
| 08 | `08-generating-auto.png` | Generating → just `Auto` |
| 09 | `09-fallback-tooltip-zh.png` | `首选 X 失败，改用 Y` |
| 10 | `10-skill-pose-fission.png` | pose-fission → `Auto · Nano Banana Pro` |
| 11 | `11-legacy-no-empty.png` | No model_choice → tool fallback label, not empty Auto |
| 12 | `12-refresh-survives.png` | Remount / same persisted blocks keep label |

## Lovart vs ours (enhancement, not parity)
| File | Notes |
|------|-------|
| `LR-lovart-vs-ours-auto-label.png` | L Lovart 「图片模型」 / R real app Auto · |
| `LR-lovart-vs-ours-hover.png` | L Lovart / R hover reason |

## Harness
```bash
# from repo root (needs npm ci + /workspace/pw-venv playwright chromium)
/workspace/pw-venv/bin/python tests/js/pill825/shoot.py
```

Hover tips in shots: title string painted under the label (CSS `::after` also exists for real hover; label `overflow` no longer clips tips).
