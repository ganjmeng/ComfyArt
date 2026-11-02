# #498 L/R notes — Lovart left-bottom personal vs ComfyArt main

**Date:** 2026-11-02 Asia/Shanghai · from OLD shots only (no browser)  
**Gold:** `495-498/lovart/` P*/U* (+ design issue comment 18:39)  
**Ours:** `495-498/main-733d3dc/account-menu-{zh,en,dark-zh}.png` + sbs/498-*  
**M279:** reuse tokens; **label location** (home left-bottom ≠ canvas top-right ≠ a12 project sidebar)

---

## 1. Gold structure (Lovart home left-bottom)

### 1.1 Entry (resting / hover) — P1 / P3

- Pinned **bottom of left rail**, below「最近项目」.
- Row: **circular avatar** | name (masked in shots) | **⚡ credit count** (evidence shows **30**).
- Collapsed rail: avatar/credits compact (S2); exact collapsed personal chrome not separately cropped.

### 1.2 Open menu — U1 (zh) / U5 (en); design measure ~**150** wide, opens **upward**

**Header block**

1. Avatar + display name + email  
2. Plan line: **Free** + **⚡30 ›** (credits row is clickable → account/usage)  
3. Black CTA **升级** / **Upgrade**

**Body items (top → bottom)** — design comment + U1/U5 aligned:

| # | zh (U1) | en (U5) | Submenu? |
|---|---|---|---|
| 1 | 创建团队 | Create a Team | — |
| 2 | 账户管理 | Manage Account | → account modal |
| 3 | 使用指南 | User Guide | — |
| 4 | 联系我们 | Contact Us | — |
| 5 | 最新动态 | What's New | — |
| 6 | 安装插件 / Install Lovart Clipper | Install Lovart Clipper | — |
| 7 | 语言 (shows current, e.g. 简体中文) | Language (English) | › **语言** |
| 8 | 主题 (shows 浅色) | Theme (Light) | › **主题** |
| 9 | Lovart Agent | Lovart Agent | › (product: out) |
| 10 | 更多信息 | More Information | › |
| 11 | 退出登录 | Log Out | — |

**Theme submenu (U2):** 浅色 ✓ / 深色 / 跟随系统 — flyout to the **right** of trigger in left-bottom shots.  
**Language submenu (U2b):** English / 한국어 / 日本語 / 简体中文 ✓ / 繁體中文.

> Note: M279 `a12-avatar-menu` left-bottom list differs (canvas sidebar): 基础版 + 水印 + 星流迁移 + 复制账户 ID; **no** 语言/使用指南/最新动态. Prefer **U1/U5 + issue design comment** as #498 gold.

### 1.3 Credits / account modal — U3 / U4

- Opens from credits row (and/or 账户管理). Design: ~**770×480**「账户管理」.
- Left nav: **个人主页** / **订阅** / **账单**.
- **订阅** (U3): plan Free + 升级; balance ⚡30; table「用量」cols **明细 | 全部▾ (全部/已消耗/已获取) | 日期 | 积分消耗**; pagination mentioned on-issue.
- **个人主页** (U4): 账户信息 (avatar change, username, email) + 设备管理 — ComfyArt has no login → **hide** per product.

### 1.4 M279 token reuse (same chrome family; different chrome location)

From `cards/top-right.md` + `sidebar-recent.md` (apply cautiously):

- Menu surface: bg-float, radius **12**, item min-h **32**, hover **rgba(0,0,0,0.06)**, open **100ms** / close **75ms**.
- Theme submenu: 浅色/深色/跟随系统 + ✓; dark menu text #FFF (`a3-avatar-menu-dark`).
- Account modal dark: mask ~**rgba(0,0,0,0.6)**; shell bg-float **#1F1F1F** (`gap4-dark-account-modal`).
- **Do not** copy M279 modal size **1160×720** over #498 home measure **~770×480** without re-measure.
- **Do not** copy top-right item order (升级/创建团队/账户管理/对话区位置/…) into left-bottom ComfyArt.

---

## 2. ComfyArt main today (733d3dc)

| Aspect | Evidence | Gap vs gold |
|---|---|---|
| Entry | Lucide **gear** at left-bottom; no avatar, no plan, no credits on rail | Product: keep settings icon +「设置」label; show **$balance** when key+balance OK (not ⚡ credits) |
| Menu chrome | Flat sections with **inline** 语言/主题 options (checks), not › flyouts | Align Lovart: compact ~150w upward popover; **语言 › / 主题 ›** submenus |
| Menu items | 语言 · 主题 · WaveSpeed 密钥 · 卸载模型 · 清缓存 · 使用指南; WaveSpeed 任务历史 was **sidebar external** (design 19:19) | Must **keep all** main items; add **$x.xx ›** balance row first; move 任务历史 into menu per product AC |
| Credits page | **None** (sbs/498-credits-zh:「main 无积分页」); spend only in cloud confirm | Need **Usage** modal + real ledger |
| Dark | main has `account-menu-dark-zh` | Lovart left-bottom dark **missing** in gold folder |
| Auth | No login | Hide avatar/name/email/plan/logout/upgrade/team/… |

---

## 3. ComfyArt gaps (top → product-relevant)

1. **No usage/credits ledger UI** — biggest functional gap; only cloud confirm today.  
2. **Entry IA** — gear-only vs Lovart avatar+⚡; product locks settings+optional `$balance` (not avatar).  
3. **Menu IA** — inline lang/theme vs Lovart › submenus; missing leading balance row; 任务历史 not yet in menu.  
4. **Modal chrome** — no ~770×480 Usage shell; Lovart left-nav 个人主页/订阅/账单 all **hidden** for us → single-pane「用量」.  
5. **Visual tokens** — radius/shadow/item height not yet matched to Lovart/M279 float menu.  
6. **zh/en × light done for main menu**; Lovart gold dark left-bottom absent.  
7. **Hidden Lovart-only entries** already product-locked (must not render as dead buttons).

---

## 4. True gaps needing live re-eye

Ashley rule: only if old shots insufficient.

| Gap | Why old shots insufficient | Blocking? |
|---|---|---|
| **Lovart left-bottom DARK** personal menu + theme/language submenu | `495-498/lovart/` is light-only; M279 dark is **top-right** / a12 rail, not home personal menu | **Yes if** design requires pixel AC for dark left-bottom; else provisional reuse `a3-avatar-menu-dark` + `gap4-dark-*` + main dark |
| **EN credits/usage modal** | Only `U3` zh | Soft — layout same; copy from product AC |
| **Ledger empty state + pagination chrome** | U3 has rows; M279 explicitly「空态不在范围」 | Soft — product already wrote empty copy「还没有花费记录」 |
| **More-info / Agent submenu contents** | Not expanded in U* | **No** — product **hides** these |
| **Collapsed-rail personal entry detail** | S2 exists but not focused crop | Soft — product: collapsed = icon only |
| **Exact px width left-bottom menu** | Design said ~150; a12 says 225×439 | Soft — use design ~150 unless live remeasure |

**Live re-eye needed?** **YES — narrow:** Lovart **dark left-bottom** personal menu (+ theme submenu). Everything else for TARGETS/AC can ship from old evidence + on-issue product lock. **Do not** full re-scrape Lovart personal light/EN (already have U1–U5).

---

## 5. Suggested L/R shot list for design tip (when posting)

Pin from existing (no new Lovart light scrape):

1. U1 + main account-menu-zh → menu IA  
2. U5 + main account-menu-en → EN  
3. U2 + U2b → submenu pattern  
4. U3 + sbs/498-credits / main placeholder → Usage  
5. main account-menu-dark-zh (ours) + **(optional live)** Lovart dark left-bottom  

Tag each M279 embed as `location: top-right canvas` or `a12 left-rail`.
