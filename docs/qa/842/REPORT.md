# #842 确认展示独立复验

签字对象只有 **`69223e84763a9e02d24e87281da3e005d50a0842`**。不用 `246cdf0994b40f741b656b4211743c54e3b22229` 签这一版。

## 漂移

| 时刻（北京时间） | 远端 `cursor/gpt-image-26-default-e355` |
|---|---|
| 2026-11-09 08:00:30，本次 fetch 之前的本地记录 | `2e7d7f21cb3b40519adb119fa712143f33aa81de` |
| 08:00:30 这次 fetch 之后 | `69223e84763a9e02d24e87281da3e005d50a0842` |
| 复验结束后 08:03:55 再读 | 仍是 `69223e84763a9e02d24e87281da3e005d50a0842` |

`246cdf0994b40f741b656b4211743c54e3b22229` 是 `69223e84` 的父提交，不是当前 head。相对 246 的差异只有文档：

- `docs/qa/825/GIF-CONFIRM-LOCAL-FIXTURE.md`
- `docs/qa/825/gif-confirm-local-fixture.png`

确认句的代码在父提交 `246cdf09`（`fix(#825): show clamped GIF frames and duration in the priced confirm`）里，并包含在 `69223e84` 中。下面的测试和截图都在 `69223e84` 的工作树上跑，不把 246 写成通过版本。

`#844` 只记录、未测：`b00d0b3a38932456f0f43f05ec3262f895117be6`。

## 结论

| 范围 | 在 `69223e84` 上 |
|---|---|
| 实时报价确认：字段链 quote / 409 / 模拟 POST | **PASS**（mock） |
| 用户可见确认句，与字段链分开断言 | **PASS**（mock 积分，真实组件渲染） |
| 正常边界不写「已调整」，越界才写 | **PASS** |
| 默认 / Auto × 文生、编辑，显式 2.5，quality 缺席或显式 | **PASS**（同一命令里的回归） |
| 静图 → GIF 的拒绝保护 | **PASS**（估价前 400，零 POST） |
| 静图 → GIF 原 AC（参考图进入编辑 GIF payload） | **未完成**。本轮没有把它写成通过 |
| 真实供应商、真实价格、付费 | **未测** |

mock 报价固定为 **0.07 USD**。确认句里的 **7 积分**来自 `uiCredits(0.07)`，不是线上价格，也不是历史表里的 0.05。

## 字段链（不看确认句）

`tests/_qa842_confirm_69223.py`，`GATE=1`，进程内假会话。99 帧 / 5ms：

- 估价 `model` = `openai/gpt-image-2.6-flare/text-to-image`，`price` = 0.07，`source` = `quote`，`gif` = 16 帧 / 20ms，`tier` 含 `16f` 与 `20ms`
- 409：`confirm` = 0.07，`model` 同上，`estimate` 为 false，`gif.frame_count` = 16，`gif.frame_duration_ms` = 20，`asked_frame_count` = 99，`asked_frame_duration_ms` = 5
- 确认前生成 POST 次数 = 0
- `confirmed` 之后的模拟 POST：同一文生 URL，body `frame_count` 16、`frame_duration_ms` 20、`output_format=gif`，没有 `quality`。价格请求不含 `frame_count`

边界：2/20、16/2000、9/200 的 409 没有 asked 字段。1 帧夹成 2 并带 `asked_frame_count=1`。9 帧 / 5ms 夹成 20ms 并只带时长的 asked。

## 确认句（不看 409 JSON）

`tests/js/qa_confirm_sentences.ts` 只调用产品函数 `confirmDesc`。0.07 的积分是 7。

- 中文实时：这次云端生成约需 7 积分，GIF 16 帧（已从 99 帧调整），每帧 20 毫秒（已从 5 毫秒调整），确定继续吗？
- 英文实时：This cloud job costs about 7 credits, GIF 16 frames (adjusted from 99), 20 ms per frame (adjusted from 5). Continue?
- 中文边界 9/200：没有「调整」
- 中文 1 帧：2 帧（已从 1 帧调整），每帧 200 毫秒，没有毫秒调整
- 估算价与无价各有自己的句子，无价句不含「积分」

## 真实组件截图

Playwright Chromium 打开 Vite 上的产品 `Confirm`（`src/ui/Confirm.tsx`），句子由 `confirmDesc` 填进 `confirmAtom`。不是重画，也不是提交里那张 `docs/qa/825/gif-confirm-local-fixture.png`。页面顶上的 “QA RENDER · mock USD 0.07” 只是夹具标签。

DOM 文本与上面六句一致后才截图。文件：

- `docs/qa/842/shots/zh-adjusted.png`
- `docs/qa/842/shots/en-adjusted.png`
- `docs/qa/842/shots/zh-edge.png`
- `docs/qa/842/shots/zh-low.png`
- `docs/qa/842/shots/zh-estimate.png`
- `docs/qa/842/shots/zh-unpriced.png`

## 命令

工作树 `/tmp/qa-69223/ComfyArt`，HEAD `69223e84763a9e02d24e87281da3e005d50a0842`。

```text
env -u WAVESPEED_API_KEY -u KIE_API_KEY GATE=1 \
  python3 -m pytest --import-mode=prepend -q --tb=line \
  tests/_qa842_confirm_69223.py \
  tests/test_gpt_image_26_route.py \
  tests/test_gpt_image_26_gif.py \
  tests/test_flare_default.py \
  tests/test_linkedin_size_707.py
```

**67 passed，0 failed，0 skipped，exit 0，1.79s。** 其中本轮字段链探针 9，其余 58 是上述相关文件。

```text
ENTRY=qa_confirm_sentences.ts OUT=/tmp/qa69223-sentences.mjs \
  ./node_modules/.bin/rolldown -c tests/js/rolldown.config.mjs
node /tmp/qa69223-sentences.mjs
```

exit 0。`npx tsc --noEmit` exit 0。

## 剩余风险

- 没有打真实 WaveSpeed 报价或生成。0.07 与 7 积分都是 mock。
- 静图参考 GIF 的原 AC 仍未实现。本 SHA 继续在估价前拒绝。
- 确认框截图是夹具页面挂上产品 `Confirm`，不是在完整画布里点发送。按钮文案来自同一套 `t('jobs.confirmOk')`。
- 集成与 `#844` 不在这次范围。
