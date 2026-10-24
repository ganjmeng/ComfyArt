# Agent logos

Each file is the vendor's own asset, unmodified (no recolor, no reshaping). It is shown at 16×16 in the composer mode menu only, to identify the tool.

| Tool | File | Source |
|---|---|---|
| ComfyArt (built-in) | — (our own `Icons.agent`) | this repo |
| Claude Code | claude-code.svg | https://claude.ai/favicon.svg (Anthropic, served by claude.ai) |
| Qwen Code | qwen-code.svg | https://github.com/QwenLM/qwen-code/blob/main/packages/desktop/bootstrap/qwen-code-logo.svg |
| OpenCode | opencode.svg / opencode-dark.svg | https://github.com/sst/opencode/tree/dev/packages/console/app/src/asset/brand (opencode-logo-light-square.svg / opencode-logo-dark-square.svg) |
| Codex | codex.svg | https://developers.openai.com/favicon.svg — OpenAI Blossom on blue disc, served by OpenAI's developer site. Checked first: https://openai.com/brand/ (guidelines only, no downloadable file; direct fetch 403) and github.com/openai/codex (only codex-cli-splash.png). |
| Gemini CLI | gemini-cli.svg | https://www.gstatic.com/lamda/images/gemini_sparkle_aurora_33f86dc0c0257da337c63.svg — Gemini spark, served by gemini.google.com. github.com/google-gemini/gemini-cli has no SVG logo. |
| DeepSeek Harness | deepseek.svg | https://github.com/deepseek-ai/DeepSeek-V2/blob/main/figures/logo.svg (the logo the DeepSeek-V3 README embeds). deepseek.com only exposes favicon.ico (raster). **Only the outer `viewBox` was changed** to frame the whale symbol (the wordmark falls outside); paths and colors are untouched — product to confirm this crop is acceptable or ask DeepSeek for a symbol-only file. |

Claude: https://www.anthropic.com/press-kit checked first; no direct SVG download (assets are behind a JS/request flow), so the allowed claude.ai favicon fallback is kept.

Disabled (undetected) rows: logos sit at 55% opacity; in dark theme a light 1px plate is placed behind the logo so dark marks (Qwen) stay visible. No logo is recolored.

Brand guidelines and legal review must be confirmed by product before shipping.
