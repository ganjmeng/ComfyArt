# #825 有价确认句 · LOCAL FIXTURE

这张图是产品 `Confirm` 组件（`src/ui/Confirm.tsx`）在本地夹具里的截图，不是手写的仿界面。

| 项 | 说明 |
|---|---|
| 截图 | [`gif-confirm-local-fixture.png`](gif-confirm-local-fixture.png) |
| 实现 SHA | `246cdf0994b40f741b656b4211743c54e3b22229` |
| 价格 | mock price `0.05`（界面积分 5）。本地 stand-in，**不是**实时价格 API |
| 状态 | tldraw 资源在该环境加载失败，原子状态用同接口本地替身 `tests/js/tldrawAtom.ts` |
| 组件 | 对话框、文案、样式来自产品 `Confirm` |
| 夹具入口 | `tests/js/confirm-fixture.html` |

可见句子（有价，99 夹紧到 16，每帧 5 毫秒夹紧到 20）：

> 这次云端生成约需 5 积分，GIF 16 帧（已从 99 帧调整），每帧 20 毫秒（已从 5 毫秒调整），确定继续吗？

数字来自该次请求上已经夹紧的 `frame_count` / `frame_duration_ms`。只有请求里真有原始整数时才写「已从 N 调整」。

## 测试（与字段断言分开）

- 字段：[`tests/test_gpt_image_26_route.py`](../../../tests/test_gpt_image_26_route.py) 的 `test_confirm_fields_carry_effective_frames_from_the_request_local_mock`
- 可见句子：[`tests/test_gpt_image_26_gif.py`](../../../tests/test_gpt_image_26_gif.py) 的 `test_visible_confirm_text_uses_request_frames_local_mock`
- 句子实现：[`src/confirmText.ts`](../../../src/confirmText.ts)

当时相关 pytest（`test_gpt_image_26_route.py`、`test_gpt_image_26_gif.py`、`test_ui_credits_397.py`、`test_usd_format.py`）52 passed，`tsc --noEmit` 通过。没有供应商生成或付费请求。

静图→GIF 的参考图拒绝仍在。#825 原静图 GIF 验收没有因此完成。
