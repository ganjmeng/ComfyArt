# DRAFT issue comment for #498 — DO NOT POST (design tip)

> Parent/design: review, then post manually. Local images need **pin to review-assets** first; listed below.

---

📌 设计 L/R 预备（2026-11-02 Asia/Shanghai）— **#498 左下角个人区**  
Ashley rule：只盘旧图，**未**盲开 Lovart 重抓。金标：`495-498/lovart/`（issue 上 18:39 实测同源）。对照 main：`main-733d3dc`。M279 仅借 token，并标明 **画布顶栏右 ≠ 首页左下**。

### Gold 菜单顺序（Lovart 左下，U1/U5）
头像+名+邮 → Free ⚡N › → **升级** → 创建团队 → 账户管理 → 使用指南 → 联系我们 → 最新动态 → 安装插件 → **语言 ›** → **主题 ›**（浅/深/跟随）→ Lovart Agent › → 更多信息 › → 退出登录。  
积分行打开「账户管理」~770×480：左栏 个人主页/订阅/账单；用量表 明细 | 全部▾ | 日期 | 积分消耗（U3）。

### 我们（产品已裁）保留
入口：设置图标 +「设置」；有 key 且余额可读时跟 `$x.xx`（非头像）。  
菜单向上 ~150 宽：**$x.xx ›** → 语言 › → 主题 › → WaveSpeed key → 卸载模型 → 清缓存 → WaveSpeed 任务历史 ↗ → 使用指南。  
隐藏：升级/团队/账户管理/主页/订阅/账单/联系我们/最新动态/插件/Agent/更多/退出/头像头。  
用量弹框：无左栏；列 明细|日期|花费（按提交报价）；真数据（余额 `/balance`，明细本地 `agent_usage_events`）；空态「还没有花费记录」。

### Top gaps（相对 main-733d3dc）
1. 无用量/积分明细页（sbs：main 无积分页）  
2. 入口无余额；仅齿轮  
3. 语言/主题仍是内联列表，不是 › 子菜单  
4. 任务历史仍在侧栏外链，未进菜单  
5. 浮层视觉 token（圆角/阴影/行高）未对齐 Lovart/M279

### 真缺口（才需要 live re-eye）
- **需要（窄）：** Lovart **深色左下**个人菜单 + 主题子菜单（旧 `lovart/` 全是浅色；M279 深色是顶栏右/a12）。  
- 不需要重抓：浅色/EN 菜单（U1/U5）、主题/语言子菜单（U2/U2b）、用量浅色（U3）。

### 建议 pin 后再贴图
| 用途 | 路径 |
|---|---|
| 菜单 L | `…/495-498/lovart/U1-account-menu.png` |
| 菜单 EN | `…/U5-account-menu-en.png` |
| 主题 › | `…/U2-theme-submenu.png` |
| 语言 › | `…/U2b-language-submenu.png` |
| 用量 | `…/U3-credits.png` |
| 入口 | `…/P1-personal.png`（+P3） |
| 我们菜单 | `…/main-733d3dc/account-menu-{zh,en,dark-zh}.png` |
| 已有 SBS | `…/sbs/498-account-zh.png` · `498-account-en.png` · `498-credits-zh.png` |
| Token 参考（标 location） | `lovart-m279/a12-avatar-menu.png`（左下但画布侧栏）· `a3-avatar-menu-*.png` / `gap4-dark-account-modal.png`（**顶栏右**） |

完整盘点 / L/R / TARGETS 草稿：  
`/workspace/ComfyArt-review-assets/498/prep/{INVENTORY,LR-NOTES,TARGETS-draft,ISSUE-COMMENT-draft}.md`  
→ 请产品按 TARGETS-draft 锁 AC（多数已在卡上）；设计补深色左下对照后再 tip 全栈。

