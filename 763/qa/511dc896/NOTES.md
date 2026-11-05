# 763/qa/511dc896 — QA PASS (real ComfyArt app)

Tip: `511dc8964ba92658fdb7109f18a803a023c7f7d5` (fix `85e65f84` + harness `511dc896`).
Server: ComfyUI `--cpu --port 8199`, custom_nodes/ComfyArt → wt763 @ tip.
Served bundle: `App-5FFSotGC.js` (askQuiet present).

## Method
Seeded four chats on project `5d5bb986` via `/comfyart/bot/chats/.../log` + DB `status=streaming`, then opened each in the **full** `/comfyart/?project=…` UI (canvas + agent + composer). Not the Firefox ask763 harness.

## Four Outputting states (zh-light + en-dark)
| state | empty 输出中/Outputting shell? | Outputting present? |
|---|---|---|
| q-open (docked ask, streaming) | no | no |
| skip (skipped ask, streaming) | no | no |
| answered-pre (answered, no reply text, streaming) | no | no |
| gen-no-q (streaming, no ask) | — | yes (footer 输出中…/Outputting…) |

## Regression spot-checks (same session)
- no 「向你提问」 timeline row
- no `1 of N` on single question
- Submit `disabled` until option selected (`ca-q__submit disabled`)
- docked ask card (`.ca-q`) above composer
- fonts (#765) not blocking

Engineer RA `c4fdf755` harness SBS not used as merge proof; these shots are the real app.
