# Agent regression (#231)

Mocks only, $0. pass: 36, xfail: 6

| case | lang | result | steps/limit | paid (exp) | LLM req | msgs | tokens | status | note |
|---|---|---|---|---|---|---|---|---|---|
| 01 t2i 1 image with size + style | en | pass | 2/12 | 1 (1) | 3 | 6 | 2822 | done |  |
| 01 t2i 1 image with size + style | zh | pass | 2/12 | 1 (1) | 3 | 6 | 2807 | done |  |
| 02 t2i exactly 4 images | en | pass | 2/12 | 4 (4) | 3 | 6 | 2821 | done |  |
| 02 t2i exactly 4 images | zh | pass | 2/12 | 4 (4) | 3 | 6 | 2808 | done |  |
| 03 selected image: change background to beach (image edit) | en | pass | 3/12 | 1 (1) | 4 | 8 | 3917 | done |  |
| 03 selected image: change background to beach (image edit) | zh | pass | 3/12 | 1 (1) | 4 | 8 | 3893 | done |  |
| 04 t2v 5s | en | pass | 2/12 | 1 (1) | 3 | 6 | 2636 | done |  |
| 04 t2v 5s | zh | pass | 2/12 | 1 (1) | 3 | 6 | 2619 | done |  |
| 05 i2v from the selected image | en | pass | 3/12 | 1 (1) | 4 | 8 | 3736 | done |  |
| 05 i2v from the selected image | zh | pass | 3/12 | 1 (1) | 4 | 8 | 3714 | done |  |
| 06 15s upbeat music | en | pass | 2/12 | 1 (1) | 3 | 6 | 2635 | done |  |
| 06 15s upbeat music | zh | pass | 2/12 | 1 (1) | 3 | 6 | 2621 | done |  |
| 07 SFX + voiceover as audio cards | en | pass | 3/12 | 2 (2) | 4 | 8 | 3755 | done |  |
| 07 SFX + voiceover as audio cards | zh | pass | 3/12 | 2 (2) | 4 | 8 | 3708 | done |  |
| 08 edit elements, then title -> SALE | en | pass | 3/12 | 1 (1) | 4 | 8 | 3700 | done |  |
| 08 edit elements, then title -> SALE | zh | pass | 3/12 | 1 (1) | 4 | 8 | 3652 | done |  |
| 09 single image to 3D | en | pass | 2/12 | 1 (1) | 3 | 6 | 2615 | done |  |
| 09 single image to 3D | zh | pass | 2/12 | 1 (1) | 3 | 6 | 2600 | done |  |
| 10 poster with brand kit font + colors | en | pass | 4/12 | 1 (1) | 5 | 10 | 5253 | done |  |
| 10 poster with brand kit font + colors | zh | pass | 4/12 | 1 (1) | 5 | 10 | 5221 | done |  |
| 11 multi-turn 'brighter': 1 new image edited from the untouched original | en | pass | 5/12 | 2 (2) | 7 | 10 | 6851 | done |  |
| 11 multi-turn 'brighter': 1 new image edited from the untouched original | zh | pass | 5/12 | 2 (2) | 7 | 10 | 6801 | done |  |
| 12 PPTX deck, editable mode | en | pass | 2/12 | 1 (1) | 3 | 6 | 2724 | done |  |
| 12 PPTX deck, editable mode | zh | pass | 2/12 | 1 (1) | 3 | 6 | 2707 | done |  |
| 13 over threshold -> Cancel: no charge, no retry | en | pass | 2/12 | 0 (0) | 3 | 6 | 2719 | done | refused retry step shows success: to fix in #232 |
| 13 over threshold -> Cancel: no charge, no retry | zh | pass | 2/12 | 0 (0) | 3 | 6 | 2689 | done | refused retry step shows success: to fix in #232 |
| 14 no key: immediate message, no model call | en | pass | 0/12 | 0 (0) | 0 | 0 | 0 | error |  |
| 14 no key: immediate message, no model call | zh | pass | 0/12 | 0 (0) | 0 | 0 | 0 | error |  |
| 15-429 fault injection: LLM 429 | en | pass | 1/12 | 1 (1) | 2 | 4 | 784 | error | baseline, flips in P1-a #232 |
| 15-429-retry fault injection: LLM 429 retried x2 (P1-a) | en | xfail | 1/12 | 1 (1) | 2 | 4 | 784 | error | P1-a #232 |
| 15-429-retry fault injection: LLM 429 retried x2 (P1-a) | zh | xfail | 1/12 | 1 (1) | 2 | 4 | 783 | error | P1-a #232 |
| 15-429 fault injection: LLM 429 | zh | pass | 1/12 | 1 (1) | 2 | 4 | 783 | error | baseline, flips in P1-a #232 |
| 15-500 fault injection: LLM 500 | en | pass | 1/12 | 1 (1) | 2 | 4 | 784 | error | baseline, flips in P1-a #232 |
| 15-500-retry fault injection: LLM 500 retried x2 (P1-a) | en | xfail | 1/12 | 1 (1) | 2 | 4 | 784 | error | P1-a #232 |
| 15-500-retry fault injection: LLM 500 retried x2 (P1-a) | zh | xfail | 1/12 | 1 (1) | 2 | 4 | 783 | error | P1-a #232 |
| 15-500 fault injection: LLM 500 | zh | pass | 1/12 | 1 (1) | 2 | 4 | 783 | error | baseline, flips in P1-a #232 |
| 15-steps80 80-step limit | en | pass | 80/80 | 0 (0) | 80 | 160 | 297570 | error |  |
| 15-steps80 80-step limit | zh | pass | 80/80 | 0 (0) | 80 | 160 | 297370 | error |  |
| 15-timeout fault injection: LLM timeout | en | pass | 1/12 | 1 (1) | 2 | 4 | 784 | error | baseline, flips in P1-a #232 |
| 15-timeout-retry fault injection: LLM timeout retried x2 (P1-a) | en | xfail | 1/12 | 1 (1) | 2 | 4 | 784 | error | P1-a #232 |
| 15-timeout-retry fault injection: LLM timeout retried x2 (P1-a) | zh | xfail | 1/12 | 1 (1) | 2 | 4 | 783 | error | P1-a #232 |
| 15-timeout fault injection: LLM timeout | zh | pass | 1/12 | 1 (1) | 2 | 4 | 783 | error | baseline, flips in P1-a #232 |
