---
title: "Image tools"
description: "Everything in the image toolbar: edit, upscale, split layers, remove background, erase, edit text, multi-angle and more."
---

# Image tools

Select an image to open its toolbar. **Quick Edit**, **Upscale**, **Remove Background** and **Eraser** sit on the bar; everything else is under **⋯**. Use **Customize Toolbar** at the bottom of that menu to choose which tools are pinned and whether their names are shown.

![Image toolbar with the More menu open](/images/image-toolbar.webp)

**Edit Elements** and **Mockup** have their own page, [Edit Elements and mockups](/guides/elements-mockups); **Image to 3D** is in [Audio and 3D](/guides/audio-3d).

::: tip WaveSpeed Key and cost
Every tool that shows a progress ring: these run on WaveSpeed cloud models, so they need a [WaveSpeed Key](/guides/wavespeed-key). The estimated cost is shown next to **Send** (or on the button) before anything runs, and jobs of $0.50 or more ask you to confirm. See [Models and costs](/guides/models).
:::

Tools that run a model place their result next to the original with a progress ring; the original is never overwritten. **Restore original** brings back an image's first version.

## Edit

| Tool | What it does |
|---|---|
| **Quick Edit** (Tab) | Describe a change in words. |
| **Edit Text** | Reads the text in the image and lists each line in an editable box; change any line and the image is redrawn with the same font, color and position. If no text is found, type the old and new text yourself. |
| **Inpaint** | Select an area with brush, eraser, lasso, box or smart select (WaveSpeed SAM3), invert or feather it, then describe what goes there. Optional styles: realistic, portrait photo, anime, illustration, 3D, game CG or keep original. |
| **Style Transfer** | Restyle with a preset or a reference image. |
| **Move Object** | Select an object, drag it to a new spot; the old spot is filled in. |
| **Multi-Angle** | Re-render the subject from another camera angle: presets (front, left, right, back, top, low angle, close-up, medium, wide) or sliders, or four angles at once. |
| **Expand** | Outpaint to a preset ratio (original, square, landscape, portrait, post, story, cover photo, profile photo, thumbnail) or by scale, with an optional prompt. |

## Clean up

| Tool | What it does |
|---|---|
| **Remove Background** | Cut out the subject with BiRefNet. |
| **Eraser** | Paint over something and a WaveSpeed eraser model fills it in. |
| **Smudge** | Push pixels around with a brush. |
| **Crop** | Drag the handles or type an exact size in pixels, with ratio presets for each platform. |
| **Flip & Rotate** | Flip horizontally or vertically and rotate by 90°, instantly in the browser. |
| **Adjust** | Light, color, detail and effects (below). |
| **Effects** | Opacity, shadow and blur. |

The brush tools (Eraser, Inpaint, Smudge) show the brush size as a circle under the pointer.

### Crop

![Crop bar with ratio presets](/images/crop-bar.webp)

The crop bar replaces the toolbar while you crop. Pick **Free**, **Original** or a preset (1:1 and 4:5 for Instagram, 3:4 for Xiaohongshu, 9:16 for Story and TikTok, 16:9 for YouTube, 2:3 for Pinterest, 3:2, 1.91:1 for Facebook and X), or type the width and height in pixels. **Reset** returns to the full image, **Done** applies.

### Adjust

![Adjust panel next to a poster](/images/adjust-panel.webp)

Four tabs: **Light** (exposure, contrast, highlights, shadows, whites, blacks), **Color** (saturation, vibrance, temperature, tint), **Detail** (clarity, sharpen, grain) and **Effects** (vignette, bloom, glamour). **Auto** picks values for you; hold **Hold to compare** to see the original.

Adjustments are non-destructive. ComfyArt keeps the original pixels and your slider values, so opening Adjust again starts from where you left off instead of stacking a second adjustment on top. **Reset** followed by **Apply** puts the untouched pixels back; your crop and flip stay.

## Upscale

Upscale 2× or 4×. **Faithful to original** uses 4x-UltraSharp; **Enhance details** redraws at the larger size with a style preset and a detail strength, adding new detail.

## Split layers

**Split Layers** separates an image into editable layers inside a frame, with a background layer underneath:

- **Auto Split** runs WaveSpeed's layer decomposition model and keeps the useful layers.
- **Custom Split** lets you draw boxes; WaveSpeed SAM3 cuts out the object in each box.
- **Separate Regions** works on any layer, including one that a split left with two things mixed together: draw one box around the part to pull out, adjust its edges, and that part becomes its own layer, cropped to its visible pixels. It is instant and runs no model.

After a split, the background is the original image with every split layer erased and filled in, so moving or hiding a layer reveals clean background instead of a duplicate.

## Text, vectors and info

- **Extract Text** copies the text in an image (OCR with WaveSpeed `paddle-ocr` or the Agent).
- **Vectorize** traces the image into an SVG. The canvas shows it as a bitmap rendered for the current zoom so it stays fast; downloads and exports keep the full SVG.
- **Generation Info** shows the prompt, model and settings; **Copy Prompt**, **Remix** (same prompt, new seed) and **Regenerate** are next to it.
- **View Larger** opens the preview lightbox; **Export** saves PNG, JPG or PDF.
