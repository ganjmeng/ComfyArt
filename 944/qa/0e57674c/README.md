# QA #944 @ 0e57674c ($0)

- `test_zz_qa944_clock.py`: Rig repros A-E (drop into tests/ of a 0e57674c checkout).
- `test_zz_qa944_fullapp.py`: Full App, Firefox, real mouse; real HTTP composer route + real LocalLlmProvider loop (LLM scripted);
  agent MCP generate_image / wait_generation -> backend pin pipeline -> page HANDLERS (window.__comfyartE2E) -> ComfyArt WaveSpeed
  routes -> local mock WaveSpeed. IMAGE_JOB_TIMEOUT shortened to 2s; each wait slice advances the run clock 601s (30-min cap after 3).
- `gate-summary.txt`: scripts/gate.sh output (UNIT failures = /workspace/lovart-inputs environment, identical on main 4683c95c).
