# 96259b9e scripted 0-LLM preview-only paid run

Written 2026-11-17 08:35:22 Asia/Shanghai. **STOP for parent visual review. No finals. Not a default-agent / UI / Lovart L/R PASS.**

Authorization used: PM passed back the user's 08:22 Asia/Shanghai answer “授权没变啊，继续给你们付费授权”. Treated as the user's continuing paid-testing authorization for exactly one preview, not independent EL authority.

## Remote head and in-flight scope

`git ls-remote` at 2026-11-17 08:31:20 +0800: `refs/heads/fix/multiangle-stages-1116` and `refs/pull/1003/head` both `96259b9e17da5990e5655c01b663c3252cec6ee6`. Unchanged; the run proceeded. Merge ref unused.

In-flight check scope (not whole-account uniqueness): this box's processes; loopback listeners; saved QA JSON under the 96259 / 0f0e / e838 evidence dirs; presence of `active.json` here. No WaveSpeed job-list was called. Within that scope: no in-flight 96259 provider preview (preflight placeholder `local-preflight-preview-holder` is not a provider task; `0f0e` tasks remain delivered and were not reused). See `paid/start-check.json`.

8916 pid 14265 and 8927 pid 285091 were not used or written. Engineer worktree was not written. Isolated TestClient was ephemeral `127.0.0.1:43513`.

## Quote, submit, balances

Fresh live quote (prior preflight $0.1035 was not assumed): **$0.1035**, source `quote`/`live`, model `openai/gpt-image-2.6-flare/edit`, 2k + 9:16, 1 ref. Within remaining cap **$0.7237**. No 409 confirm.

- Balance before 2026-11-17 08:32:56 +0800 Asia/Shanghai: **$20.790008**
- Provider image POST at 08:33:02 (exactly one). Task ID recorded before poll: `656362db606041debf18e657e44b1ba7` (`prompt_id` `ws:656362db606041debf18e657e44b1ba7`). See `go/preview.task.json`.
- Poll completed 08:35:09; generation succeeded.
- Balance after 08:35:15: **$20.686508**
- Quoted spend **$0.1035**. Shared-account balance delta **$0.1035** (matches the quote). Shared WaveSpeed balance is not exclusive to this QA unless proved.

Cumulative skill cap $1: old $0.2763 (`0f0e9328`) + this $0.1035 = $0.3798 recorded; remaining at most **$0.6202** if this delta is attributed here (shared-account caveat). Guard: 1/1 provider image POST, LLM blocked, finals blocked, uncertain=false. HTTP: 71 allowed, 0 blocked. One Flare POST only; polls and one result download followed. Requests log (redacted): `paid/http-allowed.jsonl`.

## Image (for parent visual review)

Ratio-only 2k policy was enforced (`size_lock_mode=ratio`, `exact_pixels=false`, requested 1152×2048 / 9:16). Provider output **1440×2560** PNG, ratio match true, ratio error 0.0%, `size_notice` none.

- Original: `/workspace/qa1002-96259b9e-preview-preflight/runtime/output/wavespeed/ws_656362db6060_0.png`
- Copy: `/workspace/qa1002-96259b9e-preview-preflight/downloads/preview-9x16.png`
- sha256 `87fb45980ce6fbec407d16e49b78bc4561d0d020505d8ef9c33c1c9ad92df540` (original and copy match)
- 2,435,795 bytes

Fresh structured 9-plan: `structured-plan.json` (panel 7 genuine top-down geometry; panels 1/2/3 include camera/handedness). Same fixture sha256 `f92f6c3eb265a1421003a4682d21c3e472450eb084ef027ab0290b6e2d550b5e`, DESC `商品详情页，纯白无缝背景`, source single front. Application prepare / plan / reserve / quote / audit / `/comfyart/wavespeed/run` routing was used. This is a scripted 0-LLM effect subset only. Prompt wiring and ratio audit do **not** prove visual lineart, genuine top-down panel 7, or identity.

## STOP

No finals were started. No LLM, no Lovart, no GitHub post/push, no second provider POST. Await parent visual review of the original preview path above.

## Independent visual verdict (2026-11-17 08:35 Asia/Shanghai)

HOLD. Preview now visibly uses black outline lineart on white rather than material rendering. Panel 7 still repeats a front-like silhouette with the full arch and cushion interiors visible, not the frozen overhead/top-down camera showing cup top edges only. Panel 7 fails. Stop here: no finals, no retry. See parent-visual-review.json. Not default agent/UI/LR acceptance.
