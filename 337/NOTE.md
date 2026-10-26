# #78 Question card assets for PR #338 · issue #337

- tip: `54baf74` (`fix/p1-337-question-other-input`) — product-locked LIVE MVP
  https://github.com/ganjmeng/ComfyArt/issues/337#issuecomment-6410414076
- **after/** = tip-CSS harness at ~300 CSS sidebar column (not full ComfyUI/app runtime).
  Badges: `tip-CSS harness · 54baf74 · ~300 sidebar`
- **lovart-live/** = product signed-in Lovart light UI (NOTES 00–07). Dark Lovart N/A this pass.
- **design-mvp/** = hung HTML harness PNGs (spec-mock).
- **compare/** = tip harness ‖ Lovart live (empty / filled-other / keep-text) + tip dark‖light.

## Interaction locked (tip matches)
1. Fill other → clears A–D soft-select; other soft-on
2. Click A–D → **keeps other text**; soft-select moves only
3. Focus nonempty other → steals soft-select back
4. Nonempty other enables primary; empty placeholder does not
5. letter + textarea; flat unselected; no border/underline

## #78 sign-off status
**DEFERRED / NOT SIGN-OFF.** Harness + Lovart-live refs ≠ sidebar-embedded ComfyArt chat × Lovart light+dark.
Still need live ComfyUI sidebar after shots for formal #78. Product proofread before Ashley DM.
