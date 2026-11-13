# #955 / #953 same-id manual source — Full App evidence (tip b3bc40f5)

$0 mock only: local mocked LLM/WaveSpeed, committed `dist/` built from this tip
(`npm run build`), Playwright **Chromium** (Firefox not installed in this env),
`GATE=1`, all real provider keys unset. No paid calls.

Scenario (QA HOLD repro, real mouse):

Studio → new Image Generator → prompt “a cup of coffee on a table” → wait for the
Auto estimate (Flare) → Model menu **Auto off** → explicitly check the **same**
`openai/gpt-image-2.6-flare/text-to-image` row → Generate.

## Screenshots

| file | scene |
|---|---|
| `studio-same-manual-selected-zh.png` | zh: Auto off + the same Flare row checked, card label `GPT Image 2.6 Flare` (no `Auto`) |
| `studio-same-manual-selected-en.png` | en: same state |
| `studio-same-submitted-zh.png` | zh: exactly 1 mock submit (Flare), result label `GPT Image 2.6 Flare` (no `Auto`, no Auto reason tip) |
| `studio-same-submitted-en.png` | en: same result state |
| `studio-en-manual-selected.png` / `studio-en-submitted.png` | older different-id case (Auto off → GPT Image 2) still manual / submitted GPT Image 2 |
| `auto-{zh,en}-quote.png`, `auto-{zh,en}-hover.png` | Agent skill-pin source: quote + task-history reason (still Auto + skill, not “you named”) |
| `manual-{zh,en}-quote.png`, `manual-{zh,en}-hover.png` | Agent user-named source: quote + task history (name only, no Auto) |

## Estimate provenance captured from the real Full App (page.route on `/comfyart/wavespeed/estimate`)

`same-id-estimate-before-after.json`:

- before (a43ad880): the request after Auto off + same-id pick still carried
  `model_choice.auto=true` + `auto_model=true`, backend answered `auto=true`,
  category `default` (“这是通用生图的默认模型”) → UI stayed `Auto · GPT Image 2.6 Flare`.
- after (b3bc40f5): the same request carries
  `model_choice={model: Flare, auto:false, category:"user", reason:"你指定了这个模型"}`,
  no `auto_model`; the response is the same manual record → label has no `Auto`.
  The submitted model is unchanged (`openai/gpt-image-2.6-flare/text-to-image`,
  exactly one submit).

## Reproduce

```
cd <checkout of fix/953-model-choice-display @ b3bc40f5>
env -u WAVESPEED_API_KEY -u KIE_API_KEY -u DEEPSEEK_API_KEY -u REPLICATE_API_TOKEN \
  GATE=1 no_proxy='*' python -m pytest -q -p no:cacheprovider \
  tests/test_e2e_953_studio_quote.py -k same_model_after_auto
```

Screenshots are written to `$CA_953_SHOTS` (default `/tmp/953-fullapp/new-tip`).
