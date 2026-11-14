/** #978 behavior harness: real src/skills.ts data + real src/agent.ts sendToAgent, with only the bot boundary
 *  stubbed (`tests/js/preset978/stubs.ts`). Proves the selected template's prompt reaches the send body with this
 *  run's values and that no-template / no-preset skills send exactly what they sent before. $0, no network. */
import { sendToAgent } from '../../../src/agent'
import {
  BUILTIN_SKILLS, interpolatePresetPrompt, presetInputValues, skillDefaults, skillRunParams,
  withPreset, withTemplateInputs, type Skill,
} from '../../../src/skills'
import { sent } from './stubs'

const by = (id: string) => BUILTIN_SKILLS.find((s) => s.id === id)!
const editor = {
  getDocumentSettings: () => ({ meta: { projectId: 'p978' } }),
  getCurrentPageShapeIds: () => new Set<string>(),
  getSelectedShapeIds: () => [] as string[],
}

interface Case { skillId: string; presetId: string | null; values?: Record<string, string> }
async function run(c: Case, attach?: Skill) {
  const base = by(c.skillId)
  const withInputs = c.presetId ? withTemplateInputs(base, c.presetId) : base
  const params = skillRunParams(withInputs, { ...skillDefaults(withInputs), ...(c.values ?? {}) }, c.presetId)
  const skill = attach ?? (c.presetId ? withPreset(base, c.presetId) : base)
  const ask = String(params.ask ?? '')
  await sendToAgent(editor as never, ask, [], skill)
  return {
    ask,
    skillName: skill.name,
    activePreset: skill.activePreset ?? null,
    presetParam: params.preset ?? null,
    instructionsUnchanged: skill.instructions === base.instructions,
    payload: sent[sent.length - 1],
  }
}

const out: Record<string, unknown> = {}
const brand = by('brand-identity-director')
const packaging = by('packaging-design-director')
const clothing = by('clothing-swap')

// Template skills: the selected template's prompt must be in the body, with this run's values.
out.brandFood = await run({ skillId: 'brand-identity-director', presetId: 'geometric', values: { brand_info: 'Wildpeak Coffee', visual_direction: 'warm light, handmade, generous white space' } })
out.packagingMulti = await run({ skillId: 'packaging-design-director', presetId: 'playful', values: { product_info: 'AURELIA 30ml serum', visual_direction: 'clean studio, soft shadow' } })
// Selected template, optional value left empty: the placeholder must disappear, not leak {{visual_direction}}.
out.brandNoVisual = await run({ skillId: 'brand-identity-director', presetId: 'geometric', values: { brand_info: 'Wildpeak Coffee' } })
// Short `Style:` preset (no {{...}}): delivered verbatim.
out.clothingFormal = await run({ skillId: 'clothing-swap', presetId: 'formal' })
// No template / unknown preset / skill without presets: payload must carry no preset at all.
out.brandUnknown = await run({ skillId: 'brand-identity-director', presetId: 'nope' })
out.brandNoPreset = await run({ skillId: 'brand-identity-director', presetId: null })
out.posterNoPresets = await run({ skillId: 'poster-differentiated-compiler', presetId: null })

// Pure interpolation contract, including a missing and an unknown variable.
const sample = 'Logo for {{brand_info}} — {{visual_direction}} {{unknown}}. End.'
out.interpolate = {
  both: interpolatePresetPrompt(sample, { brand_info: 'Wildpeak', visual_direction: 'warm' }),
  missing: interpolatePresetPrompt(sample, { brand_info: 'Wildpeak' }),
  blank: interpolatePresetPrompt('A {{a}} B {{b}} C', { a: '   ', b: 'two' }),
  none: interpolatePresetPrompt('No variables here.', {}),
  values: presetInputValues(brand.presets!.find((p) => p.id === 'geometric')!, 'Brand information: line one\nline two\nVisual direction: warm light'),
}
// #978 table-driven: every built-in preset (not just the 5 long-prompt skills) must reach the send body
// with no literal placeholder left, whatever the template form happens to contain.
const placeholderNames = (text: string) => [...text.matchAll(/\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}/g)].map((m) => m[1])
out.allPresets = []
out.unresolved = []
for (const s of BUILTIN_SKILLS) {
  for (const p of s.presets ?? []) {
    const withInputs = withTemplateInputs(s, p.id)
    const params = skillRunParams(withInputs, skillDefaults(withInputs), p.id)
    const ask = String(params.ask ?? '')
    await sendToAgent(editor as never, ask, [], withPreset(s, p.id))
    const payload = sent[sent.length - 1] as { preset?: { id: string; prompt: string } }
    const known = new Set((p.inputs ?? []).filter((f) => f.type !== 'image').map((f) => f.key))
    const missing = placeholderNames(p.prompt ?? '').filter((v) => !known.has(v))
    if (missing.length) out.unresolved.push({ skill: s.id, preset: p.id, missing })
    out.allPresets.push({ skill: s.id, preset: p.id, delivered: payload.preset?.id === p.id, prompt: payload.preset?.prompt ?? null, raw: p.prompt ?? null })
  }
}
out.presets = {
  brandCount: brand.presets?.length ?? 0,
  packagingCount: packaging.presets?.length ?? 0,
  clothingPrompt: clothing.presets?.find((p) => p.id === 'formal')?.prompt ?? null,
  brandPrompt: brand.presets?.find((p) => p.id === 'geometric')?.prompt ?? null,
  packagingPrompt: packaging.presets?.find((p) => p.id === 'playful')?.prompt ?? null,
}
console.log(JSON.stringify(out))
