# Agent regression (#231)

Mocks only, $0. pass: 42

| case | lang | result | steps/limit | paid (exp) | LLM req | msgs | tokens | status | note |
|---|---|---|---|---|---|---|---|---|---|
| 01 t2i 1 image with size + style | en | pass | 2/12 | 1 (1) | 3 | 6 | 2861 | done |  |
| 01 t2i 1 image with size + style | zh | pass | 2/12 | 1 (1) | 3 | 6 | 2847 | done |  |
| 02 t2i exactly 4 images | en | pass | 2/12 | 4 (4) | 3 | 6 | 2861 | done |  |
| 02 t2i exactly 4 images | zh | pass | 2/12 | 4 (4) | 3 | 6 | 2849 | done |  |
| 03 selected image: change background to beach (image edit) | en | pass | 3/12 | 1 (1) | 4 | 8 | 3971 | done |  |
| 03 selected image: change background to beach (image edit) | zh | pass | 3/12 | 1 (1) | 4 | 8 | 3946 | done |  |
| 04 t2v 5s | en | pass | 2/12 | 1 (1) | 3 | 6 | 2677 | done |  |
| 04 t2v 5s | zh | pass | 2/12 | 1 (1) | 3 | 6 | 2660 | done |  |
| 05 i2v from the selected image | en | pass | 3/12 | 1 (1) | 4 | 8 | 3790 | done |  |
| 05 i2v from the selected image | zh | pass | 3/12 | 1 (1) | 4 | 8 | 3767 | done |  |
| 06 15s upbeat music | en | pass | 2/12 | 1 (1) | 3 | 6 | 2674 | done |  |
| 06 15s upbeat music | zh | pass | 2/12 | 1 (1) | 3 | 6 | 2662 | done |  |
| 07 SFX + voiceover as audio cards | en | pass | 3/12 | 2 (2) | 4 | 8 | 3810 | done |  |
| 07 SFX + voiceover as audio cards | zh | pass | 3/12 | 2 (2) | 4 | 8 | 3763 | done |  |
| 08 edit elements, then title -> SALE | en | pass | 3/12 | 1 (1) | 4 | 8 | 3753 | done |  |
| 08 edit elements, then title -> SALE | zh | pass | 3/12 | 1 (1) | 4 | 8 | 3705 | done |  |
| 09 single image to 3D | en | pass | 2/12 | 1 (1) | 3 | 6 | 2654 | done |  |
| 09 single image to 3D | zh | pass | 2/12 | 1 (1) | 3 | 6 | 2640 | done |  |
| 10 poster with brand kit font + colors | en | pass | 4/12 | 1 (1) | 5 | 10 | 5320 | done |  |
| 10 poster with brand kit font + colors | zh | pass | 4/12 | 1 (1) | 5 | 10 | 5288 | done |  |
| 11 multi-turn 'brighter': 1 new image edited from the untouched original | en | pass | 5/12 | 2 (2) | 7 | 10 | 7058 | done |  |
| 11 multi-turn 'brighter': 1 new image edited from the untouched original | zh | pass | 5/12 | 2 (2) | 7 | 10 | 7007 | done |  |
| 12 PPTX deck, editable mode | en | pass | 2/12 | 1 (1) | 3 | 6 | 2764 | done |  |
| 12 PPTX deck, editable mode | zh | pass | 2/12 | 1 (1) | 3 | 6 | 2747 | done |  |
| 13 over threshold -> Cancel: no charge, no retry | en | pass | 2/12 | 0 (0) | 3 | 6 | 2761 | done |  |
| 13 over threshold -> Cancel: no charge, no retry | zh | pass | 2/12 | 0 (0) | 3 | 6 | 2729 | done |  |
| 14 no key: immediate message, no model call | en | pass | 0/12 | 0 (0) | 0 | 0 | 0 | error |  |
| 14 no key: immediate message, no model call | zh | pass | 0/12 | 0 (0) | 0 | 0 | 0 | error |  |
| 15-429 fault injection: LLM 429, retries exhausted | en | pass | 1/12 | 1 (1) | 4 | 4 | 798 | error |  |
| 15-429-retry fault injection: LLM 429 retried x2 (P1-a) | en | pass | 2/12 | 1 (1) | 5 | 6 | 2850 | done |  |
| 15-429-retry fault injection: LLM 429 retried x2 (P1-a) | zh | pass | 2/12 | 1 (1) | 5 | 6 | 2845 | done |  |
| 15-429 fault injection: LLM 429, retries exhausted | zh | pass | 1/12 | 1 (1) | 4 | 4 | 796 | error |  |
| 15-500 fault injection: LLM 500, retries exhausted | en | pass | 1/12 | 1 (1) | 4 | 4 | 798 | error |  |
| 15-500-retry fault injection: LLM 500 retried x2 (P1-a) | en | pass | 2/12 | 1 (1) | 5 | 6 | 2850 | done |  |
| 15-500-retry fault injection: LLM 500 retried x2 (P1-a) | zh | pass | 2/12 | 1 (1) | 5 | 6 | 2845 | done |  |
| 15-500 fault injection: LLM 500, retries exhausted | zh | pass | 1/12 | 1 (1) | 4 | 4 | 796 | error |  |
| 15-steps80 80-step limit | en | pass | 80/80 | 0 (0) | 80 | 160 | 298650 | error |  |
| 15-steps80 80-step limit | zh | pass | 80/80 | 0 (0) | 80 | 160 | 298450 | error |  |
| 15-timeout fault injection: LLM timeout, retries exhausted | en | pass | 1/12 | 1 (1) | 4 | 4 | 798 | error |  |
| 15-timeout-retry fault injection: LLM timeout retried x2 (P1-a) | en | pass | 2/12 | 1 (1) | 5 | 6 | 2850 | done |  |
| 15-timeout-retry fault injection: LLM timeout retried x2 (P1-a) | zh | pass | 2/12 | 1 (1) | 5 | 6 | 2845 | done |  |
| 15-timeout fault injection: LLM timeout, retries exhausted | zh | pass | 1/12 | 1 (1) | 4 | 4 | 796 | error |  |
