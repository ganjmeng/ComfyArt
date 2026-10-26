# #349 — Home ↔ 画布 Model / Image·Video 同源 + 非原生感扫尾（设计 AC）

**Card:** [ganjmeng/ComfyArt#349](https://github.com/ganjmeng/ComfyArt/issues/349)  
**Refs:** #311 · #316 · #318 · #320 · Ashley 2026-10-26 after #313/#314  
**Local:** `/workspace/ComfyArt-review-assets/349/`

---

## 1. 问题（before）

| 表面 | 现象 |
|---|---|
| Model 值 | Home 可能显示「Default」/短名，画布显示长 model id（如 `deepseek/…-1017`）——**不是同一数据源** |
| Model 控件 | 个别表面仍像系统原生 `<select>`；#318/#320 FieldSelect 已盖 Audio/OCR/blend/Kit/Workflows，Home/画布 composer 要扫尾 |
| Image / Video | Home 右侧控件与画布 DirectPills **交互或尺寸不一致** |
| 关闭 pill | 必须以 agent **shortLabel**（如 ComfyArt）为准；Home 与画布一致（#311 锁） |

---

## 2. 目标（after）

1. **同源：** Home 与画布读取/写入 **同一 Model 状态源**（同一 store/prefs key）。同一 Agent + 同一 mode 下，两处展示字符串必须一致（允许 ellipsis，但 `title` 完整值相同）。禁止 Home 单独「Default」兜底而画布写死长 id。
2. **控件：** Model 触发器 = 共享 **FieldSelect**（#316 token / #318 AC）——Popover + `.ca-menu`，**无**原生 select 观感（浅+深）。
3. **DirectPills：** Home 右侧 Image / Video = 画布 DirectPills **同组件或同 token**（高度、字号、间距、选中态、hit area）。
4. **Pill：** 关闭态 shortLabel 同源；**不**把 Agent/图像/视频 mode 名强写进 pill（#311）。
5. **空画布：** 仍 = empty only；不加 Lovart 空态 chrome。

---

## 3. Token / 尺寸 AC（FieldSelect · 对齐 #316/#318）

| Token | Value |
|---|---|
| Trigger height | `32px` |
| Label | `13px` / line `20px` |
| Field | `--ca-field` + 1px border + `8px` radius |
| Chevron | `16px` |
| Open trigger | bg `--ca-hover` |
| Value | ellipsis + `title` = full model id |
| Menu item | `32px` row · check `18px` |
| Menu max-width | `320px`（toolbar 场景可 `240px`） |

DirectPills（Image/Video）：与画布现网 DirectPills **逐项对齐**（高度、padding、字号、选中 fill/border、图标 16）。Home 不得另造一套 chip。

---

## 4. 数据源规则（开发必验）

- 单一 source of truth：例如 `modelPrefs` / agent model binding——Home composer 与 canvas GenBar/AgentPicker Model **读同一 getter、写同一 setter**。
- 切 Agent / 切 Image↔Video mode 后，两处 Model 同步更新（无 stale）。
- 未配置模型时：两处同一 empty/placeholder 文案（i18n），禁止一端 Default、一端长 id。

---

## 5. 视觉验收（#78）

| Shot | 要求 |
|---|---|
| Home + 画布并排 · Model 关闭态 | 浅必做；深建议 |
| Home + 画布并排 · Model 打开态 | 浅必做；菜单 = `.ca-menu` 非 OS |
| Home + 画布 · Image 选中 / Video 选中 | DirectPills 尺寸一致 |
| Audio/OCR/blend/Kit/Workflows | 回归：无原生 select 回潮（#320 已合；本卡抽检） |

**Sign 流程：** tip+#78 → 产品 PASS → 设计 COMMENT + Ashley DM（Home|canvas before→after）→ 测签 → EL merge。

---

## 6. 明确不做 / DEFER

| 项 | 口径 |
|---|---|
| Mode 菜单第三方 + 图像/视频 行为 | #311 已锁，本卡不改 IA |
| AgentPicker 整表迁 FieldSelect | 可选同 PR / 拆 tip；**不挡** Model+Pills 主验收 |
| 空画布 Lovart 引导层 | Ashley 否过 |
| #318 深色 after 全表面补拍 | 产品已定不补；本卡关键表面深色 **建议** 即可 |
| #5 tldraw | 已关 / 不管 |

---

## 7. 设计签字清单

- [ ] Home vs 画布 Model 值字符串一致（含 title）
- [ ] Model 打开态无原生 select 感（浅+深至少各一关键路径）
- [ ] Image/Video DirectPills 尺寸/交互一致
- [ ] shortLabel pill Home=画布
- [ ] 空画布无新增 chrome
