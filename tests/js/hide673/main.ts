// #673: real src/skills.ts against an in-memory store. Prints one JSON report of what each pick-list exposes.
import { setLang } from '../i18n_stub'
import * as S from '../../../src/skills'
async function safe(fn: () => Promise<unknown>) { try { return await fn() } catch (e) { return { error: String((e as Error).message) } } }
async function main() {
  setLang('zh')
  const all = await S.loadSkills()
  const listed = await S.loadListedSkills()
  const chips = S.skillChips(listed)
  const byChip: Record<string, string[]> = {}
  for (const c of chips) byChip[c] = listed.filter((s) => S.matchesSkillChip(s, c)).map((s) => s.id)
  const featured = [...new Set(S.skillFeaturedCases(listed).map((f) => f.skill.id))]
  const agentList = ((await S.skillTool({ action: 'list' })) as { skills: { id: string }[] }).skills.map((s) => s.id)
  const hiddenReads: Record<string, unknown> = {}
  const resolved: Record<string, unknown> = {}
  for (const id of S.HIDDEN_BUILTIN_SKILL_IDS) {
    const b = S.BUILTIN_SKILLS.find((s) => s.id === id)!
    hiddenReads[id] = { byId: await safe(() => S.skillTool({ action: 'read', id })), byName: await safe(() => S.skillTool({ action: 'read', name: b.name })) }
    // saved session / card path: handoff.ts + Home starter use loadSkills().find(id) → withPreset → run params
    resolved[id] = await safe(async () => {
      const s = all.find((x) => x.id === id)
      if (!s) return { found: false }
      const p = S.withPreset(s, s.presets?.[0]?.id ?? null)
      return { found: true, name: s.name, params: Object.keys(S.skillRunParams(p, S.skillDefaults(p), s.presets?.[0]?.id ?? null)).length >= 0,
        cover: S.skillCover(s) !== undefined, desc: typeof S.skillDescription(s) }
    })
  }
  const listedRead = await safe(() => S.skillTool({ action: 'read', id: 'poster' }))
  const unknown = await safe(() => S.skillTool({ action: 'read', id: 'nope' }))
  console.log(JSON.stringify({
    hidden: S.HIDDEN_BUILTIN_SKILL_IDS, builtinAll: S.BUILTIN_SKILLS.map((s) => s.id), listed: listed.map((s) => s.id),
    chips, byChip, featured, agentList, hiddenReads, resolved, listedReadId: (listedRead as any).id, unknown,
  }))
}
main()
