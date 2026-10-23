---
title: "Generate"
description: "Image and video generators with references, color palettes, base images and storyboards."
---

# Generate

There are three ways to generate:

::: tip WaveSpeed Key and cost
Image and video generation: these run on WaveSpeed cloud models, so they need a [WaveSpeed Key](/guides/wavespeed-key). The estimated cost is shown next to **Send** (or on the button) before anything runs, and jobs of $0.50 or more ask you to confirm. See [Models and costs](/guides/models).
:::

- **On the canvas**: click **Image Generation** in the bottom bar (its arrow switches to video or [audio](/guides/audio-3d)). A generator card appears with a prompt box under it, and the card already has the size of the image it will make.
- **From the chat**: switch the mode under the chat box to **Image** or **Video**, type a prompt and send. No agent is involved.
- **On a selection**: select images on the canvas and press **Shift+Enter** (or **Chat** in the selection toolbar). See [Chat on the canvas](#chat-on-the-canvas).

![Image generator card with a prompt](/images/generator.webp)

Results land on the canvas next to the card; the card shows a progress ring while WaveSpeed works.

## Image settings

Click the settings button (for example `1K · 1:1 · 1 image(s)`) to open **Image Settings**:

![Image settings](/images/image-settings.webp)

| Option | Values |
|---|---|
| Resolution | 1K, 2K or a custom width and height |
| Aspect ratio | 1:1, 3:2, 2:3, 4:3, 3:4, 16:9, 9:16, 4:5, 5:4, 21:9 |
| Count | 1 to 4 images per run |
| Quality | Turbo, Standard, High Quality |
| Style | None, Photo, Cinematic, Illustration, 3D, Anime, Minimal, Retro |
| Transparent background | on or off |

Put text that should appear in the image in quotes. The default image models render both Chinese and English text well.

## Advanced

The **Advanced** button next to the settings holds:

- **Seed**: shown when the selected WaveSpeed model accepts one. Leave **Random** on, or untick it to type a seed; every result's **Info** shows the seed it used.
- **Negative prompt**: shown only for models that accept it.

## Models
The model picker lists the curated WaveSpeed image models and tags the ones that accept references. **Auto** (on by default) uses the default model. See [Models and costs](/guides/models) for the full list.

Recommended image models (the first is the default):

- `openai/gpt-image-2.5-flare/text-to-image`
- `openai/gpt-image-2/text-to-image`
- `google/nano-banana-2.1/text-to-image`
- `bytedance/seedream-v5.0-pro`
- `openai/gpt-image-2.5-sunburst/text-to-image`
- `alibaba/qwen-image-3.0/text-to-image`

<!-- TODO(#35 tester table): add a "good for" column once the tester's comparison is in. -->

## References

Click **Reference image** to attach references, up to the limit of the selected model. Each extra reference can change the price, and the estimate next to **Send** already counts them. The menu offers:

- **Upload image** from your computer.
- **Choose from Assets**: files you uploaded or generated before.
- **Choose from My Assets**: images and logos saved in your [library](/guides/assets) items.
- **Pick on canvas**: the prompt box hides and a bar asks you to click an image on the canvas. Click empty canvas, press Esc or **Cancel** to stop.

Each reference has a mode:

- **Content, style, composition**: what the result should follow.
- **Structure modes**: line art, depth, pose, soft edge and more. They run on a WaveSpeed ControlNet model with these controls:
  - **Reference strength**.

  - **Detail**: preprocessor resolution (512, 1024 or 2048), for modes that have one.
  - **Fit**: crop the control map to the output's aspect ratio, or stretch it.
  - **Preview control map**: runs only the preprocessor and shows the result, so you can check the line art or pose before generating. The preview dims when a setting changes; click **Extract again**.

References are numbered ("image 1", "image 2") in the order they are used. If the selected model does not accept references, or not that mode, the chip is greyed out with the reason and generation still runs without it.

## Chat on the canvas

Select one or more images, videos or audio clips and press **Shift+Enter**, or click **Chat** in the image or multi-selection toolbar. A box opens under the selection with the selected items already in it as `[Image 1]`, `[Image 2]`…

- Keep typing, and click more items on the canvas while you type: each one is dropped in at the cursor, so you can write "put [Image 1] on [Image 2]" in one go. Removing a thumbnail renumbers the tags.
- **Generate** (or Enter) makes an image right away with the items as references, in the order of their tags. **Send to Agent** hands the same request and items to the [Agent](/guides/agent).
- Esc or × closes the box.

### One by one

With two or more items, **One by one** runs the request once per item instead of once for all of them. Each thumbnail then shows **Each** or **Shared**: items marked Shared go into every run. For "put this coffee cup on each of these tables", mark the cup Shared and you get one picture per table, each placed under its table. The same toggle is in the chat box under the Agent panel; with the Agent it tells the agent to make one result per item.

## Color reference

**Color reference** adds a palette. The colors are named in the prompt, and on models that accept references a small color-swatch image is attached as well, so the result picks up the palette without copying any layout. Hover a color and click × to remove it.

## Base image

**Base image** turns generation into image-to-image: pick an image on the canvas and set how much the result may change (0–100).

## Video generation

Switch the generator, or the chat mode, to **Video**. The video settings hold:

![Video settings opened from the chat box](/images/composer-video.webp)

- **Aspect ratio** 16:9, 9:16, 1:1, 4:3, 3:4 or 21:9; **Resolution** 768p or 1080p; **Duration** 5, 10 or 15 seconds.
- **Camera motion**: Auto, Static, Push In, Pull Out, Orbit, Follow, Handheld, Pan Left / Right, Tilt Up / Down.

The video generator has five modes: **First/last frame**, **References** (reference to video with images, videos and audio), **Motion control**, **Lip sync** and **Storyboard**. More in [Video](/guides/video).
