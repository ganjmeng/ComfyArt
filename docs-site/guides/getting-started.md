---
title: "Getting started"
description: "Install ComfyArt, add your WaveSpeed Key, open the canvas and make your first image."
---

# Getting started

ComfyArt is a ComfyUI plugin. ComfyUI stays the host and does not need a GPU: every model runs on [WaveSpeed](https://wavespeed.ai) with your own API key.

## Install

### Option A: one command

From a clone of this repository, `scripts/start.sh` installs ComfyUI (CPU only), links ComfyArt into `custom_nodes/` and starts it:

```bash
git clone https://github.com/ganjmeng/ComfyArt
cd ComfyArt
./scripts/start.sh
```

Without a WaveSpeed Key it still starts, and only warns that cloud generation is off.

### Option B: into an existing ComfyUI

1. Clone into `ComfyUI/custom_nodes/`:
   ```bash
   cd ComfyUI/custom_nodes
   git clone https://github.com/ganjmeng/ComfyArt
   ```
2. Install the Python requirements in the Python environment that runs ComfyUI. This only adds `pypdfium2` for PDF uploads; text recognition runs on WaveSpeed, so there is no local OCR package.
   ```bash
   pip install -r ComfyArt/requirements.txt
   ```
   The video editor export needs `ffmpeg` on PATH.
3. Restart ComfyUI and open [http://127.0.0.1:8188/comfyart/](http://127.0.0.1:8188/comfyart/).

## Add your WaveSpeed Key

Open **Settings → WaveSpeed API key** and paste your key, or set `WAVESPEED_API_KEY` before starting ComfyUI. See [WaveSpeed Key](/guides/wavespeed-key). The balance chip in the top bar shows your remaining WaveSpeed balance.

## Make your first image

1. On the [home page](/guides/home), click **New Project** for an empty canvas.
2. Pick the image generator on the left toolbar, type a prompt and look at the estimated cost next to **Send**.
3. Click **Send**. Jobs estimated at $0.50 or more ask you to confirm first. The result lands on the canvas.

## Next

- **[Generate](/guides/generate)**: references, color palettes, base images and video.
- **[Agent](/guides/agent)**: turn on the agent and let it plan and build designs for you.
- **[Models and costs](/guides/models)**: which WaveSpeed model each feature uses.
