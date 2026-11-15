# Design local review — Home form, captured f4479456 / final c44a16a0

2026-11-15 19:25 Asia/Shanghai (UTC+8). Local, unpublished. 设计本人已独立阅读五张原版 Home 表单、五张新 tip 表单及五张左右对照图。本记录不恢复旧 PASS。

## 最终待评 tip 映射（设计本人独立核验）

2026-11-15 20:43 Asia/Shanghai（UTC+8）。最终待评提交为 `c44a16a0fa142727c08c3e8ff0617382e97fae3e`；实拍提交仍为 `f4479456f95c19215180bb82e2242755d775e286`，未重拍或改图标记冒充最终提交实跑。

- 两提交间 `git diff --exit-code ... -- src dist` 返回 **0**，只按提交对象核验，未以含测试产物的工作树作依据。
- `src` tree 对象均为 `8e385db89952fd2503cb561a8f49a796fd97193d`；`dist` tree 对象均为 `66b606dfc135a8e20e436bd9881181fa24b0280b`，因此这两目录的路径、文件模式及所有文件字节一致。
- 从实拍 tip 到最终 tip 仅两测试文件变化：`tests/test_skill_e2e_992_example_presets.py`、`tests/test_e2e_skill_hidden_notice_673.py`。`1897e228` 到最终 tip 仅后一文件变化。
- 本人明确将上述五项首页表单的设计观察和“撤预设芯片视觉修复已核实”的本地结论映射至最终 tip；不是整体 Lovart 对齐或输出质量结论，也不是宣称已重跑最终 tip UI。
- 秘书通报 QA gate 已完成；本次只独立核提交差异，不代签或复述为本人已验 QA 日志。正式仍 **HOLD**，待证据固定 review-assets SHA 与本人纠正发布；旧 PASS 不沿用。Logo Home 未知、双必填星号与示例差异、真实输出未跑边界不变。

## 设计本人本地结论

On tip `f4479456f95c19215180bb82e2242755d775e286`, five Home **Start with a Skill** row → in-place Start Creating forms have **no preset chips**. Examples/thumbs plus Upload Files and Additional Details are retained and empty. Ours still shows **\*** on both fields and a dark, disabled-looking Start making. Original has **no \*** and a dark button. **No runtime validation was tested.**

**Local #992 removal is a visual fix VERIFIED.** This is not global Lovart parity and not a full design release.

Entries must be stated and are **not the same**: original = Home **Featured card body**; ours = Home **Start with a Skill** row. Both are modal, input-ready. **Logo Home remains unknown** (not found on For you / Branding); no expansion here.

Examples differ and are **not** claimed equivalent (artwork, counts, or output): RedNote original **10** vs ours **5** tabs; other counts as in the capture tables (Mobile 13/13, Web 9/9, Marketing 8/8; Meta original tab count was **not** in the original capture table, ours 4). Themes differ (original light, ours dark). Output was never run.

**Formal HOLD** until the canonical pack is fixed to SHA, the correction is filed, and QA closes. Old PASS is not reused.

## SHA check (this machine, read-only)

- Captured / served tip: `f4479456f95c19215180bb82e2242755d775e286`
- Follow-up commit (full SHA): `1897e228e5a3469b0afbcb34434bd511063e99b4` (2026-11-15 19:19:47 +0800, parent = f4479456, subject `test(#992): lock Home e2e to home-skill-card and fix dialog await`)
- `git diff --exit-code f4479456f95c19215180bb82e2242755d775e286 1897e228e5a3469b0afbcb34434bd511063e99b4 -- src dist` → **exit 0** (src and dist identical).
- The only file that differs is `tests/test_skill_e2e_992_example_presets.py`.

Design observations above apply to **identical src/dist** on 1897e228. **No new runtime UI was run on 1897e228.**

## Pairs (new files only; prior long pack not rewritten)

Same-surface L/R, native 1920×1072 panes, padded header, no stretch: `/workspace/lovart-form-entry-study/2026-11-15/f4479456/sbs/lr-home-form-default-{skill}.png` (3840×1220). Public original copies: `originals-redacted/`. Hash and native redaction boxes: `NEW-FILES-SHA256.md`. Sources and times: `HOME-FORM-RESULTS.md` (ours 19:19–19:20) and `../HOME-FORM-QUICK-TABLE.md` (original 18:41–18:43).

## Visible notes (not clearance)

- Original files are native **1920×1072**, not 1024×572 (that is display scale 1.875). Masks were measured on the native frames.
- Ours frames show Loomi branding and no operator account/credits; those were not redacted.
- Ours capture notes mention a pre-existing Home banner (“This generation didn't finish. Please try again.”), left untouched; it is not used as a product finding.
- Bookmark Share controls remain visible; only the bookmark **count** (and author / uses / left-rail credits) are redacted.
