#513-1 / PR #530 API-billed evidence (budget ≤ $0.50)

prediction_id == `/comfyart/wavespeed/history/<id>` task id (same pattern as #509/#514).

| path | model | prediction id | quoted | actual |
|---|---|---|---:|---:|
| generate_refs | wavespeed-ai/flux-dev-lora | defd54f9fb5a47fbb5741ebd43e04483 | 0.015 | 0.015 |
| generate_base | wavespeed-ai/flux-dev-lora | 0f0360efd02941c88b8e1c9ea70b1fd2 | 0.015 | 0.015 |
| lipsync | wavespeed-ai/infinitetalk-fast | 1e9f82f988c64d8d8cc623c9a2d638d4 | 0.045 | 0.045 |
| motion | wavespeed-ai/wan-2.2/animate | 91dca275421b4ddbb46575ff100aac42 | 0.12 | 0.12 |

Balance 6.179044 → 5.984044 = **$0.195** total.

Kling v2.6 motion failed twice (no upper-body in video; $0 billed) — switched to curated `wan-2.2/animate`.
