import { atom } from 'tldraw'
import { unzipSync } from 'fflate'

import { deleteUserFile, listUserFiles, readUserText, uploadImage, viewUrl, writeUserText } from './comfy'
import { rulesText } from './customMarkers'
import { lang, t } from './i18n'
import { uuid } from './id'
import { BRAND } from './brand'

/** #494 — zh/en copy carried by the skill data itself (not locales), so adding a skill never touches UI code. */
export interface LocText { zh: string; en: string }
/** #494 — Explore category (data only, never hardcoded in components). Unset = only under 「为你推荐」. A category with no skill gets no chip. */
export type SkillCategory = 'ecommerce' | 'branding' | 'social' | 'website' | 'ads'
/** #494 — one preset (template): `prompt` is the style text appended after the skill's instructions when the user runs
 *  the skill with this preset (step 2). `image` is the preset's own example image; unset → the skill's list cover. */
export interface SkillPreset { id: string; name: LocText; prompt?: string; image?: string }
/** #494 — one field of the skill's input dialog. Label / placeholder / default / required all come from here. */
export interface SkillInput {
  key: string; label: { zh: string; en?: string }; type: 'text' | 'textarea' | 'select' | 'image'; required?: boolean
  options?: { value: string; label: { zh: string; en?: string } }[]; default?: string; placeholder?: LocText
}
export interface Skill {
  id: string; name: string; description?: string; instructions: string; files?: Record<string, string>; images?: Record<string, string>; custom?: boolean; learned?: string[]
  /** #494 built-in metadata. Imported / personal skills have none of these and need no migration. */
  category?: SkillCategory; cover?: string; video?: string; presets?: SkillPreset[]; inputs?: SkillInput[]
  /** #541 Lovart 「效果示例」 carousel images (commit-pinned). Unset / empty → the section is not rendered. */
  examples?: string[]
}
export interface SkillVersion { time: number; skill: Skill }

const ROOT = 'comfyart/skills'
const TEXT_FILE = /\.(md|txt|json|csv|ya?ml|html?|css|js|ts|svg)$/i
const IMAGE_FILE = /\.(png|jpe?g|webp|gif)$/i

/** #494 — list covers + wash presets on orphan review-assets (commit-pinned; washed outputs only).
 *  Legacy local `/comfyart/skills/<id>/cover.webp` kept as SKILL_ASSET_BASE for any non-data callers. */
export const SKILL_ASSET_BASE = '/comfyart/skills'
/** #494 wash covers (10×462x346 webp). */
const WASH_COVER_COMMIT = '48362260e70c8d60a1a755a1b31d0f4ae5c0ab67'
const cover = (id: string) =>
  `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${WASH_COVER_COMMIT}/494/wash/covers/${id}.webp`
/** #529 list/detail cover videos (10× short mp4 on review-assets; commit-pinned). */
const WASH_VIDEO_COMMIT = '1bbb3f208f18b26ef95c8d9f16efeea111c43ac7'
const video = (id: string) =>
  `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${WASH_VIDEO_COMMIT}/494/wash/videos/${id}.mp4`
/** #494 wash presets. */
const WASH_PRESET_COMMIT = '7607a8e95ba69357d86fdcb583dc7af122f4ff65'
const washPreset = (skillId: string, presetId: string) =>
  `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${WASH_PRESET_COMMIT}/494/wash/presets/${skillId}__${presetId}.webp`
/** #541 AC rev 2 washes on review-assets (541/wash/<skill>/<skill>__<preset>.webp; each pinned to its own commit). */
const WASH_541 = {
  product: '688a702a1f322082cde4e5ed46200c3593db9c43', // 1:1, Amazon 商品主图
  productDetail: '2422dc53d37b8f4437a7f9f7986440d2ea79bbf1', // detail → true macro
  brand: 'f2045022727c73e24bd6d5ebcb3815bedb7b8797', // 4:3 stacked, Logo 系统
  packaging: 'c26cfaddc5e12c8652b151ef09ad12c47b2062a0', // 4:3, 品牌包装设计系统 (5); manifest c26cfad (mockup dropped, same 5 images as 1014ef2)
  packagingShelf: '35c819e64b38cc7d64dcd814ae8b86133976fc8a', // shelf re-wash: retail shelf rows (manifest d574dda6)
}
/** #541 「效果示例」 carousel washes (541/wash/<skill>/examples/<n>.webp), pinned to each IMAGE commit (manifest commit in comment). */
const EX_541 = {
  poster: '6d864bd2dd53b9f5b487829f2834d94be013b0a5', // 5 @3:4, manifest 5eb216e
  thumbnail: '5fc35b17f11ee58fde21671b16b574ecb0d35e5a', // 6 @16:9 (#5 single-scene re-wash), manifests 249b9e09 / 88824ff1
  character: 'dd97ee3782fc85090217c573b2ebb59ea4f19654', // 6 @16:9, manifest 65a99b1
  // interior: not wired — design re-washing to 3× 4:5 + 1× 1:1
  social: 'cb41cb8a450139cd903e777c8f84024019d517cd', // 10 @3:4 (小红书封面制作器), manifest e1b34fa
  banner: '8cc3fb305f7ce29ebbab63525680e3436e964dbb', // 1 × ~2:1 composite (4:3 + 3:4 side by side), manifest cd871d76
}
const ex541 = (skillId: keyof typeof EX_541, ids: number[]) =>
  ids.map((n) => `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${EX_541[skillId]}/541/wash/${skillId}/examples/${n}.webp`)
const wash541 = (commit: string, skillId: string, presetId: string) =>
  `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${commit}/541/wash/${skillId}/${skillId}__${presetId}.webp`
const washProduct541 = (presetId: string) => wash541(presetId === 'detail' ? WASH_541.productDetail : WASH_541.product, 'product', presetId)
const P = (id: string, zh: string, en: string, prompt: string, image?: string): SkillPreset =>
  ({ id, name: { zh, en }, prompt, ...(image ? { image } : {}) })
type L = [zh: string, en: string]
function I(key: string, [zh, en]: L, type: SkillInput['type'], required = false, ph?: L): SkillInput {
  return { key, label: { zh, en }, type, ...(required ? { required } : {}), ...(ph ? { placeholder: { zh: ph[0], en: ph[1] } } : {}) }
}
const SEL = (key: string, [zh, en]: L, values: string[], def?: string): SkillInput =>
  ({ key, label: { zh, en }, type: 'select', options: values.map((v) => ({ value: v, label: { zh: v, en: v } })), default: def ?? values[0] })
const SELL = (key: string, [zh, en]: L, opts: [string, string, string][], required = false): SkillInput =>
  ({ key, label: { zh, en }, type: 'select', ...(required ? { required } : {}), options: opts.map(([value, z, e]) => ({ value, label: { zh: z, en: e } })), default: opts[0][0] })
const REF: L = ['参考图', 'Reference image']

/** #494 — pick the current UI language from data-carried copy. */
export const loc = (text: { zh: string; en?: string }) => (lang === 'en' && text.en) || text.zh

export const BUILTIN_SKILLS: Skill[] = [
  { id: 'poster', name: t('skills.posterDesign'), instructions: 'Design posters: strong headline typography in quotes, clear visual hierarchy, one hero subject, generous margins. Default ratio 3:4. Offer 2 distinct directions when the brief is open.',
    category: 'ads', cover: cover('poster'), video: video('poster'), examples: ex541('poster', [1, 2, 3, 4, 5]), presets: [P('minimal', '极简排版', 'Minimal layout', 'Style: minimal Swiss layout, lots of white space, one accent color, clean sans-serif type.', washPreset('poster', 'minimal')), P('retro', '复古印刷', 'Retro print', 'Style: retro risograph print, grain texture, limited 2-3 ink palette, vintage typography.', washPreset('poster', 'retro')), P('neon', '霓虹潮流', 'Neon trend', 'Style: neon glow on a dark background, saturated magenta and cyan, bold condensed type.', washPreset('poster', 'neon'))],
    inputs: [I('topic', ['主题', 'Topic'], 'text', true, ['例如：秋季新品发布会', 'e.g. Autumn product launch']), I('headline', ['标题文字', 'Headline'], 'text'), SEL('ratio', ['比例', 'Aspect ratio'], ['3:4','2:3','9:16'],'3:4'), I('reference', REF, 'image')] },
  { id: 'social', name: t('skills.socialMediaSet'), instructions: 'Create a consistent social media set: one 1:1 feed post, one 4:5 post and one 9:16 story sharing palette, typography and motif. Keep text short and legible on mobile.',
    category: 'social', cover: cover('social'), video: video('social'), examples: ex541('social', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]), presets: [P('fresh', '清新生活', 'Fresh lifestyle', 'Style: fresh lifestyle photography, soft daylight, pastel palette, airy composition.', washPreset('social', 'fresh')), P('grey', '高级灰调', 'Premium grey', 'Style: premium muted grey tones, low saturation, refined serif accents, calm luxury mood.', washPreset('social', 'grey')), P('clash', '撞色活力', 'Bold color clash', 'Style: bold complementary color clash, flat graphic shapes, energetic playful layout.', washPreset('social', 'clash'))],
    inputs: [I('topic', ['主题', 'Topic'], 'text', true, ['例如：周末咖啡探店', 'e.g. Weekend coffee shop visit']), I('account', ['品牌或账号名', 'Brand or account name'], 'text'), I('copy', ['文案', 'Copy'], 'textarea'), I('reference', REF, 'image')] },
  { id: 'brand', name: t('skills.brandIdentity'), instructions: 'Build a brand identity: a logo mark on plain background (1:1), a color palette board, and a stationery/mockup scene applying the logo. Describe shapes, colors (hex) and type style precisely.',
    category: 'branding', cover: cover('brand'), video: video('brand'), presets: [P('geometric', '极简几何', 'Minimal geometric', 'Style: minimal geometric mark built from simple shapes, strict grid, two-color palette.', wash541(WASH_541.brand, 'brand', 'geometric')), P('handmade', '手作温暖', 'Handmade warmth', 'Style: hand-drawn warm mark, organic lines, earthy palette, craft paper textures.', wash541(WASH_541.brand, 'brand', 'handmade')), P('tech', '科技未来', 'Tech future', 'Style: futuristic tech identity, precise linework, gradient-free electric blue accents, monospace details.', wash541(WASH_541.brand, 'brand', 'tech')), P('beauty', '美妆个护', 'Beauty & personal care', 'Style: beauty and personal care logo system presentation board, soft refined mark with primary and secondary lockups, monogram, color swatches and typography specimen laid out on a clean board, no product mockups.', wash541(WASH_541.brand, 'brand', 'beauty')), P('foodbev', '食品饮料', 'Food & beverage', 'Style: food and beverage logo system presentation board, lively mark with primary and stacked lockups, icon variant, color swatches and typography specimen laid out on a clean board, no product mockups.', wash541(WASH_541.brand, 'brand', 'foodbev')), P('pet', '宠物用品', 'Pet supplies', 'Style: pet supplies logo system presentation board, friendly playful mark with primary and secondary lockups, mascot icon, color swatches and typography specimen laid out on a clean board, no product mockups.', wash541(WASH_541.brand, 'brand', 'pet'))],
    inputs: [I('brandName', ['品牌名', 'Brand name'], 'text', true, ['例如：山野咖啡', 'e.g. Wildpeak Coffee']), I('industry', ['行业', 'Industry'], 'text'), I('tone', ['调性关键词', 'Tone keywords'], 'text'), I('color', ['主色', 'Main color'], 'text')] },
  { id: 'packaging', name: t('skills.packagingDesign'), instructions: 'Design product packaging: a front view of the package on a clean studio background, then a 3/4 angle mockup in a lifestyle scene. Mention material, finish and label layout.',
    category: 'ecommerce', cover: cover('packaging'), video: video('packaging'), presets: [P('eco', '自然环保', 'Natural eco', 'Style: natural eco packaging, kraft and recycled paper, botanical line art, muted greens.', wash541(WASH_541.packaging, 'packaging', 'eco')), P('gold', '奢华烫金', 'Luxury gold foil', 'Style: luxury packaging, deep matte color with gold foil stamping, embossed logo.', wash541(WASH_541.packaging, 'packaging', 'gold')), P('playful', '潮玩插画', 'Playful illustration', 'Style: playful illustrated packaging, bright characters, bold outlines, pop colors.', wash541(WASH_541.packaging, 'packaging', 'playful')), P('panels', '展开结构图', 'Panels & structure', 'Style: packaging panels and structural dieline, flat unfolded box with front, back and side panels laid out.', wash541(WASH_541.packaging, 'packaging', 'panels')), P('shelf', '货架陈列', 'Shelf display', 'Style: packaging shelf display, the product repeated in rows on a retail shelf, eye-level store lighting.', wash541(WASH_541.packagingShelf, 'packaging', 'shelf'))],
    inputs: [I('productName', ['产品名', 'Product name'], 'text', true, ['例如：桂花乌龙茶', 'e.g. Osmanthus oolong tea']), I('kind', ['品类', 'Category'], 'text'), SELL('form', ['包装形式', 'Package type'], [['box', '盒', 'Box'],['bottle', '瓶', 'Bottle'],['bag', '袋', 'Bag'],['can', '罐', 'Can']]), I('reference', REF, 'image')] },
  { id: 'thumbnail', name: t('skills.youtubeThumbnail'), instructions: 'Design 16:9 video thumbnails: big expressive subject, 2-4 word bold title in quotes, high contrast, readable at small size. Offer 2 variations.',
    category: 'social', cover: cover('thumbnail'), video: video('thumbnail'), examples: ex541('thumbnail', [1, 2, 3, 4, 5, 6]), presets: [P('expression', '夸张表情', 'Exaggerated expression', 'Style: exaggerated surprised facial expression, close crop, bright rim light, yellow-red title.', washPreset('thumbnail', 'expression')), P('tech', '科技评测', 'Tech review', 'Style: clean tech review look, product hero on dark gradient-free backdrop, crisp white title.', washPreset('thumbnail', 'tech')), P('vlog', 'Vlog 清新', 'Fresh vlog', 'Style: fresh vlog look, natural daylight, soft colors, handwritten-style title.', washPreset('thumbnail', 'vlog'))],
    inputs: [I('topic', ['视频主题', 'Video topic'], 'text', true, ['例如：一周减脂餐', 'e.g. A week of healthy meals']), I('title', ['标题（2–4 个词）', 'Title (2–4 words)'], 'text'), I('photo', ['人物照片', 'Person photo'], 'image')] },
  { id: 'banner', name: t('skills.bannerDesign'), instructions: 'Design wide banners (21:9 or 16:9): headline on one side, visual on the other, safe margins for cropping, clear call to action text in quotes.',
    category: 'ads', cover: cover('banner'), video: video('banner'), examples: ex541('banner', [1]), presets: [P('sale', '大促促销', 'Big sale', 'Style: big sale banner, huge discount numerals, red and gold, festive energy.', washPreset('banner', 'sale')), P('brand', '品牌形象', 'Brand image', 'Style: calm brand image banner, single lifestyle photo, restrained type, lots of space.', washPreset('banner', 'brand')), P('event', '活动预告', 'Event teaser', 'Style: event teaser, dramatic lighting, date and place as strong typographic element.', washPreset('banner', 'event'))],
    inputs: [I('headline', ['标题', 'Headline'], 'text', true, ['例如：双十一全场五折', 'e.g. 50% off everything']), I('cta', ['行动号召文案', 'Call to action'], 'text'), SEL('ratio', ['比例', 'Aspect ratio'], ['21:9','16:9'],'21:9'), I('reference', REF, 'image')] },
  { id: 'character', name: t('skills.characterSheet'), instructions: 'Create a character sheet: full body front, side and back views on white background in one 16:9 image, plus a close-up expression sheet. Keep outfit and colors identical across views.',
    cover: cover('character'), video: video('character'), examples: ex541('character', [1, 2, 3, 4, 5, 6]), presets: [P('anime', '日系动漫', 'Anime style', 'Style: Japanese anime cel shading, clean line art, flat colors.', washPreset('character', 'anime')), P('cartoon3d', '3D 卡通', '3D cartoon', 'Style: stylized 3D cartoon render, soft subsurface lighting, rounded proportions.', washPreset('character', 'cartoon3d')), P('concept', '写实概念', 'Realistic concept', 'Style: realistic concept art, painterly detail, accurate anatomy and materials.', washPreset('character', 'concept'))],
    inputs: [I('character', ['角色描述', 'Character description'], 'textarea', true, ['例如：戴红围巾的少年剑客', 'e.g. A young swordsman with a red scarf']), I('outfit', ['服装', 'Outfit'], 'text'), I('reference', REF, 'image')] },
  { id: 'product', name: t('skills.eCommerceProductImages'), instructions: 'Create e-commerce product imagery: a clean white-background hero shot (1:1), a lifestyle scene, and a detail close-up. Keep the product identical. When the user gives a product image, pass its shape id in refs (ref_modes content) on every generate_image call; describing it in the prompt does not send the image.',
    category: 'ecommerce', cover: cover('product'), video: video('product'), presets: [P('white', '白底主图', 'White background hero', 'Focus on the white-background hero shot: pure white seamless background, soft shadow, product centered.', washProduct541('white')), P('lifestyle', '生活场景', 'Lifestyle scene', 'Focus on the lifestyle scene: product in use in a realistic home setting, natural light.', washProduct541('lifestyle')), P('detail', '细节特写', 'Detail close-up', 'Focus on the detail close-up: macro view of material and craftsmanship, shallow depth of field.', washProduct541('detail')), P('electronics', '数码电子', 'Electronics', 'Focus on the electronics hero: earbuds and their charging case on a clean studio backdrop, crisp reflections, precise edges.', washProduct541('electronics')), P('food', '美食', 'Food', 'Focus on the food hero: appetizing close shot, fresh ingredients as props, warm natural light, rich texture.', washProduct541('food')), P('beauty', '美妆个护', 'Beauty', 'Focus on the beauty hero: skincare or cosmetic product on soft pastel surfaces, gentle diffused light, clean premium mood.', washProduct541('beauty'))],
    inputs: [I('productImage', ['产品图', 'Product image'], 'image', true), I('productName', ['产品名', 'Product name'], 'text'), I('points', ['卖点', 'Selling points'], 'textarea')] },
  { id: 'motion', name: t('skills.motionPoster'), instructions: 'Make a poster first (3:4) with generate_image, wait for it, then animate that image shape with animate_image using subtle motion (loop on) so the text stays readable.',
    category: 'ads', cover: cover('motion'), video: video('motion'), presets: [P('loop', '微动循环', 'Subtle loop', 'Motion: subtle seamless loop, gentle floating of the subject, text static.', washPreset('motion', 'loop')), P('light', '光影流动', 'Flowing light', 'Motion: light and shadow sweeping across the scene, glints on surfaces, text static.', washPreset('motion', 'light')), P('push', '镜头推拉', 'Camera push-pull', 'Motion: slow camera push in then pull out, slight parallax, text static.', washPreset('motion', 'push'))],
    inputs: [I('topic', ['主题', 'Topic'], 'text', true, ['例如：新年音乐节', 'e.g. New Year music festival']), I('headline', ['标题文字', 'Headline'], 'text'), SEL('ratio', ['比例', 'Aspect ratio'], ['3:4','9:16'],'3:4')] },
  { id: 'interior', name: t('skills.interiorArchitecturalVisualization'), instructions: 'Produce photoreal interior or architecture renders: eye-level wide shot, natural light, accurate materials, 16:9. Add a detail vignette at 4:3.',
    cover: cover('interior'), video: video('interior'), presets: [P('nordic', '北欧自然光', 'Nordic daylight', 'Style: Nordic interior, light oak and white walls, soft overcast daylight, linen textiles.', washPreset('interior', 'nordic')), P('minimal', '现代极简', 'Modern minimal', 'Style: modern minimal, concealed storage, neutral palette, sharp architectural lines.', washPreset('interior', 'minimal')), P('industrial', '工业风', 'Industrial', 'Style: industrial loft, exposed brick and concrete, black steel, warm Edison lighting.', washPreset('interior', 'industrial'))],
    inputs: [SELL('space', ['空间类型', 'Space type'], [['living', '客厅', 'Living room'],['bedroom', '卧室', 'Bedroom'],['office', '办公', 'Office'],['exterior', '建筑外观', 'Building exterior']], true), I('style', ['风格描述', 'Style notes'], 'textarea'), I('reference', ['参考图或平面图', 'Reference or floor plan'], 'image')] },
  { id: 'custom-workflow', name: t('skills.customWorkflow'), instructions: `${rulesText()}\n\nUse the custom_workflow tool for every step; action rules returns these same rules.`,
    inputs: [I('brief', ['需求描述', 'Brief'], 'textarea', true, ['描述你要用自定义工作流做什么', 'Describe what the custom workflow should make'])] },
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

/** #529 — list/detail cover video URL when the skill data carries `video` (no video → no badge, no fake). */
export function skillVideo(skill: Skill): string | null {
  return skill.video || null
}

/** #494/#489 — author line: built-ins show BRAND.name (logo); personal / imported skills say 个人. No counts. */
export function skillAuthor(skill: Skill): { kind: 'builtin' | 'personal'; label: string } {
  return skill.custom ? { kind: 'personal', label: t('home.skillsAuthorPersonal') } : { kind: 'builtin', label: BRAND.name }
}

/** #494-2 — a skill has its own input dialog only when its data carries `inputs[]`. Old imported / personal skills
 *  have none and keep main's behaviour (open a project with the skill chip) — no migration. */
export const hasSkillDialog = (skill: Skill) => !!skill.inputs?.length

export type SkillValues = Record<string, string>

/** #494-2 — initial dialog values, straight from each input's `default` (selects fall back to their first option). */
export function skillDefaults(skill: Skill): SkillValues {
  return Object.fromEntries((skill.inputs ?? []).map((f) => [f.key, f.default ?? (f.type === 'select' ? f.options?.[0]?.value ?? '' : '')]))
}

/** #494-2 — keys of required inputs that are still empty (the dialog disables 生成 until this is empty). */
export function missingInputs(skill: Skill, values: SkillValues): string[] {
  return (skill.inputs ?? []).filter((f) => f.required && !values[f.key]?.trim()).map((f) => f.key)
}

/** #494-2 — the chosen preset (unknown id → first preset; no presets → undefined). */
export function skillPreset(skill: Skill, presetId?: string | null): SkillPreset | undefined {
  return skill.presets?.find((p) => p.id === presetId) ?? skill.presets?.[0]
}

/** #494-2 product rule: the selected preset's `prompt` is appended AFTER the skill's instructions. */
export function withPreset(skill: Skill, presetId?: string | null): Skill {
  const p = presetId ? skill.presets?.find((x) => x.id === presetId) : undefined
  return p?.prompt ? { ...skill, instructions: `${skill.instructions.trimEnd()}\n\n${p.prompt}` } : skill
}

/** #541 — Lovart meta line under the description. Only real data: no usage counter exists in our data, so the line
 *  carries the template count alone (never a made-up 「已使用N次」); no presets → null (no line). */
export function skillMeta(skill: Skill): { templates: number } | null {
  const n = skill.presets?.length ?? 0
  return n ? { templates: n } : null
}

/** #494-2 — the preset's own image, else the skill's list cover (one decision point, like `skillCover`). */
export function presetImage(skill: Skill, preset: SkillPreset): string | null {
  return preset.image ?? skillCover(skill)?.src ?? null
}

/** #494-3 — home 「精选」 tiles: one card per preset with a real image (data-driven; no demo rows). */
export function skillFeaturedCases(skills: Skill[]): { skill: Skill; preset: SkillPreset; image: string }[] {
  const out: { skill: Skill; preset: SkillPreset; image: string }[] = []
  for (const skill of skills) {
    for (const preset of skill.presets ?? []) {
      const image = presetImage(skill, preset)
      if (image) out.push({ skill, preset, image })
    }
  }
  return out
}

/** #494-2 — turn the dialog into the handoff: the text the user "sends" (label: value per filled text/select field,
 *  in data order), image fields as refs, and the skill + preset ids. Read by src/home/handoff.ts. */
export function skillRunParams(skill: Skill, values: SkillValues, presetId?: string | null): Record<string, string | string[]> {
  const lines: string[] = []
  const refs: string[] = []
  for (const f of skill.inputs ?? []) {
    const v = values[f.key]?.trim()
    if (!v) continue
    if (f.type === 'image') { refs.push(v); continue }
    const shown = f.type === 'select' ? loc(f.options?.find((o) => o.value === v)?.label ?? { zh: v }) : v
    lines.push(`${loc(f.label)}: ${shown}`)
  }
  const preset = presetId ? skill.presets?.find((p) => p.id === presetId) : undefined
  return { skill: skill.id, mode: 'agent', ask: lines.join('\n') || skill.name, ...(preset ? { preset: preset.id } : {}), ...(refs.length ? { ref: refs } : {}) }
}
