# #673 C pilot — naive-illustration ex01
- Model google/nano-banana-2.1/edit, 1k, 3:4, base = gold ex01, no mask; raw 896×1200 → local Lanczos upscale 1536×2048.
- WaveSpeed balance 45.268249 → 45.230449 (cost $0.0378). 1 call, 0 retries.
- meanAbs vs gold (64×64 grey) = 19.6 (< 40 gate): uniform, pose and colours stay close to the gold pilot outfit.

## v2 (retry 1 of 2)
- Design's prompt + S, same model/1k/3:4/gold base. Raw 896×1200 → 1536×2048 local upscale. Files: naive-illustration-ex01.v2.webp, LR-naive-illustration-ex01.v2.jpg (gold | v1 | v2).
- Balance 45.230449 → 45.192649 ($0.0378). meanAbs 39.6. Fur, uniform and pose all changed.
