/** #725: pure restore helpers (dedupe, persist, replace-on-refresh). No network, $0. */
import {
  clearSkillLinkRestore,
  dedupeLooseRefs,
  encodeSkillLinkRestore,
  isSkillLinkRestoreActive,
  markSkillLinkRestoreActive,
  parseSkillLinkRestore,
  readSkillLinkRestore,
  replaceSkillLinkRestore,
  skillLinkStoreKey,
  writeSkillLinkRestore,
  type SkillLinkRestore,
} from '../../src/home/skillLinkRestore'

class MemoryStorage {
  map = new Map<string, string>()
  getItem(k: string) { return this.map.has(k) ? this.map.get(k)! : null }
  setItem(k: string, v: string) { this.map.set(k, String(v)) }
  removeItem(k: string) { this.map.delete(k) }
}

const a = { src: '/api/view?filename=a.png&type=input', name: 'a.png' }
const b = { src: '/api/view?filename=b.png&type=input', name: 'b.png' }

const deduped = dedupeLooseRefs([a, a, b, a])
const empty = dedupeLooseRefs([])
const blank = dedupeLooseRefs([{ src: '  ', name: 'x' }, { src: '', name: 'y' }])

const parsedDup = parseSkillLinkRestore(JSON.stringify({
  draft: 'keep725',
  refs: [a, a, b],
  skillId: 'yingzao',
}))

const encoded = encodeSkillLinkRestore({ draft: 'keep725', refs: [a, a, b], skillId: 'yingzao' })
const encodedEmpty = encodeSkillLinkRestore({ draft: '', refs: [], skillId: null })

const store = new MemoryStorage() as unknown as Storage
const project = 'p725'
markSkillLinkRestoreActive(store, project)
writeSkillLinkRestore(store, project, { draft: 'keep725', refs: [a, b], skillId: 'yingzao' })
const first = readSkillLinkRestore(store, project)
// simulate two refreshes: re-read, never append
const second = readSkillLinkRestore(store, project)
const third = readSkillLinkRestore(store, project)
const replaced = replaceSkillLinkRestore(first, first!)
const appendWouldGrow = [...(first?.refs ?? []), ...(first?.refs ?? [])]

// save the same state again (as persist after refresh would)
writeSkillLinkRestore(store, project, second!)
const afterRewrite = readSkillLinkRestore(store, project)

// no-draft, refs only
writeSkillLinkRestore(store, project, { draft: '', refs: [a, b, a], skillId: 'before-after' })
const refsOnly = readSkillLinkRestore(store, project)

// ask only, no refs
writeSkillLinkRestore(store, project, { draft: 'only-ask', refs: [], skillId: 'yingzao' })
const askOnly = readSkillLinkRestore(store, project)

const wasActive = isSkillLinkRestoreActive(store, project)
clearSkillLinkRestore(store, project)
const afterClear = readSkillLinkRestore(store, project)
const activeAfterClear = isSkillLinkRestoreActive(store, project)

console.log(JSON.stringify({
  deduped: deduped.map((r) => r.src),
  empty: empty.length,
  blank: blank.length,
  parsedDup: { draft: parsedDup?.draft, n: parsedDup?.refs.length, srcs: parsedDup?.refs.map((r) => r.src), skillId: parsedDup?.skillId },
  encodedEmpty,
  first: { draft: first?.draft, n: first?.refs.length, skillId: first?.skillId },
  refreshTwice: [first?.refs.length, second?.refs.length, third?.refs.length, replaced.refs.length, afterRewrite?.refs.length],
  appendWouldGrow: appendWouldGrow.length,
  refsOnly: { draft: refsOnly?.draft, n: refsOnly?.refs.length, skillId: refsOnly?.skillId },
  askOnly: { draft: askOnly?.draft, n: askOnly?.refs.length },
  wasActive,
  afterClear,
  activeAfterClear,
  storeKey: skillLinkStoreKey(project),
}))
