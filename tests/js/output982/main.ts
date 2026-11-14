/** #982 behavior harness: the real src/skills.ts delivery tables (SKILL_OUTPUT, the generic lock,
 *  the TODO list) and what skill read would report for every built-in. No network, $0. */
import { BUILTIN_SKILLS, GENERIC_SKILL_OUTPUT, LOGO_MATERIAL_SIZE_982, SKILL_OUTPUT, TODO_SKILL_OUTPUT_982, skillOutputOf } from '../../../src/skills'

console.log(JSON.stringify({
  skillOutput: SKILL_OUTPUT,
  generic: GENERIC_SKILL_OUTPUT,
  todo: TODO_SKILL_OUTPUT_982,
  logoSize: LOGO_MATERIAL_SIZE_982,
  builtins: BUILTIN_SKILLS.map((s) => s.id),
  readOutput: Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, skillOutputOf(s.id) ?? null])),
  characterPresets: (BUILTIN_SKILLS.find((s) => s.id === 'character-sheet-design')?.presets ?? []).map((p) => p.id),
  logoPresets: (BUILTIN_SKILLS.find((s) => s.id === 'logo-material-explorer')?.presets ?? []).map((p) => p.id),
}))
