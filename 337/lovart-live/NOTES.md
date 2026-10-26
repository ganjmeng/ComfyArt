# Lovart 「其他」 live · 2026-10-26

Site: https://www.lovart.art/ (signed in, China). Project: `/canvas?projectId=2u0r6y1fvri8`. Prompt asked for a 新茶饮品牌视觉 and a question card. Light UI only (no dark toggle found). Did **not** click 提交 or 跳过. Card left unanswered.

Question card stacks all 4 questions in one scroll (`max-h` ~440, thin grey scrollbar on the right). Header pager `1 / 4` at the top, `3 / 4` once scrolled to Q2–Q3. Primary button label is **下一个** on an early page and **提交** once scrolled toward the later questions.

## Widget

「其他」 is **not** a chip and **not** click-to-expand. It is the same row as an open-text answer:

`[letter badge 20×20 r4] + <textarea data-testid="agent-inline-questions-custom-input">`

Row ~36px tall (`min-h 32`, `px-8 py-8 gap-8 rounded-8`). Textarea is transparent, `outline-none`, height 20, no border, **no underline**. Unselected letter is `text-lo-text-secondary` on `bg-lo-bg-overlay`.

Placeholders (exact):

- Q1 C open-text: `已有品牌名...`
- Q2 D other: `其他定位...`
- Q3 D other: `其他方向...`
- Q4 C free text: `详细说明...` (not the word 其他)

Open-text and 其他 are the **same geometry and classes**. Only the placeholder string differs. The word 「其他」 is placeholder copy, not a separate control.

## States

- **Empty:** always the textarea. Placeholder visible (`其他定位...`). No pill wash, no border, no underline. Letter badge stays light grey. Focus (`textarea:focus`) does **not** hide the placeholder, does **not** add a border, and does **not** add the selected wash. Still looks like `01-empty-other-row.png`.
- **Filled (typed `包装袋`):** placeholder hides because the value is set. Whole row gets `bg-lo-bg-overlay-active` (grey wash). Letter flips to `text-lo-text-onbrand` (white on a dark badge). Wash **stays after blur**. Same look as a selected A–C row.
- **Clear:** emptying the textarea drops the wash and restores the grey letter + placeholder. Nothing in that question stays selected.

## Mutual exclusion (this pass)

Single-select. Chrome is exclusive; the typed string is not deleted.

1. **Select B, then type in 其他.** B’s wash and dark badge turn off as soon as 其他 has text. D takes the selected wash. They are not both active. (`03` → `04`)
2. **Fill 其他, then click A.** Text **stays** `包装袋`. Selected chrome **moves to A**. D letter goes back to grey; the leftover string is plain text, not a second selection. (`06`, `07`)
3. **Submit gate.** With only 其他 filled (`包装袋`, D active, A–C off), **提交 is enabled** (black). (`05`) With 其他 empty and no A–D selected, **提交 is disabled** (grey). (`02`, `isDisabled=true`) Selecting B alone also enables 提交. 跳过 stays enabled.

Refocusing a nonempty 其他 re-selects D and deselects A/B. Backspace/clear after that leaves the question with no selection (A does not come back).

## Shots

- `00-card-empty-page1.png` — empty card, pager 1/4, primary 下一个, thin scrollbar
- `01-empty-other-row.png` — Q2 empty D `其他定位...` next to flat A–C (also the focused-empty look)
- `02-empty-submit-disabled.png` — no answer, 提交 grey/disabled, pager 3/4
- `03-select-B-other-empty.png` — B selected, 其他 still placeholder
- `04-type-other-deselects-B.png` — typed 包装袋; B off, D on
- `05-only-other-submit-enabled.png` — only 其他 filled; 提交 black
- `06-click-A-other-text-stays.png` — A on, D off, text `包装袋` still in the field
- `07-click-A-card.png` — same, card + enabled 提交
