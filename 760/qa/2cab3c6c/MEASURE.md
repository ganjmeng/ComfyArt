# QA @ `2cab3c6c` (r7)

Tip: `2cab3c6cf04e98c10d928eb5b2100549ca5281c8`

## 1280 / 1920

| | 1280 target | 1280 measured | 1920 target | 1920 measured |
|--|--|--|--|--|
| dialog | 1112×820 | 1112×820 | 1200×820 | 1200×820 |
| card | 344×288 | 344×288 | 388×321 | 388×321 |
| frame | 344×258 | 344×258 | — | 388×291 |
| dlg open | 200ms | 0.2s ca-skillrun-in | 200ms | 0.2s |

## Packaging

- tile0 主款: `master.webp` 270×360 contain, box 181.48×242, stackMounted=false, imgCount=1
- tile1 landscape stack n=3 contain; hover 1-row; clickleave restores pile
- tile2 multi-SKU n=4 portrait height-fill cover+scale~.8057; hover 2×2 161×118 gap6; L3 opacity0

## Motion card2

- raw 1536×2752 contain, box 144×258 @1280 / 162.41×291 @1920 (letterbox)

## 16 FINAL dialogs @1280

All 16 open; dlg 1112×820; cards 344×288; no direct-img cover; landscape stacks stay contain. Portrait stack cover = intentional height-fill.

## Suites

- tip `2cab3c6c`: 46 passed (incl. 11× test_skillrun_stack_760)
- main `9b1b56ec`: 35 passed (no test_skillrun_stack_760)
- delta: +11 new tip-only, all green; shared 35 still green
