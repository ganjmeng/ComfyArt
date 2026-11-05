# QA HOLD @ 98fa5b44 (#764 / Closes #763)

Tip: `98fa5b44cc2c1711f4e6298f3e6fccb38821ab95`
Engineer SBS: `5d729f6f` `763/98fa5b44/` · Lovart `53446c23`

## Verdict: HOLD — empty/leftover 「输出中…」 while ask card is open

### Must-haves (PASS on this tip)
1. @ popup Assets→Model, search placeholder, send stays send (not stop), no side RefFrame chip
2. No timeline 「向你提问」 (ask_user tool row hidden)
3. Single-question: no `1 of N` (`showPager = pageCount > 1`)
4. Submit disabled until choice; enabled after select (q → qsel)

Also OK: no 工作中/终止 bar; Stop square while generating (prior tip); ask docks above input; Skip + solid Submit; selected = light gray.

P2 note: D is always Other input row (en `Other (type your answer)...`) — not a HOLD.

### HOLD gap
When the docked ask card is open, timeline still shows live **「输出中…」** process status (and often a second empty/thinking box). Lovart ask-card has neither. Not a brief flicker — persists while waiting for the user.

Code:
- `AssistantBlocks`: on `ask` while `!done` pushes live `outputting` into the process rail → `ca-process__status`
- `AgentPanel`: `m.status === 'streaming'` still paints `ca-chat__thinking` (empty label if thinking blocks exist)

### Suites
`test_composer_stop_763.py` + `test_at_capsule_362.py`: **23 passed**
vs main `986af067`: A `test_composer_stop_763.py`; M `test_at_capsule_362.py`, `test_memory_once_423.py`, `test_process_rows_437.py`; no deleted tests.
