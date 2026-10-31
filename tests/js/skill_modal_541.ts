// #541 harness: Lovart meta line is real data only (template count from presets[]; no usage counter).
import { BUILTIN_SKILLS, presetImage, skillMeta } from '../../src/skills'
const old = { id: 'old-skill', name: 'Old', instructions: 'Old rules.', custom: true }
console.log(JSON.stringify({
  meta: Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, skillMeta(s)])),
  presets: Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, s.presets?.length ?? 0])),
  old: skillMeta(old),
  productIds: BUILTIN_SKILLS.find((s) => s.id === 'product')!.presets!.map((p) => p.id),
  productNew: BUILTIN_SKILLS.find((s) => s.id === 'product')!.presets!.slice(3).map((p) => presetImage(BUILTIN_SKILLS.find((s) => s.id === 'product')!, p)),
}))
