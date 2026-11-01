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
  /** #541 「效果示例」 carousel images (commit-pinned). Unset / empty → the section is not rendered. */
  examples?: string[]
  /** #580 cut 2 — the three image slots, one per surface: `cover` = Skills module (above, unchanged);
   *  `quickStartCover` = home 「用 Skill 快速开始」 row (fixed 4:3, full-bleed); `featured` = home masonry images
   *  (natural ratio, full-bleed). Unset → fall back to the existing images (see skillQuickStartCover / skillFeaturedCases). */
  quickStartCover?: string
  featured?: string[]
  /** #580 P2 — preset id shown first for this skill in home 「Skill 案例」 (fallback path only). */
  featuredPreset?: string
}
export interface SkillVersion { time: number; skill: Skill }

const ROOT = 'comfyart/skills'
const TEXT_FILE = /\.(md|txt|json|csv|ya?ml|html?|css|js|ts|svg)$/i
const IMAGE_FILE = /\.(png|jpe?g|webp|gif)$/i

/** #494 — list covers + wash presets on orphan review-assets (commit-pinned; washed outputs only).
 *  Legacy local `/comfyart/skills/<id>/cover.webp` kept as SKILL_ASSET_BASE for any non-data callers. */
export const SKILL_ASSET_BASE = '/comfyart/skills'
/** #581 final list covers (11×462x346 webp), manifest review-assets 494/covers-final/manifest.json @7237c371.
 *  Each entry is [dir, commit]: v3 for 9, banner v3.1, character v3.2 (composed from the merged #574 templates). */
const COVER_V3 = '3c9b87e7eae72164efdd1fe30e00f576144475f4'
const COVERS_581: Record<string, readonly [string, string]> = {
  poster: ['494/covers-v3', COVER_V3], social: ['494/covers-v3', COVER_V3], brand: ['494/covers-v3', COVER_V3],
  packaging: ['494/covers-v3', COVER_V3], thumbnail: ['494/covers-v3', COVER_V3],
  banner: ['494/covers-v3.1', '9b23a3e8e3ca2f6b64dc16c0cf36fbf9c41fcaf4'],
  character: ['494/covers-v3.2', 'dc335056e81e0350e2f98487fb680e22ffb14bb9'],
  product: ['494/covers-v3', COVER_V3], motion: ['494/covers-v3', COVER_V3], interior: ['494/covers-v3', COVER_V3],
  'custom-workflow': ['494/covers-v3', COVER_V3],
}
const cover = (id: string) => {
  const [dir, commit] = COVERS_581[id]
  return `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${commit}/${dir}/${id}.webp`
}
/** #580 cut 2 — home-feed image sets, parallel to COVERS_581 / WASH_569: skill id → [dir, commit, files[]] on
 *  review-assets (commit-pinned). Empty until design delivers the washed home sets; skills absent here fall back. */
const QUICK_START_COVERS: Record<string, readonly [string, string, string]> = {}
const FEED_V1 = '98a34727037f806895a4baed34dd2a498cb9baa2'  // #588 PASS, manifest review-assets 580/featured-v1/manifest.json
const FEED_COVERS: Record<string, readonly [string, string, readonly string[]]> = {
  poster: ['580/featured-v1/poster', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  social: ['580/featured-v1/social', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  brand: ['580/featured-v1/brand', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  packaging: ['580/featured-v1/packaging', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  thumbnail: ['580/featured-v1/thumbnail', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  banner: ['580/featured-v1/banner', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  character: ['580/featured-v1/character', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  product: ['580/featured-v1/product', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  motion: ['580/featured-v1/motion', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  interior: ['580/featured-v1/interior', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
}
const pinned = (dir: string, commit: string, file: string) => `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${commit}/${dir}/${file}`
const quickStartCover = (id: string) => { const e = QUICK_START_COVERS[id]; return e ? pinned(e[0], e[1], e[2]) : undefined }
/** #588 — the two masonry special cards' collage images (580/embed-v1/manifest.json, commit-pinned). */
export const FEED_SPECIAL_COLLAGE: Readonly<Record<string, string>> = {
  capture: pinned('580/embed-v1', FEED_V1, 'inspiration@thumb.webp'),
  connector: pinned('580/embed-v1', FEED_V1, 'connector@thumb.webp'),
}
const feedCovers = (id: string) => { const e = FEED_COVERS[id]; return e ? e[2].map((f) => pinned(e[0], e[1], f)) : undefined }
/** #529 list/detail cover videos (10× short mp4 on review-assets; commit-pinned). */
const WASH_VIDEO_COMMIT = '1bbb3f208f18b26ef95c8d9f16efeea111c43ac7'
const video = (id: string) =>
  `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${WASH_VIDEO_COMMIT}/494/wash/videos/${id}.mp4`
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
  interior: '535d9568d1b8ca25e300fa32db1eca887889ba88', // 4 = 3 scenes @4:5 + 1:1 material mood board, manifest ea13dd4
  social: 'cb41cb8a450139cd903e777c8f84024019d517cd', // 10 @3:4 (小红书封面制作器), manifest e1b34fa
  banner: '8cc3fb305f7ce29ebbab63525680e3436e964dbb', // 1 × ~2:1 composite (4:3 + 3:4 side by side), manifest cd871d76
}
const ex541 = (skillId: keyof typeof EX_541, ids: number[]) =>
  ids.map((n) => `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${EX_541[skillId]}/541/wash/${skillId}/examples/${n}.webp`)
const wash541 = (commit: string, skillId: string, presetId: string) =>
  `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${commit}/541/wash/${skillId}/${skillId}__${presetId}.webp`
const washProduct541 = (presetId: string) => wash541(presetId === 'detail' ? WASH_541.productDetail : WASH_541.product, 'product', presetId)
/** #569 character (7) + motion (2) template washes, from review-assets manifest 881494ff (assets pinned to bd043d4c). */
const WASH_569_COMMIT = 'bd043d4cff5019fc4117b5b2f3a33ae437015a28'
// character final (manifest review-assets f81ce12a): v3 @b63d44ea under templates/v3/, 04/05 v3.1 @9024565c under templates/v3.1/
const CHARACTER_V2 = 'b63d44ea61085a77a1c990605c31ae552db36c71'
const CHARACTER_V3_1 = '9024565c9857c5cb79e3bce85e636f5f102ad181' // 04 + 05 re-washed under templates/v3.1/
type Wash569 = string | readonly [string, string, string]
const WASH_569: Record<'character' | 'motion', readonly Wash569[]> = {
  character: [['v3/01-character-turnaround-sheet', '569/wash', CHARACTER_V2], ['v3/02-expression-pose-sheet', '569/wash', CHARACTER_V2], ['v3/03-modeling-detail-reference-sheet', '569/wash', CHARACTER_V2], ['v3.1/04-outfit-form-variation-sheet', '569/wash', CHARACTER_V3_1], ['v3.1/05-prop-interaction-sheet', '569/wash', CHARACTER_V3_1], ['v3/06-basic-character-sheet', '569/wash', CHARACTER_V2], ['v3/07-complete-technical-character-sheet', '569/wash', CHARACTER_V2], ['v3/08-luxury-editorial-character-sheet', '569/wash', CHARACTER_V2]],
  motion: ['01-poster-animation', '02-first-to-last-frame-animation'],
}
// Manifest-driven (review-assets 569/wash/manifest.json @f81ce12a): an entry is a file name at WASH_569_COMMIT, or
// [name, dir, commit] when the manifest pins that template to another assets commit. A re-wash only edits this data.
const wash569 = (skillId: keyof typeof WASH_569, n: number) => {
  const e = WASH_569[skillId][n]
  const [name, dir, commit] = typeof e === 'string' ? [e, '569/wash', WASH_569_COMMIT] : e
  return `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${commit}/${dir}/${skillId}/templates/${name}@thumb.webp`
}
const P = (id: string, zh: string, en: string, prompt: string, image?: string): SkillPreset =>
  ({ id, name: { zh, en }, prompt, ...(image ? { image } : {}) })
type L = [zh: string, en: string]
function I(key: string, [zh, en]: L, type: SkillInput['type'], required = false, ph?: L): SkillInput {
  return { key, label: { zh, en }, type, ...(required ? { required } : {}), ...(ph ? { placeholder: { zh: ph[0], en: ph[1] } } : {}) }
}
/** #569 effect-example skills: right side is only 上传文件 + 补充描述. */
const EFFECT_INPUTS: SkillInput[] = [I('file', ['上传文件', 'Upload file'], 'image'), I('note', ['补充描述', 'Additional notes'], 'textarea', false, ['有什么想补充的吗？', 'Anything you want to add?'])]
/** #569 template skills: shared third field 视觉呈现方式. */
const VISUAL = I('visual', ['视觉呈现方式', 'Visual presentation'], 'text', false, ['补充想保留或避开的视觉要求，没有可以留空', 'Visual preferences to keep or avoid; leave blank if none'])

/** #494 — pick the current UI language from data-carried copy. */
export const loc = (text: { zh: string; en?: string }) => (lang === 'en' && text.en) || text.zh

/** #591 Phase1-S1 data contract + #592 Phase1-S2 production instructions for the upgrade 9
 *  (`brand` `packaging` `poster` `product` `character` `social` `motion` `banner` `thumbnail`).
 *  New 6 skeletons stay until #593. `interior` / `custom-workflow` untouched.
 *  Product lock: canvas f784c59b + box PRODUCT-LOCK-TOP15.md (gold UX site external — never name it in src).
 *  Keep existing covers/videos/feeds/presets/examples; #594 washes new-6 media later. Soft FU #596 separate.
 */
export const BUILTIN_SKILLS: Skill[] = [
  { id: 'poster', name: t('skills.posterDesign'), instructions: 'You are a production poster designer. Deliver print-ready compositions, not loose mood sketches.\n1) Brief: pull headline, subject, audience and use (event, promo, editorial) from the upload and notes.\n2) Hierarchy: one hero subject, strong headline typography in quotes, clear subcopy ladder, generous margins.\n3) Ratio: default 3:4; keep safe margins for print crop. Offer 2 distinct art directions when the brief is open.\n4) Finish: high contrast, legible at arm length, no clipped type. Put every on-art phrase in quotes.\n5) Refs: when the user uploaded a file, pass its shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ads', cover: cover('poster'), quickStartCover: quickStartCover('poster'), featured: feedCovers('poster'), video: video('poster'), examples: ex541('poster', [1, 2, 3, 4, 5]),
    inputs: EFFECT_INPUTS },
  { id: 'social', name: t('skills.socialMediaSet'), instructions: 'You are a production social content designer. Deliver a consistent set ready to post, not a single random frame.\n1) Brief: brand voice, product, and channel (feed / story) from the upload and notes.\n2) System: share one palette, type style and motif across a 1:1 feed, a 4:5 post and a 9:16 story.\n3) Copy: keep text short and mobile-legible; every on-art phrase in quotes.\n4) RedNote / lifestyle covers: bold subject, clean negative space for title stickers, high thumb-stop contrast.\n5) Refs: when a file is uploaded, pass its shape id in refs (ref_modes content) on every generate_image call.',
    category: 'social', cover: cover('social'), quickStartCover: quickStartCover('social'), featured: feedCovers('social'), video: video('social'), examples: ex541('social', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
    inputs: EFFECT_INPUTS },
  { id: 'brand', name: t('skills.brandIdentity'), instructions: 'You are a production brand-identity designer. Deliver a usable VI kit, not a single decorative mark.\n1) Discover: brand name, category, positioning and any elements to keep from brandInfo and brandAssets.\n2) Mark: design a primary logo mark on a plain background (1:1). State shape language, hex colors and type style precisely.\n3) System board: color palette swatches, primary + secondary lockups, and a clear typography specimen.\n4) Applications: at least one stationery or object mockup applying the mark; keep geometry identical across frames.\n5) Scope: when a template is selected, follow that template focus (logo system board vs mockup). Do not invent a new category.\n6) Refs: when brandAssets are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    category: 'branding', cover: cover('brand'), quickStartCover: quickStartCover('brand'), featured: feedCovers('brand'), video: video('brand'), presets: [P('geometric', '极简几何', 'Minimal geometric', 'Style: minimal geometric mark built from simple shapes, strict grid, two-color palette; deliver primary mark, lockup and palette board production-ready.', wash541(WASH_541.brand, 'brand', 'geometric')), P('handmade', '手作温暖', 'Handmade warmth', 'Style: hand-drawn warm mark, organic lines, earthy palette, craft paper textures; deliver primary mark plus warm stationery application.', wash541(WASH_541.brand, 'brand', 'handmade')), P('tech', '科技未来', 'Tech future', 'Style: futuristic tech identity, precise linework, gradient-free electric blue accents, monospace details; deliver mark, lockup and UI-ready glyph.', wash541(WASH_541.brand, 'brand', 'tech')), P('beauty', '美妆个护', 'Beauty & personal care', 'Style: beauty and personal care logo system presentation board, soft refined mark with primary and secondary lockups, monogram, color swatches and typography specimen laid out on a clean board, no product mockups.', wash541(WASH_541.brand, 'brand', 'beauty')), P('foodbev', '食品饮料', 'Food & beverage', 'Style: food and beverage logo system presentation board, lively mark with primary and stacked lockups, icon variant, color swatches and typography specimen laid out on a clean board, no product mockups.', wash541(WASH_541.brand, 'brand', 'foodbev')), P('pet', '宠物用品', 'Pet supplies', 'Style: pet supplies logo system presentation board, friendly playful mark with primary and secondary lockups, mascot icon, color swatches and typography specimen laid out on a clean board, no product mockups.', wash541(WASH_541.brand, 'brand', 'pet'))],
    inputs: [I('brandInfo', ['品牌资料', 'Brand details'], 'text', true, ['简单介绍品牌名称和主营业务，已有定位或要沿用的元素也写上', 'Brand name and main business, plus any positioning or elements to keep']), I('brandAssets', ['品牌素材', 'Brand assets'], 'image'), VISUAL] },
  { id: 'packaging', name: t('skills.packagingDesign'), instructions: 'You are a production packaging designer. Deliver shelf-ready concepts through structure, not flat posters.\n1) Brief: product, size, pack form and brand cues from packInfo and packAssets.\n2) Front: package front view on a clean studio background; call out material, finish and label layout.\n3) Structure: when relevant, show dieline / panel logic or a clear 3/4 mockup in context.\n4) Shelf: ensure the design reads at eye level in a retail row; keep logo and claims legible.\n5) Apply the selected packaging style focus (eco, foil, playful, panels, shelf).\n6) Refs: when packAssets are uploaded, pass shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'ecommerce', cover: cover('packaging'), quickStartCover: quickStartCover('packaging'), featured: feedCovers('packaging'), video: video('packaging'), presets: [P('eco', '自然环保', 'Natural eco', 'Style: natural eco packaging, kraft and recycled paper, botanical line art, muted greens; show front label hierarchy and material callouts.', wash541(WASH_541.packaging, 'packaging', 'eco')), P('gold', '奢华烫金', 'Luxury gold foil', 'Style: luxury packaging, deep matte color with gold foil stamping, embossed logo; keep foil readable at shelf distance.', wash541(WASH_541.packaging, 'packaging', 'gold')), P('playful', '潮玩插画', 'Playful illustration', 'Style: playful illustrated packaging, bright characters, bold outlines, pop colors; keep character on-pack consistent across panels.', wash541(WASH_541.packaging, 'packaging', 'playful')), P('panels', '展开结构图', 'Panels & structure', 'Style: packaging panels and structural dieline, flat unfolded box with front, back and side panels laid out.', wash541(WASH_541.packaging, 'packaging', 'panels')), P('shelf', '货架陈列', 'Shelf display', 'Style: packaging shelf display, the product repeated in rows on a retail shelf, eye-level store lighting.', wash541(WASH_541.packagingShelf, 'packaging', 'shelf'))],
    inputs: [I('packInfo', ['商品与包装资料', 'Product & packaging details'], 'text', true, ['简单说明要包装的商品、规格和包装形式', 'What product is being packaged, its size and package type']), I('packAssets', ['商品与包装素材', 'Product & packaging assets'], 'image'), VISUAL] },
  { id: 'thumbnail', name: t('skills.youtubeThumbnail'), instructions: 'You are a production cover / thumbnail designer for video and short drama. Deliver clickable covers, not vague key art.\n1) Brief: title mood, subject and platform (16:9 video or vertical short-drama cover) from the upload and notes.\n2) Hook: big expressive subject, 2-4 word bold title in quotes, high contrast, readable at small size.\n3) Variants: offer 2 variations with different crop or emotion while keeping the same title lockup.\n4) Safe area: keep faces and title clear of UI chrome edges.\n5) Refs: when a file is uploaded, pass its shape id in refs (ref_modes content) on every generate_image call.',
    category: 'social', cover: cover('thumbnail'), quickStartCover: quickStartCover('thumbnail'), featured: feedCovers('thumbnail'), video: video('thumbnail'), examples: ex541('thumbnail', [1, 2, 3, 4, 5, 6]),
    inputs: EFFECT_INPUTS },
  { id: 'banner', name: t('skills.bannerDesign'), instructions: 'You are a production banner designer for web and campaign placement. Deliver crop-safe wide frames, not square posts.\n1) Brief: campaign goal, offer and placement width from the upload and notes.\n2) Layout: wide 21:9 or 16:9; headline on one side, visual on the other; clear CTA text in quotes.\n3) Safe margins: protect type and logo from edge crop across common ad slots.\n4) Hierarchy: one focal product or scene; avoid cluttered multi-offer walls.\n5) Refs: when a file is uploaded, pass its shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ads', cover: cover('banner'), quickStartCover: quickStartCover('banner'), featured: feedCovers('banner'), video: video('banner'), examples: ex541('banner', [1]),
    inputs: EFFECT_INPUTS },
  { id: 'character', name: t('skills.characterSheet'), instructions: 'You are a production character-sheet designer. Deliver turnaround-ready reference boards for downstream art and IP.\n1) Lock identity: from characterRef and characterInfo, freeze face, body, outfit colors and key props.\n2) Board: follow the selected template (turnaround, expression, modeling detail, outfit, prop, basic, technical, editorial).\n3) Consistency: identical proportions, palette and costume language across every cell in the sheet.\n4) Presentation: prefer clean backgrounds; label nothing with stray UI chrome; keep sheets readable as production refs.\n5) Refs: when characterRef images are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    cover: cover('character'), quickStartCover: quickStartCover('character'), featured: feedCovers('character'), video: video('character'), featuredPreset: 'editorial', presets: [P('turnaround', '角色转身板', 'Character Turnaround Sheet', 'Template: character turnaround sheet, full-body front, side and back views evenly spaced in one row on a white background.', wash569('character', 0)), P('expression', '表情动作板', 'Expression & Pose Sheet', 'Template: expression and pose sheet, a row of head-shot expressions above full-body poses (standing, walking, sitting).', wash569('character', 1)), P('modeling', '建模细节参考板', 'Modeling Detail Reference Sheet', 'Template: modeling detail reference sheet, full-body angles on the left and close-up cells of face, eyes, lips, ears, hair, hands and shoes on the right.', wash569('character', 2)), P('outfit', '服装/形态变体板', 'Outfit / Form Variation Sheet', 'Template: outfit variation sheet, the same character in three different outfits shown full body side by side.', wash569('character', 3)), P('prop', '道具互动板', 'Prop Interaction Sheet', 'Template: prop interaction sheet, full-body poses holding a prop on top and close-up cells of hands and prop below.', wash569('character', 4)), P('basic', '基础角色板', 'Basic Character Sheet', 'Template: basic character sheet, full-body three views on the left and four head-shot expressions on the right.', wash569('character', 5)), P('technical', '完整技术角色板', 'Complete Technical Character Sheet', 'Template: complete technical character sheet, multi-angle full body, an expression grid, outfit items, color swatches and detail close-ups.', wash569('character', 6)), P('editorial', '时装大片角色板', 'Editorial Fashion Sheet', 'Template: editorial fashion sheet, the reference character as the lead in a luxury-brand fashion campaign style; full-body standing pose, half-body and face close-ups of the same person, keeping facial features, hairstyle and body shape consistent, soft studio lighting, clean light background, no text or logos.', wash569('character', 7))],
    inputs: [I('characterRef', ['角色参考图片', 'Character reference images'], 'image'), I('characterInfo', ['角色资料', 'Character details'], 'text', false, ['描述角色外观，以及这次需要保持一致的地方', 'Describe the look and what must stay consistent this time']), VISUAL] },
  { id: 'product', name: t('skills.eCommerceProductImages'), instructions: 'You are a production e-commerce product photographer / art director. Deliver listing-ready image sets for Amazon, Taobao and A+.\n1) Lock the product: from productImage and productInfo, keep silhouette, materials, logo and color identical in every frame.\n2) Hero: clean white-background 1:1 main image, soft shadow, product centered.\n3) Set: add lifestyle context and a material detail close-up; for A+ style, plan a clear benefit sequence without rewriting claims as paragraphs.\n4) Apply the selected shot focus (white, lifestyle, detail, electronics, food, beauty).\n5) Refs: ALWAYS pass the product image shape id in refs (ref_modes content) on every generate_image call; describing it in the prompt does not send the image.',
    category: 'ecommerce', cover: cover('product'), quickStartCover: quickStartCover('product'), featured: feedCovers('product'), video: video('product'), presets: [P('white', '白底主图', 'White background hero', 'Focus on the white-background hero shot: pure white seamless background, soft shadow, product centered; listing-ready 1:1 main image.', washProduct541('white')), P('lifestyle', '生活场景', 'Lifestyle scene', 'Focus on the lifestyle scene: product in use in a realistic home setting, natural light; keep product identity locked to the hero.', washProduct541('lifestyle')), P('detail', '细节特写', 'Detail close-up', 'Focus on the detail close-up: macro view of material and craftsmanship, shallow depth of field; useful as A+ or PDP inset.', washProduct541('detail')), P('electronics', '数码电子', 'Electronics', 'Focus on the electronics hero: earbuds and their charging case on a clean studio backdrop, crisp reflections, precise edges.', washProduct541('electronics')), P('food', '美食', 'Food', 'Focus on the food hero: appetizing close shot, fresh ingredients as props, warm natural light, rich texture.', washProduct541('food')), P('beauty', '美妆个护', 'Beauty', 'Focus on the beauty hero: skincare or cosmetic product on soft pastel surfaces, gentle diffused light, clean premium mood.', washProduct541('beauty'))],
    inputs: [I('productImage', ['商品图片', 'Product images'], 'image', true), I('productInfo', ['商品资料', 'Product details'], 'text', false, ['补充商品名称、真实卖点和使用场景', 'Product name, real selling points and use cases']), VISUAL] },
  { id: 'motion', name: t('skills.motionPoster'), instructions: 'You are a production motion designer for UGC ads, product TVC stills-to-video and poster animation.\n1) Still first: if stillArt is missing, generate a strong 3:4 or 9:16 key still with generate_image and wait for it.\n2) Animate: drive animate_image from that image shape with subtle, readable motion (loop on); keep titles sharp.\n3) Preset focus: Poster Animation keeps text locked while the scene breathes; First-to-Last Frame Animation morphs cleanly between two planned frames.\n4) Ad intent: prefer product-hero or UGC-style energy over abstract noise; CTA text in quotes when present.\n5) Refs: pass the still shape id into animate_image; never invent motion on a missing frame.',
    category: 'ads', cover: cover('motion'), quickStartCover: quickStartCover('motion'), featured: feedCovers('motion'), video: video('motion'), presets: [P('poster', '海报动画', 'Poster Animation', 'Template: poster animation for ads — lock the still, then subtle looping motion; show static vs animated pair; text stays sharp and readable.', wash569('motion', 0)), P('firstlast', '首帧到末帧动画', 'First-to-Last Frame Animation', 'Template: first-to-last frame animation for product TVC beats — plan first and last frames that share layout and transition smoothly.', wash569('motion', 1))],
    inputs: [I('stillArt', ['静态原稿', 'Static artwork'], 'image', true), I('motionNotes', ['动态要求', 'Motion requirements'], 'text', false, ['说明希望怎么动，哪些部分保持不动', 'How it should move and what should stay still']), VISUAL] },
  // #591 Phase1 new 6 — skeleton cut2 fields; washed cover/video/featured/#594 later. No near-duplicate of upgrade-9 intents.
  { id: 'multi-angle', name: t('skills.multiAngleImageGenerator'), instructions: 'Generate a multi-angle set of the same subject (product or person). Keep identity, materials and proportions locked across views. Deliver front, 3/4, side and detail angles on clean or matching backgrounds. When the user uploads a reference, pass its shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ecommerce',
    inputs: [I('subjectImage', ['主体图片', 'Subject images'], 'image', true), I('angleBrief', ['角度与用途', 'Angles & use'], 'text', false, ['需要哪些角度、用途（详情页/广告）', 'Which angles and where they will be used (PDP / ads)']), VISUAL] },
  { id: 'logo-material', name: t('skills.logoMaterialExplorer'), instructions: 'Explore the uploaded logo as a 3D material study: keep the mark geometry identical while varying finish (metal, glass, plastic, fabric, ceramic). Show each material on a neutral studio turntable or soft gradient. Do not redesign the logo or invent a full brand system — this skill is material only.',
    category: 'branding',
    inputs: [I('logoImage', ['Logo 图片', 'Logo image'], 'image', true), I('materialNotes', ['材质偏好', 'Material preferences'], 'text', false, ['想试的材质、光泽或场景，可留空', 'Materials, finishes or scenes to try; leave blank if none']), VISUAL] },
  { id: 'meta-ads', name: t('skills.metaAdsCreative'), instructions: 'Create a Meta (Facebook/Instagram) paid-social creative pack: 1:1 feed, 4:5 feed and 9:16 story/reel frames that share one campaign idea, palette and CTA in quotes. Keep text short and high-contrast for mobile. Prefer photo-led UGC or product-hero treatments over static website banners.',
    category: 'ads',
    inputs: [I('campaignBrief', ['投放简报', 'Campaign brief'], 'text', true, ['产品、受众、卖点与 CTA', 'Product, audience, offer and CTA']), I('adAssets', ['投放素材', 'Ad assets'], 'image'), VISUAL] },
  { id: 'mobile-ui', name: t('skills.mobileAppVisualDesign'), instructions: 'Design mobile app visual screens: coherent type scale, spacing and component language across 2–4 key flows (home, detail, checkout or onboarding). Deliver phone-framed mockups at ~9:19.5 with clear hierarchy and accessible contrast. Prefer product UI, not marketing landing posters.',
    category: 'website',
    inputs: [I('appBrief', ['应用与页面资料', 'App & screen brief'], 'text', true, ['应用名称、目标用户与要做的页面', 'App name, audience and screens to design']), I('uiRefs', ['界面参考', 'UI references'], 'image'), VISUAL] },
  { id: 'web-product', name: t('skills.webProductVisualDesign'), instructions: 'Design web product visuals: landing or product-page hero, feature modules and UI chrome that share one system. Use desktop 16:9 plus an optional responsive crop. Keep marketing copy short; focus on layout, illustration/photo treatment and component consistency — not a printable poster.',
    category: 'website',
    inputs: [I('webBrief', ['产品与页面资料', 'Product & page brief'], 'text', true, ['产品名称、页面目标与关键模块', 'Product name, page goal and key modules']), I('webRefs', ['视觉参考', 'Visual references'], 'image'), VISUAL] },
  { id: 'marketing-campaign', name: t('skills.marketingCampaignGenerator'), instructions: 'Plan and visualize a cross-platform marketing campaign: one big idea, then keyed frames for social, display and a hero key visual that share motif, palette and slogan in quotes. Show how the system adapts across ratios without becoming a single poster or a Meta-only ad set.',
    category: 'ads',
    inputs: [I('campaignGoal', ['战役目标', 'Campaign goal'], 'text', true, ['品牌/产品、目标与主口号', 'Brand/product, goal and lead slogan']), I('campaignAssets', ['品牌与参考素材', 'Brand & reference assets'], 'image'), VISUAL] },
  { id: 'interior', name: t('skills.interiorArchitecturalVisualization'), instructions: 'Produce photoreal interior or architecture renders: eye-level wide shot, natural light, accurate materials, 16:9. Add a detail vignette at 4:3.',
    cover: cover('interior'), quickStartCover: quickStartCover('interior'), featured: feedCovers('interior'), video: video('interior'), examples: ex541('interior', [1, 2, 3, 4]),
    inputs: EFFECT_INPUTS },
  { id: 'custom-workflow', name: t('skills.customWorkflow'), instructions: `${rulesText()}\n\nUse the custom_workflow tool for every step; action rules returns these same rules.`,
    cover: cover('custom-workflow'),
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
/** Display order of category chips; a category no skill uses is dropped by `skillChips` (#591: `website` appears once `mobile-ui`/`web-product` land). */
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
/** #580 cut 2 — video skills whose quick-start tile is the video's first frame (design v2 / product confirmed). */
export const QUICK_START_VIDEO_FIRST: ReadonlySet<string> = new Set(['motion'])
/** #580 cut 2 — home quick-start row image: optional `quickStartCover` override; default = video skills' first frame,
 *  else the Skills-module `cover` (center-cropped to 4:3 by CSS object-fit). */
export function skillQuickStartCover(skill: Skill): { src: string; own: 'bundled' | 'userdata' | 'video' } | null {
  if (skill.quickStartCover) return { src: skill.quickStartCover, own: 'bundled' }
  if (QUICK_START_VIDEO_FIRST.has(skill.id) && skill.video) return { src: skill.video, own: 'video' }
  return skillCover(skill)
}

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

/** #541 — design-spec meta line under the description. Only real data: no usage counter exists in our data, so the line
 *  carries the template count alone (never a made-up 「已使用N次」); no presets → null (no line). */
export function skillMeta(skill: Skill): { templates: number } | null {
  const n = skill.presets?.length ?? 0
  return n ? { templates: n } : null
}

/** #494-2 — the preset's own image, else the skill's list cover (one decision point, like `skillCover`). */
export function presetImage(skill: Skill, preset: SkillPreset): string | null {
  return preset.image ?? skillCover(skill)?.src ?? null
}

/** #580 — home 「Skill 案例」 tiles, data-driven from the skill list (no demo rows).
 *  Example-type skills (`examples`) contribute their 「效果示例」 images; template-type skills their presets' own images.
 *  `featured` (preset id) moves that template to the front of the skill's queue.
 *  Round-robin: one image per skill per round, in list order; no repeated image, and never two adjacent tiles
 *  from the same skill (a tile that would be is dropped, which only happens once a single skill is left). */
export interface SkillFeaturedCase { skill: Skill; preset: SkillPreset | null; image: string; key: string }
export function skillFeaturedCases(skills: Skill[]): SkillFeaturedCase[] {
  const queues = skills.map((skill) => {
    const q: SkillFeaturedCase[] = []
    if (skill.featured?.length) {
      skill.featured.forEach((image, i) => { if (image) q.push({ skill, preset: null, image, key: `${skill.id}:feed${i}` }) })
    } else if (skill.examples?.length) {
      skill.examples.forEach((image, i) => { if (image) q.push({ skill, preset: null, image, key: `${skill.id}:ex${i}` }) })
    } else {
      const presets = [...(skill.presets ?? [])]
      const first = presets.findIndex((p) => p.id === skill.featuredPreset)
      if (first > 0) presets.unshift(...presets.splice(first, 1))
      for (const preset of presets) if (preset.image) q.push({ skill, preset, image: preset.image, key: `${skill.id}:${preset.id}` })
    }
    return q
  }).filter((q) => q.length)
  const out: SkillFeaturedCase[] = []
  const seen = new Set<string>()
  for (let round = 0; queues.some((q) => q.length > round); round++) {
    for (const q of queues) {
      const c = q[round]
      if (!c || seen.has(c.image)) continue
      if (out.length && out[out.length - 1]!.skill.id === c.skill.id) continue
      seen.add(c.image)
      out.push(c)
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
