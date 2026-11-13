# PR 944 clock HOLD fix

Code tip: `0e57674c1c5ae4a99382f174eec9c7561f4753b8`.

$0 mocked acceptance, not supplier output. The browser composer submits through the real HTTP route; the real LocalLlmProvider agent loop executes generate_image and wait_generation (only LLM/MCP boundaries and clock are scripted). The route persists the real emitted run_stop. The browser reloads the actual conversation to render the built app; no handcrafted summary card is inserted. The shared test host stubs Comfy websocket transport, so these screenshots do not claim live websocket delivery.

The mock wait advances 1801 seconds and returns running; there is exactly one generate_image and one wait_generation, two LLM requests. zh/light and en/dark show the still-generating copy with no continue button.

Separate agent-loop regressions cover 180s chat + 933s generation, then running wait followed by 2400s add_text, and a mixed wait/add_text dispatch. Pure wait returns resume the clock in finally; mixed steps count in full.

101 targeted tests and 2 full-app chain tests passed. npm run build succeeded with no dist byte changes.
