# #78 Question card assets for PR #338 · issue #337

- tip: `fb56d4f` (`fix/p1-337-question-other-input`) — tests on tip; product behavior from `54baf74`
  https://github.com/ganjmeng/ComfyArt/pull/338

## sidebar-live/ (this pin) — tip dist AgentPanel + seeded ask

**Honest label:** `Playwright + tip dist AgentPanel (.ca-agent ~400px) + seeded bot_asks kind=question · NOT full Electron/ComfyUI desktop.`

Production React QuestionCard inside real agent sidebar chrome (composer + chat history + tip CSS/JS). Stubbed aiohttp, no live LLM.

See `sidebar-live/NOTES.md`. Closer than rejected chat-shell `after-live/` @ `83cc4ea`.

### States captured (light + dark)
| id | state |
|----|--------|
| `*-empty` | empty other · flat · submit disabled |
| `*-other` | filled other soft-on (`包装袋`) · A–D cleared |
| `*-keep` | A soft-on · other text **kept** after A–D click |
| `*-soft` | B soft-select · other empty |

## after-live/ (prior REJECTED pin 83cc4ea) — chat-shell harness

**Honest label:** `chat-shell harness · tip 54baf74 · ~300 left chat column · not Electron/ComfyUI runtime.`

Formal COMMENT HOLD by EL/design/test/PM — do **not** claim as live Electron sidebar.


## after/ (prior pin edf1ea9)
tip-CSS-only harness at ~300 column (floating card). Superseded for #78 direction by **after-live/**.

## lovart-live/
Product signed-in Lovart light UI (NOTES 00–07). Dark Lovart N/A this pass.

## compare/
- `shell-*-vs-lovart0*.png` — chat-shell ‖ Lovart live empty / filled / keep / soft
- `shell-card-*-vs-lovart0*.png` — full sidebar stage ‖ Lovart full card
- `shell-other-light-vs-dark.png` — shell light ‖ dark filled other
- prior `tip-*-vs-lovart*.png` kept for history

## Interaction locked (tip matches)
1. Fill other → clears A–D soft-select; other soft-on
2. Click A–D → **keeps other text**; soft-select moves only
3. Focus nonempty other → steals soft-select back
4. Nonempty other enables primary; empty placeholder does not
5. letter + textarea; flat unselected; no border/underline

## #78 sign-off status
**NOT product PASS / NOT formal #78 sign-off.**  
Chat-shell is a step toward sidebar-embedded evidence product will accept; remaining gap = real ComfyUI/Electron runtime with injected `kind=question` + `allow_other` ask in the live agent sidebar (light+dark), then product proofread before Ashley DM.
