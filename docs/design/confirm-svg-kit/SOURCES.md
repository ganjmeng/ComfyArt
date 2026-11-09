# 参考来源

本目录只做设计规范。不改生成、报价或安全校验，也不把任何绘制稿称作 Lovart 截图。

仓内没有 Lovart 的版本号或构建号。能核对的是截图里的地址栏，以及文件进入本仓库的提交。下面不补造版本号。

## 实测过的 Lovart 图

| 文件 | 进入仓库的提交 | 时间 | 画面里能核对的来源 | 本轮用途 |
| --- | --- | --- | --- | --- |
| `docs/design/381/78/lovart/memory-delete-confirm-dialog-light.png` | `61f65c1ea7b9c8302d38333541e81602a51ac994` | 2026-10-27 18:56 +0800 | 浏览器标题为 Lovart。地址栏 `lovart.ai/canvas?projectId=2tpwxashe70g` | 确认框 default、取消 / 删除按钮 default |
| `docs/design/381/78/lovart/memory-deleted-toast-light.png` | 同上 | 同上 | 同上 | Toast；同一张图底部的非危险实心胶囊；遮罩下的工具条只看结构 |
| `docs/design/376/78/lovart/composer-pixel-notify-light.png` | `5cdc45719317ca80543287bb19c8900053e2c76f` | 2026-10-27 13:41 +0800 | 裁图，没有地址栏。提交说明写 Lovart CN | 通知空态面板 |
| `docs/design/376/78/lovart/composer-pixel-notify-hoverclose-light.png` | 同上 | 同上 | 同上 | 关闭按钮悬停。光标挡住右缘 |

`#381` 的说明写明：确认框、toast、删除后的参考来自画布记忆弹层，用的是同一套 Confirm 和 toast。费用句子不在这张图里。

裁图（原像素，未重绘）在 `refs/`。对照板上的数字来自这些位图，量法写在 `SPEC.md`。

## 有图、本轮没有逐像素复测

`docs/design/376/78/lovart/` 里还有深色通知：`composer-pixel-notify-dark.png`、`composer-pixel-notify-closed-dark.png`、`composer-pixel-notify-hoverclose-dark.png`。深色确认框在 `#381` 注明「CN 无深色」。本轮不从这些图报深色色值。

`docs/design/397/78/lovart/README.md` 写明：积分确认这面没有签入 CN 参考。`docs/design/397/78/NOTES.md` 把云端 `jobs.confirmCost` 标为「CN 无对照」。

## 没有 Lovart 参考、禁止当成 LEFT 的状态

- 费用确认的内容层级（积分、有效帧、每帧时长、已调整）
- 按钮的 hover、focus、disabled、loading
- SVG 正常透明、安全但画不出、危险拒绝
- 下载工具条的像素尺寸（遮罩图只能看见结构）
- 窄屏、长英文、键盘焦点环

这些在对照板上标「设计建议，非实测 Lovart」。

## BEFORE，不是 Lovart

| 文件 | 来源 | 说明 |
| --- | --- | --- |
| `before/qa-confirm-zh-adjusted.png` | 2026-11-09 上传的 QA mock | 中文，16 帧从 99 调整，20 毫秒从 5 调整 |
| `before/qa-confirm-en-adjusted.png` | 同上 | 英文长句 |
| `before/qa-confirm-zh-plain.png` | 同上 | 中文，9 帧、每帧 200 毫秒，没有「已调整」 |
| `before/826-01-path-preview.png` | `#844` `b00d0b3a38932456f0f43f05ec3262f895117be6` 的 `docs/qa/826/01-path-preview.png` | 正常 path。实现 `f36fa178ae8cc48ee2cbd867ac66629ef7191296` 的本地夹具 |
| `before/826-02-preview-failed.png` | 同提交 `02-preview-failed-download.png` | 安全但画不出，原文件仍可下载 |
| `before/826-03-rejected.png` | 同提交 `03-rejected-no-download.png` | 恶意脚本，拒绝，没有下载 |

三张确认图顶上写着 `QA RENDER · mock USD 0.07 · not a live price`。三张 SVG 图顶上写着 `LOCAL FIXTURE · mock · 不是供应商结果`。

## 文案逻辑（不改）

`69223e84763a9e02d24e87281da3e005d50a0842`（2026-11-08 23:56 UTC）里的 `src/confirmText.ts` 是当前确认句的有效参数逻辑。GIF 数字用请求上已经生效的 `frame_count` / `frame_duration_ms`。只有 `asked_frame_count` 或 `asked_frame_duration_ms` 真是数字时才写「已从 N 调整」。积分来自报价字段，经 `uiCredits`（1 积分 = $0.01，向上取整）。mock USD 0.07 因此显示为 7。这个 7 是示例，不是新核价。
