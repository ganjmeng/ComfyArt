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
    // duplicate name: 2nd import -> poster-2, 3rd -> poster-3; same display name; original bytes untouched; no prompt, no error.
    r.dup = await (async () => {
      reset(); await S.importZip(zipFile(GOOD))
      const orig = Object.fromEntries(Object.entries(files).filter(([k]) => k.startsWith('comfyart/skills/poster/')))
      const NEW = { ...GOOD, 'poster/SKILL.md': '---\nname: Poster\n---\nNEW' }
      const second = await S.importZip(zipFile(NEW))
      const third = await S.importEntries(Object.entries(NEW).map(([path, v]) => ({ path, file: new Blob([v]) })), 'poster', { strict: true })
      const now = Object.fromEntries(Object.entries(files).filter(([k]) => k.startsWith('comfyart/skills/poster/')))
      return { ids: [second.skill.id, third.skill.id], names: [second.skill.name, third.skill.name], origSame: JSON.stringify(orig) === JSON.stringify(now),
        skillMds: Object.keys(files).filter((k) => k.endsWith('/SKILL.md')).sort(), secondMd: files['comfyart/skills/poster-2/SKILL.md'] ?? null }
    })()
    // "Import folder" in My Skills keeps main's direct overwrite.
    r.folder = await (async () => {
      reset(); await S.importZip(zipFile(GOOD))
      const { skill } = await S.importFolder(Object.entries({ ...GOOD, 'poster/SKILL.md': '---\nname: Poster\n---\nNEW' }).map(([path, v]) => Object.assign(new File([v], path.split('/').pop()!), { webkitRelativePath: path }) as File))
      return { id: skill.id, skillMds: Object.keys(files).filter((k) => k.endsWith('/SKILL.md')).sort() }
    })()
    out[lang] = r
  }
  out.maxBytes = S.SKILL_IMPORT_MAX_BYTES
  console.log(JSON.stringify(out))
}
void main()
