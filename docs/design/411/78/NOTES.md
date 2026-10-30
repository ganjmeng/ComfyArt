# #411 → #78 visual / audit evidence

Honest label: tip CSS harness (`SkillForm`/`SkillsDialog`/`Composer`/`Home`/`Arti` markup classes + tip CSS) — NOT full Electron / not live LLM / not WaveSpeed.

## Shots
`after/<scene>-{zh,en}-{light,dark}.png` for every scene in `tests/js/skills411/main.tsx`.

Regenerate:

```bash
AUDIT411_SHOTS=docs/design/411/78/after \
  pytest tests/test_skills_create_audit_411.py -k shoot -q
```

## Reference crops (neutral names)

| File | Source meaning (「reference」 UI) |
|---|---|
| `reference/skills-explore.png` | Skills Explore / community card wall |
| `reference/create-dropdown.png` | Create menu with Import skill entry |
| `reference/creator-chip.png` | Skill Creator chip / preloaded creator strip |
| `reference/creator-prefill.png` | Creator prefill / conversational create strip |
| `reference/personal-list.png` | Personal skills list |
| `reference/edit-dialog.png` | Edit skill dialog |
| `reference/import-dialog.png` | Import skill dialog (dropzone) |
| `reference/publish-dialog.png` | Publish skill dialog |
| `reference/slash-picker.png` | Slash skill picker |

Crops taken from design handoff packs under `docs/m2/handoff/…` and research shots; tip files use **neutral** names only. Never embed a tip SHA in this NOTES file — PR body tip-pins `raw.githubusercontent.com` URLs to **branch HEAD**.

## Deferred (not this PR)
Product UI redesign for G1–G9 → PM fix cards after 三签. Real-call reuse quality → EL $5 budget. Arti memory module → #430.
