# #766 / PR #768 tip 81736d33 — confirm-in-completion (no pre-generate Got it)

Tip: `81736d33` (full: `81736d338590fc27d2ee607c2116ef1ff9b5b438`)
PR: https://github.com/ganjmeng/ComfyArt/pull/768
How: Full App Firefox `http://127.0.0.1:8199/comfyart/` + canvas + composer; natural-language seed (**no** `ask_user` in typed prompt; generate path has **no** wait/don't-generate wording).

## Product lock (NEW — supersedes tip 4fe81522 pre-gen confirm)

1. After user answers a normal ask → **NO** separate pre-generate confirmation sentence (no “Got it — … I'll continue” / “知道了 — …我按这个方向来做”).
2. After right Q/A bubble (#767 shipped — UI untouched here) → **immediately continue** original task; generation expected when user did not ask to wait.
3. **AFTER** images: left assistant body restates the choice and invites adjustments (EN structure like measured post-image copy; no `Lovart` string in src).
4. Skip: also no pre-gen “Got it I'll skip”; continue original task.
5. **ONLY** if user explicitly asked to wait / not generate → pinned #766 wait sentences.
6. Do not force ask_user on a plain logo prompt.

## Captured (FF, light)

| Shot | Result |
|------|--------|
| zh-light submit after-answer | Q/A `问/答` bubble; `pre_gen_confirm_detected=false`; gen continued |
| en-light submit after-answer | Q/A `Q/A` bubble Minimal; `pre_gen_confirm_detected=false`; gen continued |
| zh/en completion | restates choice (极简线条 / Minimal) + invites adjustments |
| tip leak ask_user | false (both) |
| left grey qmemo | 0 |

## Assert

See `assert.json`.
