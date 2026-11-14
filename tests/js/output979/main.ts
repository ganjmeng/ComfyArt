/** #979 behavior harness: the real src/skills.ts SKILL_OUTPUT table and the real
 *  template ids that applyRaw748 keeps, so the Python contract table can be checked
 *  against the TS one row by row. No network, $0. */
import { BUILTIN_SKILLS, SKILL_OUTPUT } from '../../../src/skills'

const presets = (id: string) =>
  (BUILTIN_SKILLS.find((s) => s.id === id)?.presets ?? []).map((p) => ({ id: p.id, prompt: p.prompt ?? '' }))

console.log(JSON.stringify({
  skillOutput: SKILL_OUTPUT,
  presets: {
    brand: presets('brand-identity-director'),
    packaging: presets('packaging-design-director'),
  },
}))
