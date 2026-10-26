# #78 Question card assets for PR #336 · issue #335

- tip: `47c7c2d` (`fix/p1-335-question-other-scroll`)
- source: **tip-CSS harness live** — static HTML copies `QuestionCard` class structure from `src/ui/ChatMessage.tsx` + `.ca-q*` from tip `overlays.css` (+ tokens). Not a full ComfyUI/app runtime capture.
- badges in PNGs: `tip-CSS harness · 47c7c2d`
- no API keys in shots
- Chinese: 问题 / 跳过 / 下一步 / 提交; pageOf `{n} of {N}`; 「其他…」; 无「修改」

## Required #78 states (all three · side-by-side Lovart)

| file | shows |
|------|-------|
| after/light-scroll.png | Light · multi-q overflow · **thin scrollbar** · last opts clipped · light selected (no black ring) |
| after/dark-scroll.png | Dark same |
| after/light-other.png | Light · **E 其他… expanded** with input value「包装袋」· no black ring |
| after/dark-other.png | Dark same |
| after/light-selected.png | Light · **轻选中** C 自然有机 · inverted letter · **no thick black border** |
| after/dark-selected.png | Dark same |
| compare/lovart94-vs-comfy-scrollbar.png | Lovart RS/94 ‖ Comfy scrollbar |
| compare/lovart96-vs-comfy-other.png | Lovart RS/96 ‖ Comfy 其他展开 |
| compare/lovart95-vs-comfy-selected.png | Lovart RS/95 ‖ Comfy 轻选中无黑边 |
| compare/overview-3states-light.png | Comfy light 三态并排 |
| before/333-light-pending-no-scroll.png | Prior #333 tip (no body scroll / E not expanded) |

## CSS notes shipped in tip
- `.ca-q` max-height 420 + flex column; head/foot `flex:none`; body `flex:1; min-height:0; overflow-y:auto` + thin scrollbar
- Selected: `border-color: transparent` + `--ca-hover` fill + letter invert (killed `--ca-strong` ring)
