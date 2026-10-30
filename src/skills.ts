import { atom } from 'tldraw'
import { unzipSync } from 'fflate'

import { deleteUserFile, listUserFiles, readUserText, uploadImage, viewUrl, writeUserText } from './comfy'
import { rulesText } from './customMarkers'
import { t } from './i18n'
import { uuid } from './id'

export interface Skill { id: string; name: string; description?: string; instructions: string; files?: Record<string, string>; images?: Record<string, string>; custom?: boolean; learned?: string[] }
export interface SkillVersion { time: number; skill: Skill }

const ROOT = 'comfyart/skills'
const TEXT_FILE = /\.(md|txt|json|csv|ya?ml|html?|css|js|ts|svg)$/i
const IMAGE_FILE = /\.(png|jpe?g|webp|gif)$/i

export const BUILTIN_SKILLS: Skill[] = [
  { id: 'poster', name: t('skills.posterDesign'), instructions: 'Design posters: strong headline typography in quotes, clear visual hierarchy, one hero subject, generous margins. Default ratio 3:4. Offer 2 distinct directions when the brief is open.' },
  { id: 'social', name: t('skills.socialMediaSet'), instructions: 'Create a consistent social media set: one 1:1 feed post, one 4:5 post and one 9:16 story sharing palette, typography and motif. Keep text short and legible on mobile.' },
  { id: 'brand', name: t('skills.brandIdentity'), instructions: 'Build a brand identity: a logo mark on plain background (1:1), a color palette board, and a stationery/mockup scene applying the logo. Describe shapes, colors (hex) and type style precisely.' },
  { id: 'packaging', name: t('skills.packagingDesign'), instructions: 'Design product packaging: a front view of the package on a clean studio background, then a 3/4 angle mockup in a lifestyle scene. Mention material, finish and label layout.' },
  { id: 'thumbnail', name: t('skills.youtubeThumbnail'), instructions: 'Design 16:9 video thumbnails: big expressive subject, 2-4 word bold title in quotes, high contrast, readable at small size. Offer 2 variations.' },
  { id: 'banner', name: t('skills.bannerDesign'), instructions: 'Design wide banners (21:9 or 16:9): headline on one side, visual on the other, safe margins for cropping, clear call to action text in quotes.' },
  { id: 'character', name: t('skills.characterSheet'), instructions: 'Create a character sheet: full body front, side and back views on white background in one 16:9 image, plus a close-up expression sheet. Keep outfit and colors identical across views.' },
  { id: 'product', name: t('skills.eCommerceProductImages'), instructions: 'Create e-commerce product imagery: a clean white-background hero shot (1:1), a lifestyle scene, and a detail close-up. Keep the product identical. When the user gives a product image, pass its shape id in refs (ref_modes content) on every generate_image call; describing it in the prompt does not send the image.' },
  { id: 'motion', name: t('skills.motionPoster'), instructions: 'Make a poster first (3:4) with generate_image, wait for it, then animate that image shape with animate_image using subtle motion (loop on) so the text stays readable.' },
  { id: 'interior', name: t('skills.interiorArchitecturalVisualization'), instructions: 'Produce photoreal interior or architecture renders: eye-level wide shot, natural light, accurate materials, 16:9. Add a detail vignette at 4:3.' },
  { id: 'custom-workflow', name: t('skills.customWorkflow'), instructions: `${rulesText()}\n\nUse the custom_workflow tool for every step; action rules returns these same rules.` },
]

export const skillAtom = atom<Skill | null>('skill', null)

const listFiles = (dir: string) => listUserFiles(`${ROOT}/${dir}`.replace(/\/$/, ''), true)
const read = (path: string) => readUserText(`${ROOT}/${path}`)
const write = (path: string, body: string) => writeUserText(`${ROOT}/${path}`, body)
const remove = (path: string) => deleteUserFile(`${ROOT}/${path}`)

export function toMarkdown(skill: Skill): string {
  const desc = skill.description?.replace(/\s+/g, ' ').trim()
  // #462: JSON-quoted (valid YAML) so colons and surrounding quotes survive the round trip.
  return `---\nname: ${skill.name}\n${desc ? `description: ${JSON.stringify(desc)}\n` : ''}---\n\n${skill.instructions}\n`
}

function unquote(v: string): string {
  if (v.startsWith('"')) { try { return String(JSON.parse(v)) } catch { /* fall through */ } }
  return v.replace(/^'(.*)'$/, '$1')
}

export function parseMarkdown(text: string): { name: string; description: string; instructions: string } {
  const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(text)
  const name = m ? /^name:\s*(.+)$/m.exec(m[1])?.[1].trim() ?? '' : ''
  const description = m ? unquote(/^description:\s*(.+)$/m.exec(m[1])?.[1].trim() ?? '') : ''
  return { name, description, instructions: (m ? m[2] : text).trim() }
}

async function readSkill(id: string, paths: string[]): Promise<Skill | null> {
  const md = await read(`${id}/SKILL.md`)
  if (md === null) return null
  const { name, description, instructions } = parseMarkdown(md)
  const files: Record<string, string> = {}
  for (const p of paths.filter((p) => p.startsWith('files/'))) files[p.slice(6)] = (await read(`${id}/${p}`)) ?? ''
  const images = paths.includes('images.json') ? JSON.parse((await read(`${id}/images.json`)) ?? '{}') as Record<string, string> : {}
  const learned = paths.includes('learned.json') ? JSON.parse((await read(`${id}/learned.json`)) ?? '[]') as string[] : undefined
  return { id, name: name || id, ...(description ? { description } : {}), instructions, files, images, custom: true, ...(learned ? { learned } : {}) }
}

export async function loadSkills(): Promise<Skill[]> {
  const byId = new Map<string, string[]>()
  for (const f of await listFiles('')) {
    const [id, ...rest] = f.split('/')
    byId.set(id, [...(byId.get(id) ?? []), rest.join('/')])
  }
  const custom = await Promise.all([...byId].filter(([, paths]) => paths.includes('SKILL.md')).map(([id, paths]) => readSkill(id, paths)))
  return [...custom.filter((s): s is Skill => !!s), ...BUILTIN_SKILLS]
}

export async function saveSkill(skill: Skill) {
  const paths = await listFiles(skill.id)
  const current = paths.includes('SKILL.md') ? await readSkill(skill.id, paths) : null
  if (current) await write(`${skill.id}/versions/${Date.now()}.json`, JSON.stringify(current))
  const files = skill.files ?? {}
  await write(`${skill.id}/SKILL.md`, toMarkdown(skill))
  await write(`${skill.id}/images.json`, JSON.stringify(skill.images ?? {}))
  if (skill.learned) await write(`${skill.id}/learned.json`, JSON.stringify(skill.learned))
  for (const [path, content] of Object.entries(files)) await write(`${skill.id}/files/${path}`, content)
  for (const p of paths.filter((p) => p.startsWith('files/') && !(p.slice(6) in files))) await remove(`${skill.id}/${p}`)
}

export async function deleteSkill(id: string) {
  for (const p of await listFiles(id)) await remove(`${id}/${p}`)
}

export async function listVersions(id: string): Promise<SkillVersion[]> {
  const names = (await listFiles(`${id}/versions`)).filter((f) => f.endsWith('.json')).sort().reverse()
  const out: SkillVersion[] = []
  for (const f of names) {
    const text = await read(`${id}/versions/${f}`)
    if (text) out.push({ time: Number(f.replace('.json', '')), skill: JSON.parse(text) as Skill })
  }
  return out
}

export const slug = (name: string) => name.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-').replace(/^-|-$/g, '') || uuid().slice(0, 8)

export async function uploadSkillImage(file: File, id: string): Promise<string> {
  return viewUrl(await uploadImage(file, `skill-${id}-${file.name}`))
}


/** One file of an imported skill: its path inside the folder / ZIP and its content. */
export interface SkillEntry { path: string; file: Blob }

/** #463 — size limit for one import (no earlier limit existed, so the product default of 20 MB applies). */
export const SKILL_IMPORT_MAX_BYTES = 20 * 1024 * 1024

/** #463 — the only three import errors the drop dialog shows. */
export type SkillImportErrorCode = 'noSkillMd' | 'unreadable' | 'tooLarge'
export class SkillImportError extends Error {
  constructor(readonly code: SkillImportErrorCode) {
    super(t(`skillsImport.error.${code}`))
    this.name = 'SkillImportError'
  }
}

/** Zip-slip / unsafe entry path: absolute, drive letter, backslash, `..`, or NUL. */
export function unsafeEntryPath(path: string): boolean {
  if (!path || path.includes('\\') || path.includes('\0')) return true
  if (path.startsWith('/') || /^[a-zA-Z]:/.test(path)) return true
  return path.split('/').some((part) => part === '..')
}

export interface ImportOptions {
  /** ZIP / drop dialog: enforce path safety + size limit. Folder import in the manage dialog keeps its old behaviour. */
  strict?: boolean
}

/** Shared by folder import and ZIP import (#463): finds the shallowest SKILL.md and imports its siblings.
 *  Everything is validated and read before the first write, so a failed import writes nothing. */
/** First id not taken by an existing skill folder: `id`, else `id-2`, `id-3`, … */
export async function freeSkillId(id: string): Promise<string> {
  const taken = new Set((await listFiles('')).map((f) => f.split('/')[0]))
  if (!taken.has(id)) return id
  let n = 2
  while (taken.has(`${id}-${n}`)) n++
  return `${id}-${n}`
}

export async function importEntries(all: SkillEntry[], fallbackName = '', opts: ImportOptions = {}): Promise<{ skill: Skill; skipped: string[] }> {
  if (opts.strict) {
    if (all.some((e) => unsafeEntryPath(e.path))) throw new SkillImportError('unreadable')
    if (all.reduce((n, e) => n + e.file.size, 0) > SKILL_IMPORT_MAX_BYTES) throw new SkillImportError('tooLarge')
  }
  const entries = all.filter((e) => e.path && !/(^|\/)(__MACOSX|\.DS_Store)(\/|$)/.test(e.path))
  const md = entries.filter((e) => /(^|\/)SKILL\.md$/i.test(e.path)).sort((a, b) => a.path.split('/').length - b.path.split('/').length)[0]
  if (!md) throw opts.strict ? new SkillImportError('noSkillMd') : new Error(t('skills.noSkillMdInFolder'))
  const root = md.path.replace(/SKILL\.md$/i, '')
  let parsed: { name: string; instructions: string }
  try { parsed = parseMarkdown(await md.file.text()) } catch { throw opts.strict ? new SkillImportError('unreadable') : new Error(t('skills.noSkillMdInFolder')) }
  const folder = root.replace(/\/$/, '').split('/').pop() || fallbackName
  let id = slug(folder || parsed.name)
  const extra: Record<string, string> = {}
  const imageEntries: [string, SkillEntry][] = []
  const skipped: string[] = []
  for (const e of entries) {
    if (e === md || !e.path.startsWith(root)) continue
    const path = e.path.slice(root.length)
    if (!path) continue
    if (TEXT_FILE.test(path)) extra[path] = await e.file.text()
    else if (IMAGE_FILE.test(path)) imageEntries.push([path, e])
    else skipped.push(path)
  }
  // #463: a duplicate name in the drop dialog becomes a new skill (`id-2`, `id-3`, …) with the same display name;
  // the existing skill is never touched. Folder import (non-strict) keeps main's direct overwrite.
  if (opts.strict) id = await freeSkillId(id)
  const images: Record<string, string> = {}
  for (const [path, e] of imageEntries) {
    const name = path.split('/').pop() ?? path
    images[path] = await uploadSkillImage(e.file instanceof File ? e.file : new File([e.file], name), id)
  }
  const skill: Skill = { id, name: parsed.name || folder, ...(parsed.description ? { description: parsed.description } : {}), instructions: parsed.instructions, files: extra, images, custom: true }
  await saveSkill(skill)
  return { skill, skipped }
}

export async function importFolder(list: FileList | File[]): Promise<{ skill: Skill; skipped: string[] }> {
  return importEntries(Array.from(list).map((f) => ({ path: f.webkitRelativePath || f.name, file: f })))
}

/** #463 — list the files of a skill ZIP (directories dropped). Pure: used by tests too. */
export function zipEntries(bytes: Uint8Array): SkillEntry[] {
  const out = unzipSync(bytes)
  return Object.entries(out).filter(([path]) => !path.endsWith('/')).map(([path, data]) => ({ path, file: new Blob([data as BlobPart]) }))
}

export const isZip = (f: File) => /\.zip$/i.test(f.name) || /zip/.test(f.type)

export async function importZip(file: File): Promise<{ skill: Skill; skipped: string[] }> {
  if (file.size > SKILL_IMPORT_MAX_BYTES) throw new SkillImportError('tooLarge')
  if (!isZip(file)) throw new SkillImportError('unreadable')
  let entries: SkillEntry[]
  try { entries = zipEntries(new Uint8Array(await file.arrayBuffer())) } catch { throw new SkillImportError('unreadable') }
  return importEntries(entries, file.name.replace(/\.zip$/i, ''), { strict: true })
}

/** #460/#461 — Explore wall + conversational creator (form kept as fallback). */
const FAV_KEY = 'comfyart.skillFavourites'

/** #462: `edit` set = Edit in Chat for an existing personal skill (same Composer chip path). */
export const skillCreatorAtom = atom<{ on: boolean }>('skillCreator', { on: false })

export function loadFavourites(): string[] {
  try {
    const raw = localStorage.getItem(FAV_KEY)
    const list = raw ? JSON.parse(raw) as unknown : []
    return Array.isArray(list) ? list.filter((x): x is string => typeof x === 'string') : []
  } catch {
    return []
  }
}

export function toggleFavourite(id: string): string[] {
  const set = new Set(loadFavourites())
  if (set.has(id)) set.delete(id)
  else set.add(id)
  const next = [...set]
  localStorage.setItem(FAV_KEY, JSON.stringify(next))
  return next
}

/** Chip ids for Explore wall filters (EN keys; UI labels via locales). */
export type SkillChipId = 'forYou' | 'ecommerce' | 'branding' | 'social' | 'website' | 'ads'

const CHIP_BY_SKILL: Record<string, SkillChipId> = {
  poster: 'ads',
  social: 'social',
  brand: 'branding',
  packaging: 'ecommerce',
  thumbnail: 'social',
  banner: 'ads',
  character: 'forYou',
  product: 'ecommerce',
  motion: 'ads',
  interior: 'website',
  'custom-workflow': 'forYou',
}

export function skillChip(id: string): SkillChipId {
  return CHIP_BY_SKILL[id] ?? 'forYou'
}

export function skillDescription(skill: Skill): string {
  if (skill.description?.trim()) return skill.description.trim()
  const key = `skills.desc.${skill.id}`
  const localized = t(key)
  if (localized !== key) return localized
  const line = skill.instructions.split('\n').find((l) => l.trim()) ?? ''
  return line.slice(0, 72) + (line.length > 72 ? '…' : '')
}

const WALL_META: Record<string, { author: string; views: string; likes: string; tone: string }> = {
  poster: { author: '社区', views: '12.4k', likes: '860', tone: 'warm' },
  social: { author: '社区', views: '9.1k', likes: '640', tone: 'cool' },
  brand: { author: '社区', views: '7.8k', likes: '520', tone: 'mint' },
  packaging: { author: '社区', views: '11.2k', likes: '910', tone: 'sand' },
  thumbnail: { author: '社区', views: '15.6k', likes: '1.2k', tone: 'pop' },
  banner: { author: '社区', views: '6.4k', likes: '410', tone: 'sky' },
  character: { author: '社区', views: '18.3k', likes: '1.5k', tone: 'lilac' },
  product: { author: '社区', views: '14.0k', likes: '980', tone: 'steel' },
  motion: { author: '社区', views: '8.7k', likes: '700', tone: 'rose' },
  interior: { author: '社区', views: '5.2k', likes: '360', tone: 'sage' },
  'custom-workflow': { author: '社区', views: '3.1k', likes: '210', tone: 'ink' },
}

export function skillWallMeta(id: string): { author: string; views: string; likes: string; tone: string } {
  const base = WALL_META[id] ?? { author: '', views: '—', likes: '—', tone: 'ink' }
  return { ...base, author: t('home.skillsCommunity') }
}
