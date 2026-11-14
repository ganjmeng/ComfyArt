# Local-only #999 geometry HOLD hypothesis verification

Published baseline35c9cee16b40cff94bf1bfbe76cbbea1a6fab552. All work stays LOCAL; mock $0. No GitHub writes/push, review-assets publication, teammate messages or new Lovart browsing. This is technical hypothesis verification, NOT design approval; PR999 remains HOLD.

## Read-only clarification check / discrepancy
Fresh issue940 and PR999 comments are saved in issue-comments.json/pr-comments.json. Latest PR design comment is6882290830. No posted clarification of ink/THUMB anchors was found. HOLD requests track-right distance; PM-relayed hypothesis targets VISIBLE THUMB-right. This discrepancy needs design/owner confirmation; measured values below explicitly separate both.

## Minimal CSS + matching dist
Only dock BODY gap16→9; WITHIN-question block gap remains16. BODY margin-right:-12 and padding-right20 (old8) preserve question content width. Typography, line heights, descriptions, header/footer and question logic unchanged. Matching dist rebuilt, stale hashed assets removed. dist-check.log records built declarations.

## Actual Full App 1× measurements
Chromium159/Linux; viewport1280×900; deviceScaleFactor1; original raw PNGs1280×900. Native scrollbar enabled by removing Playwright --hide-scrollbars and passing --disable-features=OverlayScrollbar,OverlayScrollbars. Original-CSS captures remain separate from named diagnostic-native-track screenshots (temporary native scrollbar-color PAINT only; no fake track). All numerical geometry is identical before/after diagnostic paint.

Each pair uses one simultaneous DOM/raster snapshot with BOTH anchors visible. Two pairs require different scroll positions; source Lovart numerical scrollTop is unknown. Selected state chooses A in all three questions; numeric layout/raster equality against unselected state is directly asserted.

|Lang/state|Q1→Q2 scrollTop|Q2→Q3 scrollTop|D-placeholder INK top|Next PROMPT INK top|Pitch|
|---|---:|---:|---:|---:|---:|
|CN unselected/selected|206|493|408|444|36|
|EN unselected/selected|302|645|410|445|35|

At these aligned views, D border rect x29..357/y396..432 (36px, border1) → next prompt line box x29..357/top441 (20px per line, border0): bottom461 except EN Q3, which naturally wraps to two lines/bottom481. DOM top-top45, bottom-top9. Rects are half-open; ink rows are integer raster anchors. DOM line box, DOM text Range and raster ink are separate in JSON; DOM45 is NOT compared as equivalent to raster36.

Pinned source1920×1072: https://raw.githubusercontent.com/ganjmeng/ComfyArt/2082537ff964633a1c5779884d4d7ac3a5744ffa/911/lovart-ai/youtube-channel-banner/card-1.png . Existing source D-placeholder ink top675→Q2 prompt ink top711=36 (about±1px per anchor/±2px difference). EN translation has different glyph ascenders;35 is within proposed36±2. Source Q2→Q3 is NOT visible, DOM row/prompt boxes unknown. Historical anchor intent is unconfirmed; this verifies the relayed hypothesis only.

## Visible native THUMB versus TRACK
Card outer(12,279)..(388,721), border1→right INNER edge387. Scroll-body border box(29,326)..(387,664), border0. Body offsetWidth358/clientWidth348, native gutter10; padding-right20. Native track x377..387 (right-exclusive); gray thumb x379..384 inclusive→right boundary385. Thus TRACK distance0; THUMB distance387−385=2px. Thumb width6 is observed in raster; pseudo width6 alone would not prove track width (actual native track10).

Content width remains328px. Old-position rollback yields identical block widths/heights, wrapped description heights and exact header/footer rects. Within-question prompt-bottom→first-option-top remains16; descriptions remain18px line-height and natural multiline wrapping. Direct containment/spacing assertions detect internal overlap/clipping; scrolling viewport intentionally clips scrolled-away content. Both measured anchors stay visible. Source raster thumb-right1317→inner edge≈1319 gives≈2px; its transparent track edge remains unknown.

## Actual rollback/mutation evidence
- Runtime BODY gap rollback16: CN ink36→43; EN35→42. SAME raster pitch assertion raises in both languages; within-question spacing stays16.
- Runtime margin0/padding8 rollback: THUMB gap2→14; TRACK gap0→12. SAME raster thumb assertion raises. Content dimensions/description wrapping/header/footer unchanged.
- Removing mutations restores target geometry. Selected/unselected numeric layout/raster equality is asserted.

## Evidence / test audit
measurements-{zh,en}.json = full rect/style/range/scroll/mutation/raster data; summary.json = concise values. zh/en-{unselected,selected}-q1-q2.png and -q2-q3.png = unmodified app CSS1× originals; separately named diagnostic-native-track images = paint-only diagnostics; annotated-*.png = labeled copies. local-lr-* =1× crops of pinned Lovart UNSELECTED raster on left, actual app on right, D INK tops aligned; selected-right views are explicitly labeled and do not claim a source selected reference.

New repository test: tests/test_skill_e2e_940_geometry.py. Existing official mock baseline6 passed in30.36s. Initial geometry tests reached all raster/mutation assertions but failed an overly broad diagnostic equality comparing inherited paint strings; corrected to numerical geometry equality (initial log retained). Subsequent geometry-tests.log:2 passed. targeted.log/gate.log record final broader runs. No approval is inferred from tests. Existing #934/#949/#960/#962/#966 locks are exercised unchanged.

Pending: posted confirmation of ink-top and VISIBLE THUMB target interpretation; original source Q2→Q3/DOM geometry remains unavailable. No design PASS or issue closure claim.

## Final validation / local commit
Unpublished local commit63ca9fe452722ebd5939c562845b3cd6b95eaa53 includes CSS, new Full App test and matching dist (no QA/temp artifacts). Full gate ONE attempt: GATE_EXIT0,4731 unit passed/25 skipped,191 E2E passed,455 node-unit tests included. Typecheck/build passed. mock $0. No gate rerun or flake waiver. Full logs preserved in gate-details/ and gate.log. Existing QA image leftovers modified by normal suite are left uncommitted.
Header actual box(29,296)..(375,316); footer(29,674)..(375,706), unchanged during scrollbar rollback. Before-change original raw screenshots remain separately in ../geometry-hold/. Publication is NOT authorized/executed; PR999 remains HOLD.
