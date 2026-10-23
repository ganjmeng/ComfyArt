---
title: "Home and projects"
description: "Start a design from the home page, manage projects and change language, theme and layout."
---

# Home and projects

## Home

Open [http://127.0.0.1:8188/comfyart/](http://127.0.0.1:8188/comfyart/) to land on the home page.

![ComfyArt home page](/images/home.webp)

- **What do you want to design?** Type a request and send it. ComfyArt creates a project and hands the request to the [Agent](/guides/agent). Attach images with **+** or by dropping them on the box, or switch the mode to Image or Video to generate straight away.
- **Help me make:** quick starts (Social media, E-commerce, Brand, Creative, Website) fill in the first half of a prompt for you.
- **Recent projects** shows your latest canvases; **View all** opens the project library.
- **Start from a skill** lists the built-in skills and your own (marked *Mine*). Picking one opens a new project with that skill attached.

::: tip WaveSpeed Key and cost
Starting a design from a prompt or a skill: these run on WaveSpeed cloud models, so they need a [WaveSpeed Key](/guides/wavespeed-key). The estimated cost is shown next to **Send** (or on the button) before anything runs, and jobs of $0.50 or more ask you to confirm. See [Models and costs](/guides/models).
:::

The rail on the left has **New Project**, **Home**, **Projects** and the settings menu.

## Projects

![Project library](/images/projects.webp)

The project library shows every project with a preview of its canvas. From a card's menu you can **Pin to top**, rename, **Duplicate** (chats are not copied) or delete it. Use **Select** to pick several (or **Select all**) and delete them together. Deleting a project removes its canvas, chats and saved versions; generated files stay in ComfyUI's output folder.

Each project is a URL, `/comfyart/?project=<id>`, and is saved, with its snapshot history, in ComfyArt's SQLite database (`user/__comfyart/data.db`). Projects from older versions, which were JSON files under `comfyart/projects/`, are imported the first time you open ComfyArt after updating; the old files stay where they were. A link to a project that does not exist (deleted, or a typo) shows **Project not found** with buttons to the project library and a new project, instead of opening an empty canvas.

## Inside a project

Click the logo at the top left of a project for the project menu.

![Project menu](/images/project-menu.webp)

It jumps back to Home or Projects, creates, duplicates or deletes projects, opens **Canvas History** (restore a snapshot), imports an image, holds the undo, duplicate and zoom commands, opens the Agent's **Memory**, and links the project to a **Project Brand Kit**. The Agent receives the linked kit with every message.

Projects save automatically about a second after each change. The label next to the project name shows **Saving…** or **Saved** (hover for the time). If a save fails it turns into **Save failed · Retry**; click it to try again. Closing the tab while a change is not saved yet asks you to confirm.

## Settings

The gear button (top right in a project, bottom left on Home) opens the settings menu.

![Settings menu](/images/ours/settings-menu-en.png)

| Setting | Options |
|---|---|
| Language | 中文 or English, switched instantly |
| Theme | Light, Dark or Follow System |
| WaveSpeed API key | add or replace your [WaveSpeed Key](/guides/wavespeed-key) |
| User Guide | opens this documentation site in the current interface language |
| Chat position | Agent panel on the left or the right |
| Keyboard Shortcuts | the full shortcut list (also on `?`) |
| System notifications in background | a browser notification when a task finishes while the tab is hidden |
