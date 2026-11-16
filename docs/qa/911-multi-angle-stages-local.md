# #1002 staged multi-angle implementation — Refs #911

Base: `4ce96715bc10ee5ff1841b7d55baf9c17d197ea4`
Worktree: `/workspace/fs911-multiangle-1116`
Branch: `fix/multiangle-stages-1116` (local commit prepared; no publication)

## Executable contract

- Existing `ask_user` / `bot_asks` pager collects source + final aspect, with no guessed answer.
- Existing `generate_image` relay guards the setup answer; first allowed submission is ONE numbered 3x3 nine-panel lineart preview.
- Existing `wait_generation` must report `status=done` and placed shape IDs for that specific preview holder before composition inquiry unlocks.
- Existing ask card then offers multi-select panel IDs 1..9 (other field accepts numeric IDs); pending, expired, cancelled or empty answers cannot authorize finals.
- Each selected ID authorizes one independent final image, not a fixed three or four. Selection is deduplicated, including other-field IDs.
- Original attachment URLs + user description + source + chosen final aspect are snapshotted in the setup ask block's `multi_angle_state`. Finals retain original refs as content and the delivered preview as composition reference.
- Static TS/Python 4 x 1536x2048 locks and blanket grid prohibition are removed. Skill aliases still resolve; it is deliberately not a single-image or fixed-count skill.
- Final sizes use selected aspect at long-edge 2048, not a universal 1:1. Preview layout can use a separately requested supported aspect; absent that, it follows selected aspect. The fixture's 9:16 preview is NOT an implicit default.

## Replay / safety

The existing persisted ask block owns a request ledger keyed by `preview` and `final:<panel ID>`, not an in-memory turn counter. The relay persists a reservation synchronously immediately before dispatch. Subsequent calls return the stored holder/result; uncertain timeout, crash or explicit failure is fail-closed and never automatically resubmitted. A repeated composition card is refused; expired/cancelled unanswered cards may be re-asked without repeating the preview. A new explicit skill start scopes a new run. A source/aspect mutation after reservation is refused.

Reservations and subsequent ledger updates now use SQL compare-and-swap on the persisted ask-owner message, reject stale ledger snapshots, and update live ask blocks only after persistence succeeds. A real SQL stale-writer regression is included. The supported app model remains a single active turn owner per chat; cross-worker end-to-end exactly-once is not claimed because generic message writers do not all use CAS. Recovery of an uncertain reservation remains manual reconciliation, never automatic regeneration/fallback.

## Fixture vs implementation policy

Read-only reference: `/workspace/design-911-multiangle/lovart-paid-20261116/manifest.md`.
Input fixture: `tests/fixtures/ma_subject_691.png`, description `商品详情页，纯白无缝背景` / `PDP, white seamless`.
Observed left run: one 1152x2048 numbered lineart; selected 1/2/3 -> three independent 2048x2048 finals; 74 Lovart credits total. These are measured fixture facts, not all-branch defaults. No left rerun was made.

Minimum safe slice limitations: source choices are single front / multiple refs / description; nine supported final aspects, no arbitrary custom pixel dimensions. Panel labels 1..5 match the observed broad compositions; 6..9 use generic alternative/detail views rather than inferring subject-specific details from the fixture. Image visual consistency and provider-delivered dimensions remain unverified. A positive no-browser application-stack test now runs the real LocalLlmProvider loop, MCP dispatcher, ask futures, SQL chat persistence and canvas relay against mocked LLM/page-supplier boundaries. It selects FOUR finals after one preview to prove variable output count, placement and cap handling; this synthetic mock choice is not the three-selection left fixture. The existing browser Full App test remains a negative bypass regression and was not run. Browser/visual Full App acceptance is still pending.

## Validated mocked coverage

`tests/test_multi_angle_stages_911.py`: source/aspect pager, order guards, unfinished preview, unanswered/expired/cancelled cards, numeric custom entry + dedup, variable selected IDs/counts, four final aspects, original ref/description retention in zh/en, preview composition binding, pure quote, replay across persisted reads, concurrent same-process dispatch, timeout/failed response, persistence failure, new-run isolation, edited setup refusal, unrelated skill/ask nonregression.

The superseded #974 assertions now check staged behavior/removal of the false lock; the old Full App scripted direct-four plan now expects zero supplier submissions. Existing unrelated output and snapshot tests remain in place; whole-file snapshot values were refreshed only for the intentional multi-angle changes.

Parent announced the exclusive Python slot at approximately 21:47 Asia/Shanghai. Process recheck found no foreign runner. The initial plain invocation hit missing local node_modules, followed by pytest package initialization errors because the worktree basename contains hyphens. A canonical package symlink under the evidence directory resolved collection without changing repository packaging or skipping frontend prerequisites. The first executed seven-file run passed 425 tests. Strengthened application-stack coverage then found the legacy four-unit paid cap blocked the fourth selected final after the preview; that implementation defect was fixed without weakening the assertion.

The focused command is now run through the canonical package alias (full final log and JUnit XML under `/workspace/fs911-ma-ev/`):

```sh
# Existing read-only alias: /workspace/fs911-ma-ev/package/ComfyArt -> this worktree
# Temporarily link this worktree/node_modules to QA dependencies read-only; remove after.
PYTHONPATH=/workspace/fs911-ma-ev/package python3 -m pytest --maxfail=3 --tb=short -q \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_multi_angle_stages_911.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_multi_angle_974.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_skill_output_982.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_skill_param_guard_956_957.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_product_packaging_flow.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_clothing_swap_911.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_auto_pick.py
```

Do not include Playwright/Full App tests until a separate slot and supported browser environment are available. `tests/conftest.py` binds `ComfyArt` to this worktree and uses temporary test settings; do not import the stale sibling checkout or QA runtime. Only the authorized focused Python tests were run. No Playwright, server, paid API, browser action, credential operation, push, PR or outgoing message occurred. A local implementation commit includes the rebuilt production dist.

## Static checks actually run

- `python3 -m compileall -q` on all changed Python source/tests: exit 0.
- TypeScript `tsc --noEmit`: exit 0, with a temporary worktree-local `node_modules` symlink to QA's restored dependencies, used read-only and removed immediately after compilation.
- `git diff --check`: exit 0.

Static success is not mocked-test success, browser/visual acceptance, or paid PASS. QA worktree, settings/runtime/dist/dependencies were not edited.


## Additional integration fixes from the positive test

`api/mcp.py` preflights only multi-angle generation before paid-unit accounting, so persisted replay results do not consume a second paid unit and restored original references reach the existing product-reference guard. `multi_angle.allow_selected_cap` bounds this skill's image allowance to current used units plus unreserved selected finals, including continuation in a new turn. Explicit user final counts are still enforced; the intermediate preview does not steal one of those finals. Dollar/quote/approval guards remain in place. No other skill's missing-parameter guard was edited (`api/skill_param_guard.py` and `api/paid_guard.py` are unchanged).

Receipt gating now requires the specific holder to report done, `placed=true`, no failure flag, exactly one delivered image when reported, and exactly one placed shape; status alone, unrelated holders, zero/multiple deliveries and unplaced completions do not unlock finals.

## Final focused result

437 passed, 0 failed, 0 errors, 0 skipped in 8.60s. Full output: `/workspace/fs911-ma-ev/focused-final.log`; machine-readable report: `/workspace/fs911-ma-ev/focused-final.xml`. TypeScript noEmit, changed-Python compilation and whitespace checks also passed. Python slot released after this result; no frontend/browser runner was started or touched.


## Production build / local publication preparation

`npm run build` (`tsc --noEmit && vite build`) succeeded; Vite transformed 3260 modules and finished in 3.96s. Full build log: `/workspace/fs911-ma-ev/production-build.log`. The normal large-chunk warning and the existing lottie-web direct-eval warning remain; they are not multi-angle runtime failures. The changed production assets and `dist/index.html` are included with the source changes. QA dependencies were reused read-only through a temporary worktree-local symlink, then the symlink was removed. No pytest or Playwright was rerun during this build-only phase; the validated focused result remains 437 passed / 0 failed / 0 skipped.

Prepared PR title/body are `/workspace/fs911-ma-ev/pr-title.txt` and `/workspace/fs911-ma-ev/pr-body.md`. Four commit-pinned LEFT Lovart baseline screenshot URLs were verified with HTTP HEAD: all returned 200 image/png. Evidence check: `/workspace/fs911-ma-ev/left-evidence-link-check.txt`. No right screenshots were invented. Visual/paid right acceptance and L/R PASS are still not established. Local commit only; push/PR/publication must be performed separately after authorization.
