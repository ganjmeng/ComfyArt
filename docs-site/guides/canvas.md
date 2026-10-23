---
title: "The canvas"
description: "Layout, artboards, layers, comments, history and export."
---

# The canvas

The canvas is an infinite board built on [tldraw](https://tldraw.dev). Everything you make (images, videos, audio, text, shapes, artboards, web pages, 3D models) lives on it, and everything stays editable.

![ComfyArt with the Agent panel on the left and an artboard on the canvas](/images/agent-result.webp)

## Layout

::: tip WaveSpeed Key and cost
Running a comment as an edit, and click-to-edit: these run on WaveSpeed cloud models, so they need a [WaveSpeed Key](/guides/wavespeed-key). The estimated cost is shown next to **Send** (or on the button) before anything runs, and jobs of $0.50 or more ask you to confirm. See [Models and costs](/guides/models).
:::

- **Left**: the [Agent](/guides/agent) panel. Move it to the right from the settings menu, maximize it, or collapse it.
- **Top**: the project menu and name, **Reference** and **My Assets**, page tabs (double-click a tab to rename it), **Export**, all comments and settings.
- **Bottom**: tools (Select, Comment, Draw, Insert) and the generate button, whose arrow switches between image, video and audio generation.
- **Bottom right**: background color, Layers, Generated Files, minimap and zoom.

## Working with shapes

- **Text and shapes**: rich text, any font, gradient and image fills, the pen tool and boolean operations. See [Text, shapes and paths](/guides/design).
- **Draw** with any color and width, and sticky notes from the Insert menu.
- **Uploads**: drop images, videos, audio, PDFs (each page becomes an image in a frame), Lottie animations, 3D models (GLB, GLTF, OBJ, FBX, STL, PLY) and HTML widgets.

Selecting several shapes shows a toolbar to tidy up, group, merge layers, combine shapes with **Boolean**, align, distribute and download (including PSD export).

![Multi-select toolbar](/images/multi-select.webp)

The right-click menu covers clipboard, order, group, flip, lock, replace, send to generator, batch rename and export.

## Artboards

Artboards (frames) hold a design at an exact size. Select one for its toolbar:

![Artboard toolbar above the Spring menu artboard](/images/frame-toolbar.webp)

- **Name**, width and height, each **Fixed** or hugging its content, and **Lock aspect ratio**.
- **Size presets**: Instagram, Instagram portrait, Story / TikTok, YouTube thumbnail, Presentation 16:9, Desktop web, Mobile, A4 and A4 landscape.
- **Fill, stroke and corners**: the artboard's background color, border and corner radius.
- **Auto** layout re-flows the children when they change; **Manual** leaves them where you put them. **Hug Contents** shrinks the artboard to fit.
- **Generate** straight into the artboard, **Re-render** an [Edit Elements](/guides/elements-mockups) artboard, play the artboards as a fullscreen slideshow, download them as a ZIP or export.

![Artboard size presets](/images/size-presets.webp)

## Layers

The **Layers** panel lists everything on the page. Recent results sit in a **History** strip at the top.

![Layers panel next to the canvas](/images/layers-panel.webp)

- Drag rows to reorder them or to move a shape into or out of an artboard.
- Double-click a name to rename it; collapse or expand artboards and groups.
- Click to select, Ctrl + click to add, Shift + click to select a range.
- Hide and lock toggles on each row.

Split layer results (see [Image tools](/guides/image-tools#split-layers)) and Edit Elements results show up as an artboard with one row per layer.

## Comments

Use the **Comment** tool to pin feedback on the canvas: click a point, or draw a lasso or a box around an area. A comment on an image can be run as an edit, or sent to the chat; the Agent receives the image and the exact region you marked. The comments panel lists all comments with an open / done filter, and can add them to the chat or run them all at once.

**Touch edit**: Ctrl + click an image (or hover and press C) to mark an object, then describe the change. Shift + click adds more mark points.

## History and export

- Projects save automatically. **Canvas history** in the project menu keeps snapshots you can restore.
- Export a selection or a page as PNG, JPG or PDF at any scale, or as **PPTX**: one slide per artboard or page, either as images or with editable text (including mixed styles), images and shapes.
- If the same project is open in another tab, ComfyArt warns you and stops saving in the stale tab so you do not overwrite newer work.
