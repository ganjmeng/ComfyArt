# #498 TARGETS-draft — for product to lock AC

**Status:** DRAFT for product lock (do **not** invent items beyond evidence + on-issue rulings).  
**Date:** 2026-11-02 Asia/Shanghai  
**Gold evidence:** `495-498/lovart/` U1/U2/U2b/U3/U5 + P1–P3; design comment 18:39.  
**Ours baseline:** `main-733d3dc` SettingsMenu / account-menu-*.  
**Prior product AC on issue:** already detailed — this draft consolidates into checklist form. Product may tip as-is or amend.

---

## 0. Non-goals / hard rules (already EL+产品)

- Browse-only design capture; **no credit spend** in design work.  
- **No fake / demo / estimated** balance or ledger rows.  
- **No dead buttons**: Lovart-only entries we lack → **hide** (no「即将推出」).  
- Join **existing** `SettingsMenu.tsx` / Jotai / i18n / theme — no parallel account stack (Jingmeng).  
- Chat UI still **does not** show per-call spend.  
- Lovart PNGs / GT Standard / scraped fixtures **not** into app repo (#494).

---

## 1. Left-bottom entry (ComfyArt keep list)

| Item | TARGET | Source |
|---|---|---|
| Control | Lucide **settings** + label「设置」/ `Settings` | Product AC; main today |
| Balance | If WaveSpeed key configured **and** `GET /api/v3/balance` OK → show real **`$x.xx`** (same source as TopBar); else omit | Product AC |
| Collapsed rail | **Icon only** | Product AC |
| Avatar / name / email / plan badge | **Do not show** (no auth) | Product AC |
| Lovart「升级」on entry card | **Hide** | Product hide list |

---

## 2. Menu — PoloX/ComfyArt **keeps** (order locked by product)

Popup: upward from left-bottom, ~**150** wide, Lovart float styling (reuse M279 menu tokens; home width from #498 design measure).

1. **`$x.xx ›`** — opens Usage modal (only when balance known; behavior per product)  
2. **语言 ›** — submenu: 中文 / English (current ✓) — *ComfyArt locales only; do not add KO/JA/繁 from U2b*  
3. **主题 ›** — submenu: 浅色 / 深色 / 跟随系统 (current ✓) — gold U2  
4. **WaveSpeed key** — existing behavior  
5. **卸载模型** — existing  
6. **清缓存** — existing  
7. **WaveSpeed 任务历史 ↗** — move from sidebar external; existing link behavior  
8. **使用指南** — existing (main has it → **keep**, even though early hide note said「no link → hide」; later AC keeps it)

**Lang/theme presentation:** change from inline section lists → Lovart-style **› flyout** (U2/U2b).

---

## 3. Menu — **hide** (Lovart gold has them; we do not)

From U1/U5 + product hide list — **do not render**:

升级/Upgrade · 创建团队/Create a Team · 账户管理/Manage Account · 个人主页 · 订阅 · 账单 · 联系我们 · 最新动态/What's New · 安装插件/Clipper · Lovart Agent · 更多信息 · 退出登录 · (any avatar header block)

**Mutation:** any hidden item appears; or any no-op entry.

---

## 4. Pages / surfaces in vs out

| Surface | In/out | Notes |
|---|---|---|
| Left-bottom settings menu | **IN** | Restyle + reorder on `SettingsMenu.tsx` |
| Usage modal「用量」/ `Usage` | **IN** | ~770×480; **no** left nav |
| Lovart 个人主页 / 设备管理 | **OUT** | U4 reference only |
| Lovart 订阅 plan / 升级 CTA | **OUT** | |
| Lovart 账单 tab | **OUT** | |
| Ledger filter「全部/已消耗/已获取」▾ | **OUT** | No「已获取」data |
| Top-right canvas avatar menu (M279) | **OUT of #498** | Different product surface |

---

## 5. Usage modal + credit ledger (real data)

| Spec | TARGET | Source |
|---|---|---|
| Title |「用量」/ `Usage` | Product AC |
| Top | Live balance from `/api/v3/balance` | 全栈+产品 |
| Columns | 明细 (task/model) \| 日期 \| **花费（按提交报价）** / `Cost (quoted at submit)` | Product data ruling |
| Footnote |「以 WaveSpeed 余额为准」 | Product |
| Page size | 10 / page, time desc | Product AC |
| Filter ▾ | **None** | Product |
| Empty |「还没有花费记录」 | Product |
| Row amount | Local `agent_usage_events.amount_usd` quoted-at-submit; **skip** fail/cancel/0/missing; **no backfill** | Product |
| Canvas tools | Log on `/comfyart/wavespeed/run` success — **in #498** (first PR per EL) | Product+PM |
| WaveSpeed predictions history | Optional context only; **no cost field** — never invent | 全栈 |

**Mutation:** fake/estimate amounts; fail rows shown; column title drops「按提交报价」; canvas tool spend missing; chat shows per-call cost.

---

## 6. Theme / i18n matrix (design proof)

Screenshot matrix required before fullstack tip (EL rule):

- Menu: zh×light, zh×dark, en×light (en×dark if feasible)  
- Usage: zh×light at minimum; dark + en when implemented  
- Submenus: theme + language open states (U2/U2b pattern)

---

## 7. PR split (EL)

1. **First:** `/comfyart/wavespeed/run` usage event logging (so ledger has real rows).  
2. Then: menu restyle + balance row.  
3. Then: Usage modal + ledger read UI.  
(Exact split: fullstack proposes, EL locks.)

---

## 8. Open for product (only if amending prior AC)

- Confirm collapsed entry: icon-only vs icon+$ (prior AC = icon-only).  
- Confirm whether balance row appears when balance fetch fails (prior = omit).  
- Whether design must live-capture **dark left-bottom Lovart** before AC tip, or provisional dark tokens from M279 top-right are enough.

**No new menu items proposed.**
