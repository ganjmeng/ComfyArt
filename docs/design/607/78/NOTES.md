# #607 → #78 tip-pin — desktop rail default expand + collapsed hide recent

**Branch:** `feat/607-sidebar-default-expand` · **Asia/Shanghai** · Issue #607  
**Tip-pin:** absolute `raw.githubusercontent.com` URLs live in the PR body (exact tip SHA). Do not treat an older tip in chat history as current.  
**Product lock A:** follow gold — collapsed rail does **not** show 最近项目 (Ashley「收起也露」overridden by design/product A).

## Behavior

| State | Width | 最近项目 |
|------|------:|----------|
| Desktop cold start / clear local | **240px** expanded | Visible when user has projects (≤8) |
| Collapsed | **60px** | **Not rendered** (DOM gone; lovart parity) |
| Mobile ≤640 | bottom nav | Recent / collapse chrome hidden (existing) |

Persist key `comfyart.rail.collapsed`: only `'1'` = collapsed; missing/`'0'` = expanded (#607 flips #546 default-collapsed).

Copy: `最近项目` / `Recent projects` (not 最近任务). No competitor brand strings in `src/`.

## LEFT = ours (AFTER) — live dist zh-light 1280×800

Harness: `harness/shoot.py` (Playwright vs `app_url`, mock $0). Seeds 4 projects so expanded recent is visible.

| File | Shows |
|------|-------|
| `left-ours/AFTER-rail-default-expanded-zh-light.png` | Cold start expanded rail + 最近项目 list |
| `left-ours/AFTER-rail-collapsed-no-recent-zh-light.png` | Collapsed 60px icon rail; no 最近项目 block |

## @design
Please re-sign after visual check on tip (default expand + collapsed no-recent vs gold A).
