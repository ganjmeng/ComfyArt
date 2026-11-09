# B pasteback edge notes

- crop_sha256: `645c5be50f8bc1f7c112e0e5cd2af4f29a066b6bc8e46ce2cccd3c0783e71e1b`
- box: `{'x': 0, 'y': 0, 'w': 768, 'h': 632}` region: `{'x': 0, 'y': 0, 'w': 768, 'h': 421}`
- Both calls: same crop file, `resolution=1k`, `aspect_ratio=3:4`, same prompt, **no mask_image**; only model id differed.

## Acceptance
- B1p: {"max_abs_diff_outside": 0, "n_diff_pixels_outside": 0, "black_band": false, "inside_mean_rgb": [244.3, 172.6, 139.6]}
- B2p: {"max_abs_diff_outside": 0, "n_diff_pixels_outside": 0, "black_band": false, "inside_mean_rgb": [233.4, 175.2, 167.8]}

## Seam metrics (200% crop x=200..500, y=380..460)
- {'name': 'orig', 'mean_above_rgb': [147.60000610351562, 188.0, 200.5], 'mean_below_rgb': [210.0, 200.0, 190.0], 'seam_jump_mean': 27.33, 'luma_3px_inside': 178.3, 'luma_3px_outside': 201.8, 'luma_delta_in_out': -23.6}
- {'name': '2.5', 'mean_above_rgb': [253.3000030517578, 197.3000030517578, 133.1999969482422], 'mean_below_rgb': [211.10000610351562, 200.10000610351562, 188.60000610351562], 'seam_jump_mean': 34.12, 'luma_3px_inside': 209.6, 'luma_3px_outside': 201.8, 'luma_delta_in_out': 7.8}
- {'name': '2.6', 'mean_above_rgb': [251.60000610351562, 191.1999969482422, 158.5], 'mean_below_rgb': [211.0, 199.89999389648438, 189.10000610351562], 'seam_jump_mean': 27.27, 'luma_3px_inside': 207.2, 'luma_3px_outside': 201.8, 'luma_delta_in_out': 5.3}

## Visual
- 2.5: seam jump similar to orig (34.12)
- 2.6: seam jump similar to orig (27.27)
- 2.5: outside-below mean abs vs orig = 0.00 (expect ~0)
- 2.6: outside-below mean abs vs orig = 0.00 (expect ~0)
- sky mean 2.5=[244.3, 172.6, 139.6] 2.6=[233.4, 175.2, 167.8]
- peach R-B 2.5=104.7 2.6=65.6

**Read:** 2.6-sunburst: peach/pink sky looks more sunset-like and seamless enough; 2.5 is more orange-flat. Neither shows black band. Outside is byte-identical.
