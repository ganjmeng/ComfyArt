# 660c4026 Lovart left / ours right — cells 1, 2, 3

Additive asset pack for PR #1003. It does not change product code and it does not rewrite the archived QA verdict.

## Bound

- Prior code SHA `660c402678626972e5214119da0b0d0bfda6edeb` only.
- Route: scripted tool-only application stack, zero LLM calls. Not the default agent and not the UI.
- PM effect approval applies to that prior output only. It is not approval of the current default quotation flow.
- Current default quotation `project01e72bb2` remains FAIL: no actionable quote, 30/30, WaveSpeed catalog guard.
- `911/wavespeed/20261118-660c4026-finals/verdict.json` (commit `118f63d9d23ca7afeaffa4b9e8d736a43e1bf104`) still records overall HOLD for cells 1, 2, and 3. That file is unchanged.

## Pictures

LEFT in each `lovart-ours-cell{1,2,3}.png` is the frozen Lovart final at commit `44b6ab3756a96f82ec85e31525a31c07728d690d`, 2048×2048, pasted unscaled.

RIGHT is `ours-cell{1,2,3}-right-panel-extract.png`. The full 2048 paid finals named in `verdict.json` are not in the git archive. Each extract is the exact RGB interior of the right-hand red frame on `side-by-side-cell{1,2,3}.png` from commit `118f63d9d23ca7afeaffa4b9e8d736a43e1bf104`. Those boards are our preview-cell crop on the left and our paid final on the right. They are not Lovart-versus-ours sheets. `contact-sheet-finals.png` is the reference plus three ours finals.

The frame, the board caption, and the left preview crop are excluded. The extract is 1024×1024. It was not rescaled, padded, cropped into the product, or retouched. Labels on the composite sit in the gray band outside both image rectangles. The gray area is layout chrome. Pixel checks confirmed the pasted panels match the source files.

Pairing is panel number: cell 1 front, cell 2 three-quarter, cell 3 side. Images were not flipped to force a match.

Boxes, dimensions, and sha256 values are in `MANIFEST.json`.
