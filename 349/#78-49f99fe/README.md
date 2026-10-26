#349 Home↔画布 Model FieldSelect + DirectPills 同源

- tip: `49f99fe047dbbdf702a91fb179b50aa7a7e374a0` (PR https://github.com/ganjmeng/ComfyArt/pull/352)
- base main: `d1629e9`
- before: main @ d1629e9 — AgentExtras Model = bespoke `ca-agentpick__modelbtn` Popover
- after: tip 49f99fe — AgentExtras Model = shared `FieldSelect` (`.ca-fieldselect` + ca-menu)；Composer Mode open `loadSettings`+`loadProviders`
- token: #316 32px / field / ellipsis — FieldSelect ≡ modelbtn，故关/开态像素可近同；验收看 DOM 类 + Home|画布并排一致
- light 必做：A/B Model 关开、C–F Image/Video pills、G shortLabel、H 空画布
- dark 建议：I Home agent+Mode；J 空画布+Mode
- 抽检：Audio/OCR 等无 `<select>`（e2e spotcheck）
- 截自 `tests/test_e2e_home_canvas_model_349.py` + AGENT_SHOTS
