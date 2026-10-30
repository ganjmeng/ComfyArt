# #411 Skills create — audit vs 「reference」

Honest label: tip CSS harness (`tests/js/skills411` + `src/styles/{base,canvas,shell,overlays,home}.css`) — NOT full Electron / not live LLM / not WaveSpeed. Mocks only ($0). Real-call fallback stats stay on the shared EL-approved **$5** audit budget with #410 (none spent this PR).

Product rule: gaps → PM opens fix cards (#78). This PR does **not** change product UI. Jingmeng: design comparison shots before any Skills-creator redesign; Lucide stroke 2 (#326); never brand the reference product in tip files.

Related: #410 AUDIT **G2** → this card. Arti memory module depth → #430 (out of scope here).

---

## A. Inventory — our Skills-create surfaces

| Surface | Entry | Code |
|---|---|---|
| Composer + skills menu | `+` → Skill Creator / Create from this chat / Manage / list | `Composer.tsx` `menu==='skills'\|'create'` |
| SkillForm (create/edit) | Name + SKILL.md + files + images + Cancel/Save | `SkillsDialog.tsx` `SkillForm` |
| SkillsDialog manage | My skills list, New, Import folder, Use / Edit / History / Delete | `SkillsDialog.tsx` |
| Slash picker | `/` filters skills → sets `skillAtom` chip | `Composer.tsx` |
| Skill chip | Composer chip with skill name + remove | `Composer.tsx` `ca-chip` |
| Home start-from-skill | Grid of built-in + personal cards → `newProject({ skill })` | `Home.tsx` |
| Agent tool `skill` | `list` / `read` / `save` | `botLayout.ts` |
| Create-from-chat | Fixed prompt `composer.turnTheApproachCompletedIn` → agent | `Composer.tsx` `SKILL_PROMPT` |
| Proactive evolve | Background `evolveSkill` → `learned-*` skills + notify | `proactive.ts` |
| Arti skills tab | Skeleton + `arti.skillsEmpty` (no list UI yet) | `Arti.tsx` |
| Storage | `comfyart/skills/<id>/SKILL.md` + files/ + images.json + versions/ | `skills.ts` |

Harness scenes (lock): `menu-skills`, `form-empty`, `form-filled`, `dialog-list`, `dialog-list-empty`, `dialog-edit`, `slash-picker`, `skill-chip`, `home-grid`, `arti-skills`.

---

## B. Audit matrix

| 项目 | 「reference」怎么做 | 我们怎么做 | 截图 | 对齐 / 差距 |
|---|---|---|---|---|
| **入口 · Explore / 社区页** | 独立 Skills Explore（分类、Favourites、卡片墙） | **无** Explore 页；Home 仅有「从 Skill 开始」网格 | ref `skills-explore` · after `home-grid-*` | **差距** P0 — 无社区/Explore 壳 |
| **入口 · Create 下拉** | Create → Import skill / 其它入口（下拉） | Composer `+` → 技能创建器 / 从本对话创建 / 管理技能 + 列表 | ref `create-dropdown` · after `menu-skills-*` | **部分对齐** — 有创建与管理；无 Import 在此菜单（Import 在管理弹窗） |
| **触发 · 用户主动创建** | Skill Creator 会话式：chip + 思考/输出/技能就绪轨 | 弹层表单：名称 + SKILL.md + 附件/图 | ref `creator-chip` · after `form-empty-*` / `form-filled-*` | **差距** P0 — 表单 ≠ 会话式 Creator |
| **触发 · 从对话沉淀** | 对话内沉淀进 Creator / 预填 | 「从本对话创建技能」发固定 prompt 给 agent；agent `skill.save` 可写盘 | after `menu-skills-*` | **部分对齐** — 链路有，无 Creator 预填 UI（ref `creator-prefill`） |
| **触发 · 系统主动建议** | （产品侧）建议沉淀 | `proactive.evolveSkill` 周期性学技能 + 通知；Arti 开关 | — | **增强 → Ideas**（我们有、对照不一定有） |
| **创建 · 名称/描述/步骤** | Creator 产出结构化技能；编辑含描述、预览/代码 Tab | 仅 `name` + `instructions`（SKILL.md body）；无独立 description 字段 | after `form-filled-*` · `dialog-edit-*` · ref `edit-dialog` | **差距** P1 — 缺 description / 预览·代码 Tab |
| **创建 · 确认/取消** | Creator 内确认；失败态有文案 | Cancel / Save；Save 在空名或空指令时 disabled | after `form-empty-*` | **对齐**（表单路径） |
| **创建 · Edit in Chat** | 编辑弹窗可回聊天改 | 无 | ref handoff `15-edit-in-chat`（未裁进 tip；见 NOTES） | **差距** P1 |
| **导入** | Import 弹窗：ZIP/拖放区 + 说明 | `webkitdirectory` 选文件夹；无 ZIP 弹窗 | ref `import-dialog` · after `dialog-list-*` | **差距** P1 — 交互壳不同；文件夹导入功能有 |
| **原创声明 / 发布** | Originality statement → Publish 弹窗 | **无** | ref `publish-dialog` | **差距** P2（社区发布链路；无 Explore 时次要） |
| **个人列表** | Personal skills 列表 + 操作 | SkillsDialog「我的技能」：Use / Edit / History / Delete；空态文案 | ref `personal-list` · after `dialog-list-*` / `dialog-list-empty-*` | **对齐**（管理能力）；视觉密度不同 |
| **版本历史** | （若有） | `versions/*.json` + 回滚按钮 | after（history 未单独 scene；代码 `SkillsDialog` history view） | **对齐** — Ideas：对照若无版本则属我们增强 |
| **Slash 选择** | `/` 技能选择器；Personal tab | `/` 过滤全部技能（内置+个人）；无 Personal tab | ref `slash-picker` · after `slash-picker-*` | **部分对齐** — 缺 Personal/社区分 tab P2 |
| **Composer chip** | 选中技能 chip 可移除 | `ca-chip` + skill 图标 + 关闭 | after `skill-chip-*` | **对齐** |
| **主页从技能开始** | 卡片 → 新项目带技能 | `ca-skillgrid` / `ca-skillcard`；`newProject({ skill })` | after `home-grid-*` | **对齐** |
| **技能详情页** | Preview / Code / Try | **无** 独立详情 | ref handoff `11`/`12` | **差距** P1 |
| **存储完整性** | 可复用技能包 | `SKILL.md` frontmatter + files/ + images.json；`loadSkills` 合并内置 | —（单测 lock `toMarkdown`/`parseMarkdown` 行为 via inventory） | **对齐**（本地用户盘） |
| **复用 · 下轮调用** | 新对话可选并生效 | slash / 菜单 / Home / `skillAtom` → `sendToAgent(..., skill)`；agent tool `read` | after `slash-picker-*` · `skill-chip-*` | **对齐**（mock；$0；真效果进预算） |
| **复用 · 删改残留** | 删除干净 | `deleteSkill` 清目录；chip 可清 | — | **对齐**（代码路径；e2e 真盘未跑） |
| **Arti 技能 Tab** | （对照侧技能中心） | 骨架 +「还没有自进化技能」；`evolveSkill` 有写入无列表 | after `arti-skills-*` | **差距** P1 — UI 未接 learned 列表 |
| **Agent 循环内 skill 步骤** | 见 #410 | `skill` / `skill_file_read` 步骤行已审 | → #410 | **对齐**（本卡不重审） |

---

## C. 差距优先级（产品填表；PM 开卡）

| ID | 差距 | 建议 | 备注 |
|---|---|---|---|
| G1 | 无 Skills Explore / 社区 / Favourites 壳 | **P0** | 设计先出对照图再开发（Jingmeng） |
| G2 | Skill Creator 表单 ≠ 会话式 Creator（chip + 过程轨） | **P0** | 照搬布局/信息结构；保留现有表单能力作退路或合并 |
| G3 | 编辑缺 description、预览/代码 Tab、Edit in Chat | **P1** | |
| G4 | Import 无 ZIP 拖放弹窗（仅文件夹） | **P1** | 可保留文件夹能力 |
| G5 | 无技能详情页（Preview/Code/Try） | **P1** | |
| G6 | Arti 技能 Tab 骨架，learned 无列表 | **P1** | 与 proactive 写入对接 |
| G7 | Slash 无 Personal / 社区分 tab | **P2** | |
| G8 | 无 Originality / Publish | **P2** | 依赖 G1 社区模型 |
| G9 | Create-from-chat 无 Creator 预填壳 | **P1** | 与 G2 同造 |

产品：在 PR 评论或本表确认 P0/P1；有 P0/P1 由 **项目经理** 开修复卡（#78）。

---

## D. Ideas（「reference」没有、我们有的增强 — 不进本轮修复）

| Idea | 说明 |
|---|---|
| I1 | Proactive `evolveSkill` 后台自进化 + 通知 |
| I2 | 技能版本历史 + 一键回滚 |
| I3 | Agent tool `skill` list/read/save（MCP 式） |
| I4 | 内置 11 个设计向 BUILTIN_SKILLS |
| I5 | 技能附件文件可展开就地编辑 |

---

## E. 测试与预算

- Mock harness + inventory lock：`tests/test_skills_create_audit_411.py`（$0）。
- 真 WaveSpeed / 真对话沉淀效果：**未跑**；与 #410 共用 $5，跑前报 EL。
- Tip 文案禁品牌名；一律写「reference」。

---

## F. 本 PR 产出清单

- `docs/design/411/78/AUDIT.md`（本表）
- `docs/design/411/78/NOTES.md`
- `docs/design/411/78/reference/*.png`（中性文件名，出处见 NOTES）
- `docs/design/411/78/after/<scene>-{zh,en}-{light,dark}.png` + `manifest.json`
- `tests/js/skills411/{main.tsx,rolldown.config.mjs}`
- `tests/test_skills_create_audit_411.py`

Regenerate shots:

```bash
AUDIT411_SHOTS=docs/design/411/78/after \
  pytest tests/test_skills_create_audit_411.py -k shoot -q
```
