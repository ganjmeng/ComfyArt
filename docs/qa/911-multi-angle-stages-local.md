# #1002 staged multi-angle implementation — Refs #911

Base: `4ce96715bc10ee5ff1841b7d55baf9c17d197ea4`
Worktree: `/workspace/fs911-multiangle-1116`
Branch: `fix/multiangle-stages-1116` — existing PR #1003; original published baseline `a11f6f5c1314765341c94155a357e13eaa1345f2`.

## Executable contract

- Existing `ask_user` / `bot_asks` pager collects source + final aspect, with no guessed answer.
- Existing `generate_image` relay guards the setup answer; first allowed submission is ONE numbered 3x3 nine-panel lineart preview.
- Existing `wait_generation` must report `status=done` and placed shape IDs for that specific preview holder before composition inquiry unlocks.
- Existing ask card then offers multi-select panel IDs 1..9 (other field accepts numeric IDs); pending, expired, cancelled or empty answers cannot authorize finals.
- Each selected ID authorizes one independent final image, not a fixed three or four. Selection is deduplicated, including other-field IDs.
- Original attachment URLs + user description + source + chosen final aspect are snapshotted in the setup ask block's `multi_angle_state`. Finals retain original refs as content and the delivered preview as composition reference.
- Static TS/Python 4 x 1536x2048 locks and blanket grid prohibition are removed. Skill aliases still resolve; it is deliberately not a single-image or fixed-count skill.
- User-owned description or the existing aspect card other field can specify exact integer pixels or a custom ratio. Exact pixels win over fallback/model guesses; selected ratio must agree with them. An explicit user preview layout wins; otherwise the model may choose the nine-grid preview ratio independently of the final aspect. Final pixel requests are not automatically preview pixel requests. The named request fallback is the shared aspect-size table / approximately 2k long edge (square 2048), NOT measured Lovart output or a delivery guarantee.

## Replay / safety

The existing persisted ask block owns a request ledger keyed by `preview` and `final:<panel ID>`, not an in-memory turn counter. The relay persists a reservation synchronously immediately before dispatch. Subsequent calls return the stored holder/result; uncertain timeout, crash or explicit failure is fail-closed and never automatically resubmitted. A repeated composition card is refused; expired/cancelled unanswered cards may be re-asked without repeating the preview. A new explicit skill start scopes a new run. A source/aspect mutation after reservation is refused.

Reservations and subsequent ledger updates now use SQL compare-and-swap on the persisted ask-owner message, reject stale ledger snapshots, and update live ask blocks only after persistence succeeds. A real SQL stale-writer regression is included. The supported app model remains a single active turn owner per chat; cross-worker end-to-end exactly-once is not claimed because generic message writers do not all use CAS. Recovery of an uncertain reservation remains manual reconciliation, never automatic regeneration/fallback.

## Fixture vs implementation policy

Read-only reference: `/workspace/design-911-multiangle/lovart-paid-20261116/manifest.md`.
Input fixture: `tests/fixtures/ma_subject_691.png`, description `商品详情页，纯白无缝背景` / `PDP, white seamless`.
Observed left run: one 1152x2048 numbered lineart; selected 1/2/3 -> three independent 2048x2048 finals; 74 Lovart credits total. These are measured fixture facts, not all-branch defaults. No left rerun was made.

Scope: existing source choices plus retained other-scenario free text; nine suggested aspects plus custom ratio/pixels in the existing other field. Image-only references are valid. Exact pixels require cached, verifiable native pixel-size support; unsupported/unknown capability blocks before submission instead of silently switching models. Panel labels 1..5 match the observed broad compositions; 6..9 use generic alternative/detail views rather than inferring subject-specific details from the fixture. Image visual consistency and provider-delivered dimensions remain unverified. A positive no-browser application-stack test now runs the real LocalLlmProvider loop, MCP dispatcher, ask futures, SQL chat persistence and canvas relay against mocked LLM/page-supplier boundaries. It selects FOUR finals after one preview to prove variable output count, placement and cap handling; this synthetic mock choice is not the three-selection left fixture. The existing browser Full App test remains a negative bypass regression and was not run. Browser/visual Full App acceptance is still pending.

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

Do not include Playwright/Full App tests until a separate slot and supported browser environment are available. `tests/conftest.py` binds `ComfyArt` to this worktree and uses temporary test settings; do not import the stale sibling checkout or QA runtime. Only the authorized focused Python tests were run. No Playwright, server, paid API, browser action, credential operation or outgoing message occurred. The original implementation includes rebuilt production dist; the initial branch was subsequently published as PR #1003. Publication statements in the earlier build section below describe that earlier preparation phase only.

## Static checks actually run

- `python3 -m compileall -q` on all changed Python source/tests: exit 0.
- TypeScript `tsc --noEmit`: exit 0, with a temporary worktree-local `node_modules` symlink to QA's restored dependencies, used read-only and removed immediately after compilation.
- `git diff --check`: exit 0.

Static success is not mocked-test success, browser/visual acceptance, or paid PASS. QA worktree, settings/runtime/dist/dependencies were not edited.


## Additional integration fixes from the positive test

`api/mcp.py` preflights only multi-angle generation before paid-unit accounting, so persisted replay results do not consume a second paid unit and restored original references reach the existing product-reference guard. `multi_angle.allow_selected_cap` bounds this skill's image allowance to current used units plus unreserved selected finals, including continuation in a new turn. Explicit user final counts are still enforced; the intermediate preview does not steal one of those finals. Dollar/quote/approval guards remain in place. No other skill's missing-parameter guard was edited (`api/skill_param_guard.py` and `api/paid_guard.py` are unchanged).

Receipt gating now requires the specific holder to report done, `placed=true`, no failure flag, exactly one delivered image when reported, and exactly one placed shape; status alone, unrelated holders, zero/multiple deliveries and unplaced completions do not unlock finals.

## Original a11f6f5c focused result (historical, not current acceptance)

437 passed, 0 failed, 0 errors, 0 skipped in 8.60s. Full output: `/workspace/fs911-ma-ev/focused-final.log`; machine-readable report: `/workspace/fs911-ma-ev/focused-final.xml`. TypeScript noEmit, changed-Python compilation and whitespace checks also passed. Python slot released after this result; no frontend/browser runner was started or touched.


## Production build / local publication preparation

`npm run build` (`tsc --noEmit && vite build`) succeeded; Vite transformed 3260 modules and finished in 3.96s. Full build log: `/workspace/fs911-ma-ev/production-build.log`. The normal large-chunk warning and the existing lottie-web direct-eval warning remain; they are not multi-angle runtime failures. The changed production assets and `dist/index.html` are included with the source changes. QA dependencies were reused read-only through a temporary worktree-local symlink, then the symlink was removed. No pytest or Playwright was rerun during this build-only phase; the validated focused result remains 437 passed / 0 failed / 0 skipped.

Prepared PR title/body are `/workspace/fs911-ma-ev/pr-title.txt` and `/workspace/fs911-ma-ev/pr-body.md`. Four commit-pinned LEFT Lovart baseline screenshot URLs were verified with HTTP HEAD: all returned 200 image/png. Evidence check: `/workspace/fs911-ma-ev/left-evidence-link-check.txt`. No right screenshots were invented. Visual/paid right acceptance and L/R PASS are still not established. Local commit only; push/PR/publication must be performed separately after authorization.


## Product HOLD corrections and independent QA regressions

- Source and aspect cards reuse `allow_other`; the source's original bilingual free text is retained in the prompt and immutable setup snapshot. No new editor/component.
- Only actual user text (minus existing app-injected skill templates) or aspect-card answers can authorize final sizes. Model final `width`/`height`/`ratio` guesses are ignored. Without an explicit user preview request the model may independently choose its layout ratio; model-guessed pixel dimensions are not promoted to user requests. Positive exact pixels are retained through preview, final, quotes and persisted resume. Examples: 1200x900 at 4:3, or 1250x1000 via other; custom 5:4/7:5 ratios are supported by existing shared sizing.
- A ratio/pixel conflict, conflicting specifications, fractional/zero/negative/out-of-policy pixels or malformed custom field fails pre-submit with clarification. Integer pixels are bounded 1..32768; ratios 1:16..16:1. Shared default-ratio sizing can impose further representation limits; explicit pixels avoid the fallback parser.
- Existing `wavespeed.validate_user_ratio`, cached provider schemas and `skill_size.accepts_exact_pixels` are reused. Detectable range/step/enum incompatibility or exact-pixel capability uncertainty blocks without provider submission. Routing may not rewrite authoritative sizes. An exact request pins the verified model and disables page auto fallback, including an Auto choice's later metadata step. It reuses the existing `size_lock` path for off-dropdown preference gating and returned-file pixel auditing (no new frontend path). These checks do not fetch provider metadata or call paid APIs.
- Legal image-only input no longer needs a fabricated description. In-flight preview continuation without an explicit stage returns the existing preview holder. Custom panel IDs are complete tokens: 11/12 are rejected, never split into 1/1 or 1/2. Frozen empty original refs remain empty even if later model args or uploads contain images.
- Source/aspect/pixel/preview-spec edits after reservation fail closed, including the initial published ledger format without a specification snapshot. Reconciliation/new explicit start is required; never re-dispatch an uncertain prior request. A fresh explicit skill start resets scope; ordinary continuation does not.
- The positive application-stack mock now handles real `plan_quote` cards with the existing `start` answer, asserts approvals, and mocks pricing/catalog boundaries too. It still exercises real MCP, asks, SQL, placement and four selected finals; no browser or visual/paid PASS is claimed.

Independent QA cases were copied from the read-only `/workspace/qa1002-a11f6f5c-evidence/test_adversarial_1002.py` to `tests/test_multi_angle_qa_adversarial_1002.py`. The previous fixture adaptation adding user preview text was incorrect under the 22:46 product ruling. It is now removed: all 13 original cases are byte-identical to QA (SHA256 `b90134914337b6d77a0fc2979af5c0f84c8927360548868dce1678604525178b`). QA files/environments were not modified.

### 8393c1dd focused result (historical; supersedes original 437 only)

**479 passed, 0 failed/errors/skipped in 6.01s**, nine focused files. This includes all 13 independent QA adversarial cases, 29 new specification/capability regressions, the repaired positive application-stack mock, and unchanged neighboring parameter guards. Initial new-only run was 93 passed / 1 failed because the newly added model-choice mock omitted `reason`; the stub was corrected, not the assertions. Intermediate focused run: 478 passed; final strengthened routing case brings the current run to 479.

Logs: `/workspace/fs911-ma-ev/product-hold-first.log`, `product-hold-second.log`, **`product-hold-focused.log`**, **`product-hold-focused.xml`**. Process checks found no foreign pytest before each dispatch. Python slot is free after this run.

```sh
# Canonical package alias and temporary read-only node_modules link as above.
PYTHONPATH=/workspace/fs911-ma-ev/package python3 -m pytest --maxfail=3 --tb=short -q \
  --junitxml=/workspace/fs911-ma-ev/product-hold-focused.xml \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_multi_angle_stages_911.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_multi_angle_specs_1002.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_multi_angle_qa_adversarial_1002.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_multi_angle_974.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_skill_output_982.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_skill_param_guard_956_957.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_product_packaging_flow.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_clothing_swap_911.py \
  /workspace/fs911-ma-ev/package/ComfyArt/tests/test_auto_pick.py
```

`npm run build` (`tsc --noEmit && vite build`) passed again, Vite 924ms; log `/workspace/fs911-ma-ev/product-hold-build.log`. Frontend source is unchanged in this correction, and rebuilding leaves committed dist unchanged. Only the existing chunk-size/lottie eval warnings remain. Changed Python compile and `git diff --check` passed. Temporary dependency symlink was removed; no symlink is committed. No other skills' missing-parameter guards were changed.

Remaining acceptance limits: exact support is conservative (existing native W*H helper, no snapped aspect-only adapter); cached schema may be stale and returned provider file pixels/visual fidelity remain unverified. Cross-worker exactly-once and uncertain-submission recovery limitations above remain. No browser/paid/L/R PASS; no paid or credential operation, merge or deployment.


## 22:46 product ruling: independent model preview layout

The setup ratio is the **final** aspect. Without explicit user preview ratio/pixels, model preview `ratio=9:16` is valid while final `1:1` remains unchanged. The preview uses the existing named ratio-size fallback, not model-guessed pixels or a universal measured fixture. With no preview ratio supplied, the final aspect may be reused as a fallback layout, but exact final pixels are never implicitly applied to the preview.

An explicit user preview specification always wins over tool arguments. The setup ledger now distinguishes `preview_request` (user authority) from resolved `preview` layout. Both are immutable after reservation; model ratio changes on resume return the same holder, not another submission. New/changed user preview specifications fail closed after dispatch, even when adding a request numerically identical to an earlier model choice. Old snapshot formats fail closed rather than being migrated into a paid replay.

`prepare` stays pure/idempotent for the MCP preflight → canvas relay path. Quotes use the same resolved ratio/pixels and do not reserve/freeze a model choice prematurely. Known provider range/step checks remain; exact-pixel unknown-capability restrictions apply only to stages where the user actually requested pixels. Explicit final pixels are still preserved and validated on the final stage, independently of a model-chosen preview ratio.

The actual-fixture and positive app-stack mocks no longer insert fictitious user preview requests: final setup 1:1 + model preview 9:16 is now tested directly. All 13 original QA cases are restored unmodified. Tests additionally cover explicit preview ratio/pixels overriding model input, replay immutability, final-size authority, quote/preflight consistency and final-only-pixel preflight idempotence. Other skills and their guards are unchanged.

### Current validation

**486 passed, 0 failed/errors/skipped in 5.45s**, the same nine focused files (56 staged-flow, 36 specification branches, all 13 original QA adversarial, and 381 neighboring regressions). The prior 479 result is historical. One newly added parametrization initially used pytest's reserved name `request` and failed collection; the variable was renamed without changing assertions. That collection failure is retained in `preview-policy-collection-error.log`; no implementation test failed in the current run.

Exact executable command: `/workspace/fs911-ma-ev/preview-policy-test-command.sh` (includes process recheck, canonical package alias environment, temporary read-only dependency link and cleanup). Full output/JUnit: `/workspace/fs911-ma-ev/preview-policy-focused.log` and `preview-policy-focused.xml`. The initial three-file run also passed 103 cases (`preview-policy-first.log`). No foreign pytest was active at either dispatch; Python slot is free.

`npm run build` (including TypeScript noEmit) passed: 3260 modules, Vite 1.10s; `/workspace/fs911-ma-ev/preview-policy-build.log`. Dist is unchanged and consistent; only existing chunk/lottie eval warnings. Changed Python compile, whitespace checks, byte-identical QA comparison and unchanged other-skill guards were verified. No symlink is committed. No browser, paid API, merge, deployment or PR comment/body update was performed; visual/paid/L/R acceptance remains pending.


## 23:23 product HOLD: subject-aware composition planning

The universal hard-coded `VIEWS` table is removed. Before the first preview submission,
the existing agent must inspect the actual subject/reference and requested use and supply
`composition_plan={subject, purpose, panels:[{id,name,description} x9]}` to `generate_image`.
This is a tool argument, not another UI card, editor, paid LLM request, or a new planning engine.
No generic/default plan is substituted if missing. Validation requires nine distinct numbered
entries (1..9) with non-empty names and descriptions, plus the subject and purpose context.
The backend validates structure, not semantic quality; actual relevance/visual correspondence
still requires product and real-image acceptance.

Quotes remain pure. The normalized plan is stored using the existing durable setup-ledger CAS
in the same reservation that occurs **before** canvas/provider submission. The preview prompt,
composition multi-select labels/descriptions and each selected final prompt read that same
mapping. Model attempts to supply a new map after dispatch do not replace the frozen one.
Concurrent stale reservation with a different map fails closed. Final requests and composition
cards lacking a valid persisted plan block; legacy delivered previews must be reconciled, never
automatically regenerated/charged. Existing specification/reference retention is unchanged.

New mock coverage supplies distinct headphones, ceramic teapot and courtyard-building plans;
it verifies shared preview/card/final numbering, selected IDs 2/7/9, restart/replay freeze,
quote-versus-dispatch freezing, missing/malformed plans and persistence before page dispatch.
Existing stage/specification/adversarial tests now explicitly provide the mock agent plan as
preview input. Their assertions were retained; the 13-case QA file is therefore no longer
byte-identical to the historical original (only plan fixture import/arguments added).
No hidden fixture auto-injection or bypass of the new missing-plan guard is used.

The first focused run yielded 502 passed / 2 failed: only the existing whole-file
`bot/skill_output.py` hash and combined skill-entry hash changed due to the intentional
multi-angle planning hints. Both pins were advanced to the inspected bytes; no tests were
removed, skipped or weakened. Other skill source, parameter guards and shared blocks are
unchanged. Current validation results are recorded below after rerun.


Current focused result: **504 passed, 0 failed/errors/skipped in 6.28s** (ten files,
including 18 new planning cases). Logs: `/workspace/fs911-ma-ev/subject-plan-focused.log`
and `subject-plan-focused.xml`; executable `subject-plan-test-command.sh` includes the
shared-runner check, temporary dependency symlink and cleanup. Production build passed
(TypeScript noEmit + Vite, 3260 modules, 1.40s); updated dist is included. Only existing
chunk-size/lottie-eval warnings remain. Python compilation and whitespace checks passed.
AST comparison confirms every assertion in the three adapted stage/spec/QA files remains
unchanged (`subject-plan-assertion-audit.json`). The original QA evidence directory is untouched.
Python test slot is free; no browser, paid request, merge, deployment or change to 8916.
Product/QA fixed-tip review and real provider/visual/L/R acceptance remain required.


## 2026-11-17 real paid tool-only failure and offline correction

QA ran frozen `0f0e9328` through a **scripted application tool chain**, not the default
agent (zero LLM calls), and obtained one WaveSpeed preview plus three selected finals.
Reported live image quotes totaled $0.2763 and the shared account balance decreased by
that amount; the total was below the $1 ceiling, but this is not evidence of a paid
default-agent run. Left Lovart was not repeated; existing 8916 was not modified.
Evidence remains `/workspace/qa1002-0f0e9328-appstack-paid/PAID.md`, original requests,
provider task IDs and images in that directory. The paid preview SHA256 is
`f4ee76543809a66306f5ef554227068c83e8ff4711974263b536c1ff073f798c`.

The preview is visibly a textured/shaded product-render grid, **not lineart**; the
planned overhead seventh panel looks near-frontal. Product/effect HOLD remains.
Preview file dimensions were 1440x2560 for the fallback request 1152x2048 (same9:16);
final files were2048x2048. The previous blanket exact audit incorrectly flagged the
larger fallback file and described every mismatch as smaller.

Correction (no additional generation):
- Preview prompt now demands thin black contour/structural lines on white paper,
  no fill/shading/texture/photo/clay/3D render, using the reference only for geometry
  and identity. It demands actual planned camera/framing/visible geometry, not a
  reused front silhouette. These are prompt constraints, **not a proven effect fix**.
- Final prompt explicitly restores original color/material/finish and uses the
  preview only for composition, rather than copying its line-only appearance.
- A specification without user-requested pixels sets the existing ratio/minimum-long-side
  audit mode; explicitly requested pixels remain exact (and retain provider capability
  preflight). Routing restores this stage-specific flag after any model pin. Existing
  WaveSpeed behavior still keeps exact audit when the actual payload supplies exact size.
- Backend and zh/en page copy now says the delivered size differs from the requested
  specification, true for larger/smaller/wrong-ratio cases. No resizing, hiding an image,
  reduced resolution, model substitution or automatic retry is introduced.

Reusable offline tests cover the actual 1440x2560/1152x2048 relation, undersized and wrong
ratio files, exact pixel nonrelaxation, line-only versus finished-material prompts and
relay propagation. Old notice-copy expectations and intentional size-module/locale hash
pins are updated, not removed. Browser e2e fixture copy is updated but **not executed**.
All WaveSpeed calls in the focused test suite are mocked. Real effects, default agent,
UI and Lovart L/R remain unverified; do not spend again merely to repeat this failure.


Current offline validation: **809 passed, 0 failed/errors/skipped in10.90s** across
14 focused files, including size-audit/WaveSpeed adapter mocks and portrait/packaging
neighbor regressions. Executable `paid-preview-fix-test-command.sh`; logs/JUnit
`/workspace/fs911-ma-ev/paid-preview-fix-focused.log` and `paid-preview-fix-focused.xml`.
Production build (tsc noEmit + Vite) passed,3260 modules,1.34s; updated locale dist is
included. Only existing chunk-size/lottie-eval warnings remain. Python compilation,
whitespace and copy-only regression audit passed (`paid-preview-fix-static-audit.json`).
Temporary dependency symlink removed; test slot is free. No new paid/API/browser call,
no change to8916, no merge/deploy. Prompt-effect HOLD is NOT cleared by these tests.

## Follow-up after e838b1be (handedness, plan projection, exact-pixel pin)

The 809-passed result above is historical for tip `e838b1be` only.

This follow-up keeps the frozen `composition_plan` (IDs, names, descriptions,
subject, purpose) unchanged in the ledger. Finals use that original plan,
restore material/color/finish, and require the selected panel's
screen-left/right orientation, camera direction and handedness (no
mirror/horizontal flip; no hardcoded facing).

Preview projection is a **limited, explicit-pattern** helper, not a universal
filter. `preview_plan_view` runs `preview_text` only on `subject` and
`panels[].description`. `_APPEARANCE_RENDER_RE` covers paid-failure phrases
and a few close variants ("exact gray materials", "matte surface finish",
"matching the reference plastic", "same gray …", "matte gray ", "亚光灰材质…").
Unlisted appearance wording is kept, including the recorded counterexamples
"glossy red leather", "哑光黑色材质", and "金属光泽". Fields not projected:
`purpose`, `panels[].id`, `panels[].name`, and the user description (so a name
like "matte surface finish close-up", a purpose that mentions sheen, or a user
brief like "红色皮革外观" remains in the preview prompt). Geometry/subject
labels such as "wall material" / "墙面材质特写" / "lining texture" /
"surface finish close-up" are also kept. Older plans with no listed phrases
project to the same panel lines, so existing mapping assertions still hold.
The preview prompt states this limited coverage; it must not claim that all
material/color/finish/lighting clauses are omitted.

Robust bilingual separation of mixed prose is **not** solved here. Shipping a
broader word blacklist would risk geometry phrases and would still be
incomplete. Product ruling is needed before any of: (A) optional structured
`geometry` / `appearance` fields on the existing plan (legacy `description`
remains required; preview would prefer `geometry` when present), or (B)
keeping this limited projector and treating unrecognized appearance wording
as an accepted residual, or (C) a larger language-specific filter. (C) is not
recommended. This commit does not add a parallel planning subsystem.

`apply_audit_mode` restores missing `width` or `height` individually. If a pin
rewrites one edge and drops the other, the rewritten edge is left intact and
`validate_provider_size` refuses the conflict. Both edges are never assigned
just because one is missing. Explicit 1152×2048 keeps exact audit; a
same-ratio 1440×2560 file does not pass.

Pre-fix new-test record (3 failed / 2 passed in 0.25s):
`/workspace/fs911-ma-ev/review-fix-failures.log` and `review-fix-failures.xml`.
The failures were the silent both-edge restore of a rewritten width or height,
and the preview prompt's universal-omission claim while unlisted appearance
phrases remained.

Current offline validation: **821 passed, 0 failed/errors/skipped in 9.62s**
across the same 14 focused files (809 historical plus later contract cases).
Command reused the focused 14-file set; logs/JUnit
`/workspace/fs911-ma-ev/review-fix-focused.log` and `review-fix-focused.xml`.
Production build (tsc noEmit + Vite) passed, 3260 modules, 1.06s; dist was
unchanged. Only existing chunk-size/lottie-eval warnings remain. Python
compilation and `git diff --check` passed. Temporary `node_modules` symlink
removed. No paid/API/browser call, no change to 8916, no merge/deploy/push,
and this tip is not published. Prompt-effect HOLD is NOT cleared.


### 2026-11-17 01:28 Asia/Shanghai structured-plan ruling (supersedes local text projection)

Product and engineering agreed: no keyword blacklist / automatic mixed-prose migration.
The earlier unpublished 2906fdde/d2b0fdeb text-projector mechanism is removed in the
current working revision; its historical test counts are not current-tip acceptance.
Existing `composition_plan` now requires `subject_geometry` and `appearance`, plus
`panels[].geometry` and `panels[].appearance`, alongside original subject, purpose,
name and description. Appearance can be an empty string when unspecified. Geometry
is explicitly shape/visible structures/camera/framing only. This is a semantic
planning contract, not proof that an arbitrary model honors it.

Preview prompt assembly reads ONLY subject_geometry, numbered panel geometry,
stage dimensions and lineart rules. It never interpolates names, purpose, original
user/source wording, or appearance fields. Originals stay in the durable plan and
stage metadata for cards/finals; finals include original user/source wording,
subject/panel appearance, selected geometry, and handedness/no-mirror constraints.
No source/reference input is lost. Existing card and ledger mechanisms are reused;
no parallel planning API, component or migration is introduced.

Legacy boundary: any old mixed plan with a preview reservation/submission record
is query/archive only, including reserved/uncertain, pending and delivered states.
The generate/quote/reserve boundaries block conversion, finals or a fresh submission;
existing task IDs remain available, and result collection/archiving may continue.
A legacy plan without any preview submission/reservation may be explicitly replanned
before dispatch; the software does not derive a new plan by scrubbing old prose.
The paid `PAID_FAILURE_PLAN` fixture remains byte/value-identical to the archive.
No old task is resubmitted. No new paid API, browser or8916 activity.

Regression changes are explicit, not weakened assertions: old raw-brief-in-preview
checks now require raw text to remain in metadata/final output and be absent from
preview, as mandated by product. Earlier unpublished regex-filter tests retain
all scenario names but now assert no filter, rejection of mixed legacy inputs,
geometry-only projection and preservation of bilingual appearance in finals.
All original stage/spec/selection/exact-pin-quote checks still run. Mock planning
fixtures now supply the required separated fields; no production fixed-view table.
Hash pins updated only for the intentionally changed multi-angle instructions;
other src/skills.ts entries verified byte-identical to the previous local head.

Validation: **835 passed, 0 failed/errors/skipped in9.71s**, same fourteen focused
files. Command `/workspace/fs911-ma-ev/structured-plan-test-command.sh`; final logs
`structured-plan-focused.log` and `structured-plan-focused.xml`. First transition
run (6 failed/826 passed: four now-obsolete raw-text preview expectations and two
intentional instruction hash pins) is preserved as
`structured-plan-contract-transition-failures.log/.xml`, followed by832-pass interim
run before three extra schema/legacy routing probes (`structured-plan-832-pre-extra`).
Effect HOLD remains: no new WaveSpeed image, default agent, UI or L/R acceptance.

Production build (tsc noEmit + Vite,3260 modules) passed in1.10s; consistent
dist committed. Python compilation/whitespace checks passed and the temporary
node_modules symlink was removed. No new component or migration.


## 2026-11-17 camera-only wording revision

One numbered nine-panel generation remains unchanged. Global geometry no longer
requires reproducing all front-reference-visible surfaces at every camera. Each
panel specifies camera position/direction, subject pose, visible surfaces and
occlusions; changing camera does not silently tilt the subject.

The reviewed headphone planning case is separately versioned in
`tests/fixtures/multi-angle-camera-plan-1002.json`; panel 7 is directly above the
upright subject, looking vertically down. This is a regression fixture, NOT an
engine default, a migrated paid snapshot or proof of the real agent's next plan.
Existing paid task snapshots remain immutable and may not be resubmitted.

`test_reviewed_camera_plan_reaches_canvas_without_network` exercises the real
canvas relay with `submit_command` mocked; it captures the full assembled canvas
request, NOT an actual provider outbound record. Effect/default-agent/UI/LR
acceptance still requires separately authorized fresh verification, pinned SHA,
actual provider payload/quote comparison and real image review. No guide, mask,
local edit, collage, 3D or model change is included.

The packaging regression suite pins the entire `bot/skill_output.py` file. Its
SHA pin is refreshed solely for the reviewed multi-angle planning text; AST
comparison against the parent confirms `_run_hint_declared` is the only changed
top-level function. All unrelated portrait/model/self-check pins and tests remain.


## Preview/final separation correction (2026-11-17 product ruling)

The setup card `ma_aspect` is the FINAL specification, not a preview answer.
For a new run without an explicit preview specification, the independent preview
default is 1152x2048 (9:16); finals retain their answered aspect. Explicit user
preview ratios/pixels win over this default. Already-frozen preview snapshots
remain unchanged. Quoting and dispatch use the same resolved stage specification,
and the existing quote-confirm gate remains mandatory. No paid call is included.

Updated prior fallback tests now lock this independent default rather than the
withdrawn final-as-preview behavior. Explicit square preview coverage is added;
final dimensions, exact pixels, replay and routing guards remain exercised.


## 2026-11-17 15:48 product ruling (c8860a69 follow-up)

`cb9421a3` changed the unspecified-preview default from independent 1152x2048
(9:16) to the setup-card aspect. Product ruled that the 12:48 two-stage policy
is not superseded: preview stays 1152x2048 (9:16) unless the user explicitly
specifies a preview size; finals still follow the setup card. The first
quote/paid generate must remain the numbered lineart preview, labelled as such,
and must not price a final first. Camera wording is unchanged. Official gate
and $0 quote checks belong on a new instance of the corrected tip, not 8927.


## 2026-11-17 aspect custom entry

Product did not approve removing the aspect card's custom ratio/pixel field
with the 9ff63633 preview/camera static check. The setup card still decides
the final hero aspect; the Other row is restored for custom ratio or exact
pixels, and user-text exact pixels remain authoritative. The error that
pointed at a hidden Other field is valid again because that row is visible.
Whether Lovart's question card can later drop custom entry remains an open
product/design comparison, not a reason to hide the field on this tip.
