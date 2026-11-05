# #769 Full-App Firefox @1920×1072

Tip `ae601b6f` on `fix/composer-ref-modelprefs-icon` (follow-up: icon-only Hash).

Design lock (YohakuX + product HOLD 5788863113):
- `#` is Lucide Hash (not Frame); glyph 16×16, stroke 2.5 (~1.67px), same class as Cube
- Hit 32×32; linked gray + count badge must not widen past 32
- Cube c2c to primary = 40 (8px gap) unchanged
- Missing `#` on Lovart LEFT is not a defect

Measured idle-zh/en: hashIcon=cubeIcon=16×16, strokes 2.5, c2c=40, gap=8, refW=prefW=32.
Wait-done: outRows=statusBoxes=footers=0.
