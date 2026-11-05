# #763 HOLD fix @ 511dc896 (PR #764)
Fix for design 5783457718 / product 5783482534 / QA 6655783604: no empty 输出中… / Outputting… shell
(rail row, bordered status, streaming footer) while the question is docked, after Skip, or after an answer before reply text.
Plain generating with no question keeps Outputting… (`ours/gen-*`). `ours/answered-text-*` = reply text resumes normally.

SBS: LEFT lovart.ai (reused, already-masked lefts from RA 5d729f6f `763/98fa5b44/sbs/`; qsel left for answered-pre) | RIGHT ours.
RIGHT = Firefox shot of tests/js/ask763 harness (real AssistantBlocks + docked QuestionCard, mock blocks, $0, no network).
