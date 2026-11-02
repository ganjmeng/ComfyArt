# #608 → #78 tip-pin — Lucide icons (sidebar / tools / canvas)

**Branch:** `feat/608-lucide-icons` · **Asia/Shanghai** · Issue #608  
**Tip-pin:** absolute `raw.githubusercontent.com` URLs live in the PR body (exact tip SHA). Do not treat an older tip in chat history as current.  
**PM lock:** Lucide (`lucide-react`, ISC). Design shortlist → Lucide. No competitor SVG assets or brand strings in `src/`.

## Scope

| Surface | Icons API keys (metaphor → Lucide) |
|---------|--------------------------------------|
| Sidebar rail | plus→Plus, home→Home, folder→Folder, skill→FileText, assets→Layers, bell→Bell, sparkles→Sparkles, exit→ExternalLink, settings→Settings, panelLeft→PanelLeft |
| Dock / utility | select→MousePointer2, comment→MessageCircle, doodle→Pencil, upload→Paperclip, genImage→ImagePlus, genVideo→Video, music→Music, plus→Plus |
| Canvas tools | layers→Layers, files→Files, map→Map |

`strokeWidth` default **1.75** (`LUCIDE_STROKE`); keep `.ca-icon` size tokens. Custom brand marks kept: LoomiMono, sparkleImage, searchFolder, quick, memory*, mem*.

## LEFT = ours (AFTER) — live dist zh-light 1280×800

Harness: `harness/shoot.py` (Playwright vs `app_url`, mock $0).

| File | Shows |
|------|-------|
| `left-ours/AFTER-sidebar-expanded-icons-zh-light.png` | Expanded rail with Lucide nav icons |
| `left-ours/AFTER-tools-strip-zh-light.png` | Home 「实用工具」strip |
| `left-ours/AFTER-canvas-toolbar-zh-light.png` | Canvas Dock + `.ca-tools` toolbar sample |

## @design
Please re-sign after visual check on tip (Lucide line icons vs prior hand SVG; no competitor assets).
