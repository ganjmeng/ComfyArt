# #498 — Left-bottom personal center inventory (OLD evidence only)

**Date:** 2026-11-02 Asia/Shanghai · inventory only (Ashley rule: no blind Lovart re-scrape)  
**Issue:** [ganjmeng/ComfyArt#498](https://github.com/ganjmeng/ComfyArt/issues/498) OPEN — `[P1] 左下角个人中心对齐 Lovart：账户、积分明细等`  
**Scope:** left-bottom avatar/settings entry + menu, usage/credits modal, settings/personal pages; zh/en × light/dark; browse only; real data only.  
**Prior design/product on issue:** design L/R comment (18:39), product hide list, product AC #498, WaveSpeed ledger data rulings — **AC largely already drafted on-issue**; this prep consolidates evidence for design TARGETS tip.

---

## Counts

| Bucket | PNG count | Role for #498 |
|---|---:|---|
| `495-498/lovart/` | **18** | **Primary gold** (home left-bottom personal) |
| `495-498/main-*` | **42** | ComfyArt main baselines (several SHAs) |
| `495-498/sbs/` | **10** | Side-by-side (3 are #498-specific) |
| `495-498/v2–v5/` | **17** | Later SBS for #495–497 (context only) |
| `lovart-m279/` relevant | **~20** listed below | **Reuse tokens/structure**; label location (top-right canvas vs left-bottom) |
| **#498-critical subset** (P*/U* + main account + sbs/498* + m279 avatar/credits) | **~28** | Still-valid for L/R |

---

## 1. Primary gold — ` /workspace/ra-623-new6-hover-v1/495-498/lovart/` (LEFT-BOTTOM home)

Cited on-issue as review-assets `21bbce8` 495-498/lovart/ (browse-only; credits stayed 30; email/IP masked).

| Path | Shows | Location | Locale / theme | Still-valid? |
|---|---|---|---|---|
| `P1-personal.png` | Left-rail resting personal row: avatar + ⚡30 under Recent | **left-bottom** | zh / light | **Yes** — entry resting |
| `P2-personal-click.png` | Personal row on skills detail context (avatar + ⚡30) | **left-bottom** | zh / light | **Yes** — entry on non-home |
| `P3-personal-hover.png` | Personal row hover/rest on Skills Personal tab | **left-bottom** | zh / light | **Yes** — entry hover |
| `P4-bookmark.png` | Bookmark-related (not core #498 IA) | sidebar | zh / light | Contextual only |
| `U1-account-menu.png` | Open personal menu upward from left-bottom (full item list + Upgrade) | **left-bottom menu** | zh / light | **Yes — gold menu** |
| `U2-theme-submenu.png` | Theme flyout: 浅色 ✓ / 深色 / 跟随系统 | **left-bottom** | zh / light | **Yes** |
| `U2b-language-submenu.png` | Language flyout: EN / KO / JA / 简中 ✓ / 繁中 | **left-bottom** | zh / light | **Yes** (ComfyArt keeps 中文/English only) |
| `U3-credits.png` |「账户管理」modal ~770×480; left nav 个人主页/订阅/账单; 订阅 usage table 明细\|全部▾\|日期\|积分消耗 | **modal from left-bottom credits** | zh / light | **Yes — gold ledger chrome** |
| `U4-settings.png` | Same modal, 个人主页 selected (账户信息 / 设备管理) | **modal** | zh / light | **Yes** (ComfyArt hides profile — reference only) |
| `U5-account-menu-en.png` | EN mirror of personal menu (Create a Team … Log Out) | **left-bottom menu** | **en** / light | **Yes** |
| `S1-sidebar-zh.png` | Full sidebar zh (entry context) | left rail | zh / light | Yes — rail context |
| `S2-sidebar-collapsed.png` | Collapsed rail | left rail | zh / light | Yes — collapsed entry |
| `S3-recent-hover.png` | Recent hover (#495) | left rail | zh / light | Context (#495) |
| `S4-sidebar-en.png` | Sidebar EN | left rail | en / light | Context |
| `F1-home-top.png` / `F6-home-en.png` | Home chrome | page | zh·en / light | Context (#496) |
| `M1-assets-zh.png` / `M2-assets-en.png` | Assets (#497) | page | zh·en / light | Context |

**True gap in this folder:** **no Lovart left-bottom dark** personal menu / theme submenu / credits modal. No EN credits modal. No empty ledger state.

---

## 2. ComfyArt main baselines — `495-498/main-*`

### 2.1 `main-733d3dc/` — **#498 baseline cited on-issue** (e2e fake backend; no spend)

| Path | Shows | Location | Locale / theme | Still-valid? |
|---|---|---|---|---|
| `account-menu-zh.png` | Gear entry → settings popover: 语言(中文✓/EN) · 主题(浅/深/跟随) · WaveSpeed 密钥 · 卸载模型 · 清缓存 · 使用指南 | **left-bottom** | zh / light | **Yes — current IA** |
| `account-menu-en.png` | Same EN | **left-bottom** | en / light | **Yes** |
| `account-menu-dark-zh.png` | Same dark | **left-bottom** | zh / **dark** | **Yes** (main has dark; Lovart left-bottom dark missing) |
| `home-*.png` / `projects-*` / `skills-*` / `recent-hover-*` | Home/skills/recent | page/rail | mixed | Context; shows **gear only**, no avatar/credits |

On-issue design note (19:19): no avatar/account; gear settings; WaveSpeed 任务历史 as sidebar external link; no dedicated credits page (spend only in cloud confirm dialog).

### 2.2 Other main SHAs (inventory; not primary #498 delta)

| Folder | PNG # | #498 relevance |
|---|---:|---|
| `main-397f219/` | 5 | Older home/recent — no account menu |
| `main-66dbb4e/` | 10 | Home/libpanel/projects — no account menu |
| `main-aba9d3e/` | 5 | Home theme variants |
| `main-ecdde11/` | 6 | Home + `sidebar-zh/en` — rail before account work |

---

## 3. Side-by-side — `495-498/sbs/`

| Path | Shows | Still-valid? |
|---|---|---|
| `498-account-zh.png` | L Lovart left-bottom menu vs R main-733d3dc settings | **Yes** — core L/R |
| `498-account-en.png` | EN L/R account | **Yes** |
| `498-credits-zh.png` | L Lovart usage modal vs R placeholder「main 无积分页」 | **Yes** — ledger gap |
| `494–497-*.png` | Other cards | Not #498 primary |

`v2/`–`v5/` = later #495–497 SBS only (17 PNGs) — do not treat as #498 personal gold.

---

## 4. M279 reuse — `/workspace/lovart-m279/` (**location labels required**)

### 4.1 Left-rail / left-bottom (closest structural cousin)

| Path | Shows | Location | Still-valid for #498? |
|---|---|---|---|
| `a12-avatar-menu.png` | Cropped left-bottom avatar menu (基础版 ⚡424 › / 升级 / … / 浅色 › / …) | **left-bottom** (canvas project sidebar) | **Reuse IA/tokens**; item list **≠** home U1 (no 语言/使用指南/最新动态; has 水印/星流/复制 ID) |
| `a12-sidebar-default.png` | Rail + bottom avatar row | left rail | Entry sizing tokens |
| `a12-sidebar-dark.png` | Dark rail | left rail dark | Dark **rail** tokens (not full home personal menu) |
| `a12-sidebar-recent-projects.png` | Recent + bottom | left rail | Context |
| `cards/sidebar-recent.md` | Measured AC incl. left-bottom menu **225×439**; PoloX keep list | notes | **Reuse measurements**; PoloX keep list differs from ComfyArt product AC |

### 4.2 Canvas **TOP-RIGHT** chrome (NOT #498 entry — reuse chrome tokens only)

| Path | Shows | Location | Reuse? |
|---|---|---|---|
| `cards/top-right.md` | Full measured AC for ⚡ / avatar menu / share / account modal | **top-right** | Menu item chrome, hover rgba(0,0,0,0.06), open 100ms/close 75ms, theme submenu left flyout, dark modal tokens |
| `a3-avatar-menu-light.png` / `a3-avatar-menu-dark.png` | Top-right avatar menus | top-right | Style only |
| `a3-credits-account-modal.png` | Account modal shell | top-right open path | Modal shell (~1160×720 in M279 notes vs ~770×480 in #498 design comment — **prefer #498 home measure**) |
| `a3-account-subscription-panel.png` | Subscription + ledger rows | top-right path | Ledger column pattern |
| `gap2-c-avatar-menu.png` / `gap2-c-avatar-hover.png` / `gap2-c-credits-hover.png` | Area C crops | top-right | Tokens |
| `gap3-tr-avatar-menu.png` / `gap3-tr-account-modal.png` / `gap3-tr-credits-hover.png` / `gap3-tr-subscription-modal.png` | Round-3 top-right | top-right | Tokens |
| `gap4-dark-account-modal.png` / `gap4-dark-credits-*` / `gap4-dark-share.png` / `gap4-dark-toast.png` | Dark top-right | top-right dark | **Dark modal/credits tokens** until left-bottom dark re-eye |

---

## 5. Issue comments already locking design/product (do not re-invent)

| When (UTC+8) | Who | Content |
|---|---|---|
| 18:39 | 设计 | Measured left-bottom menu ~150w; item order; credits modal ~770×480; ledger cols |
| 18:40 | EL | Hide vs keep = product; no dead buttons |
| — | 产品 | Hide upgrade/team/plugin/what's new/…; no filter ▾; hide 订阅/账单 tabs |
| 19:19 | 设计 | main-733d3dc gear menu inventory |
| — | 产品 | Full #498 AC (settings entry + $balance; menu order; Usage modal; mutations) |
| — | 全栈+产品 | WaveSpeed no per-row cost; local `agent_usage_events`; label「按提交报价」; canvas `/wavespeed/run` must log |

---

## 6. Still-valid summary / do-not-rescrape

**Enough for L/R + TARGETS draft without live Lovart:** U1/U2/U2b/U3/U5 + P1–P3 + main-733d3dc account-* + sbs/498-* + product AC comments.

**Only flag live re-eye if design needs pixel-locked dark left-bottom or empty ledger** (see `LR-NOTES.md` §True gaps).
