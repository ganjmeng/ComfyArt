# #461 G2 Conversational Creator — design SBS v2

Adds full zh/en × light/dark + 预填 + 创建中过程轨 (思考→技能就绪).

## States
1. **Opening / 空开** — tip `creator-prefill` is empty opening (misnamed); labeled 空开 honestly.
2. **Prefill / 预填** — LEFT live ref chip with creation prompt + Outputting (handoff 04 / assets-10); RIGHT ours SkillForm filled (name / SKILL.md / attachments). Not tip empty.
3. **Process rail / 过程轨** — LEFT live ref 思考完成 → 技能就绪 (handoff 05 / assets-11); RIGHT ours form (gap: no process rail). Live reference captures, not target mocks.
4. **Outputting** — mid-create Outputting… vs form (zh-light, en-dark).
5. **Entry** — Create menu Skills entry (zh-light, en-dark).

KEEP form as fallback — never delete. No Lovart word in image chrome. No product code changes.

Files: sbs-opening-vs-form-empty-*, sbs-prefill-vs-form-filled-*, sbs-process-vs-form-*, sbs-outputting-vs-form-*, sbs-entry-* · src/
