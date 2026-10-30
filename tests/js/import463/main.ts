// #463: real importZip / importEntries against an in-memory store. Prints one JSON report.
import { zipSync, strToU8 } from 'fflate'
import { files, writes } from './comfy_stub'
import { setLang } from '../i18n_stub'
import * as S from '../../../src/skills'

const reset = () => { for (const k of Object.keys(files)) delete files[k]; writes.length = 0 }
const zipFile = (entries: Record<string, string>, name = 'poster.zip') => new File([zipSync(Object.fromEntries(Object.entries(entries).map(([k, v]) => [k, strToU8(v)])))], name, { type: 'application/zip' })
const GOOD = { 'poster/SKILL.md': '---\nname: Poster\n---\nDo posters', 'poster/files/ref.md': 'hi', 'poster/a.png': 'png' }

async function attempt(fn: () => Promise<unknown>) {
  reset()
  try { await fn(); return { ok: true, writes: writes.length } } catch (e) { return { ok: false, message: (e as Error).message, writes: writes.length } }
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
    // conflict: second import of the same skill must ask; cancel writes nothing, keepBoth keeps the old one, replace keeps a version.
    const asked: string[] = []
    const conflict = async (choice: S.SkillConflictChoice) => {
      reset(); await S.importZip(zipFile(GOOD)); const before = { ...files }; writes.length = 0
      let error = ''
      try { await S.importZip(zipFile({ ...GOOD, 'poster/SKILL.md': '---\nname: Poster\n---\nNEW' }), { onConflict: async (s) => { asked.push(s.id); return choice } }) } catch (e) { error = (e as Error).name }
      return { error, writes: writes.length, oldKept: files['comfyart/skills/poster/SKILL.md'] === before['comfyart/skills/poster/SKILL.md'], keys: Object.keys(files).filter((k) => !(k in before)).sort() }
    }
    r.conflictCancel = await conflict('cancel')
    r.conflictKeep = await conflict('keepBoth')
    r.conflictReplace = await conflict('replace')
    r.asked = asked
    r.noPromptSilent = await (async () => {
      reset(); await S.importZip(zipFile(GOOD)); writes.length = 0
      // Drop dialog always passes onConflict; without asking it must never reach a write. Simulate by an import that never answers.
      let answered = false
      void S.importZip(zipFile(GOOD), { onConflict: () => new Promise(() => {}) }).then(() => { answered = true })
      await new Promise((r2) => setTimeout(r2, 50))
      return { answered, writes: writes.length }
    })()
    out[lang] = r
  }
  out.maxBytes = S.SKILL_IMPORT_MAX_BYTES
  console.log(JSON.stringify(out))
}
void main()
