# QA HOLD @ a8641d6c (#764 / Closes #763)

Tip head: `a8641d6ce307a41959db392ab13fe95ee8497392` (feature `2746631f` + tests-only `a8641d6c`).
Lovart RA: `53446c23`. Engineer SBS: `23a32194` `763/2746631f/`.

## Verdict: HOLD (EL: @ in #763 scope; tip incomplete)

### Missing / gaps
1. **@ popup** — tip did not land Lovart-aligned @ (Assets/Model, placeholder → search, no side reference chip). No tip @ delta / no engineer @ SBS this tip. Target: `04-lovart-reference-at-menu-missing.png` / RA `53446c23` reference-at-menu.
2. **Timeline 「向你提问」** — still used as a status row in live q shot (`02-ours-q-zh-light-timeline-askyou.png`) despite docked ask card.
3. **Ask card D / Submit** — D should be full Other input row (Lovart `Other (type your answer)...`); live zh shows truncated 「其他...」. Submit must stay disabled until a user choice (defaults/recommended must not soft-enable).
4. Stop + docked ask still must match Lovart on the next tip (see 01 / 03).

### Already looking OK on this tip (keep)
- Stop = same circular primary → black circle + white square while running (`01`)
- No 「工作中 / 终止」 bar
- Ask card docks above composer; voice/send while waiting
- Single-question: no `1 of N` pager
- EN idle placeholder aligned

### Suites
- `tests/test_composer_stop_763.py`: 4 passed
- tip delta vs main: A test_composer_stop_763.py; M #423/#437 only; no deleted tests
