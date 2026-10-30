// #462 Edit in chat harness: dialog → new project URL, the opening turn (title + one auto-sent message), and the agent
// skill tool's by-name save overwriting the original in place. In-memory user files, no network, no paid API.
import { setLang } from '../../src/i18n'
import { editSkillInChat, startSkillEdit } from '../../src/skillEdit'
import { loadSkills, saveSkill } from '../../src/skills'
const assigned: string[] = []
;(globalThis as any).location = { pathname: '/', origin: 'http://ca.test', href: 'http://ca.test/', assign: (u: string) => assigned.push(u) }
const r: Record<string, unknown> = {}
const name = '早安咖啡店海报生成器'
await saveSkill({ id: 'cafe1', name, description: 'd', instructions: 'old rules', files: { 'notes.md': 'n' }, custom: true })
await saveSkill({ id: 'other', name: 'Other', instructions: 'x', files: {}, custom: true })
const skill = (await loadSkills()).find((s) => s.id === 'cafe1')!
editSkillInChat(skill)
const u = new URL(assigned[0])
r.urls = assigned.length
r.params = { project: !!u.searchParams.get('project'), new: u.searchParams.get('new'), editSkill: u.searchParams.get('editSkill'), createSkill: u.searchParams.get('createSkill') }
for (const lang of ['zh', 'en'] as const) {
  setLang(lang)
  const titles: string[] = []
  const sends: { text: string; skill: string; context: string }[] = []
  await startSkillEdit({ updateDocumentSettings: (s) => titles.push(s.name) }, skill, async (text, s, context) => { sends.push({ text, skill: s.name, context }) })
  r[lang] = { titles, sends }
}
// Mock agent turn (no LLM): follow the context's directive — read the skill with the real tool, list it, ask.
setLang('zh')
const turn = (r.zh as any).sends[0]
const readName = /action="read", name="([^"]+)"/.exec(turn.context)?.[1]
const found = (await loadSkills()).find((s) => s.name === readName)!  // what the agent skill tool's read returns
const read = { name: found.name, instructions: found.instructions, files: Object.keys(found.files ?? {}) }
r.mockReply = [
  { type: 'thinking', text: '…' },
  { type: 'tool_use', name: 'skill', input: { action: 'read', name: readName } },
  { type: 'tool_result', text: JSON.stringify(read) },
  { type: 'text', text: `已加载这个 Skill，它目前包含：\n- ${read.instructions}\n- 文件：${read.files.join('、')}\n你想修改哪些方面？` },
]
const before = (await loadSkills()).filter((s) => s.custom).length
// The agent skill tool's save (src/botLayout.ts, unchanged from main): find the custom skill by name, then
// saveSkill({ ...existing, id: existing?.id ?? new, ... }). Same loadSkills → saveSkill path, same arguments.
const args = { action: 'save', name, instructions: 'new rules 9:16' }
const existing = (await loadSkills()).find((s) => s.custom && s.name === args.name)
await saveSkill({ ...existing, id: existing?.id ?? 'fresh', name: String(args.name), instructions: String(args.instructions), custom: true })
r.reusedId = existing?.id
const after = (await loadSkills()).filter((s) => s.custom)
r.countBefore = before
r.countAfter = after.length
r.cafe = after.find((s) => s.id === 'cafe1')
r.ids = after.map((s) => s.id).sort()
console.log(JSON.stringify(r))
