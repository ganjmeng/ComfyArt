# Agent regression set (#231)

The tester's 15 Agent tasks, each run with the zh and the en UI, plus the fault-retry targets and the
80-step limit. **Mocks only, $0, no network**: a scripted mock LLM (OpenAI-compatible), a mock WaveSpeed
submit endpoint and a fake canvas page. The real pieces under test are the bot send route
(`api/bot_turns.py`), the built-in agent loop (`bot/local_llm.py` via `AgentLlmProvider`), MCP dispatch
(`api/mcp.py`) and the paid guard (`api/paid_guard.py`). Any lookup of a non-local host fails the case.

Run (one command, prints the summary):

    COMFYART_SKIP_NODE_TESTS=1 python tests/agent_regression/run.py

Output: `tests/agent_regression/report/summary.{json,md}` (committed baseline; set
`AGENT_REGRESSION_OUT` to write elsewhere). Diff it before/after each Agent PR.

Each case checks: tool-call order and args, model ids in `api/curated_models.json`, shapes landed on
the canvas, reply/notice language follows the UI, paid submits == expected (no double charge), no
key sentinel in logs or the stored chat, steps <= limit (actual steps recorded).

Known gaps / expected to change:
- `15-*` (LLM timeout / 429 / 500): baseline today is no retry, the turn ends with the error after one
  paid call. `15-*-retry` are strict xfail `P1-a #232` (retry the LLM twice, never the paid tool).
- `11` "brighter" (product ruling): exactly 1 new image whose edit input is the original, the original
  is unchanged (id/props/asset), 1 paid call per edit.
- `13`: the guard-refused retry step shows as success in the chat; to fix in #232.
- `12` covers the editable deck (`create_slides`); the PPTX file export itself is covered by
  `tests/test_export_formats.py`.
