# #687 Phase1 re-wash prompt pre-check (draft, no generation)

Base: origin/main `b47b6671368581f54d8a5c9e26fd0f3548010ffc`. Gold: `gold_lovart/<id>/` (box-local, `/workspace/qa687/gold_lovart`, not committed).
Model: WaveSpeed `google/nano-banana-2.1/edit`, 1K, ~$0.0378/img; free local upscale (Real-ESRGAN/Lanczos) to gold cover size.
Excluded: taobao-product (handled in its own PR, cap $0.3).

## Global rules (apply to every prompt)
- Person/photo slots: gold = base image; feathered mask (~24px) on head/face only; new person, no less attractive (campaign-grade, real skin texture), same head angle, gaze, light; 1–2 small scene tweaks. Keep gold pose, outfit, light, grade, grain.
- Non-portrait (product/illustration/anime) slots with soft-wash risk: gold = **style reference only**, new composition stated in prompt.
- Every prompt ends with: `No text, no letters, no logos, no numbers, no watermark anywhere in the image.` All text added locally (PIL), every gold brand/word/number replaced.
- One brand per slot (social = **LUMORA**); same character consistent across all views inside one sheet.
- Budget: social + character cap **$0.50**; stop after 2 consecutive fails on the same image; max 2 extra retries per batch. Log WaveSpeed balance before/after each batch.
- Local post (all): OCR check (no gold text survives), upscale to gold size, LANCZOS resize, webp q90.
