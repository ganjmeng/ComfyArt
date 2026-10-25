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

Fault and limit cases (#232):
- `15-*-retry` (LLM timeout / 429 / 500 twice, then OK): the LLM call is retried twice with two retry rows
  (attempt 1/2, 2/2), the turn finishes, the paid tool ran once.
- `15-timeout` / `15-429` / `15-500` (fault never clears): 3 LLM attempts, then a bilingual error that lists
  the steps already done; the zh UI accepts only Chinese, the en UI only English. 1 paid call.
- `15-steps80`: stops at the (configurable, default 80) step limit with a bilingual notice + done steps.
- `11` "brighter" (product ruling): exactly 1 new image whose edit input is the original, the original
  is unchanged (id/props/asset), 1 paid call per edit.
- `13`: the declined step and the guard-refused retry both carry tool status `cancelled` (已取消 / Cancelled).
- `12` covers the editable deck (`create_slides`); the PPTX file export itself is covered by
  `tests/test_export_formats.py`.
