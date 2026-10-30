# #410 → #78 visual / audit evidence

Honest label: tip CSS harness (`AssistantBlocks` + `src/styles/{base,canvas,shell,overlays}.css`) — NOT full Electron / not live LLM / not WaveSpeed.

## Shots
`after/<scene>-{zh,en}-{light,dark}.png` for every scene in `tests/js/process410/main.tsx`.

Regenerate:

```bash
AUDIT410_SHOTS=docs/design/410/78/after \
  pytest tests/test_agent_loop_audit_410.py -k shoot -q
```

## Reference crops (neutral names)
| File | Source meaning |
|---|---|
| `reference/process-timeline-liked.png` | CN process rail: Thought → Skill ready → Thought → Searching the web |
| `reference/memory-updated-row-in-chat-light.png` | CN memory-updated row in chat |

PR body tip-pins `raw.githubusercontent.com` URLs to **branch HEAD**. Do not embed a tip SHA in this NOTES file.
