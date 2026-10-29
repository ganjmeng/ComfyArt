# Agent regression (#231)

Mocks only, $0. pass: 56

| case | lang | result | steps/limit | paid (exp) | LLM req | msgs | tokens | status | note |
|---|---|---|---|---|---|---|---|---|---|
| 01 t2i 1 image with size + style | en | pass | 2/12 | 1 (1) | 3 | 6 | 4946 | done |  |
| 01 t2i 1 image with size + style | zh | pass | 2/12 | 1 (1) | 3 | 6 | 4931 | done |  |
| 02 t2i exactly 4 images | en | pass | 2/12 | 4 (4) | 3 | 6 | 4946 | done |  |
| 02 t2i exactly 4 images | zh | pass | 2/12 | 4 (4) | 3 | 6 | 4933 | done |  |
| 03 selected image: change background to beach (image edit) | en | pass | 3/12 | 1 (1) | 4 | 8 | 6750 | done |  |
| 03 selected image: change background to beach (image edit) | zh | pass | 3/12 | 1 (1) | 4 | 8 | 6725 | done |  |
| 04 t2v 5s | en | pass | 2/12 | 1 (1) | 3 | 6 | 4761 | done |  |
| 04 t2v 5s | zh | pass | 2/12 | 1 (1) | 3 | 6 | 4744 | done |  |
| 05 i2v from the selected image | en | pass | 3/12 | 1 (1) | 4 | 8 | 6570 | done |  |
| 05 i2v from the selected image | zh | pass | 3/12 | 1 (1) | 4 | 8 | 6546 | done |  |
| 06 15s upbeat music | en | pass | 2/12 | 1 (1) | 3 | 6 | 4759 | done |  |
| 06 15s upbeat music | zh | pass | 2/12 | 1 (1) | 3 | 6 | 4747 | done |  |
| 07 SFX + voiceover as audio cards | en | pass | 3/12 | 2 (2) | 4 | 8 | 6588 | done |  |
| 07 SFX + voiceover as audio cards | zh | pass | 3/12 | 2 (2) | 4 | 8 | 6542 | done |  |
| 08 edit elements, then title -> SALE | en | pass | 3/12 | 1 (1) | 4 | 8 | 6533 | done |  |
| 08 edit elements, then title -> SALE | zh | pass | 3/12 | 1 (1) | 4 | 8 | 6485 | done |  |
| 09 single image to 3D | en | pass | 2/12 | 1 (1) | 3 | 6 | 4739 | done |  |
| 09 single image to 3D | zh | pass | 2/12 | 1 (1) | 3 | 6 | 4724 | done |  |
| 10 poster with brand kit font + colors | en | pass | 4/12 | 1 (1) | 5 | 10 | 8793 | done |  |
| 10 poster with brand kit font + colors | zh | pass | 4/12 | 1 (1) | 5 | 10 | 8763 | done |  |
| 11 multi-turn 'brighter': 1 new image edited from the untouched original | en | pass | 5/12 | 2 (2) | 7 | 10 | 11920 | done |  |
| 11 multi-turn 'brighter': 1 new image edited from the untouched original | zh | pass | 5/12 | 2 (2) | 7 | 10 | 11872 | done |  |
| 12 PPTX deck, editable mode | en | pass | 2/12 | 1 (1) | 3 | 6 | 4849 | done |  |
| 12 PPTX deck, editable mode | zh | pass | 2/12 | 1 (1) | 3 | 6 | 4831 | done |  |
| 13 over threshold -> Cancel: no charge, no retry | en | pass | 2/12 | 0 (0) | 3 | 6 | 4846 | done |  |
| 13 over threshold -> Cancel: no charge, no retry | zh | pass | 2/12 | 0 (0) | 3 | 6 | 4814 | done |  |
| 14 no key: immediate message, no model call | en | pass | 0/12 | 0 (0) | 0 | 0 | 0 | error |  |
| 14 no key: immediate message, no model call | zh | pass | 0/12 | 0 (0) | 0 | 0 | 0 | error |  |
| 15-429 fault injection: LLM 429, retries exhausted | en | pass | 1/12 | 1 (1) | 4 | 4 | 1493 | error |  |
| 15-429-retry fault injection: LLM 429 retried x2 (P1-a) | en | pass | 2/12 | 1 (1) | 5 | 6 | 4934 | done |  |
| 15-429-retry fault injection: LLM 429 retried x2 (P1-a) | zh | pass | 2/12 | 1 (1) | 5 | 6 | 4930 | done |  |
| 15-429 fault injection: LLM 429, retries exhausted | zh | pass | 1/12 | 1 (1) | 4 | 4 | 1491 | error |  |
| 15-500 fault injection: LLM 500, retries exhausted | en | pass | 1/12 | 1 (1) | 4 | 4 | 1493 | error |  |
| 15-500-retry fault injection: LLM 500 retried x2 (P1-a) | en | pass | 2/12 | 1 (1) | 5 | 6 | 4934 | done |  |
| 15-500-retry fault injection: LLM 500 retried x2 (P1-a) | zh | pass | 2/12 | 1 (1) | 5 | 6 | 4930 | done |  |
| 15-500 fault injection: LLM 500, retries exhausted | zh | pass | 1/12 | 1 (1) | 4 | 4 | 1491 | error |  |
| 15-hardcap #391 hard cap 300: stops and says so | en | pass | 300/300 | 0 (0) | 300 | 600 | 3293305 | error |  |
| 15-hardcap #391 hard cap 300: stops and says so | zh | pass | 300/300 | 0 (0) | 300 | 600 | 3291195 | error |  |
| 15-readonly #391 read-only steps are not 'no progress' up to 8 in a row, then stuck | en | pass | 18/40 | 0 (0) | 18 | 37 | 38673 | error |  |
| 15-readonly #391 read-only steps are not 'no progress' up to 8 in a row, then stuck | zh | pass | 18/40 | 0 (0) | 18 | 37 | 38327 | error |  |
| 15-steps120 #391 a 120-step task completes (no 80 cap) | en | pass | 120/300 | 0 (0) | 121 | 242 | 638188 | done |  |
| 15-steps120 #391 a 120-step task completes (no 80 cap) | zh | pass | 120/300 | 0 (0) | 121 | 242 | 637331 | done |  |
| 15-timeout fault injection: LLM timeout, retries exhausted | en | pass | 1/12 | 1 (1) | 4 | 4 | 1493 | error |  |
| 15-timeout-retry fault injection: LLM timeout retried x2 (P1-a) | en | pass | 2/12 | 1 (1) | 5 | 6 | 4934 | done |  |
| 15-timeout-retry fault injection: LLM timeout retried x2 (P1-a) | zh | pass | 2/12 | 1 (1) | 5 | 6 | 4930 | done |  |
| 15-timeout fault injection: LLM timeout, retries exhausted | zh | pass | 1/12 | 1 (1) | 4 | 4 | 1491 | error |  |
| 16-sc-pass #383 4 images generated, 4 on the canvas -> done, self_check pass | en | pass | 2/12 | 4 (4) | 3 | 6 | 4946 | done |  |
| 16-sc-pass #383 4 images generated, 4 on the canvas -> done, self_check pass | zh | pass | 2/12 | 4 (4) | 3 | 6 | 4933 | done |  |
| 17-sc-missing #383 4 generated but only 2 still on the canvas -> no done claim, missing 2 | en | pass | 3/12 | 4 (4) | 5 | 10 | 8682 | error |  |
| 17-sc-missing #383 4 generated but only 2 still on the canvas -> no done claim, missing 2 | zh | pass | 3/12 | 4 (4) | 5 | 10 | 8634 | error |  |
| 18-sc-allfail #383 every generation fails -> the reason, never 'done' | en | pass | 2/12 | 4 (4) | 4 | 8 | 6793 | error |  |
| 18-sc-allfail #383 every generation fails -> the reason, never 'done' | zh | pass | 2/12 | 4 (4) | 4 | 8 | 6752 | error |  |
| 19-sc-claim #383 'done, 4 images' with zero tool calls -> rewritten | en | pass | 0/12 | 0 (0) | 2 | 4 | 3033 | error |  |
| 19-sc-claim #383 'done, 4 images' with zero tool calls -> rewritten | zh | pass | 0/12 | 0 (0) | 2 | 4 | 2998 | error |  |
| 20-sc-qa #383 pure Q&A -> no self-check | en | pass | 0/12 | 0 (0) | 1 | 2 | 1495 | done |  |
| 20-sc-qa #383 pure Q&A -> no self-check | zh | pass | 0/12 | 0 (0) | 1 | 2 | 1483 | done |  |
