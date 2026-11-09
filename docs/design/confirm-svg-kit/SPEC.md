# 确认费用与 SVG 三态 · 组件规范（首版，WIP）

这是截止时已有的一版，不是终稿。下面列的图和句子都在仓库里；没画出来的对照不补。

## 这版没有做完

- 深色。`#376` 有深色通知图，本轮没有逐像素复测，也不报深色色值。`#381` 写明确认框没有深色 CN 参考。
- 下载工具条的像素。遮罩图只能看见结构，`boards/06` 的尺寸是建议，不是实测对照。
- 按钮 hover / focus / disabled / loading。没有 Lovart 截图。`boards/04` 里这四列是建议。
- 费用内容、SVG 三态、窄屏、长英文、焦点环。没有 Lovart 同画面。提案不能当成 LEFT。
- 关闭按钮悬停的宽高。光标挡住右缘，没有量。
- 生产组件。本目录不实现，也不改确认句、报价、安全校验。

范围只包括：确认费用弹窗、主次按钮、提示、SVG 三态（正常透明 / 安全但画不出 / 危险拒绝）、下载工具条。字体、间距、圆角和状态写在下面。不改 `confirmDesc`、报价、夹紧或安全校验，也不实现生产组件。

来源和「什么没被量过」见 [SOURCES.md](SOURCES.md)。对照板在 `boards/`。右侧绘制稿都是提案，不是 Lovart 截图。

## 设计接口

给后续实现用的形状。名字是设计接口，不是要求照抄的文件名。

```ts
type ButtonVariant = "primary" | "secondary" | "danger" | "ghost"
type ButtonSize = "md" | "sm"
type ButtonState = "default" | "hover" | "focus" | "disabled" | "loading"

interface ButtonSpec {
  variant: ButtonVariant
  size: ButtonSize
  label: string
  state?: ButtonState
}

interface DialogFact {
  id: "cost" | "frames" | "frameMs"
  label: string
  value: string
  unit: string
  mock?: boolean
}

interface DialogSpec {
  title: string
  modelId?: string
  facts: DialogFact[]
  /** 仅当 asked_* 是数字时出现，对应 gifClause */
  adjustment?: { from: string; to: string }[]
  /** 读屏与现有 confirmDesc 句子相同 */
  sentence: string
  mockNote?: string
  cancelLabel: string
  okLabel: string
  danger?: boolean
}

interface NoticeSpec {
  tone: "info" | "warning" | "danger"
  title: string
  body?: string
  placement: "toast" | "inline" | "panel"
}

interface PreviewStateSpec {
  state: "transparent" | "failed" | "rejected"
  reason: string
  /** 棋盘格只属于显示层，不写进下载文件 */
  checkerboard: boolean
  download: { label: string } | null
}
```

`DialogSpec.sentence` 必须仍等于 `69223e84` 的 `confirmDesc()`。视觉把费用、有效帧数、每帧时长拆开，是同一组字段的呈现。

## 实测值和建议值

位图按 1x 读：确认按钮高 36px，不是 2x 翻倍后的量级。圆角用左上轮廓对圆做平均绝对误差，写明拟合半径。

### 实测（可以当 Lovart 参数引用）

| 对象 | 图 | 量到的值 |
| --- | --- | --- |
| 确认框外框 | `#381` 删除确认 | 约 418×188。圆角拟合 R12（误差 0.80px，好于 R8 的 1.18 和 R16 的 1.39） |
| 确认框文字 | 同上 | 标题墨迹高 16；正文两行墨迹高 14。文字左缘距卡片左缘 24 |
| 确认框按钮 default | 同上 | 取消与删除各约 80×36。间距 8。距右、距下约 24。圆角拟合 R6 与 R7 同为 0.26px，R8 为 0.31 |
| 取消 | 同上 | 白底，边约 `#E7E7E7` |
| 删除 | 同上 | 填充主色约 `#E74D3D`（231,77,61），白字。这是危险色 |
| 非危险实心 | 同一次截图的记忆页底部胶囊 | 143×48。填充 `#2C2C2C`（44,44,44）。高度 48，半高 24，轮廓在约 24px 处达到全宽，是胶囊 |
| Toast | `#381` 删除成功 | 白底盒 117×48。圆角最佳拟合 R11（误差 0.91），R12 为 0.96。文字墨迹高 12 |
| 通知空态 | `#376` 浅色裁图 | 外框约 x8–390、y177–376，即 383×200。边 `#EDEDED`。直边在顶边之下 9px 出现，圆角量级约 9–10，没有做亚像素圆拟合 |
| 关闭悬停 | `#376` hover 裁图 | 可见底约 `#F0F0F0`。光标压住右缘，不报宽高 |

`#381` 的 `home.css` 注释写 toast「约 120×48、14px 字、16px 图标、圆角 14」。`#376` 的 `shell.css` 注释写通知圆角 12、距输入框 8px。那些是仓内旧注释。本轮位图与它们不完全相同，引用时以本轮位图为准，注释另列，不混成一次实测。

### 建议（设计建议，非实测 Lovart）

间距走 4/8。已经落在格上的实测（24、8、36、12）保持。没落在格上的圆角收成最近的建议值，并保持上表可追溯。

| 令牌 | 建议 | 依据 |
| --- | --- | --- |
| 确认框宽 | `min(440px, 100vw - 32px)` | 实测 418 装不下费用三列。窄屏再降到内容宽 312（360 屏减左右 24） |
| 确认框圆角 | 12 | 与实测拟合一致 |
| 确认框内边距 | 24 | 与文字左缘 24 一致 |
| 确认框阴影 | `0 16px 40px rgba(0,0,0,.18)` | 沿用仓内 `.ca-modal__card`。这张截图的遮罩盖住了阴影，没有单独量出阴影 |
| 遮罩 | `rgba(0,0,0,.4)` | 仓内 `--ca-backdrop`。不是从这张图取样 |
| 标题 | 16/24，字重 600 | 墨迹高 16 |
| 模型 id | 13/20，`rgba(0,0,0,.55)` 一级 | 现有 `note` 字段，次于标题 |
| 事实标签 | 12/16，更淡 | 建议 |
| 事实数字 | 22/28，字重 600 | 建议，用来压过「已调整」 |
| 次级说明 | 13/20 | 正文墨迹高 14 的同一级 |
| 按钮高 | 36（md），工具条 32（sm） | md 与实测 36 一致。sm 是建议 |
| 按钮圆角 | 8 | 实测是 6–7。收到 8，对齐 4/8。确认框按钮不要改成胶囊 |
| 按钮水平内边距 | 16 | 建议。短标签最小宽 80，与实测短按钮一致 |
| 主按钮填充 | `#2C2C2C`，字 `#FFFFFF` | 取实测非危险实心，不用删除红，也不改用仓内 `#191919` |
| 次按钮 | 白底，1px `#E7E7E7`，字近黑 | 与实测取消一致 |
| 危险按钮 | `#E74D3D` | 只给删除这类操作。费用确认不使用 |
| 焦点环 | 2px `#3B82F6`，向外 2px | 仓内 `--ca-blue`。没有 Lovart 焦点截图 |
| 字体 | Inter，中文用系统无衬线 | 仓内 `--ca-font`。对照板用文泉驿微米黑是出图字体，不是产品字体 |

深色不在本版。`#381` 写明确认框没有浅色以外的 CN 参考。

## Button

`md` 用于弹窗，`sm` 用于工具条。`ghost` 用于工具条里的图标按钮，32×32，图标 20。图标按钮的命中区仍是 32。

| 状态 | 主按钮 | 次按钮 | 危险 | 幽灵 |
| --- | --- | --- | --- | --- |
| default | `#2C2C2C` / 白字 | 白底 + `#E7E7E7` 边 | `#E74D3D` / 白字 | 透明，无边 |
| hover | `#444444` | 底 `#F5F5F5` | `#D44536` | 底 `#F4F4F4` |
| focus | 在 default 之外加焦点环。环不代替底色 | 同左 | 同左 | 同左 |
| disabled | 底 `#E8E8E8`，边 `#D6D6D6`，字 `#A8A8A8`，`cursor: default` | 同左 | 同左 | 同左 |
| loading | 保持宽度，标签换成 16px 圆环，`aria-busy`，不可再点 | 同左 | 同左 | 同左 |

default 里，取消、删除、胶囊三件有实测。hover、focus、disabled、loading 都是设计建议，非实测 Lovart。见 `boards/04-button-states.png`。

费用确认的主按钮是 primary，不是 danger。

## Dialog · 确认费用

骨架用上面的确认框实测：圆角 12、内边距 24、右下对齐的一对 36 高按钮、无关闭叉。`#381` 的产品结论是确认框只有取消和确认。Esc、点击遮罩等于取消，与现有 `Confirm` 的默认行为一致。费用确认不加叉。

内容是设计建议，非实测 Lovart。`#397` 已记录这面没有 CN 对照。

从上到下：

1. 标题：`确认费用` / `Confirm cost`
2. 模型 id，次级一行。现有 `note`
3. 三列事实：费用、有效帧数、每帧时长。数字用生效值 `frame_count`、`frame_duration_ms`
4. 「已调整」只在 `asked_frame_count` 或 `asked_frame_duration_ms` 为数字时出现，写成 `99 → 16` 这种次级行。没有原始整数时不出现，例如 9 帧、每帧 200 毫秒
5. 读屏原文，12px 次级。句子仍是 `confirmDesc`，按钮文案仍是 `继续生成` / `Generate`、`取消` / `Cancel`
6. mock 提示。示例里的 7 必须看得见 mock：QA 条是 mock USD 0.07，`uiCredits` 得到 7

窄于 380 时三列改成竖排，避免「credits」和 mock 标记挤进下一列。见 `boards/07-narrow-and-focus.png`。

对照：

- `boards/01-confirm-zh-adjusted.png`
- `boards/02-confirm-en-long.png`
- `boards/03-confirm-zh-plain.png`

## Notice

| 放置 | 用途 | 数值 |
| --- | --- | --- |
| toast | 短结果，例如删除成功 | 高 48、圆角建议 12（实测拟合 R11）、左右内边距建议 16、图标与文字间距建议 8。白底。实测盒是 117×48，宽度随文案 |
| inline | 对话框里的 mock、预览失败、拒绝 | 圆角 8，内边距 10×12。见下表颜色 |
| panel | 空态通知，沿用 `#376` 的面板，不在本版重做页面 | 外框量级 383×200，边 `#EDEDED`。圆角建议 12（实测量级 9–10） |

| 语气 | 底 | 字 | 何时 |
| --- | --- | --- | --- |
| info | `#F6F0E0` | `#5A4A2A` | mock、中性说明 |
| warning | `#F8F4EA` | `#6A4B16` | 安全但画不出，仍可下载 |
| danger | `#FDECEC` | `#9B2C2C` | 拒绝，没有下载 |

失败和拒绝不能共用同一套破图图标加同一条粉底。见 `boards/06-notice-and-toolbar.png`。

## PreviewState

没有 Lovart 的 SVG 三态图。下面整节都是设计建议，非实测 Lovart。BEFORE 是 `#826` 夹具。

| 状态 | 显示 | 下载 |
| --- | --- | --- |
| `transparent` | 预览底下铺棋盘格。棋盘格是显示层，不烘焙进文件。可以叠示例像素 | 有。下载原来的 SVG |
| `failed` | 居中「画不出」图标，暖色底。文案说明安全校验已通过，但没有可绘像素（例如只有文字） | 有。按钮写「下载原 SVG」 |
| `rejected` | 居中阻断图标，危险底。文案说明含有脚本或不允许的内容，不能预览也不能下载 | 无。不渲染下载按钮，也不放一个禁用的下载 |

`failed` 对应夹具 `text_only.svg` 这一类：完整通过安全校验，本地栅格没有像素。`rejected` 对应脚本、畸形、超限：不提供下载。两组原因不要写成同一句。

见 `boards/05-svg-three-states.png`。

## 下载工具条

`#381` 的画布截图里能看到浅色圆角工具条（快捷编辑、放大、去背景、橡皮、下载），但被记忆弹层遮罩压暗。本轮不从那张图报高度、圆角或间距。

建议，非实测 Lovart：

- 条高 44，圆角 14，白底，1px `#E7E7E7`。这两个数沿用仓内 `.ca-bar`，不是本轮实测
- 本版只规范下载位。其他工具不改
- 正常和失败：次按钮「下载原 SVG」，32 高
- 拒绝：整段下载位不出现
- 图标按钮悬停用 ghost hover。焦点用同一条焦点环

## 键盘、窄屏、长英文

都是设计建议，非实测 Lovart。

- `role="dialog"`，`aria-modal="true"`，标题连到 `aria-labelledby`
- 打开后焦点在「取消」，避免回车直接确认扣费
- Tab 顺序：取消 → 继续生成。焦点环在当前项上
- Enter 触发当前焦点按钮。Esc 等于取消
- 焦点困在对话框内
- 英文长句在卡片内换行，不裁切费用数字和帧数
- 360 宽：卡片 `100vw - 32px`，事实竖排。两个按钮并排放得下就并排，放不下就各占一行，间距 8，高度仍 36
- 禁用和 loading 不可聚焦为可确认项

## 对照板

| 文件 | 内容 |
| --- | --- |
| `boards/00-measured-references.png` | 只贴原像素和本轮量到的数 |
| `boards/01-confirm-zh-adjusted.png` | 中文已调整。左 BEFORE，右提案 |
| `boards/02-confirm-en-long.png` | 长英文 |
| `boards/03-confirm-zh-plain.png` | 无「已调整」 |
| `boards/04-button-states.png` | 按钮状态 |
| `boards/05-svg-three-states.png` | SVG 三态 |
| `boards/06-notice-and-toolbar.png` | 提示和下载条 |
| `boards/07-narrow-and-focus.png` | 窄屏和焦点 |

重新出图：`python3 docs/design/confirm-svg-kit/render_boards.py`。脚本只画提案，Lovart 和 QA 图从 `refs/`、`before/` 贴上去。
