/** #992: runtime applyRaw748 inventories for default UI (no example-card chips) plus source P() and optional send probes. $0, no network. */
import fs from 'node:fs'
import path from 'node:path'
import { sendToAgent } from '../../../src/agent'
import {
  BUILTIN_SKILLS, skillRunParams, skillDefaults, withPreset, type Skill,
} from '../../../src/skills'
import { SKILLS_748 } from '../../../src/skillRaw748'
import { sent } from '../preset978/stubs'

const root = process.env.CA992_ROOT || process.cwd()
const srcText = fs.readFileSync(path.join(root, 'src/skills.ts'), 'utf8')
const builtinSrc = srcText.slice(srcText.indexOf('export const BUILTIN_SKILLS'))
const sourcePresets: Record<string, { id: string; zh: string; en: string; prompt: string }[]> = {}
for (const block of builtinSrc.split(/\{ id: '/).slice(1)) {
  const id = block.slice(0, block.indexOf("'"))
  sourcePresets[id] = [...block.matchAll(/P\('([^']+)',\s*'((?:\\'|[^'])*)',\s*'((?:\\'|[^'])*)',\s*'((?:\\'|[^'])*)'/g)]
    .map((m) => ({ id: m[1], zh: m[2], en: m[3], prompt: m[4] }))
}

const by = (id: string) => BUILTIN_SKILLS.find((s) => s.id === id)
const editor = {
  getDocumentSettings: () => ({ meta: { projectId: 'p992' } }),
  getCurrentPageShapeIds: () => new Set<string>(),
  getSelectedShapeIds: () => [] as string[],
}

async function deliver(skill: Skill | undefined, presetId: string) {
  if (!skill) return { ok: false, reason: 'missing-skill', payload: null, prompt: null, activePreset: null }
  const preset = skill.presets?.find((p) => p.id === presetId)
  if (!preset) return { ok: false, reason: 'missing-runtime-preset', payload: null, prompt: null, activePreset: skill.activePreset ?? null, runtimeIds: (skill.presets ?? []).map((p) => p.id) }
  const marked = withPreset(skill, presetId)
  const ask = String(skillRunParams(marked, skillDefaults(marked), presetId).ask ?? 'Generate the selected option.')
  await sendToAgent(editor as never, ask, [], marked)
  const payload = sent[sent.length - 1] as { preset?: { id: string; prompt: string }; skill?: string }
  return {
    ok: payload?.preset?.id === presetId && !!(payload?.preset?.prompt),
    reason: payload?.preset?.id === presetId ? 'delivered' : 'preset-absent-from-send-body',
    ask,
    skillName: skill.name,
    activePreset: marked.activePreset ?? null,
    prompt: payload?.preset?.prompt ?? null,
    expectedPrompt: preset.prompt,
    payload,
  }
}

const runtime = Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, {
  kind: SKILLS_748[s.id]?.kind ?? null,
  presets: (s.presets ?? []).map((p) => ({ id: p.id, zh: p.name.zh, en: p.name.en, prompt: p.prompt ?? '', image: p.image ?? null })),
  presetChips: !!s.presetChips,
  examples: s.examples ?? null,
  inputs: (s.inputs ?? []).map((f) => ({ key: f.key, type: f.type, required: !!f.required, zh: f.label.zh, en: f.label.en ?? null })),
  instructions: s.instructions,
}]))

const restore: Record<string, string[]> = {
  'meta-ads-creative-director': ['feed1x1', 'feed4x5', 'story9x16', 'ugc'],
  'rednote-cover-maker': ['ugc-feed', 'ugc-story'],
  'mobile-app-visual-design': ['home', 'detail', 'checkout', 'onboarding'],
  'web-product-visual-design': ['hero', 'features', 'pricing', 'responsive'],
  'marketing-campaign-generator': ['kv', 'rednote-cover-maker', 'display', 'ooh'],
}

const deliveries: Record<string, unknown> = {}
for (const [sid, ids] of Object.entries(restore)) {
  deliveries[sid] = {}
  for (const pid of ids) (deliveries[sid] as Record<string, unknown>)[pid] = await deliver(by(sid), pid)
}

console.log(JSON.stringify({ sourcePresets, runtime, deliveries }))
