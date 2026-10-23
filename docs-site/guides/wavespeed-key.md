---
title: "WaveSpeed Key"
description: "Add your WaveSpeed API key, check your balance and see how costs are shown."
---

# WaveSpeed Key

Every model in ComfyArt runs on [WaveSpeed](https://wavespeed.ai) and is billed to your own WaveSpeed account. Canvas editing, exports and the video editor export are local and need no key.

## Add a key

1. Create an API key at [wavespeed.ai](https://wavespeed.ai).
2. Either open **Settings → WaveSpeed API key** and paste it, or set it in the environment before starting ComfyUI:
   ```bash
   export WAVESPEED_API_KEY=ws_xxxxxxxxxxxxxxxx   # placeholder, not a real key
   ```

## How the key is handled

- `WAVESPEED_API_KEY` in the environment takes priority over a key typed in the UI; the UI then cannot change it.
- A new key is checked with WaveSpeed's free balance call (`GET /api/v3/balance`). Invalid keys are rejected.
- A key typed in the UI is saved on the backend in a config file in the ComfyUI user directory with mode `600`. It is never logged, and the browser only ever sees the last 4 characters (`••••••••abcd`).
- With no key, the canvas works normally and model features tell you that cloud generation is off.

## Balance and costs

- The chip in the top bar shows your WaveSpeed balance; click it to open the key settings.
- Before any model runs, its estimated cost is shown next to **Send** (for example `≈$0.039`). The estimate uses WaveSpeed's own price quote for the exact inputs, including the number of reference images.
- Jobs estimated at **$0.50 or more** ask you to confirm first, and the confirm dialog shows the same price.
- You pay WaveSpeed directly. ComfyArt adds no fee.
