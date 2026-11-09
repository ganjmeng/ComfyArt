# UI 控件首批 · WIP 交接

这是中断快照，不是设计验收，也不是功能完成。价格 `0.05` / 5 积分是本地 stand-in，不是实时报价。没有付费请求、没有部署、没有合并。

起点：`69223e84763a9e02d24e87281da3e005d50a0842`（#842 头）。本分支 `cursor/ui-lovart-controls-862c`。没有改 #842 / #844 原分支，没有合入 #848 `eca055b522d2f10ca2b3993f9af1f75f338ff8bc`。那一笔不是本分支的 Lovart 工作。

## 已写入的代码

- `src/ui/Button.tsx`：`Button` / `IconButton`。文案必须可见，图标不能单独替换文案。沿用 `ca-panel__primary` / `ca-panel__secondary` / `ca-panel__danger`。
- `src/ui/ConfirmActions.tsx`：取消在前，主按钮或危险按钮在后。打开时焦点在取消。
- `src/ui/firstAction.ts`：第一次操作生效，随后的点击不再执行。
- `src/styles/controls.css`：只作用于 `.ca-btn` 和 `.ca-confirm`。用现有 `--ca-strong`、`--ca-float`、`--ca-text-2`、`--ca-error-text`、`--ca-error-bg`、`--ca-field`、`--ca-muted`。
- `src/ui/Confirm.tsx`：产品确认框改用上述按钮。句子仍由调用方传入，本文件不调用 `confirmDesc`，不重算积分或 GIF 帧。
- `src/ui/MemoryChooser.tsx`：第二个产品入口，同一套操作区。忘记/纠正逻辑仍是原来的 `forget` / `correct`。
- `src/ui/Modal.tsx`：仅 `dialog` 时增加 `role="dialog"`。其他弹窗默认不变。
- `src/main.tsx`：引入 `controls.css`。

确认框文案仍是原来的句子。夹具里可见：中文「这次云端生成约需 5 积分，GIF 16 帧（已从 99 帧调整），每帧 20 毫秒（已从 5 毫秒调整）」；英文 “5 credits, GIF 16 frames (adjusted from 99), 20 ms per frame (adjusted from 5)”。

## 已跑过的检查

- `npx tsc --noEmit`：通过（本环境，提交前）。
- `python3 tests/test_ui_controls_batch.py`：通过。`firstGate` 第一次 true、第二次 false。确认框自测：确定双击 `runs=1`；取消双击 `cancels=1`；Escape 两次 `cancels=1` 且 `runs=0`；焦点在 `confirm-cancel`。确定场景的 DOM 含上述 GIF 句子和「5 积分」。
- 仓库完整 pytest 没有在本环境跑（收集测试会导入 ComfyUI/`sqlalchemy`，这里没有装齐）。

## 截图（产品 Confirm 夹具，不是手写 HTML）

同视口对照，夹具页 `tests/js/confirm-fixture.html`。mock 价已写在页顶。

| 文件 | 状态 |
| --- | --- |
| `shots/before/confirm-zh-1280.png` | 改样式前，1280×800，中文 |
| `shots/before/confirm-zh-390.png` | 改样式前，390×780，中文 |
| `shots/after/confirm-zh-1280.png` | 改样式后，1280×800，中文。已看过：句子还在，按钮变高，取消有描边，继续生成为深色底 |
| `shots/after/confirm-zh-390.png` | 改样式后窄屏。文件在，本轮没有再打开核对 |
| `shots/after/confirm-en-1280.png` | 英文 1280。已看过，句子与 Cancel / Generate 可见 |
| `shots/after/confirm-en-390.png` | 英文窄屏。文件在，本轮没有再打开核对 |
| `shots/after/confirm-zh-hover.png` | `?force=hover`。已打开：和静止帧几乎看不出差别，不能当成 hover 已验收 |
| `shots/after/confirm-zh-focus.png` | `?force=focus`。文件在，本轮没有再打开核对 |
| `shots/after/confirm-zh-danger.png` | `?scene=danger`，产品 Confirm 的危险样式。文件在，本轮没有再打开核对 |

## 未完成（不要当成做完）

- 没有 Lovart 左 / ComfyArt 右对照图。本轮没有截到可引用的 lovart.ai 实页。仓库里旧文件 `docs/design/381/78/lovart/memory-delete-confirm-dialog-light.png` 是既有素材，浏览器标题栏能看到 lovart.ai，本快照没有把它裁进新对照，也不把它算成这次新拍的参考。
- 没有设计规范对齐，没有宣布视觉通过。
- 记忆选择器（第二入口）的界面截图没拍完。代码已接上，夹具支持 `?scene=memory`，截图不在本提交。
- 按钮 loading / disabled 状态页（`?scene=states`）没拍。
- SVG 预览三态没有做组件，没有接到产品。不要从本分支复制 #844 的安全逻辑。
- 设置页 / 供应商设置没有改。`KeySettings.tsx`、`ImageToolbar.tsx`、`GenPanel.tsx`、`GenSettings.tsx` 不在本 diff。
- 全站按钮没有替换。
- 深色主题没有截图。对比度没有用测量工具复核，只是按现有 token 写了颜色。
- #848 集成候选不要覆盖本分支，本分支也不要覆盖它。

## 后续若继续

先看确认框和记忆选择器。SVG 与设置页仍分开。共享样式只在 `.ca-btn` / `.ca-confirm`，避免改到 #844 正在动的 `ImageToolbar.tsx`。

## 2026-11-09 local continuation: narrow viewport contract

- Based on #850 `0484720396fdecbe1028733c5a4cc35d1e5aa822`; not an integration of #845 or #848.
- Applies the group design decision only below a 380px viewport: 360px viewport produces a border-box card width of 328px, 16px outer margins, 24px horizontal inner padding; actual borders reduce usable content width. Fact rows stack vertically with automatic height and wrapping.
- Related checks: `node tests/test_confirm_narrow_contract.cjs` (static CSS contract), `tsc --noEmit`, `git diff --check`. All passed locally. No browser measurement, interaction or visual PASS is claimed.
- Separate worktree `/workspace/comfyart-confirm-narrow-20261109`; the QA worktree and running port 5210 remain unchanged at the original #850 SHA. Dependencies are shared through an ignored node_modules symlink.
- Pending: browser measurements at 360/379/380/390px, actual page comparison, submitting/timeout behavior, unknown-cost protection and independent QA. No billing, routing, download or supplier changes in this patch.

### Shared button metrics follow-up

- Applied the designer's static review correction: shared Button/IconButton minimum height 36px and border radius 8px, including the footer override. Width and other padding rules unchanged.
- Static CSS assertions and TypeScript checks passed locally; actual rendered dimensions, long labels, touch usage and visual comparison remain pending.
- This does not fix paid-submit lifecycle. Current generic Confirm closes before callback; changing it globally would affect delete/restore confirmations. The paid request caller and response lifetime must be handled separately.

## Paid cost-confirm lifecycle continuation (local, no supplier calls)

Implemented only for the direct-generation cost-confirm request in `queuePrompt`:

- The confirmed POST runs while the dialog stays open. A single-shot controller prevents repeat requests and disables Cancel / OK / Escape / backdrop closing while awaiting a response. Generic delete/restore confirmations retain their old synchronous behavior.
- After 30 seconds, the UI says the result is unconfirmed, allows closing (not cancelling), and keeps the outstanding request and in-memory submission status. No timer abort or automatic retry. A late acknowledgement still resolves the originating job and cannot close a newer dialog.
- A rejected/lost response or missing prompt id stays unconfirmed and disables the primary action. An unpriced, missing, invalid or negative price cannot enable this real paid-confirm submission.
- The status map is in memory, not a durable reconciliation system. Agent plan/over-quote confirmations, reload recovery, provider-side idempotency and budget-cap enforcement are NOT completed by this patch. No real submission is authorized by these tests.

Evidence: `node --experimental-strip-types --test tests/test_confirmation_submission.mjs` passes 8 checks (controller behavior plus static wiring/policy checks); `node tests/test_confirm_narrow_contract.cjs`, `tsc --noEmit`, and `git diff --check` pass. These are not browser interaction or independent QA results.

Mock-only browser fixture scenes prepared, NOT executed: `scene=submit`, `scene=submit-reject`, `scene=submit-unpriced`; `submit-delay=35000` lets QA observe timeout then late acknowledgement. These use local timers, never provider requests.

Existing services on 8188 (#848) and 5210 (old #850) have not been moved to this head and cannot attest to this patch. Browser rendering, focus, Escape/backdrop behavior, visual comparison and independent acceptance remain pending.

### Agent quote submission follow-up (2026-11-09)

- PlanQuote and OverQuote now opt into the shared single-shot asynchronous Confirm lifecycle: submitting locks close/repeat; timeout or lost acknowledgement becomes uncertain, not automatic retry. PlanQuote no longer reopens a fresh approval on failure.
- Capture originating chat/ask before opening; require the existing API's `{ ok: true }` acknowledgement. A missing conversation or malformed acknowledgement is not success. Cleanup uses ask identity, not shared description text.
- No-network checks: `node --experimental-strip-types --test tests/test_confirmation_submission.mjs tests/test_quote_answer.mjs` (14 checks, including static wiring), narrow/button static contracts, `tsc --noEmit`, `git diff --check`. These are not browser tests.
- Scope excludes reload/remount reconciliation, server idempotency, numerical quote/budget enforcement and supplier execution. Existing host is not automatically updated by this source commit.

### Confirmation visual feedback follow-up (2026-11-09)

- User reported missing button spacing and harsh highlighting. Independent Confirm rendering omitted `canvas.css`; footer flex/gap/right-alignment previously lived only there. `controls.css` now owns footer layout (8px gap, right alignment, wrap), so it does not rely on the canvas page.
- Secondary border uses the subtle existing border token; keyboard focus keeps one 1px neutral visible outline. Removed production `data-force` selectors that gave the primary a fake extra focus ring in captures. The existing Lovart reference at `docs/design/381/78/lovart/memory-delete-confirm-dialog-light.png` is reference only, not proof of exact visual parity.
- Added three static visual contracts; existing 14 no-network submission/quote checks, narrow/button static checks and TypeScript checks remain separate from browser evidence.
- `OUT_DIR=/absolute/dir BEFORE_CSS=/absolute/before.css node tests/js/buildConfirmVisualPreview.mjs` builds actual Confirm into offline before/after HTML. It uses mock copy/quote and optional mock submission promises; it is a component preview, not a full product screenshot or provider test. Browser screenshot evidence is reported separately when captured.
