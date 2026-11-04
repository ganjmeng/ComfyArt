# QA #673 next — docs/673-audit @ 8dcb8824 (free QA, $0)
OCR (RapidOCR, full + 6 poster crops + 5 ppt pages): no residual gold text in our images (VANT/LENO/双11/BONBUN/天猫/廓形之选/LUMVEX/SUMMICRON/ASPH all absent). Only generic substring matches (付定立减, 199) = our own copy. LR gold hits are on the GOLD half only (expected). No garbled chars (velle read as elle/vel = stylised font).
- ppt: 1920x5235, 5 pages, seams pass (lum diff 1.13/0.85/8.64/1.98). Page numbers 01/05..05/05 OCR exact. 5 dots each, active dot correct 1..5. p01/p02 dots dark (dot max lum 78/122 vs bg ~16-21): p02 inactive dots near-invisible at half-screen — minor. p08 (page4): slight blur smears around dots, minor.
- promo ex01: poster5 lens smudge gone, reflection/aperture restored, lower-right rect edge not visible at half-screen. poster6: blurred blobs above left cookie, top-right in box, right edge — VISIBLE at half-screen (major). poster4: blur blocks above & below CTA pill on rug — VISIBLE at half-screen (medium). poster2 halo: not visible at half-screen.
- taobao: under-title dark patch soft, not visible at half-screen. PASS.
- Links: all 4 raw URLs pinned to 8dcb8824 -> 200.
Verdict: ppt PASS (minor dot contrast p02), taobao PASS, promo ex01 FAIL (poster6, poster4 inpaint blur).
