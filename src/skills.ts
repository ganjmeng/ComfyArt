import { atom } from 'tldraw'
import { unzipSync } from 'fflate'

import { deleteUserFile, listUserFiles, readUserText, uploadImage, viewUrl, writeUserText } from './comfy'
import { rulesText } from './customMarkers'
import { lang, t } from './i18n'
import { uuid } from './id'

/** #494 — zh/en copy carried by the skill data itself (not locales), so adding a skill never touches UI code. */
export interface LocText { zh: string; en: string }
/** #494 — Explore category (data only, never hardcoded in components). Unset = only under 「为你推荐」. A category with no skill gets no chip. */
export type SkillCategory = 'ecommerce' | 'branding' | 'social' | 'website' | 'ads'
/** #494 — one preset (template): `prompt` is the style text appended after the skill's instructions. */
/** Step 1 carries preset names only; preset images and `prompt` arrive with the step-2 dialog. */
export interface SkillPreset { id: string; name: LocText; prompt?: string }
/** #494 — one field of the skill's input dialog (rendered in step 2; data lives here). */
/** `label.en` / `placeholder` are filled in step 2 (not rendered in step 1). */
export interface SkillInput {
  key: string; label: { zh: string; en?: string }; type: 'text' | 'textarea' | 'select' | 'image'; required?: boolean
  options?: { value: string; label: { zh: string; en?: string } }[]; default?: string; placeholder?: LocText
}
export interface Skill {
  id: string; name: string; description?: string; instructions: string; files?: Record<string, string>; images?: Record<string, string>; custom?: boolean; learned?: string[]
  /** #494 built-in metadata. Imported / personal skills have none of these and need no migration. */
  category?: SkillCategory; cover?: string; presets?: SkillPreset[]; inputs?: SkillInput[]
}
export interface SkillVersion { time: number; skill: Skill }

const ROOT = 'comfyart/skills'
const TEXT_FILE = /\.(md|txt|json|csv|ya?ml|html?|css|js|ts|svg)$/i
const IMAGE_FILE = /\.(png|jpe?g|webp|gif)$/i

/** #494 — one list cover per skill: the `cover: true` image from review-assets 3c3edaa 494/covers, converted to a
 *  462x346 webp by scripts/skill_covers_494.py (pinned Pillow; source sha256 in public/skills/covers.json). */
export const SKILL_ASSET_BASE = '/comfyart/skills'
const cover = (id: string) => `${SKILL_ASSET_BASE}/${id}/cover.webp`
const P = (id: string, zh: string, en: string): SkillPreset => ({ id, name: { zh, en } })
function I(key: string, zh: string, type: SkillInput['type'], required = false): SkillInput {
  return { key, label: { zh }, type, ...(required ? { required } : {}) }
}
const SEL = (key: string, zh: string, values: string[], def?: string): SkillInput =>
  ({ key, label: { zh }, type: 'select', options: values.map((v) => ({ value: v, label: { zh: v, en: v } })), default: def ?? values[0] })
const SELL = (key: string, zh: string, opts: [string, string][], required = false): SkillInput =>
  ({ key, label: { zh }, type: 'select', ...(required ? { required } : {}), options: opts.map(([value, z]) => ({ value, label: { zh: z } })), default: opts[0][0] })

/** #494 — pick the current UI language from data-carried copy. */
export const loc = (text: { zh: string; en?: string }) => (lang === 'en' && text.en) || text.zh

export const BUILTIN_SKILLS: Skill[] = [
  { id: 'poster', name: t('skills.posterDesign'), instructions: 'Design posters: strong headline typography in quotes, clear visual hierarchy, one hero subject, generous margins. Default ratio 3:4. Offer 2 distinct directions when the brief is open.',
    category: 'ads', cover: cover('poster'), presets: [P('minimal', '极简排版', 'Minimal layout'), P('retro', '复古印刷', 'Retro print'), P('neon', '霓虹潮流', 'Neon trend')], inputs: [I('topic', '主题', 'text', true), I('headline', '标题文字', 'text'), SEL('ratio', '比例', ['3:4','2:3','9:16'],'3:4'), I('reference', '参考图', 'image')] },
  { id: 'social', name: t('skills.socialMediaSet'), instructions: 'Create a consistent social media set: one 1:1 feed post, one 4:5 post and one 9:16 story sharing palette, typography and motif. Keep text short and legible on mobile.',
    category: 'social', cover: cover('social'), presets: [P('fresh', '清新生活', 'Fresh lifestyle'), P('grey', '高级灰调', 'Premium grey'), P('clash', '撞色活力', 'Bold color clash')], inputs: [I('topic', '主题', 'text', true), I('account', '品牌或账号名', 'text'), I('copy', '文案', 'textarea'), I('reference', '参考图', 'image')] },
  { id: 'brand', name: t('skills.brandIdentity'), instructions: 'Build a brand identity: a logo mark on plain background (1:1), a color palette board, and a stationery/mockup scene applying the logo. Describe shapes, colors (hex) and type style precisely.',
    category: 'branding', cover: cover('brand'), presets: [P('geometric', '极简几何', 'Minimal geometric'), P('handmade', '手作温暖', 'Handmade warmth'), P('tech', '科技未来', 'Tech future')], inputs: [I('brandName', '品牌名', 'text', true), I('industry', '行业', 'text'), I('tone', '调性关键词', 'text'), I('color', '主色', 'text')] },
  { id: 'packaging', name: t('skills.packagingDesign'), instructions: 'Design product packaging: a front view of the package on a clean studio background, then a 3/4 angle mockup in a lifestyle scene. Mention material, finish and label layout.',
    category: 'ecommerce', cover: cover('packaging'), presets: [P('eco', '自然环保', 'Natural eco'), P('gold', '奢华烫金', 'Luxury gold foil'), P('playful', '潮玩插画', 'Playful illustration')], inputs: [I('productName', '产品名', 'text', true), I('kind', '品类', 'text'), SELL('form', '包装形式', [['box', '盒'],['bottle', '瓶'],['bag', '袋'],['can', '罐']]), I('reference', '参考图', 'image')] },
  { id: 'thumbnail', name: t('skills.youtubeThumbnail'), instructions: 'Design 16:9 video thumbnails: big expressive subject, 2-4 word bold title in quotes, high contrast, readable at small size. Offer 2 variations.',
    category: 'social', cover: cover('thumbnail'), presets: [P('expression', '夸张表情', 'Exaggerated expression'), P('tech', '科技评测', 'Tech review'), P('vlog', 'Vlog 清新', 'Fresh vlog')], inputs: [I('topic', '视频主题', 'text', true), I('title', '标题（2–4 个词）', 'text'), I('photo', '人物照片', 'image')] },
  { id: 'banner', name: t('skills.bannerDesign'), instructions: 'Design wide banners (21:9 or 16:9): headline on one side, visual on the other, safe margins for cropping, clear call to action text in quotes.',
    category: 'ads', cover: cover('banner'), presets: [P('sale', '大促促销', 'Big sale'), P('brand', '品牌形象', 'Brand image'), P('event', '活动预告', 'Event teaser')], inputs: [I('headline', '标题', 'text', true), I('cta', '行动号召文案', 'text'), SEL('ratio', '比例', ['21:9','16:9'],'21:9'), I('reference', '参考图', 'image')] },
  { id: 'character', name: t('skills.characterSheet'), instructions: 'Create a character sheet: full body front, side and back views on white background in one 16:9 image, plus a close-up expression sheet. Keep outfit and colors identical across views.',
    cover: cover('character'), presets: [P('anime', '日系动漫', 'Anime style'), P('cartoon3d', '3D 卡通', '3D cartoon'), P('concept', '写实概念', 'Realistic concept')], inputs: [I('character', '角色描述', 'textarea', true), I('outfit', '服装', 'text'), I('reference', '参考图', 'image')] },
  { id: 'product', name: t('skills.eCommerceProductImages'), instructions: 'Create e-commerce product imagery: a clean white-background hero shot (1:1), a lifestyle scene, and a detail close-up. Keep the product identical. When the user gives a product image, pass its shape id in refs (ref_modes content) on every generate_image call; describing it in the prompt does not send the image.',
    category: 'ecommerce', cover: cover('product'), presets: [P('white', '白底主图', 'White background hero'), P('lifestyle', '生活场景', 'Lifestyle scene'), P('detail', '细节特写', 'Detail close-up')], inputs: [I('productImage', '产品图', 'image', true), I('productName', '产品名', 'text'), I('points', '卖点', 'textarea')] },
  { id: 'motion', name: t('skills.motionPoster'), instructions: 'Make a poster first (3:4) with generate_image, wait for it, then animate that image shape with animate_image using subtle motion (loop on) so the text stays readable.',
    category: 'ads', cover: cover('motion'), presets: [P('loop', '微动循环', 'Subtle loop'), P('light', '光影流动', 'Flowing light'), P('push', '镜头推拉', 'Camera push-pull')], inputs: [I('topic', '主题', 'text', true), I('headline', '标题文字', 'text'), SEL('ratio', '比例', ['3:4','9:16'],'3:4')] },
  { id: 'interior', name: t('skills.interiorArchitecturalVisualization'), instructions: 'Produce photoreal interior or architecture renders: eye-level wide shot, natural light, accurate materials, 16:9. Add a detail vignette at 4:3.',
    cover: cover('interior'), presets: [P('nordic', '北欧自然光', 'Nordic daylight'), P('minimal', '现代极简', 'Modern minimal'), P('industrial', '工业风', 'Industrial')], inputs: [SELL('space', '空间类型', [['living', '客厅'],['bedroom', '卧室'],['office', '办公'],['exterior', '建筑外观']], true), I('style', '风格描述', 'textarea'), I('reference', '参考图或平面图', 'image')] },
  { id: 'custom-workflow', name: t('skills.customWorkflow'), instructions: `${rulesText()}\n\nUse the custom_workflow tool for every step; action rules returns these same rules.`,
    inputs: [I('brief', '需求描述', 'textarea', true)] },
]

export const skillAtom = atom<Skill | null>('skill', null)

const listFiles = (dir: string) => listUserFiles(`${ROOT}/${dir}`.replace(/\/$/, ''), true)
const read = (path: string) => readUserText(`${ROOT}/${path}`)
const write = (path: string, body: string) => writeUserText(`${ROOT}/${path}`, body)
const remove = (path: string) => deleteUserFile(`${ROOT}/${path}`)

// Description quoting mirrors #462 (PR #484, src/skills.ts) exactly so the two branches agree on rebase:
// whitespace (incl. newlines) collapses to one space, then the value is JSON-quoted (valid YAML), so colons and
// quotes survive the round trip and a newline can never end the frontmatter early.
export function toMarkdown(skill: Skill): string {
  const desc = skill.description?.replace(/\s+/g, ' ').trim()
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
  let parsed: { name: string; description: string; instructions: string }
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

/** #463 import progress shown in the dialog: 上传中...N% while the file is read, then 解析中... while it is unpacked/saved. */
export type ImportProgress = { phase: 'upload'; pct: number } | { phase: 'extract' }

async function readWithProgress(file: File, onProgress?: (p: ImportProgress) => void): Promise<Uint8Array> {
  if (!onProgress || typeof file.stream !== 'function') return new Uint8Array(await file.arrayBuffer())
  const out = new Uint8Array(file.size)
  const reader = file.stream().getReader()
  let loaded = 0
  onProgress({ phase: 'upload', pct: 0 })
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    out.set(value, loaded)
    loaded += value.length
    onProgress({ phase: 'upload', pct: file.size ? Math.min(100, Math.round((loaded / file.size) * 100)) : 100 })
  }
  return out.subarray(0, loaded)
}

export async function importZip(file: File, onProgress?: (p: ImportProgress) => void): Promise<{ skill: Skill; skipped: string[] }> {
  if (file.size > SKILL_IMPORT_MAX_BYTES) throw new SkillImportError('tooLarge')
  if (!isZip(file)) throw new SkillImportError('unreadable')
  let entries: SkillEntry[]
  const bytes = await readWithProgress(file, onProgress).catch(() => { throw new SkillImportError('unreadable') })
  onProgress?.({ phase: 'extract' })
  try { entries = zipEntries(bytes) } catch { throw new SkillImportError('unreadable') }
  return importEntries(entries, file.name.replace(/\.zip$/i, ''), { strict: true })
}

/** #463 — after a successful import: open the NEW skill's page (a duplicate lands on its -2/-3 id).
 *  `skipped` is the one-off toast text, only when unsupported files were actually skipped: the second half of main's
 *  `skillsDialog.importedSkipped` copy (「不支持的文件已跳过：{0}」), no new copy. */
export function importLanding(skill: Pick<Skill, 'id'>, skipped: string[] = []): { id: string; skipped: string } {
  return { id: skill.id, skipped: skipped.length ? skippedNotice(skipped) : '' }
}

export function skippedNotice(skipped: string[]): string {
  const full = t('skillsDialog.importedSkipped', skipped.join(t('common.listSep')))
  const cut = full.search(/[。.]\s*/)
  return cut < 0 ? full : full.slice(cut + 1).trim()
}

/** #463 — what "Edit in chat" tells the agent, so it reads and saves the skill by id (names can repeat: x, x-2).
 *  Used by #484's `skillEditTurn` (src/skillEdit.ts). */
export function skillEditToolHint(skill: Pick<Skill, 'id' | 'name'>): string {
  return `Read it with the skill tool (action="read", id="${skill.id}"). When saving, use action="save" with id="${skill.id}" `
    + `(not the name "${skill.name}": several skills can share it), keeping everything not mentioned; pass description to change its description.`
}

/** The agent `skill` tool (#463). Skills are addressed by `id` when given: "Edit in chat" passes the id and a save with
 *  an id updates exactly that skill. A save by name updates the one custom skill with that name; when the name is
 *  ambiguous (duplicates from import) or new, a new skill is created and no existing one is touched. */
export async function skillTool(args: Record<string, unknown>): Promise<unknown> {
  const skills = await loadSkills()
  if (args.action === 'list') return { skills: skills.map((s) => ({ id: s.id, name: s.name, description: s.description ?? '', custom: !!s.custom })) }
  const id = args.id ? String(args.id) : ''
  if (args.action === 'save') {
    if (!args.name && !id) throw new Error('save needs a name or id')
    let existing: Skill | undefined
    if (id) {
      existing = skills.find((s) => s.custom && s.id === id)
      if (!existing) throw new Error(`no custom skill with id ${JSON.stringify(id)}`)
    } else {
      const named = skills.filter((s) => s.custom && s.name === args.name)
      existing = named.length === 1 ? named[0] : undefined
    }
    // instructions/description are optional on an update (keep the stored value); a new skill needs instructions.
    if (args.instructions == null && !existing) throw new Error('save needs instructions for a new skill')
    const name = args.name ? String(args.name) : existing!.name
    const instructions = args.instructions != null ? String(args.instructions) : existing!.instructions
    const description = args.description != null ? String(args.description).replace(/\s+/g, ' ').trim() : existing?.description
    const skill: Skill = { ...existing, id: existing?.id ?? await freeSkillId(slug(name)), name, instructions, custom: true }
    if (description) skill.description = description; else delete skill.description
    await saveSkill(skill)
    return { saved: name, id: skill.id, description: description ?? '' }
  }
  if (args.action !== 'read') throw new Error('action must be list, read or save')
  const skill = id ? skills.find((s) => s.id === id) : skills.find((s) => s.name === args.name)
  if (!skill) throw new Error(`unknown skill ${JSON.stringify(id || args.name)} — available: ${skills.map((s) => `${s.name} (${s.id})`).join(', ')}`)
  if (args.path) {
    const content = skill.files?.[String(args.path)]
    if (content == null) throw new Error(`skill ${skill.name} has no file ${args.path}; files: ${Object.keys(skill.files ?? {}).join(', ') || '(none)'}`)
    return { id: skill.id, name: skill.name, path: args.path, content }
  }
  return { id: skill.id, name: skill.name, description: skill.description ?? '', instructions: skill.instructions, files: Object.keys(skill.files ?? {}), images: Object.values(skill.images ?? {}) }
}

/** #460/#461 — Explore wall + conversational creator (form kept as fallback). */
const FAV_KEY = 'comfyart.skillFavourites'

/** #462: `edit` set = Edit in Chat for an existing personal skill (same Composer chip path). */
/** #491: `chip` = i18n key of the chip label; unset falls back to composer.skillCreator (zh 技能创建器), same key as both create entries. */
export const skillCreatorAtom = atom<{ on: boolean; chip?: string }>('skillCreator', { on: false })

/** #491 product: both create entries share one chip copy — zh 技能创建器 / en Skill Creator. */
export const HOME_CREATOR_CHIP_KEY = 'composer.skillCreator'
/** #491 entry B (Skills page 「创建」) uses the same key as home. */
export const CREATE_ENTRY_CHIP_KEY = HOME_CREATOR_CHIP_KEY

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

/** Chip ids for Explore filters: 「为你推荐」 plus the categories (#494: read from each skill's `category`). */
export type SkillChipId = 'forYou' | SkillCategory
/** Display order of category chips; a category no skill uses is dropped by `skillChips` (so 「网站」 is hidden today). */
export const SKILL_CATEGORY_ORDER: SkillCategory[] = ['ecommerce', 'branding', 'social', 'website', 'ads']

/** #494 — chips shown on Explore: 「为你推荐」 + every category that has at least one of `skills`. */
export function skillChips(skills: Skill[]): SkillChipId[] {
  const used = new Set(skills.map((s) => s.category).filter(Boolean))
  return ['forYou', ...SKILL_CATEGORY_ORDER.filter((c) => used.has(c))]
}

export function matchesSkillChip(skill: Skill, chip: SkillChipId): boolean {
  return chip === 'forYou' || skill.category === chip
}

export function skillDescription(skill: Skill): string {
  if (skill.description?.trim()) return skill.description.trim()
  const key = `skills.desc.${skill.id}`
  const localized = t(key)
  if (localized !== key) return localized
  const line = skill.instructions.split('\n').find((l) => l.trim()) ?? ''
  return line.slice(0, 72) + (line.length > 72 ? '…' : '')
}

/** #494 product rule (23:20) — the ONE place that decides a card's image: `cover`, else the skill's own `images[0]`
 *  (old personal skills, no migration), else `null` → light grey background + Lucide icon (no image, no gradient). */
export function skillCover(skill: Skill): { src: string; own: 'bundled' | 'userdata' } | null {
  if (skill.cover) return { src: skill.cover, own: 'bundled' }
  const first = Object.values(skill.images ?? {})[0]
  return first ? { src: first, own: 'userdata' } : null
}

/** #494/#489 — author line: built-ins are ComfyArt (logo); personal / imported skills say 个人. No counts. */
export function skillAuthor(skill: Skill): { kind: 'builtin' | 'personal'; label: string } {
  return skill.custom ? { kind: 'personal', label: t('home.skillsAuthorPersonal') } : { kind: 'builtin', label: 'ComfyArt' }
}
