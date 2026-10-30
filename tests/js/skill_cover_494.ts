// #494-1 behavior harness: cover fallback order (cover → own images[0] → null = grey + icon) + data-driven chips.
import { BUILTIN_SKILLS, matchesSkillChip, skillChips, skillCover } from '../../src/skills'
const r: Record<string, unknown> = {}
const old = { id: 'old-skill', name: 'o', instructions: '', custom: true }
r.noImage = skillCover(old)
r.ownImage = skillCover({ ...old, images: { 'r.png': 'input/r.png' } })
r.custom = skillCover(BUILTIN_SKILLS.find((s) => s.id === 'custom-workflow')!)
r.builtinCovers = Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, skillCover(s)?.src ?? null]))
r.chips = skillChips(BUILTIN_SKILLS)
r.byChip = Object.fromEntries((r.chips as string[]).map((c) => [c, BUILTIN_SKILLS.filter((s) => matchesSkillChip(s, c as never)).map((s) => s.id)]))
console.log(JSON.stringify(r))
