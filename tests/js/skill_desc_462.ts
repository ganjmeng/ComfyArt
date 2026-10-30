// #462 behavior harness: description round-trip through the real saveSkill → loadSkills path (in-memory user files).
import { files } from '../../src/comfy'
import { loadSkills, parseMarkdown, saveSkill, toMarkdown } from '../../src/skills'
const r: Record<string, unknown> = {}
const tricky = 'Poster: "Morning" café\'s 3:4 layout\nline two — keep "quotes"'
const quoted = '"wrapped in quotes"'
await saveSkill({ id: 'k1', name: 'Coffee', description: tricky, instructions: 'Do: it', files: {}, custom: true })
await saveSkill({ id: 'k2', name: 'Plain', instructions: 'x', files: {}, custom: true })
await saveSkill({ id: 'k3', name: 'Q', description: quoted, instructions: 'y', files: {}, custom: true })
const all = await loadSkills()
const by = (id: string) => all.find((s) => s.id === id)
r.tricky = by('k1')?.description
r.trickyExpected = tricky.replace(/\s+/g, ' ').trim()
r.instructions = by('k1')?.instructions
r.quoted = by('k3')?.description
r.emptyHasDescKey = 'description' in (by('k2') ?? {})
r.emptyMd = files['comfyart/skills/k2/SKILL.md']
r.direct = parseMarkdown(toMarkdown({ id: 'z', name: 'N', description: tricky, instructions: 'i' })).description
console.log(JSON.stringify(r))
