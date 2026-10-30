// #463: real importZip / importEntries against an in-memory store. Prints one JSON report.
import { createHash } from 'node:crypto'
import { zipSync, strToU8 } from 'fflate'
import { files, writes } from './comfy_stub'
import { setLang } from '../i18n_stub'
import * as S from '../../../src/skills'

const sha = (prefix: string) => Object.fromEntries(Object.entries(files).filter(([k]) => k.startsWith(prefix)).map(([k, v]) => [k, createHash('sha256').update(v).digest('hex')]))
const reset = () => { for (const k of Object.keys(files)) delete files[k]; writes.length = 0 }
const zipFile = (entries: Record<string, string>, name = 'poster.zip') => new File([zipSync(Object.fromEntries(Object.entries(entries).map(([k, v]) => [k, strToU8(v)])))], name, { type: 'application/zip' })
const GOOD = { 'poster/SKILL.md': '---\nname: Poster\n---\nDo posters', 'poster/files/ref.md': 'hi', 'poster/a.png': 'png' }

async function attempt(fn: () => Promise<unknown>) {
  reset()
  try { await fn(); return { ok: true, writes: writes.length } } catch (e) { return { ok: false, message: (e as Error).message, writes: writes.length } }
}

// Per-case guard: an exception in one case (e.g. under a mutation) becomes { error } in that case's JSON field,
// so the pytest side fails on a specific assertion instead of the whole harness crashing.
async function safe<T>(fn: () => Promise<T> | T): Promise<T | { error: string }> {
  try { return await fn() } catch (e) { return { error: String((e as Error)?.message ?? e) } }
}

async function main() {
  const out: Record<string, unknown> = {}
  for (const lang of ['zh', 'en'] as const) {
    setLang(lang)
    const r: Record<string, unknown> = {}
    r.noSkillMd = await attempt(() => S.importZip(zipFile({ 'poster/readme.md': 'x', 'poster/a.png': 'p' })))
    r.corrupt = await attempt(() => S.importZip(new File([strToU8('PK\x03\x04 broken zip bytes')], 'bad.zip', { type: 'application/zip' })))
    r.notZip = await attempt(() => S.importZip(new File(['hello'], 'notes.txt', { type: 'text/plain' })))
    r.slipDots = await attempt(() => S.importZip(zipFile({ ...GOOD, '../evil.md': 'x' })))
    r.slipAbs = await attempt(() => S.importZip(zipFile({ ...GOOD, '/etc/evil.md': 'x' })))
    const big = new File([new Uint8Array(20 * 1024 * 1024 + 1)], 'big.zip', { type: 'application/zip' })
    r.tooLarge = await attempt(() => S.importZip(big))
    r.tooLargeUnzipped = await attempt(() => S.importEntries([{ path: 'p/SKILL.md', file: new Blob(['x']) }, { path: 'p/big.md', file: new Blob([new Uint8Array(20 * 1024 * 1024)]) }], '', { strict: true }))
    r.ok = await attempt(() => S.importZip(zipFile(GOOD)))
    r.okFiles = Object.keys(files).sort()
    // duplicate name: 2nd import -> poster-2, 3rd -> poster-3; same display name; original bytes untouched; no prompt, no error.
    r.dup = await safe(async () => {
      reset(); await S.importZip(zipFile(GOOD))
      const orig = Object.fromEntries(Object.entries(files).filter(([k]) => k.startsWith('comfyart/skills/poster/')))
      const NEW = { ...GOOD, 'poster/SKILL.md': '---\nname: Poster\n---\nNEW' }
      const second = await S.importZip(zipFile(NEW))
      const third = await S.importEntries(Object.entries(NEW).map(([path, v]) => ({ path, file: new Blob([v]) })), 'poster', { strict: true })
      const now = Object.fromEntries(Object.entries(files).filter(([k]) => k.startsWith('comfyart/skills/poster/')))
      return { ids: [second.skill.id, third.skill.id], names: [second.skill.name, third.skill.name], origSame: JSON.stringify(orig) === JSON.stringify(now),
        skillMds: Object.keys(files).filter((k) => k.endsWith('/SKILL.md')).sort(), secondMd: files['comfyart/skills/poster-2/SKILL.md'] ?? null }
    })
    // QA: the same ZIP three times -> poster, poster-2, poster-3, same display name; old files keep their sha256.
    r.same3 = await safe(async () => {
      reset()
      const first = await S.importZip(zipFile(GOOD))
      const before = sha('comfyart/skills/poster/')
      const rest = [await S.importZip(zipFile(GOOD)), await S.importZip(zipFile(GOOD))]
      const ids = [first, ...rest].map((x) => x.skill.id)
      const names = [first, ...rest].map((x) => x.skill.name)
      return { ids, names, shaBefore: before, shaAfter: sha('comfyart/skills/poster/'), dirs: [...new Set(Object.keys(files).map((k) => k.split('/')[2]))].sort() }
    })
    // Agent skill tool: two skills share a name; edit by id touches only that one; ambiguous save by name creates a new one.
    r.tool = await safe(async () => {
      reset()
      await S.importZip(zipFile(GOOD)); await S.importZip(zipFile(GOOD))
      const list = await S.skillTool({ action: 'list' }) as { skills: { id: string; name: string }[] }
      const other = sha('comfyart/skills/poster/')
      const byId = await S.skillTool({ action: 'save', id: 'poster-2', name: 'Poster', instructions: 'EDITED' })
      const otherAfterEdit = sha('comfyart/skills/poster/')
      const edited = await S.skillTool({ action: 'read', id: 'poster-2' }) as { instructions: string }
      const both = { ...sha('comfyart/skills/poster/'), ...sha('comfyart/skills/poster-2/') }
      const byName = await S.skillTool({ action: 'save', name: 'Poster', instructions: 'BY NAME' })
      const bothAfter = { ...sha('comfyart/skills/poster/'), ...sha('comfyart/skills/poster-2/') }
      return { list: list.skills.filter((x) => x.name === 'Poster').map((x) => x.id).sort(), byId, otherSame: JSON.stringify(other) === JSON.stringify(otherAfterEdit), editedInstr: edited.instructions,
        byName, bothSame: JSON.stringify(both) === JSON.stringify(bothAfter) }
    })
    // #463 ruling: after import, land on the NEW skill's detail with the guide toast; duplicates land on -2/-3.
    r.landing = await safe(async () => {
      reset()
      const runs = [await S.importZip(zipFile(GOOD)), await S.importZip(zipFile(GOOD)), await S.importZip(zipFile(GOOD))]
      const before = sha('comfyart/skills/poster/')
      const lands = runs.map((x) => S.importLanding(x.skill, x.skipped))
      const withSkip = await S.importZip(zipFile({ ...GOOD, 'poster/tool.exe': 'bin' }))
      const skipLand = S.importLanding(withSkip.skill, withSkip.skipped)
      return { ids: lands.map((l) => l.id), guides: lands.map((l) => l.guide), origSame: JSON.stringify(before) === JSON.stringify(sha('comfyart/skills/poster/')),
        skipId: skipLand.id, skipGuide: skipLand.guide, skipped: withSkip.skipped }
    })
    // "Import folder" in My Skills keeps main's direct overwrite.
    r.folder = await safe(async () => {
      reset(); await S.importZip(zipFile(GOOD))
      const { skill } = await S.importFolder(Object.entries({ ...GOOD, 'poster/SKILL.md': '---\nname: Poster\n---\nNEW' }).map(([path, v]) => Object.assign(new File([v], path.split('/').pop()!), { webkitRelativePath: path }) as File))
      return { id: skill.id, skillMds: Object.keys(files).filter((k) => k.endsWith('/SKILL.md')).sort() }
    })
    out[lang] = r
  }
  // #463 (1) Edit in chat by id. The entry text is skillEditToolHint(); PR #484's skillEditTurn must embed it
  // (depends on #484's src/skillEdit.ts). Here the "agent" follows the hint: it pulls the id out of it and saves.
  out.editChat = await safe(async () => {
    reset()
    await S.importZip(zipFile(GOOD)); const dup = await S.importZip(zipFile(GOOD))
    const hint = S.skillEditToolHint(dup.skill)
    const ids = [...hint.matchAll(/id="([^"]+)"/g)].map((m) => m[1])
    const before = sha('comfyart/skills/poster/')
    const read = await S.skillTool({ action: 'read', id: ids[0] }) as { id: string }
    const saved = await S.skillTool({ action: 'save', id: ids[1], name: dup.skill.name, instructions: 'EDITED IN CHAT' })
    const after = sha('comfyart/skills/poster/')
    return { ids, hintHasName: hint.includes('name="'), readId: read.id, saved, xSame: JSON.stringify(before) === JSON.stringify(after) && Object.keys(before).length > 0,
      x2: files['comfyart/skills/poster-2/SKILL.md'], dirs: [...new Set(Object.keys(files).map((k) => k.split('/')[2]))].sort() }
  })
  // #463 (2) description: set, list, change alone, round trip through SKILL.md with colons / quotes / newlines.
  out.desc = await safe(async () => {
    reset()
    const tricky = 'Posters: "bold" titles\nsecond line: \'x\''
    const created = await S.skillTool({ action: 'save', name: 'Desc', instructions: 'Body', description: tricky })
    const md1 = files['comfyart/skills/desc/SKILL.md']
    const list1 = (await S.skillTool({ action: 'list' }) as { skills: { id: string; description: string }[] }).skills.find((x) => x.id === 'desc')
    const changed = await S.skillTool({ action: 'save', id: 'desc', description: 'New: "two"' })
    const read2 = await S.skillTool({ action: 'read', id: 'desc' }) as { description: string; instructions: string }
    const parsed = S.parseMarkdown(files['comfyart/skills/desc/SKILL.md'])
    const kept = await S.skillTool({ action: 'save', id: 'desc', instructions: 'Body 2' })
    const read3 = await S.skillTool({ action: 'read', id: 'desc' }) as { description: string; instructions: string }
    return { created, md1, list1: list1?.description, changed, read2, parsed, kept, read3 }
  })
  // m2 target: two custom skills share a name; save by id (with that shared name) must update exactly that id.
  out.saveByIdShared = await safe(async () => {
    reset()
    await S.importZip(zipFile(GOOD)); await S.importZip(zipFile(GOOD))
    const before = sha('comfyart/skills/poster/')
    const saved = await S.skillTool({ action: 'save', id: 'poster-2', name: 'Poster', instructions: 'BY ID' }) as { id: string }
    return { savedId: saved.id, x2: files['comfyart/skills/poster-2/SKILL.md'] ?? null, x1Same: JSON.stringify(before) === JSON.stringify(sha('comfyart/skills/poster/')),
      dirs: [...new Set(Object.keys(files).map((k) => k.split('/')[2]))].sort() }
  })
  // m7 target: the pure hint text, no store involved.
  out.hint = await safe(() => S.skillEditToolHint({ id: 'poster-2', name: 'Poster' }))
  out.maxBytes = S.SKILL_IMPORT_MAX_BYTES
  console.log(JSON.stringify(out))
}
main().catch((e) => { console.log(JSON.stringify({ fatal: String(e) })) })
