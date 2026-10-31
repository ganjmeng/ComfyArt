// #541 harness: Lovart meta line is real data only (template count from presets[]; no usage counter).
import { BUILTIN_SKILLS, skillMeta } from '../../src/skills'
const old = { id: 'old-skill', name: 'Old', instructions: 'Old rules.', custom: true }
console.log(JSON.stringify({
  meta: Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, skillMeta(s)])),
  presets: Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, s.presets?.length ?? 0])),
  old: skillMeta(old),
}))
