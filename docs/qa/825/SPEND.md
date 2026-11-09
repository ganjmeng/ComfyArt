# Spend table — #825 10-image compare

- Balance before: **$31.766999**
- Balance after: **$31.217699**
- Total spend (balance delta): **$0.549300** (cap $0.65)
- Failures: **none** (all 10 ok on attempt 1)

| # | Model | Prediction id | Bal in | Bal out | Cost USD | Latency s |
|---|-------|---------------|--------|---------|----------|-----------|
| A1 | `openai/gpt-image-2.6-flare/text-to-image` | `2cf3bb30caca4166a59334c63816bdbc` | 31.766999 | 31.676999 | **$0.0900** | 36.376 |
| A2 | `openai/gpt-image-2.6-sunburst/text-to-image` | `1fe4bd2b3b1e49d3a00f97624de6bfb6` | 31.676999 | 31.586999 | **$0.0900** | 59.572 |
| B1 | `openai/gpt-image-2.5-sunburst/edit` | `c1417807dcc04c37b326287c0f859d83` | 31.586999 | 31.547999 | **$0.0390** | 25.028 |
| B2 | `openai/gpt-image-2.6-sunburst/edit` | `625389052fad43ceacebf0fb48ce56ee` | 31.547999 | 31.475999 | **$0.0720** | 30.995 |
| C1 | `google/nano-banana-2.1/edit` | `8b08f315c02541dbb31897384a4834b1` | 31.475999 | 31.438199 | **$0.0378** | 47.869 |
| C2 | `bytedance/seedream-v5.0-pro/edit` | `366abb9bae9c450cb5514a90299d619c` | 31.438199 | 31.397699 | **$0.0405** | 30.702 |
| C3 | `openai/gpt-image-2.6-sunburst/edit` | `f8c12db6c4cd4f5ea1aa8c868377be53` | 31.397699 | 31.339199 | **$0.0585** | 48.111 |
| D1 | `google/nano-banana-2.1/text-to-image` | `d69a210b926b4e039c0bb4d697da8512` | 31.339199 | 31.303199 | **$0.0360** | 35.829 |
| D2 | `bytedance/seedream-v5.0-pro` | `ade77dc5fffb465183bc30dd71c94720` | 31.303199 | 31.262699 | **$0.0405** | 36.287 |
| D3 | `openai/gpt-image-2.6-sunburst/text-to-image` | `32b2046864a44e1188302ba42506c6b1` | 31.262699 | 31.217699 | **$0.0450** | 30.936 |

**Sum of per-call costs:** $0.5493
