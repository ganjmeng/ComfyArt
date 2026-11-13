# #953 evidence @ `6b24ea6ede8abe2ed47142c51d3dbe3daf5b2bbc`

Tip `6b24ea6e` is `1bbd009b` plus a merge of `origin/main` `cd4f9496` (#961, ask_user /
paged skill reads / truncation). The merge resolved `bot/local_llm.py` by keeping both
#961's paging/cache/truncation logic and this PR's `_call_price_params` strip, and
`dist/` was rebuilt from the merged `src/` (`npm run build`, exit 0). Base for review:
`origin/main` `cd4f9496`.

## How these were produced (mock, $0)

Real Full App render (Vite `dist/`, 1600x1000), real mouse, Playwright Chromium 1254:

```bash
cd /private/tmp/wt955fix   # HEAD 6b24ea6e
env -u WAVESPEED_API_KEY -u REPLICATE_API_TOKEN -u KIE_API_KEY -u DEEPSEEK_API_KEY \
  no_proxy='*' PLAYWRIGHT_BROWSERS_PATH=/private/tmp/pw-chromium \
  CA_953_SHOTS=/private/tmp/shots955_6b24ea6e \
  /private/tmp/ca-env/bin/python -m pytest tests/test_e2e_953_studio_quote.py -q
# 14 passed in 96.18s
```

The harness serves the real app shell, points WaveSpeed at an in-process `TestServer`
(fake catalog / price / submit / CDN), and the agent is the scripted `FakeProvider`.
No real provider key is set or written to disk, and no paid call is made. The `$10.00`
balance and all result images are mock. No API key appears in any screenshot.

Each source has two shots per language: `*-quote.png` (inline quote card before
confirm) and `*-hover.png` (task-history card after submit + hover reason). The e2e
also asserts exactly **1** mock submit per case and that the submitted model equals
the quote / task-history model.

## Four #953 sources (zh + en)

| source | quote | task history / hover | submitted |
|---|---|---|---|
| generic Auto (no skill, no model) | `Auto · GPT Image 2.6 Flare（这是通用生图的默认模型）` | `自动选择：这是通用生图的默认模型` | `openai/gpt-image-2.6-flare/text-to-image` |
| agent auto-fill (user says 「你来选」/ "you pick", tool call carries a model) | `Auto · GPT Image 2.6 Flare（自动选择）` | `自动选择：自动选择` | `openai/gpt-image-2.6-flare/text-to-image` |
| skill pin `pose-fission` | `Auto · Nano Banana Pro（pose-fission 技能固定模型）` | `pose-fission 技能固定模型` | `google/nano-banana-pro/edit` (2K, 3:4) |
| user-named model | `GPT Image 2.6 Flare` (no `Auto ·`, no reason) | no tooltip | `openai/gpt-image-2.6-flare/text-to-image` |

`auto-*` (before-after skill_size) is not one of the four sources and is covered by
the earlier `955/9d7fb7f1/auto-*` captures; the four sources above are new at this tip.

## Studio same-id manual pick (old HOLD scenario, re-shot at this tip)

`studio-same-manual-selected-{zh,en}.png`: Auto estimate on GPT Image 2.6 Flare →
Auto off → explicitly check the **same** Flare id; the result frame reads
`图像生成器 GPT Image 2.6 Flare` / `Image generator GPT Image 2.6 Flare` with no
`Auto ·`, and the send goes out once on Flare. `studio-same-submitted-{zh,en}.png`
show the submitted result. The pricing fix does not touch selection (asserted by
`test_studio_manual_pick_of_the_same_model_after_auto_is_manual`).

## Pricing regression evidence (blocker 1)

`tests/test_model_choice_display_953.py::test_priced_inputs_never_carry_display_only_keys`
locks that `_price_call` hands the pricer no `_`-prefixed key and the price equals the
clean call on unknown→Auto, named and #910 routed-edit paths. Reverting
`bot/local_llm.py` turns that test and
`tests/test_smoke_blockers_732.py::test_unknown_model_is_priced_on_the_auto_model_before_the_call`
red (2 failed), restoring it turns both green.

Tests on this tip: `test_smoke_blockers_732.py + test_model_choice_display_953.py +
test_bot_local_llm.py` = 66 passed; QA 762 subset = 762 passed; full e2e = 14 passed.
