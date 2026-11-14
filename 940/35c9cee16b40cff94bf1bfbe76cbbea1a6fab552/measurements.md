# #940 computed-style audit @ 35c9cee1

Official Full App fixture; Chromium; viewport 1280×900; mock/fake only; $0.

Lovart target: issue comment 6857404832 (RA 1× pixel measurements ±1px; 14px inferred from glyph ink, not live DOM). Our values below are actual getComputedStyle of the mounted app, not a static example.

Both CN and EN verified. First cut already shipped in #947. #998 signatures were limited to #934 and are not #940 acceptance.

## Measurements (CN / EN)
| Section | CN | EN |
|---|---|---|
|card|{"maxHeight": "442px", "minHeight": "0px", "borderRadius": "18px", "borderTopWidth": "1px", "borderTopColor": "rgb(229, 229, 229)", "backgroundColor": "rgb(255, 255, 255)", "paddingLeft": "16px", "paddingRight": "12px", "paddingBottom": "14px", "overflow": "hidden"}|{"maxHeight": "442px", "minHeight": "0px", "borderRadius": "18px", "borderTopWidth": "1px", "borderTopColor": "rgb(229, 229, 229)", "backgroundColor": "rgb(255, 255, 255)", "paddingLeft": "16px", "paddingRight": "12px", "paddingBottom": "14px", "overflow": "hidden"}|
|body|{"overflowY": "auto", "minHeight": "0px", "scrollbarWidth": "thin", "scrollbarColor": "rgb(223, 224, 226) rgba(0, 0, 0, 0)"}|{"overflowY": "auto", "minHeight": "0px", "scrollbarWidth": "thin", "scrollbarColor": "rgb(223, 224, 226) rgba(0, 0, 0, 0)"}|
|scrollbar|{"width": "6px"}|{"width": "6px"}|
|thumb|{"backgroundColor": "rgb(223, 224, 226)", "borderRadius": "3px"}|{"backgroundColor": "rgb(223, 224, 226)", "borderRadius": "3px"}|
|label|{"color": "rgb(115, 115, 115)", "fontSize": "14px"}|{"color": "rgb(115, 115, 115)", "fontSize": "14px"}|
|icon|{"width": "14px", "height": "14px", "strokeWidth": "1.5px", "color": "rgb(115, 115, 115)"}|{"width": "14px", "height": "14px", "strokeWidth": "1.5px", "color": "rgb(115, 115, 115)"}|
|page|{"color": "rgb(115, 115, 115)", "fontSize": "14px"}|{"color": "rgb(115, 115, 115)", "fontSize": "14px"}|
|disabledArrow|{"color": "rgb(197, 197, 197)", "opacity": "1"}|{"color": "rgb(197, 197, 197)", "opacity": "1"}|
|prompt|{"fontSize": "14px", "lineHeight": "20px", "color": "rgb(25, 25, 25)"}|{"fontSize": "14px", "lineHeight": "20px", "color": "rgb(25, 25, 25)"}|
|row|{"height": "76px", "minHeight": "36px", "paddingLeft": "9px", "paddingRight": "9px", "borderRadius": "8px", "backgroundColor": "rgba(0, 0, 0, 0)"}|{"height": "94px", "minHeight": "36px", "paddingLeft": "9px", "paddingRight": "9px", "borderRadius": "8px", "backgroundColor": "rgba(0, 0, 0, 0)"}|
|text|{"fontSize": "14px", "color": "rgb(25, 25, 25)"}|{"fontSize": "14px", "color": "rgb(25, 25, 25)"}|
|badge|{"width": "20px", "height": "20px", "backgroundColor": "rgb(245, 245, 245)", "color": "rgb(111, 111, 111)"}|{"width": "20px", "height": "20px", "backgroundColor": "rgb(245, 245, 245)", "color": "rgb(111, 111, 111)"}|
|primary|{"height": "32px", "minWidth": "76px", "borderRadius": "10px", "backgroundColor": "rgb(44, 44, 44)", "color": "rgb(255, 255, 255)", "fontSize": "14px", "gap": "8px"}|{"height": "32px", "minWidth": "76px", "borderRadius": "10px", "backgroundColor": "rgb(44, 44, 44)", "color": "rgb(255, 255, 255)", "fontSize": "14px", "gap": "8px"}|
|key|{"width": "14px", "height": "14px", "fontSize": "14px"}|{"width": "14px", "height": "14px", "fontSize": "14px"}|
|skip|{"width": "60px", "height": "32px", "backgroundColor": "rgb(255, 255, 255)", "borderTopColor": "rgb(229, 229, 229)", "borderTopWidth": "1px", "color": "rgb(25, 25, 25)"}|{"width": "60px", "height": "32px", "backgroundColor": "rgb(255, 255, 255)", "borderTopColor": "rgb(229, 229, 229)", "borderTopWidth": "1px", "color": "rgb(25, 25, 25)"}|
|footer|{"gap": "8px"}|{"gap": "8px"}|
|scroll|{"height": 338, "content": 880}|{"height": 338, "content": 1106}|

Selected row/badge CN: {'row': 'rgb(235, 235, 235)', 'bg': 'rgb(44, 44, 44)', 'fg': 'rgb(255, 255, 255)'}
Selected row/badge EN: {'row': 'rgb(235, 235, 235)', 'bg': 'rgb(44, 44, 44)', 'fg': 'rgb(255, 255, 255)'}

## Plain one-question card (no descriptions)
zh: {
  "height": "36px",
  "pitch": 40,
  "promptPitch": 36,
  "cardHeight": 296
}
en: {
  "height": "36px",
  "pitch": 40,
  "promptPitch": 36,
  "cardHeight": 296
}

## Differences fixed
- Header span stroke 1.5 did not override SVG attribute 1.75; direct SVG style now computes to 1.5px.
- Plain prompt-to-first-option top-to-top pitch was 25px; now 36px (20px line + 16px gap). Plain option row height 36px / pitch 40px unchanged.

## Deliberate behavior / evidence limits
- Card 1 remains a single three-question scrolling card, header 1 of 3 only, Next scrolls; only at bottom with all answers complete can Submit proceed. Card 2 stays paginated and reuses the same full board image.
- Description rows wrap and exceed 36px naturally; we do not clip them to a single-line height. At narrow panel width they require more internal scroll.
- Main button stays disabled for incomplete final submission (product ruling), unlike Lovart’s always-clickable reference.
- Enabled-arrow and hover colors unchanged; no new values invented without source evidence.
- Selected left reference is clothing-swap; right is YouTube, same component/different skill, style-only comparison authorized by product.
- Screenshots are actual app: full-screen originals plus card crops, 1× L/R without rescaling.
- Remaining between-question/scrollbar-offset pixel interpretation is not a claim of live Lovart DOM parity; sources are screenshots, not live DOM.