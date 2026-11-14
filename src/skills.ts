import { atom } from 'tldraw'
import { applyRaw748, assetDir } from './skillRaw748'
import { unzipSync } from 'fflate'

import { deleteUserFile, listUserFiles, readUserText, uploadImage, viewUrl, writeUserText } from './comfy'
import { lang, t } from './i18n'
import { uuid } from './id'
import { BRAND } from './brand'

/** #494 — zh/en copy carried by the skill data itself (not locales), so adding a skill never touches UI code. */
export interface LocText { zh: string; en: string }
/** #494 — Explore category (data only, never hardcoded in components). Unset = only under 「为你推荐」. A category with no skill gets no chip. */
export type SkillCategory = 'ecommerce' | 'branding' | 'social' | 'website' | 'ads'
/** #494 — one preset (template): `prompt` is the style text appended after the skill's instructions when the user runs
 *  the skill with this preset (step 2). `image` is the preset's own example image; unset → the skill's list cover. */
export interface SkillPreset { id: string; name: LocText; prompt?: string; image?: string; /** #575 — optional template hover/detail mp4; unset → still `image` / skill cover. */ video?: string
  /** #748 — stack-expand tile: real media[] layers. Data-driven; unset → plain tile. */
  stack?: string[]
  /** #760 — rest pile orientation from primary media.ratio (<1 → portrait). */
  stackOrient?: 'portrait' | 'landscape'
  /** #760 — single-cover orientation when no stack (Master Packaging 0.75 → portrait frame). */
  mediaOrient?: 'portrait' | 'landscape'
  /** #748 — this template's own right-panel form (reference content.template.questions[]); unset → skill.inputs. */
  inputs?: SkillInput[]
  /** #751 — media indices (0 = cover, 1.. = stack) still on the unified PENDING_WASH placeholder. */
  pendingWash?: number[]
  /** #751 — our product one-liner for this template (COPY-REWRITE). */
  description?: LocText }
/** #748 §C — left media[]: data-driven template/example tiles. Same renderer branches on `type`; stack carries children.
 *  TODO(#748): seeded from presets until the product media dump lands; then fill per skill. */
export interface SkillMediaItem {
  type: 'image' | 'video' | 'stack'; url: string; ratio?: string; cover?: string
  /** links the tile to a preset (selection → 当前模板 + run params) */
  presetId?: string; name?: LocText; children?: SkillMediaItem[]
  /** #748 per-media 「已使用 N 次」 (follows the selected template). Source: OUR stats only (never copy reference-API usage numbers); filled from getTemplateUsage (localStorage) — 0 ⇒ usage line hidden. */
  usedCount?: number
}
/** #494 — one field of the skill's input dialog. Label / placeholder / default / required all come from here. */
export interface SkillInput {
  key: string; label: { zh: string; en?: string }; type: 'text' | 'textarea' | 'select' | 'image'; required?: boolean
  options?: { value: string; label: { zh: string; en?: string } }[]; default?: string; placeholder?: LocText
  /** max characters for text/textarea (500 on Additional Details; 200 where the raw field caps it). */
  maxLength?: number
  /** upload media kind for `image` fields; 'video' plays back as a clip. Unset → image. */
  accept?: 'image' | 'video'
  /** #748 — IMAGE_UPLOAD limits from the converted raw (max files / MB per file). */
  maxCount?: number; maxSizeMb?: number
}
export interface Skill {
  id: string; name: string; description?: string; instructions: string; files?: Record<string, string>; images?: Record<string, string>; custom?: boolean; learned?: string[]
  /** #978 — the template this composer attachment was opened with (set by `withPreset`). Unset = no template
   *  selected, so the send boundary adds nothing and the skill behaves exactly as before. */
  activePreset?: string
  /** #494 built-in metadata. Imported / personal skills have none of these and need no migration. */
  category?: SkillCategory; cover?: string; video?: string; presets?: SkillPreset[]; inputs?: SkillInput[]; media?: SkillMediaItem[]
  /** #541/#575 「效果示例」 carousel media (commit-pinned stills and/or short mp4). Unset → the section is not rendered.
   *  #641: an explicit empty list renders 「暂无示例」 when `presetChips` is set. */
  examples?: string[]
  /** #751: indices of examples[] still on the unified PENDING_WASH placeholder. */
  pendingWash?: number[]
  /** #641 — text preset chips (first preset selected). No per-preset still; switching stays inside the dialog. */
  presetChips?: boolean
  /** #580 cut 2 — the three image slots, one per surface: `cover` = Skills module (above, unchanged);
   *  `quickStartCover` = home 「用 Skill 快速开始」 row (fixed 4:3); `featured` = home masonry images
   *  (natural ratio, full-bleed). Unset → fall back to the existing images (see skillQuickStartCover / skillFeaturedCases). */
  quickStartCover?: string
  /** #602 — home quick-start cover object-fit. Default `cover` (full-bleed). Set `contain` for letterbox on the card plate. */
  quickStartCoverFit?: 'cover' | 'contain'
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
/** #594 Phase1 new6 covers (494/covers-v4) + featured-v2 + 594/wash examples — eye PASS 6/6 incl. mobile-ui cover regen. */
const WASH_594 = 'cc76d743d416c3d9a9a6852d811a7a80caf40319'
const COVER_V4 = WASH_594
/** #778 banner cover + single-brand featured 03 (review-assets 778/wash, kie I2I). */
const WASH_778 = '79bf01dc6342363348671c368fa1d467706a0e0f'
const WASH_778_EX01 = 'e9c0f21959787a9c7401fa95927db3e3e6931bcd'
/** #779 product cover (white-bg grid) + single-brand featured (review-assets 779/wash, kie I2I). */
const WASH_779 = '47bd97529fffde96a515b0eb44a45b41284deba0'
/** #784 product cover BR lip-tube wash + 7 RESULT video templates (review-assets 784/wash). Featured stays WASH_779. */
const WASH_784 = 'd17ae7c9a27b84ab0f0781bccee100778a9f1e18'
/** #786 brand-identity rewash: cover SOLENNE + featured 01-04 + 6 templates (review-assets 786/wash, kie I2I). */
const WASH_786 = '8ab5aa8044d71e9518ae5f054eb2f8c7e77dd127'
/** #786 r2 template remap to collection titles (餐饮服务=SOLENNE, 服装配饰=LINTEL, 家居生活=ROWAN HOUSE); review-assets 786/wash-r2. */
/** #788 character rewash: cover SIENNA VALE + featured 01-04 + 8 templates (review-assets 788/wash, kie I2I). */
const WASH_788 = '1f66faf48e8dbd625b4acf79505adb320586ad14'
/** #788 r2: featured 03 ELINA VOS rewash (tank-neck jumpsuit; review-assets 788/wash-r2). Other featured stay WASH_788. */
const WASH_788_F03 = '03cd43443ea200d8c372fe083245b67ef13c7d27'
/** logo-material r2: cover VELA liquid-chrome (+Seedance hero mp4), examples VELA/KAIO/LUMORA, featured HALO/QUILL/PRISM/TERRA (review-assets wash-lm @58f1e3e9; WaveSpeed edit+I2V; Jingmeng bar). */
const WASH_LM = '58f1e3e9ebe225e61363f0e7688149c0c6a49813'
/** mobile-ui rewash: cover SAELIN (+hero mp4), 13 examples, featured LUNEL/KIPLET/DAYOR/SYNRA (review-assets wash-mu, kie I2I). */
const WASH_MU = '4ef9ce65c6aef5afa6490c3835b80a6f925382c6'
/** web-product rewash: cover ORIVA/KINLO/AYRA (+hero mp4), 9 examples, featured ORIVA/AUREN/NEXARA/VARDA (review-assets wash-wp, WaveSpeed I2I; kie 402). */
const WASH_WP = '2438e1d8245b720d560d72a3b659551af0e95db9'
const WASH_786_R2 = 'f5c9d7770df7a8ef92cd4411371ff5b552b83eee'
/** #806 — 动态海报 cover + grid hover. Triptych of the washed poster (1324×992). */
const WASH_806 = 'ff874a61fa77c9f6e25fe0c6a6a4e116d0378d26'
const COVERS_581: Record<string, readonly [string, string]> = {
  'poster-differentiated-compiler': ['494/covers-v3', COVER_V3], 'rednote-cover-maker': ['494/covers-v3', COVER_V3], 'brand-identity-director': ['786/wash', WASH_786], /* #786 SOLENNE */
  'packaging-design-director': ['494/covers-v3', COVER_V3], 'cover-design-director': ['494/covers-v3', COVER_V3],
  'banner-design-director': ['778/wash', WASH_778], // #778: fintech hero cover (was VENTUR brand board)
  'character-sheet-design': ['788/wash', WASH_788], // #788 SIENNA VALE
  'product-tvc-advertisement-generator': ['784/wash', WASH_784], /* #784: BR lip-tube wash; featured stays 779 */ 'motion-poster-generator': ['806/wash', WASH_806], /* #806: LUMEN DRIFT triptych, same poster as the template wash */ 'interior-architectural-visualization': ['494/covers-v3', COVER_V3],
  'universal-multi-angle-grid': ['494/covers-v4', COVER_V4], 'logo-material-explorer': ['wash-lm', WASH_LM], // VELA
  'meta-ads-creative-director': ['494/covers-v4', COVER_V4], 'mobile-app-visual-design': ['wash-mu', WASH_MU], // SAELIN
  'web-product-visual-design': ['wash-wp', WASH_WP], // ORIVA/KINLO/AYRA
  'marketing-campaign-generator': ['494/covers-v4', COVER_V4],
}
const cover = (id: string) => {
  const [dir, commit] = COVERS_581[id]
  return `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${commit}/${dir}/${assetDir(id)}.webp`
}
/** #580 cut 2 — home-feed image sets, parallel to COVERS_581 / WASH_569: skill id → [dir, commit, files[]] on
 *  review-assets (commit-pinned). Empty until design delivers the washed home sets; skills absent here fall back. */
const QUICK_START_COVERS: Record<string, readonly [string, string, string]> = {}
const FEED_V1 = '0e92302302de2102ab6f66aa7633a40945a381c7'  // #590 wash-v2 PASS (supersedes #588 pin / wash-v1 b85f38cd)
const FEED_V2 = WASH_594  // #594 new6 featured-v2
const FEED_COVERS: Record<string, readonly [string, string, readonly string[]]> = {
  'poster-differentiated-compiler': ['580/featured-v1/poster', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'rednote-cover-maker': ['580/featured-v1/social', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'brand-identity-director': ['786/wash/brand/featured', WASH_786, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'packaging-design-director': ['777/wash/packaging/featured', 'e270088ea1695f5200669649e6e832057e9c8a6a', ['01.webp', '02.webp', '03.webp', '04.webp']], /* #777: featured → AURELIA */
  'cover-design-director': ['580/featured-v1/thumbnail', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'banner-design-director': ['580/featured-v1/banner', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'character-sheet-design': ['788/wash/character/featured', WASH_788, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'product-tvc-advertisement-generator': ['779/wash/product/featured', WASH_779, ['01.webp', '02.webp', '03.webp', '04.webp']], // #779 NODAL single brand, no portraits
  // #806: 动态海报 featured = the two same-topic template stills (poster motion ~4:3, start/end 9:16).
  // The 580 feed (series poster, car board, original-face still, night-street dress) is not this mapping.
  'motion-poster-generator': ['569/wash/motion/templates', 'bd043d4cff5019fc4117b5b2f3a33ae437015a28', ['01-poster-animation.webp', '02-first-to-last-frame-animation.webp']],
  'interior-architectural-visualization': ['580/featured-v1/interior', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'universal-multi-angle-grid': ['580/featured-v2/multi-angle', FEED_V2, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'logo-material-explorer': ['wash-lm/logo-material/featured-r2', WASH_LM, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'meta-ads-creative-director': ['580/featured-v2/meta-ads', FEED_V2, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'mobile-app-visual-design': ['wash-mu/mobile-ui/featured', WASH_MU, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'web-product-visual-design': ['wash-wp/web-product/featured', WASH_WP, ['01.webp', '02.webp', '03.webp', '04.webp']],
  'marketing-campaign-generator': ['580/featured-v2/marketing-campaign', FEED_V2, ['01.webp', '02.webp', '03.webp', '04.webp']],
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
  id === 'motion-poster-generator'
    ? pinned('806/wash', WASH_806, 'motion.mp4')
    : `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${WASH_VIDEO_COMMIT}/494/wash/videos/${assetDir(id)}.mp4`
/** #575 — media URL is a short cover/example video (mp4/webm/mov). Stills stay images; no fake video badge without data. */
export function isSkillMediaVideo(src: string | null | undefined): boolean {
  return !!src && /\.(mp4|webm|mov)(\?|#|$)/i.test(src)
}
/** #623 — new6 hover mp4s wired @ design pin `assets/623-new6-hover-v1` (soft PASS).
 *  Paths: 594/wash/videos/<id>.mp4 via absolute raw.githubusercontent commit-pin (same as #605 / FEED).
 *  Empty pending list = all six shipped; keep export for harness mutation surface. */
export const SKILL_VIDEO_PENDING_NEW6 = [] as const
/** #623 design soft PASS pin SHA for new6 cover hover videos. */
const WASH_623_NEW6_VIDEO = 'd03ea7938877d084c201a94ef51f943dd0e061b9'
const video594 = (id: string) =>
  `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${WASH_623_NEW6_VIDEO}/594/wash/videos/${assetDir(id)}.mp4`
/** #541 AC rev 2 washes on review-assets (541/wash/<skill>/<skill>__<preset>.webp; each pinned to its own commit). */
const WASH_541 = {
  brand: WASH_786_R2, // #786 r2 rewash (was f2045022); 4:3 stacked, 品牌视觉识别
  packaging: 'c26cfaddc5e12c8652b151ef09ad12c47b2062a0', // 4:3, 品牌包装设计系统 (5); manifest c26cfad (mockup dropped, same 5 images as 1014ef2)
  packagingShelf: '35c819e64b38cc7d64dcd814ae8b86133976fc8a', // shelf re-wash: retail shelf rows (manifest d574dda6)
}
/** #751: Final-16 example media are NOT hand lists here — slot→asset lives in src/data/wash-748.json (1:1 with raw highlights). */
// #637 Phase2-S4 B NEW5 soft wash — cover/examples/featured (+ single-video example.mp4).
// Layout hardMax from phase2/bc-refs meta: flash-cut/commerce = 1 video slot;
// style-transfer = 4 stills; person-swap = 1 still; lifestyle-scene = 2 stills.
const WASH_637 = '2109c085aa74c617cd34517f99626f357062c81c'
const cover637 = (id: string) => pinned(`637/wash/${id}`, WASH_637, 'cover.webp')
const ex637 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`637/wash/${id}/examples`, WASH_637, `${String(n).padStart(2, '0')}.webp`))
const feat637 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`637/wash/${id}/featured`, WASH_637, `${String(n).padStart(2, '0')}.webp`))
const video637 = (id: string) => pinned(`637/wash/${id}`, WASH_637, 'example.mp4')
// #643 Phase3-S4 true wash (kie offline) — thumbnail + NEW19 covers; batch1 examples wired (featured empty).
const WASH_643 = '15e9bdad271dc2cb0ac1a1c8621927c161ca9299'
const cover643 = (id: string) => pinned(`643/wash/${assetDir(id)}`, WASH_643, 'cover.webp')
// #643 per-slot PRs: optional per-slot pin so each slot merges independently.
const ex643 = (id: string, ids: number[], pin: string = WASH_643) =>
  ids.map((n) => pinned(`643/wash/${assetDir(id)}/examples`, pin, `${String(n).padStart(2, '0')}.webp`))
const feat643 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`643/wash/${assetDir(id)}/featured`, WASH_643, `${String(n).padStart(2, '0')}.webp`))
// #687 Phase1 remaining rewash — social / interior / meta-ads / marketing-campaign (thumbnail+poster already PASS).
// assetDir folders under 687/wash/; examples 1:1 via wash-748.json; cover+hover video pinned here.
const WASH_687 = '5c954dbcefb8bd50edef69688b303122debb4ffb'
const cover687 = (id: string) => pinned(`687/wash/${assetDir(id)}`, WASH_687, 'cover.webp')
const video687 = (id: string) => pinned(`687/wash/${assetDir(id)}`, WASH_687, 'cover.mp4')
const feat687 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`687/wash/${assetDir(id)}/examples`, WASH_687, `${String(n).padStart(2, '0')}.webp`))
// #777 packaging cover rewash — drop LUMIERE ARTISAN; single brand AURELIA ATELIER. Featured/presets stay 5 (#541 ref collection).
const WASH_777 = 'e270088ea1695f5200669649e6e832057e9c8a6a'
const cover777 = (id: string) => pinned(`777/wash/${assetDir(id)}`, WASH_777, 'cover.webp')
// #673 C group re-wash; #743 pin → main merge 15e9bdad (#736 wash: ppt p07, promo ex01 platform, taobao cover+ex07).
// logo carousel4; photo-split/ppt still1; promo still1; naive carousel4; featured = cover + examples.
const WASH_673 = '15e9bdad271dc2cb0ac1a1c8621927c161ca9299'
const cover673 = (id: string) => pinned(`673/wash/${id}`, WASH_673, 'cover.webp')
const ex673 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`673/wash/${id}/examples`, WASH_673, `${String(n).padStart(2, '0')}.webp`))
const feat673 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`673/wash/${id}/featured`, WASH_673, `${String(n).padStart(2, '0')}.webp`))
// #812 D-group wash (yingzao / crt-interface / crayon-sketch / fabric-collage); pin → assets tip.
const WASH_812 = 'b84ab51b402b2e2ef0102c5b97d7bca8f41ea0a1'
const cover812 = (id: string) => pinned(`812/wash/${id}`, WASH_812, 'cover.webp')
const ex812 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`812/wash/${id}/examples`, WASH_812, `${String(n).padStart(2, '0')}.webp`))
const feat812 = (id: string, ids: number[]) =>
  ids.map((n) => pinned(`812/wash/${id}/featured`, WASH_812, `${String(n).padStart(2, '0')}.webp`))
const wash541 = (commit: string, skillId: string, presetId: string) =>
  `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${commit}/${commit === WASH_786_R2 ? '786/wash-r2' : '541/wash'}/${assetDir(skillId)}/${assetDir(skillId)}__${presetId}.webp`
const washProduct784 = (n: string, kind: 'image' | 'video' = 'image') =>
  pinned(`784/wash/product/examples`, WASH_784, `${n}.${kind === 'video' ? 'mp4' : 'webp'}`)
/** #569 character (7) + motion (2) template washes, from review-assets manifest 881494ff (assets pinned to bd043d4c). */
const WASH_569_COMMIT = 'bd043d4cff5019fc4117b5b2f3a33ae437015a28'
// character: #788 rewash under 788/wash/character/templates/v4 (superseded 569 v3 @b63d44ea / v3.1 @9024565c)
type Wash569 = string | readonly [string, string, string]
const WASH_569: Record<'character-sheet-design' | 'motion-poster-generator', readonly Wash569[]> = {
  'character-sheet-design': [['v4/01-character-turnaround-sheet', '788/wash', WASH_788], ['v4/02-expression-pose-sheet', '788/wash', WASH_788], ['v4/03-modeling-detail-reference-sheet', '788/wash', WASH_788], ['v4/04-outfit-form-variation-sheet', '788/wash', WASH_788], ['v4/05-prop-interaction-sheet', '788/wash', WASH_788], ['v4/06-basic-character-sheet', '788/wash', WASH_788], ['v4/07-complete-technical-character-sheet', '788/wash', WASH_788], ['v4/08-luxury-editorial-character-sheet', '788/wash', WASH_788]], // #788 AVERY LANG (was 569 v3/v3.1)
  'motion-poster-generator': ['01-poster-animation', '02-first-to-last-frame-animation'],
}
// Manifest-driven (review-assets 569/wash/manifest.json @f81ce12a): an entry is a file name at WASH_569_COMMIT, or
// [name, dir, commit] when the manifest pins that template to another assets commit. A re-wash only edits this data.
const wash569 = (skillId: keyof typeof WASH_569, n: number) => {
  const e = WASH_569[skillId][n]
  const [name, dir, commit] = typeof e === 'string' ? [e, '569/wash', WASH_569_COMMIT] : e
  return `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${commit}/${dir}/${assetDir(skillId)}/templates/${name}@thumb.webp`
}
const P = (id: string, zh: string, en: string, prompt: string, image?: string, video?: string): SkillPreset =>
  ({ id, name: { zh, en }, prompt, ...(image ? { image } : {}), ...(video ? { video } : {}) })
type L = [zh: string, en: string]
function I(key: string, [zh, en]: L, type: SkillInput['type'], required = false, ph?: L): SkillInput {
  return { key, label: { zh, en }, type, ...(required ? { required } : {}), ...(ph ? { placeholder: { zh: ph[0], en: ph[1] } } : {}) }
}
/** #569 effect-example skills: right side is only 上传文件 + 补充描述. */
const EFFECT_INPUTS: SkillInput[] = [I('file', ['上传文件', 'Upload file'], 'image'), I('note', ['补充描述', 'Additional notes'], 'textarea', false, ['有什么想补充的吗？', 'Anything you want to add?'])]
/** #708 — portrait shot rules (UIUX wording lock v1): camera-angle variety when the user gives no angle; frame-edge + degree wording. */
export const PORTRAIT_SHOTS_708 = '\nShot rules (#708): when the user does not name an angle, plan every image before calling generate_image and vary camera angle across the batch — at most ONE frontal 0° eye-level shot per batch, and that one is never centered (subject on the left or right third). Pick the others from different entries: "head turned 45° from camera (three-quarter view), far eye still visible near the nose bridge"; "strict 90° side profile: nose, lips and chin in silhouette, the far eye is NOT visible"; "body facing away from camera, head turned 90° back over the shoulder, chin passes beyond the shoulder line, looking back toward camera"; "low camera at waist height angled up"; "camera slightly above eye level"; gaze off-camera. A single-image run is never frontal-centered: use 45° or off-camera gaze and "subject on the left third, negative space on the right". If the user names an angle, follow it exactly.\n' +
  'Write each image prompt in English with these slots, one short line each: 1 purpose ("single 3:4 photorealistic editorial fashion photograph, one frame only, not a collage, grid or contact sheet"); 2 person ("commercial fashion model, refined makeup and styling"; age, ethnicity, one distinctive feature, expression; never "beautiful girl"); 3 framing as a frame edge, never a bare label (full-length = "clear headroom above the top of the head, both feet fully inside the frame"; waist = "bottom edge of the frame cuts exactly at the navel, hips NOT visible"; chest = "bottom edge cuts across the chest, waist NOT visible"; shoulders = "bottom edge cuts at the collarbones, chest NOT visible") + angle in degrees + camera height + "subject on the left/right third"; 4 lens (35mm f/2.8 full-length, 50mm f/2 waist, 85mm f/1.8 shoulders, eyes in sharp focus); 5 named directional light with direction and shadows (no flat light); 6 "editorial color grade, strong directional light and contrast, fine film grain"; 7 outfit (one key item + fabric + one accessory); 8 location (background two stops darker than face); 9 "natural skin texture, visible pores, real fabric wrinkles; realistic does not mean unattractive, no aging; no plastic skin, no beauty filter, no extra fingers, mouth, teeth and eyes anatomically correct, no text unless requested". Default aspect 3:4; never fall back to 1024².'
/** #687-2 — poster / banner / interior: EFFECT_INPUTS structure, English copy = the reference card (Upload Files / Additional Details / Anything else to add?). */
/** #687-1 — reference-card Upload Files + Additional Details (max 500), both optional. */
const REF_CARD_INPUTS_687: SkillInput[] = [I('file', ['上传文件', 'Upload Files'], 'image'), { ...I('note', ['补充描述', 'Additional Details'], 'textarea', false, ['还有什么想补充的吗？', 'Anything else to add?']), maxLength: 500 }]
/** #806 — 动态海报. Both templates: source_image* / motion_brief / visual_direction. 首尾帧动画 also optional start_frame. */
const MOTION_BRIEF_PH: L = ['写下哪些要动、哪些保持不动；不填则自动规划。', 'Say what should move and what should stay still. Leave blank to plan it automatically.']
const MOTION_LOOK_PH: L = ['描述想要的画面效果，或附上参考；没有可不填。', 'Describe the look you want or attach a reference. Optional.']
function motionImage(key: string, label: L, required = false): SkillInput {
  return { ...I(key, label, 'image', required), accept: 'image', maxCount: 1, maxSizeMb: 10 }
}
function motionText(key: string, label: L, ph: L): SkillInput {
  return { ...I(key, label, 'text', false, ph), maxLength: 200 }
}
const MOTION_POSTER_INPUTS: SkillInput[] = [
  motionImage('source_image', ['静态原稿', 'Source artwork'], true),
  motionText('motion_brief', ['动态要求', 'Motion requirements'], MOTION_BRIEF_PH),
  motionText('visual_direction', ['视觉呈现方式', 'Visual direction'], MOTION_LOOK_PH),
]
const MOTION_START_END_INPUTS: SkillInput[] = [
  motionImage('source_image', ['静态原稿（最终定格画面）', 'Source artwork (final frame)'], true),
  motionImage('start_frame', ['首帧图片（选填）', 'First-frame image (optional)']),
  motionText('motion_brief', ['动态要求', 'Motion requirements'], MOTION_BRIEF_PH),
  motionText('visual_direction', ['视觉呈现方式', 'Visual direction'], MOTION_LOOK_PH),
]
/** English production prompts (COPY-REWRITE). applyRaw748 localizes these from copy-748.json when present. */
const MOTION_POSTER_PROMPT = 'Generate 1 motion video from the uploaded static poster. Identify elements that can move safely and propose a plan for approval; follow detailed instructions if given, otherwise plan automatically with no per-layer setup. Keep layout, subject, text, logos and hierarchy intact; confirm length, ratio and sound, then finish on a full, legible still frame. Motion: {{motion_brief}} Look: {{visual_direction}}'
const MOTION_START_END_PROMPT = 'Generate 1 motion poster video with controlled start and end frames. Use the original as the end frame, then use or design an earlier moment of the same shot as the start. Keep subject, viewpoint, style and colors consistent; confirm both frames, any adjustments, length, ratio and sound before generating smooth motion. Keep text, logos and hierarchy, avoid cutting to unrelated images, and end on a full still frame. Motion: {{motion_brief}} Look: {{visual_direction}}'
/** #691/#693: multi-angle — Upload stays optional; Additional placeholder recommends uploading a reference. */
const MULTI_ANGLE_INPUTS: SkillInput[] = [I('file', ['上传文件', 'Upload file'], 'image'), I('note', ['补充描述', 'Additional notes'], 'textarea', false, ['有什么想补充的吗？建议上传参考图', 'Anything you want to add? Uploading a reference image is recommended'])]
/** #636 C5 nearMiss Examples-only: gold isomorphic right rail — Upload Files + single-line Additional Details only. */
const NEARMISS_INPUTS: SkillInput[] = [I('file', ['上传文件', 'Upload Files'], 'image'), I('note', ['补充描述', 'Additional Details'], 'text', false, ['还有什么想补充的吗？', 'Anything else to add?'])]
/** #569 template skills: shared third field 视觉呈现方式. */
const VISUAL = I('visual', ['视觉呈现方式', 'Visual presentation'], 'text', false, ['补充想保留或避开的视觉要求，没有可以留空', 'Visual preferences to keep or avoid; leave blank if none'])

/** #494 — pick the current UI language from data-carried copy. */
export const loc = (text: { zh: string; en?: string }) => (lang === 'en' && text.en) || text.zh

/** #595 — Phase1 15 ids in hot-mapping uses order (product lock TOP15 unique).
 *  Home forYou / Explore forYou / quick-start / featured queues follow this via orderBuiltins.
 *  website chip lit by mobile-ui + web-product. interior media rewashed under #687 Phase1 remaining. */
export const PHASE1_SKILL_IDS = [
  'product-tvc-advertisement-generator', 'universal-multi-angle-grid', 'brand-identity-director', 'character-sheet-design', 'logo-material-explorer', 'packaging-design-director',
  'motion-poster-generator', 'meta-ads-creative-director', 'poster-differentiated-compiler', 'cover-design-director', 'mobile-app-visual-design', 'rednote-cover-maker',
  'marketing-campaign-generator', 'web-product-visual-design', 'banner-design-director',
] as const
export const PHASE1_SKILL_ID_SET: ReadonlySet<string> = new Set(PHASE1_SKILL_IDS)
export const UNTOUCHED_SKILL_IDS = [] as const // #687: interior media rewashed (was Phase1 hold)
/** #634 Phase2-S1 — 14 NEW ids (upgrade `social` is not listed here). */
export const PHASE2_NEW_SKILL_IDS = [
  'flash-cut-video', 'style-transfer', 'person-swap', 'commerce-strategist', 'lifestyle-scene',
  'naive-illustration', 'logo-abstract', 'photo-split-poster', 'ppt-visual', 'promo-ecommerce',
  'yingzao', 'crt-interface', 'crayon-sketch', 'fabric-collage',
] as const
export const PHASE2_NEW_SKILL_ID_SET: ReadonlySet<string> = new Set(PHASE2_NEW_SKILL_IDS)

/** #638 Phase2-S5 Soft mount — PRODUCT-LOCK-PHASE2 Soft order + #735 C + #812 D wash PASS (unhide).
 *  `social` also lives in PHASE1_SKILL_IDS (upgrade, no dup card). Slots: A social upgrade + B NEW5 + C NEW5 + D style4 washed.
 *  #490 HOLD. */
export const PHASE2_SKILL_IDS = [
  'flash-cut-video', 'style-transfer', 'person-swap', 'rednote-cover-maker', 'commerce-strategist', 'lifestyle-scene',
  'naive-illustration', 'logo-abstract', 'photo-split-poster', 'ppt-visual', 'promo-ecommerce',
  'yingzao', 'crt-interface', 'crayon-sketch', 'fabric-collage',
] as const
export const PHASE2_SKILL_ID_SET: ReadonlySet<string> = new Set(PHASE2_SKILL_IDS)
/** #638/#735/#812 — deferred empty after D wash+unhide (#812). Keep const for orderBuiltins. */
export const PHASE2_DEFERRED_SKILL_IDS = [
] as const
export const PHASE2_DEFERRED_SKILL_ID_SET: ReadonlySet<string> = new Set(PHASE2_DEFERRED_SKILL_IDS)
/** #673 — HIDE LIST (not a delete). Built-in skills listed here are kept in BUILTIN_SKILLS (data, assets, lookup by id
 *  all intact, so saved sessions / cards that reference them still open) but are NOT listed anywhere a user or the agent
 *  picks a skill for new work: home featured waterfall + quick-start + category chips, Skills page, 「+ → 技能」 menu,
 *  composer 「/」 picker, and the agent `skill` tool (list + read).
 *  TO RE-LIST A SKILL: once it is washed and design/QA PASS, delete its id from this array. Nothing else to change.
 *  #735 — C-group 5 removed; #812 — D-group 4 removed (washed + pinned). List empty. */
export const HIDDEN_BUILTIN_SKILL_IDS: readonly string[] = [
]
export const HIDDEN_BUILTIN_SKILL_ID_SET: ReadonlySet<string> = new Set(HIDDEN_BUILTIN_SKILL_IDS)
/** #673 — true when a skill may be offered for NEW selection. Personal (custom) skills are always listed. */
export const isListedSkill = (s: Pick<Skill, 'id' | 'custom'>): boolean => !!s.custom || !HIDDEN_BUILTIN_SKILL_ID_SET.has(s.id)
export const listedSkills = <T extends Pick<Skill, 'id' | 'custom'>>(skills: T[]): T[] => skills.filter(isListedSkill)
/** #673 — the plain sentence a user sees when an old session / card / link starts a hidden skill. */
export const hiddenSkillNotice = (skill: Pick<Skill, 'id' | 'custom'> | null | undefined): string | null =>
  skill && !isListedSkill(skill) ? t('skills.hiddenUnavailable') : null

/** #640 Phase3-S1 — 19 NEW ids (upgrade `thumbnail` is not listed here). PRODUCT-LOCK-PHASE3 + PHASE3-HARDEN-DIFF. Skill Creator → #650.
 *  #642 Phase3-S3 — NEW19 field parity Upload+Additional (NEARMISS_INPUTS); media wash → #643; no competitor strings in src). */
export const PHASE3_NEW_SKILL_IDS = [
  'taobao-product', 'before-after', 'anim-2d', 'creator-identity', 'product-website',
  'studio-model', 'youtube-channel-banner', 'ai-model', 'product-to-packaging',
  'game-art', 'portrait-studio', 'premium-website', 'animated-poster', 'pose-fission',
  'live-promo-decor', 'linkedin-banner', 'logo-animation', 'restaurant-website', 'clothing-swap',
] as const
export const PHASE3_NEW_SKILL_ID_SET: ReadonlySet<string> = new Set(PHASE3_NEW_SKILL_IDS)

/** Phase1 hot order → Phase2 Soft mount NEW (B+C+D) → deferred (empty after #812) → untouched / other. */
function orderBuiltins(raw: Skill[]): Skill[] {
  const skills = withMeasuredInputs748(raw)
  const phase1Rank = new Map<string, number>(PHASE1_SKILL_IDS.map((id, i) => [id, i]))
  // Soft mount NEW only (exclude `social` — already ranked in Phase1)
  const phase2MountIds = PHASE2_SKILL_IDS.filter((id) => !phase1Rank.has(id))
  const phase2Rank = new Map<string, number>(phase2MountIds.map((id, i) => [id, i]))
  const deferredRank = new Map<string, number>(PHASE2_DEFERRED_SKILL_IDS.map((id, i) => [id, i]))
  const phase1: Skill[] = []
  const phase2: Skill[] = []
  const deferred: Skill[] = []
  const rest: Skill[] = []
  for (const s of skills) {
    if (phase1Rank.has(s.id)) phase1.push(s)
    else if (phase2Rank.has(s.id)) phase2.push(s)
    else if (deferredRank.has(s.id)) deferred.push(s)
    else rest.push(s)
  }
  phase1.sort((a, b) => (phase1Rank.get(a.id)! - phase1Rank.get(b.id)!))
  phase2.sort((a, b) => (phase2Rank.get(a.id)! - phase2Rank.get(b.id)!))
  deferred.sort((a, b) => (deferredRank.get(a.id)! - deferredRank.get(b.id)!))
  return [...phase1, ...phase2, ...deferred, ...rest]
}

/** #591 Phase1-S1 data contract + #592 Phase1-S2 upgrade-9 + #593 new-6 instructions/presets + #594 wash pins + #595 hot mount order.
 *  Upgrade 9: brand packaging poster product character social motion banner thumbnail.
 *  New 6 media: covers-v4 + featured-v2 + 594/wash examples @ WASH_594; dual-fit contain (#602); hover video @ WASH_623_NEW6_VIDEO (#623).
 *  #634 Phase2-S1 — PRODUCT-LOCK-PHASE2: 14 NEW ids (B .ai5 + C deferred.art5 + D style4).
 *  #635 Phase2-S2 — deepen `social` Fashion UGC production instructions/presets/inputs (keep RedNote; no fashion-ugc id).
 *  #636/#637 Phase2-S3/S4 — B NEW5 production + soft wash; C5 later via #673/#735; D Phase4.
 *  #638 Phase2-S5 — Soft mount A+B via PHASE2_SKILL_IDS + orderBuiltins; #735 mounts C; #812 mounts D (washed); #490 HOLD.
 *  #642 Phase3-S3 — NEW19 NEARMISS_INPUTS field parity (scaffold); assets empty until #643 wash pins.
 *  Skill Creator Out → #650. `interior` untouched. Gold UX site external — never name it in src.
 */
/** #748 — the 16 reference skills take structure (name, templates, inputs) from src/data/skills-748.json. */
function withMeasuredInputs748(list: Skill[]): Skill[] {
  // Raw convert (scripts/convert_raw_748.py) wins over the measure; the measure is verification only for those skills.
  return list.map((s) => applyRaw748(s))
}
/** #748 — the skill as seen with `presetId` selected: inputs[] = that template's own form. */
export function withTemplateInputs(skill: Skill, presetId: string | null | undefined): Skill {
  const p = presetId ? skill.presets?.find((x) => x.id === presetId) : undefined
  return p?.inputs ? { ...skill, inputs: p.inputs } : skill
}
/** #707 — pixels generate_image must use. images=1 means one call, no list_models / expand / extra frame. */
export interface SkillOutputStage { width: number; height: number; ratio?: string; images: number }
/** #979 — one template's plan. A staged template carries `stages`; flat fields are its stage 1. */
export interface SkillOutputPlan extends Partial<SkillOutputStage> {
  stages?: SkillOutputStage[]
  name?: string
}
/** #979 — the deliverable is per template, not per skill. Flat fields are the default
 *  template (and stage 1); `presets` overrides per selected template; `stages` is the
 *  ordered plan (brand = 3×1:1 direction proposals, then 1×16:9 guideline board). */
export interface SkillOutput extends SkillOutputStage {
  presets?: Record<string, SkillOutputPlan>
  stages?: SkillOutputStage[]
}
/** #979: product ruling #911 comment 6872615903 — brand is a two-step 4-image set:
 *  3×1024×1024 (1:1) direction proposals, then 1×2048×1152 (16:9) guideline board. */
export const BRAND_STAGES_979: SkillOutputStage[] = [
  { width: 1024, height: 1024, ratio: '1:1', images: 3 },
  { width: 2048, height: 1152, ratio: '16:9', images: 1 },
]
/** #979: packaging multi-SKU t3 = 3×1536×2048 (3:4) + 1×2048×1152 (16:9). */
export const PACKAGING_PLAYFUL_STAGES_979: SkillOutputStage[] = [
  { width: 1536, height: 2048, ratio: '3:4', images: 3 },
  { width: 2048, height: 1152, ratio: '16:9', images: 1 },
]
export const SKILL_OUTPUT: Record<string, SkillOutput> = {
  'before-after': { width: 1920, height: 1080, ratio: '16:9', images: 1 },
  // #974: product ruling (#911 comment 6872065790) — four separate 3:4 1536x2048 images, never one grid.
  'universal-multi-angle-grid': { width: 1536, height: 2048, ratio: '3:4', images: 4 },
  'pose-fission': { width: 1536, height: 2048, ratio: '3:4', images: 4 },
  'game-art': { width: 1024, height: 1824, ratio: '9:16', images: 1 },
  'linkedin-banner': { width: 1584, height: 396, images: 1 },
  'clothing-swap': { width: 1536, height: 2048, ratio: '3:4', images: 1 },
  // #979: template-level output contract (#911 comment 6872615903). The six brand
  // templates share one staged plan; brand is never a single landscape board.
  'brand-identity-director': {
    width: 1024, height: 1024, ratio: '1:1', images: 4,
    stages: BRAND_STAGES_979,
    presets: {
      geometric: { stages: BRAND_STAGES_979 },
      handmade: { stages: BRAND_STAGES_979 },
      tech: { stages: BRAND_STAGES_979 },
      beauty: { stages: BRAND_STAGES_979 },
      foodbev: { stages: BRAND_STAGES_979 },
      pet: { stages: BRAND_STAGES_979 },
    },
  },
  // #979: five packaging templates, five plans. Flat fields = the default 主款 (eco/t1).
  'packaging-design-director': {
    width: 1536, height: 2048, ratio: '3:4', images: 1,
    presets: {
      eco: { width: 1536, height: 2048, ratio: '3:4', images: 1 },
      gold: { width: 2048, height: 1152, ratio: '16:9', images: 3 },
      playful: { width: 1536, height: 2048, ratio: '3:4', images: 4, stages: PACKAGING_PLAYFUL_STAGES_979 },
      panels: { width: 2048, height: 1152, ratio: '16:9', images: 1 },
      shelf: { width: 2048, height: 1152, ratio: '16:9', images: 1 },
    },
  },
}

export const BUILTIN_SKILLS: Skill[] = orderBuiltins([
  { id: 'poster-differentiated-compiler', name: t('skills.posterDesign'), instructions: 'You are a production poster designer. Deliver print-ready compositions, not loose mood sketches.\n1) Brief: pull headline, subject, audience and use (event, promo, editorial) from the upload and notes.\n2) Hierarchy: one hero subject, strong headline typography in quotes, clear subcopy ladder, generous margins.\n3) Ratio: default 3:4; keep safe margins for print crop. Offer 2 distinct art directions when the brief is open.\n4) Finish: high contrast, legible at arm length, no clipped type. Put every on-art phrase in quotes.\n5) Refs: when the user uploaded a file, pass its shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ads', cover: cover('poster-differentiated-compiler'), quickStartCover: quickStartCover('poster-differentiated-compiler'), featured: feedCovers('poster-differentiated-compiler'), video: video('poster-differentiated-compiler'),
    inputs: REF_CARD_INPUTS_687 },
  // #635 Phase2-S2 A: deepen `social` Fashion UGC (candid / off-duty) + keep RedNote covers/set; DO NOT invent fashion-ugc.
  { id: 'rednote-cover-maker', name: t('skills.socialMediaSet'), instructions: 'You are a production social content designer for RedNote / lifestyle covers AND candid fashion UGC stills. Deliver post-ready frames, never a staged studio look.\n1) Brief: brand voice, product, person, and channel (feed 1:1 / story 9:16 / RedNote cover) from uploads and notes.\n2) Fashion UGC path: candid off-duty real-person energy; product clearly in frame; natural light or everyday locations; never seamless studio backdrops, never stiff catalog poses.\n3) RedNote / lifestyle covers: bold subject, clean negative space for title stickers, high thumb-stop contrast; share one palette across a 1:1 feed, a 4:5 post and a 9:16 story when shipping a set.\n4) Copy: keep text short and mobile-legible; every on-art phrase in quotes; Fashion UGC may stay near-textless when the look is the message.\n5) Refs: when files are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call; lock product identity and person likeness across the set.',
    category: 'social', cover: cover687('rednote-cover-maker'), quickStartCover: quickStartCover('rednote-cover-maker'), featured: feat687('rednote-cover-maker', [1, 2, 3, 4, 5]), video: video687('rednote-cover-maker'),
    presets: [P('ugc-feed', '时尚UGC信息流 1:1', 'Fashion UGC feed 1:1', 'Style: candid off-duty fashion UGC still, 1:1 feed crop, real-person feel, product clearly in frame, never staged studio look, natural everyday light.'), P('ugc-story', '时尚UGC故事 9:16', 'Fashion UGC story 9:16', 'Style: candid off-duty fashion UGC still, 9:16 story crop, real-person energy, product in hand or worn, never staged studio backdrop, mobile-first.')],
    inputs: REF_CARD_INPUTS_687 },
  { id: 'brand-identity-director', name: t('skills.brandIdentity'), instructions: 'You are a production brand-identity designer. Deliver a usable VI kit, not a single decorative mark.\n1) Discover: brand name, category, positioning and any elements to keep from the provided files and Additional Details.\n2) Mark: design a primary logo mark on a plain background (1:1). State shape language, hex colors and type style precisely.\n3) System board: color palette swatches, primary + secondary lockups, and a clear typography specimen.\n4) Applications: at least one stationery or object mockup applying the mark; keep geometry identical across frames.\n5) Scope: when a template is selected, follow that template focus (logo system board vs mockup). Do not invent a new category.\n6) Refs: when files are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    category: 'branding', cover: cover('brand-identity-director'), quickStartCover: quickStartCover('brand-identity-director'), featured: feedCovers('brand-identity-director'), video: video('brand-identity-director'), presets: [P('geometric', '极简几何', 'Minimal geometric', 'Style: minimal geometric mark built from simple shapes, strict grid, two-color palette; deliver primary mark, lockup and palette board production-ready.', wash541(WASH_541.brand, 'brand-identity-director', 'geometric')), P('handmade', '手作温暖', 'Handmade warmth', 'Style: hand-drawn warm mark, organic lines, earthy palette, craft paper textures; deliver primary mark plus warm stationery application.', wash541(WASH_541.brand, 'brand-identity-director', 'handmade')), P('tech', '科技未来', 'Tech future', 'Style: futuristic tech identity, precise linework, gradient-free electric blue accents, monospace details; deliver mark, lockup and UI-ready glyph.', wash541(WASH_541.brand, 'brand-identity-director', 'tech')), P('beauty', '美妆个护', 'Beauty & personal care', 'Style: beauty and personal care logo system presentation board, soft refined mark with primary and secondary lockups, monogram, color swatches and typography specimen laid out on a clean board, no product mockups.', wash541(WASH_541.brand, 'brand-identity-director', 'beauty')), P('foodbev', '食品饮料', 'Food & beverage', 'Style: food and beverage logo system presentation board, lively mark with primary and stacked lockups, icon variant, color swatches and typography specimen laid out on a clean board, no product mockups.', wash541(WASH_541.brand, 'brand-identity-director', 'foodbev')), P('pet', '宠物用品', 'Pet supplies', 'Style: pet supplies logo system presentation board, friendly playful mark with primary and secondary lockups, mascot icon, color swatches and typography specimen laid out on a clean board, no product mockups.', wash541(WASH_541.brand, 'brand-identity-director', 'pet'))],
    inputs: REF_CARD_INPUTS_687 },
  { id: 'packaging-design-director', name: t('skills.packagingDesign'), instructions: 'You are a production packaging designer. Deliver shelf-ready concepts through structure, not flat posters.\n1) Brief: product, size, pack form and brand cues from Additional Details and the provided file.\n2) Front: package front view on a clean studio background; call out material, finish and label layout.\n3) Structure: when relevant, show dieline / panel logic or a clear 3/4 mockup in context.\n4) Shelf: ensure the design reads at eye level in a retail row; keep logo and claims legible.\n5) Apply the selected packaging style focus (eco, foil, playful, panels, shelf).\n6) Refs: when files are uploaded, pass shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'ecommerce', cover: cover777('packaging-design-director'), quickStartCover: quickStartCover('packaging-design-director'), featured: feedCovers('packaging-design-director'), video: video('packaging-design-director'), presets: [P('eco', '自然环保', 'Natural eco', 'Style: natural eco packaging, kraft and recycled paper, botanical line art, muted greens; show front label hierarchy and material callouts.', pinned(`777/wash/packaging/examples`, WASH_777, '01.webp') /* #777: 主款 AURELIA */), P('gold', '奢华烫金', 'Luxury gold foil', 'Style: luxury packaging, deep matte color with gold foil stamping, embossed logo; keep foil readable at shelf distance.', pinned(`777/wash/packaging/examples`, WASH_777, '02.webp') /* #777: 包装视觉方向 AURELIA */), P('playful', '潮玩插画', 'Playful illustration', 'Style: playful illustrated packaging, bright characters, bold outlines, pop colors; keep character on-pack consistent across panels.', pinned(`777/wash/packaging/examples`, WASH_777, '03.webp') /* #777: 多SKU AURELIA */), P('panels', '展开结构图', 'Panels & structure', 'Style: packaging panels and structural dieline, flat unfolded box with front, back and side panels laid out.', pinned(`777/wash/packaging/examples`, WASH_777, '04.webp') /* #777: 面板结构 AURELIA */), P('shelf', '货架陈列', 'Shelf display', 'Style: packaging shelf display, the product repeated in rows on a retail shelf, eye-level store lighting.', pinned(`777/wash/packaging/examples`, WASH_777, '05.webp') /* #777: 货架 AURELIA */)],
    inputs: REF_CARD_INPUTS_687 },
  // #641 Phase3-S2: YouTube 16:9 CTR thumbnail — dialog parity Upload+Additional only (no presets / no required titleCopy); keep id; DO NOT invent youtube-thumbnail id.
  // Media: #643 true-wash cover/examples/featured (kie); hover video stays Phase1 until video wash.
  { id: 'cover-design-director', name: t('skills.youtubeThumbnail'), instructions: 'You are a production YouTube thumbnail designer for 16:9 click-rate covers. Deliver thumb-stop frames built for mobile feed CTR, not vague key art or short-drama posters.\n1) Brief: from upload and notes, lock the video topic, emotion, and 16:9 YouTube crop; treat vertical short-drama only as a secondary path when the brief explicitly asks.\n2) Hook triad: one oversized expressive face or reaction, a three-word bold title in quotes, and extreme high contrast so the frame reads at phone-grid size.\n3) Type: prefer exactly three punchy words; keep lettering thick, high-contrast, and clear of faces; never more than a short phrase in quotes on-art.\n4) Variants: offer 2 crops or emotion shifts that keep the same three-word lockup and subject identity.\n5) Refs: when a face or subject file is uploaded, pass its shape id in refs (ref_modes content) on every generate_image call; lock likeness across variants.',
    category: 'social', cover: cover643('cover-design-director'), quickStartCover: quickStartCover('cover-design-director'), featured: feat643('cover-design-director', [1, 2, 3, 4]), video: video('cover-design-director'),
    inputs: EFFECT_INPUTS },
  { id: 'banner-design-director', name: t('skills.bannerDesign'), instructions: 'You are a production banner designer for web and campaign placement. Deliver crop-safe wide frames, not square posts.\n1) Brief: campaign goal, offer and placement width from the upload and notes.\n2) Layout: wide 21:9 or 16:9; headline on one side, visual on the other; clear CTA text in quotes.\n3) Safe margins: protect type and logo from edge crop across common ad slots.\n4) Hierarchy: one focal product or scene; avoid cluttered multi-offer walls.\n5) Refs: when a file is uploaded, pass its shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ads', cover: cover('banner-design-director'), quickStartCover: quickStartCover('banner-design-director'), featured: feedCovers('banner-design-director')?.map((u, i) => (i === 2 ? pinned('778/wash/banner/featured', WASH_778, '03.webp') : u)), /* #778: 精选03 single brand */ video: pinned('778/wash/banner/examples', WASH_778_EX01, '01.mp4'), /* #778: ex01 + hover = fintech banner wash (was supplement-jar 494 mp4) */
    inputs: REF_CARD_INPUTS_687 },
  { id: 'character-sheet-design', name: t('skills.characterSheet'), instructions: 'You are a production character-sheet designer. Deliver turnaround-ready reference boards for downstream art and IP.\n1) Lock identity: from the provided file and Additional Details, freeze face, body, outfit colors and key props.\n2) Board: follow the selected template (turnaround, expression, modeling detail, outfit, prop, basic, technical, editorial).\n3) Consistency: identical proportions, palette and costume language across every cell in the sheet.\n4) Presentation: prefer clean backgrounds; label nothing with stray UI chrome; keep sheets readable as production refs.\n5) Refs: when files are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    cover: cover('character-sheet-design'), quickStartCover: quickStartCover('character-sheet-design'), featured: feedCovers('character-sheet-design')?.map((u, i) => (i === 2 ? pinned('788/wash-r2/character/featured', WASH_788_F03, '03.webp') : u)), /* #788 r2 */ video: video('character-sheet-design'), featuredPreset: 'editorial', presets: [P('turnaround', '角色转身板', 'Character Turnaround Sheet', 'Template: character turnaround sheet, full-body front, side and back views evenly spaced in one row on a white background.', wash569('character-sheet-design', 0)), P('expression', '表情动作板', 'Expression & Pose Sheet', 'Template: expression and pose sheet, a row of head-shot expressions above full-body poses (standing, walking, sitting).', wash569('character-sheet-design', 1)), P('modeling', '建模细节参考板', 'Modeling Detail Reference Sheet', 'Template: modeling detail reference sheet, full-body angles on the left and close-up cells of face, eyes, lips, ears, hair, hands and shoes on the right.', wash569('character-sheet-design', 2)), P('outfit', '服装/形态变体板', 'Outfit / Form Variation Sheet', 'Template: outfit variation sheet, the same character in three different outfits shown full body side by side.', wash569('character-sheet-design', 3)), P('prop', '道具互动板', 'Prop Interaction Sheet', 'Template: prop interaction sheet, full-body poses holding a prop on top and close-up cells of hands and prop below.', wash569('character-sheet-design', 4)), P('basic', '基础角色板', 'Basic Character Sheet', 'Template: basic character sheet, full-body three views on the left and four head-shot expressions on the right.', wash569('character-sheet-design', 5)), P('technical', '完整技术角色板', 'Complete Technical Character Sheet', 'Template: complete technical character sheet, multi-angle full body, an expression grid, outfit items, color swatches and detail close-ups.', wash569('character-sheet-design', 6)), P('editorial', '时装大片角色板', 'Editorial Fashion Sheet', 'Template: editorial fashion sheet, the reference character as the lead in a luxury-brand fashion campaign style; full-body standing pose, half-body and face close-ups of the same person, keeping facial features, hairstyle and body shape consistent, soft studio lighting, clean light background, no text or logos.', wash569('character-sheet-design', 7))],
    inputs: REF_CARD_INPUTS_687 },
  { id: 'product-tvc-advertisement-generator', name: t('skills.eCommerceProductImages'), instructions: 'You are a production product-commercial director. Deliver finished advertisement films for beauty, fashion, food & beverage, electronics, home, outdoor and software.\n1) Lock the product: from productImage and productInfo, keep silhouette, materials, logo and color truthful in every frame.\n2) Form: one RESULT advertisement film matching the selected category template (not a white-background still packshot).\n3) Narrative: show confirmed benefits and real usage; never invent performance claims or unseen structure.\n4) Apply the selected template focus (beauty, fashion, foodbev, electronics, home, outdoor, software).\n5) Refs: ALWAYS pass the product image shape id in refs (ref_modes content) on every generate_image / animate_image call; describing it in the prompt does not send the image.',
    category: 'ecommerce', cover: cover('product-tvc-advertisement-generator'), quickStartCover: quickStartCover('product-tvc-advertisement-generator'), featured: feedCovers('product-tvc-advertisement-generator'), video: video('product-tvc-advertisement-generator'), presets: [P('beauty', '美妆', 'Beauty', 'Style: beauty product commercial film — a model holding a red lipstick, advertisement pacing, not a white bottle still.', washProduct784('01'), washProduct784('01', 'video')), P('fashion', '服装', 'Fashion', 'Style: fashion commercial film — yellow-check top, denim shorts and a blue shoulder bag, runway/lifestyle energy, not a printed water bottle.', washProduct784('02'), washProduct784('02', 'video')), P('foodbev', '食品饮料', 'Food & Beverage', 'Style: food and beverage commercial film — real packaging and appetite cues in a natural setting, honest claims only.', washProduct784('03'), washProduct784('03', 'video')), P('electronics', '数码', 'Electronics', 'Style: electronics commercial film — verified product appearance, materials and details, crisp tech lighting.', washProduct784('04'), washProduct784('04', 'video')), P('home', '家居', 'Home Decor', 'Style: home decor commercial film — interior atmosphere with the product naturally placed, warm cinematic light.', washProduct784('05'), washProduct784('05', 'video')), P('outdoor', '户外', 'Outdoor', 'Style: outdoor commercial film — active use in nature, motion and environment locked to the product category.', washProduct784('06'), washProduct784('06', 'video')), P('software', '软件', 'SaaS', 'Style: software / SaaS commercial film — professional product story with verified UI or device moments, no invented features.', washProduct784('07'), washProduct784('07', 'video'))],
    inputs: [I('productImage', ['商品图片', 'Product images'], 'image', true), I('productInfo', ['商品资料', 'Product details'], 'text', false, ['补充商品名称、真实卖点和使用场景', 'Product name, real selling points and use cases']), VISUAL] },
  { id: 'motion-poster-generator', name: t('skills.motionPoster'), instructions: 'You are a production motion-poster designer. Deliver one short motion video from a static poster: either a poster-motion clip or a start-to-end frame animation. Keep the subject, on-art text, logos, composition and information hierarchy. Do not reshoot a different ad and do not swap in a new person.\n1) Poster motion: require source_image, the static artwork. Find elements that can move safely and confirm a plan before animating. When motion_brief is filled, follow it exactly; when it is empty, plan the motion automatically with no per-layer setup. Confirm length, ratio and sound, then animate, and finish on a full, legible still frame.\n2) Start and end frames: source_image is the final held frame. When start_frame is provided, use it as the opening frame of the same shot; otherwise design an earlier moment of that shot. Keep subject, viewpoint, style and colors consistent across both frames. Confirm both frames, any adjustments, length, ratio and sound, then generate one continuous move. Do not cut to an unrelated image. End on a full still frame. Text, logos and hierarchy stay put.\n3) Look: apply visual_direction when the user wrote one; otherwise keep the artwork look. Never invent a second brand, a new headline, or a layout change.\n4) Craft: type stays sharp and in quotes; motion must not smear letters, logos or the information hierarchy. The last frame is a complete, readable still.\n5) Refs: pass every provided shape id in refs (ref_modes content) on every generate_image and animate_image call. Describing the artwork in the prompt does not send the image. Never invent motion when source_image is missing.',
    category: 'ads', cover: cover('motion-poster-generator'), quickStartCover: quickStartCover('motion-poster-generator'), featured: feedCovers('motion-poster-generator'), video: video('motion-poster-generator'),
    /* #806: playable template clips. t1 1112×834 (~4:3), t2 720×1280 (9:16). Stills stay on wash-748. */
    presets: [
      { ...P('t1', '海报动效', 'Poster Animation', MOTION_POSTER_PROMPT, undefined, pinned('569/wash/motion/templates', WASH_569_COMMIT, '01-poster-animation.mp4')), inputs: MOTION_POSTER_INPUTS },
      { ...P('t2', '首尾帧动画', 'First-to-Last Frame Animation', MOTION_START_END_PROMPT, undefined, pinned('569/wash/motion/templates', WASH_569_COMMIT, '02-first-to-last-frame-animation.mp4')), inputs: MOTION_START_END_INPUTS },
    ],
    inputs: MOTION_POSTER_INPUTS },
  // #593 Phase1-S3 new 6 instructions+presets; #594 wash pins; dual-fit contain; #623 hover video @ 594/wash/videos.
  // #691/#687: multi-angle dialog parity with the reference card — Upload + Additional only (no presets).
  // #974: product-locked delivery = four separate 3:4 1536x2048 images (one per angle), same uploaded ref on every call.
  { id: 'universal-multi-angle-grid', name: t('skills.multiAngleImageGenerator'), instructions: 'You are a production multi-angle catalog photographer. Deliver a locked identity set of exactly four separate images at 3:4 / 1536×2048 (one file per angle, never one grid, collage or contact sheet), not random variants.\n1) Lock: read the uploaded subject image (if none is uploaded, use the subject described in the Additional notes or ask for one; never invent a product unprompted); keep identity, materials, proportions and palette identical across every frame.\n2) Set: front, 3/4, a pure 90° side profile (camera exactly perpendicular, no 3/4 turn) and one detail/macro on clean matching backgrounds unless the Additional notes say otherwise.\n3) Deliver: call generate_image exactly four times, count=1 each, one angle per call, every image 1536×2048 at 3:4; do not use 1024x1024 and never merge the four angles into one image.\n4) Use: PDP and ads prefer neutral seamless; lifestyle only when the Additional notes ask; with no notes, default to neutral seamless studio light and a PDP-ready four-frame set.\n5) Consistency: same lens height and lighting family; no costume or finish drift between angles.\n6) Refs: pass the same uploaded subject shape id in refs (ref_modes content) on every generate_image call; describing the subject in the prompt does not send it.',
    category: 'ecommerce',
    cover: cover('universal-multi-angle-grid'), quickStartCover: quickStartCover('universal-multi-angle-grid'), quickStartCoverFit: 'contain',
    featured: feedCovers('universal-multi-angle-grid'), video: video594('universal-multi-angle-grid'),
    inputs: MULTI_ANGLE_INPUTS },
  { id: 'logo-material-explorer', name: t('skills.logoMaterialExplorer'), instructions: 'You are a production 3D material artist for logo finish studies. Explore materials only — never redesign the mark.\n1) Lock geometry: keep logo paths, proportions and negative space identical to the provided file.\n2) Materials: vary finish only (metal, glass, plastic, fabric, ceramic) per selected preset or Additional Details.\n3) Stage: neutral studio turntable or soft gradient; soft product lighting; no busy brand scenes.\n4) Scope: one material study per frame; do not invent a full VI kit or packaging system.\n5) Refs: pass the logo shape id in refs (ref_modes content) on every generate_image call.',
    category: 'branding',
    cover: cover('logo-material-explorer'), quickStartCover: quickStartCover('logo-material-explorer'), quickStartCoverFit: 'contain',
    featured: feedCovers('logo-material-explorer'), video: pinned('wash-lm/logo-material', WASH_LM, 'hero.mp4'), /* VELA liquid-chrome hero I2V (r2; was ffmpeg cover push-in) */  // #748: left = 1 video + 3 examples; hl0=video → this mp4
    presets: [P('metal', '金属拉丝', 'Brushed metal', 'Style: brushed metal 3D logo material study on a neutral turntable, identical mark geometry, soft studio light, no redesign.'), P('glass', '透明玻璃', 'Clear glass', 'Style: clear glass 3D logo material study with soft refraction, identical mark geometry, soft gradient backdrop.'), P('fabric', '织物绣章', 'Fabric emblem', 'Style: woven fabric or embroidered emblem material study of the same logo, identical geometry, soft studio light.'), P('ceramic', '陶瓷釉面', 'Ceramic glaze', 'Style: glazed ceramic 3D logo material study, identical mark geometry, soft highlight, neutral seamless set.')],
    inputs: REF_CARD_INPUTS_687 },
  { id: 'meta-ads-creative-director', name: t('skills.metaAdsCreative'), instructions: 'You are a production Meta paid-social creative director. Ship a ratio pack that shares one idea.\n1) Brief: pull product, audience, offer and CTA from Additional Details; put every on-art phrase in quotes.\n2) Ratios: deliver 1:1 feed, 4:5 feed and 9:16 story/reel that share motif, palette and CTA.\n3) Treatment: prefer photo-led UGC or product-hero; avoid static website-banner layouts.\n4) Mobile: short high-contrast type; safe margins for UI chrome; one clear CTA.\n5) Refs: when files are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ads',
    cover: cover687('meta-ads-creative-director'), quickStartCover: quickStartCover('meta-ads-creative-director'), quickStartCoverFit: 'contain',
    featured: feat687('meta-ads-creative-director', [1, 2, 3, 4]), video: video687('meta-ads-creative-director'),
    presets: [P('feed1x1', '信息流 1:1', 'Feed 1:1', 'Style: Meta feed 1:1 paid creative, photo-led product hero, short high-contrast CTA in quotes, mobile-first.'), P('feed4x5', '信息流 4:5', 'Feed 4:5', 'Style: Meta feed 4:5 paid creative sharing the same campaign idea and CTA in quotes, taller crop, mobile-first.'), P('story9x16', '故事 9:16', 'Story 9:16', 'Style: Meta story/reel 9:16 creative, same campaign motif and CTA in quotes, safe margins for UI chrome.'), P('ugc', 'UGC 口播风', 'UGC talking-head', 'Style: UGC-style Meta creative, handheld energy, authentic product-in-hand moment, short CTA in quotes, not a website banner.')],
    inputs: REF_CARD_INPUTS_687 },
  { id: 'mobile-app-visual-design', name: t('skills.mobileAppVisualDesign'), instructions: 'You are a production mobile product designer. Deliver coherent app UI screens, not marketing posters.\n1) System: one type scale, spacing rhythm and component language across the requested flows.\n2) Frames: phone-framed mockups at about 9:19.5; clear hierarchy and accessible contrast.\n3) Flows: cover 2–4 key screens (home, detail, checkout or onboarding) per brief.\n4) Scope: product UI chrome and content — not a landing-page poster or print layout.\n5) Refs: when files are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    category: 'website',
    cover: cover('mobile-app-visual-design'), quickStartCover: quickStartCover('mobile-app-visual-design'), quickStartCoverFit: 'contain',
    featured: feedCovers('mobile-app-visual-design'), video: pinned('wash-mu/mobile-ui', WASH_MU, 'hero.mp4'), /* SAELIN hero (was 594 mp4) */
    presets: [P('home', '首页信息架构', 'Home IA', 'Style: mobile app home screen mockup in a phone frame, clear IA, coherent type and components, product UI not a poster.'), P('detail', '详情页', 'Detail screen', 'Style: mobile app detail screen mockup, strong hierarchy, accessible contrast, same design system as home.'), P('checkout', '结算流程', 'Checkout flow', 'Style: mobile checkout or cart flow screen, trust-first layout, clear primary CTA, same component language.'), P('onboarding', '引导页', 'Onboarding', 'Style: mobile onboarding screen, short copy, one primary action, coherent with the app system, phone-framed.')],
    inputs: REF_CARD_INPUTS_687 },
  { id: 'web-product-visual-design', name: t('skills.webProductVisualDesign'), instructions: 'You are a production web product visual designer. Ship landing or product-page systems, not printable posters.\n1) System: shared layout grid, illustration/photo treatment and UI chrome across modules.\n2) Ratios: desktop 16:9 hero plus an optional responsive crop when useful.\n3) Modules: hero, feature row and supporting UI that share one visual language.\n4) Copy: keep marketing lines short; put on-art phrases in quotes; focus on layout quality.\n5) Refs: when files are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    category: 'website',
    cover: cover('web-product-visual-design'), quickStartCover: quickStartCover('web-product-visual-design'), quickStartCoverFit: 'contain',
    featured: feedCovers('web-product-visual-design'), video: pinned('wash-wp/web-product', WASH_WP, 'hero.mp4'), /* ORIVA hero (was 594 mp4) */
    presets: [P('hero', '落地页主视觉', 'Landing hero', 'Style: web product landing hero at 16:9, strong hierarchy, short headline in quotes, coherent UI chrome.'), P('features', '功能模块', 'Feature modules', 'Style: web product feature modules row, shared grid and illustration treatment, desktop product page language.'), P('pricing', '定价区', 'Pricing section', 'Style: web pricing section visual, clear cards, accessible contrast, same system as the hero.'), P('responsive', '响应式裁切', 'Responsive crop', 'Style: responsive crop of the same web product system for a narrower viewport, layout reflowed not letterboxed.')],
    inputs: REF_CARD_INPUTS_687 },
  { id: 'marketing-campaign-generator', name: t('skills.marketingCampaignGenerator'), instructions: 'You are a production campaign art director. One big idea, then keyed frames across platforms.\n1) Idea: lock brand/product, goal and lead slogan from Additional Details; put slogans in quotes.\n2) System: shared motif, palette and typography across hero KV, social and display frames.\n3) Adapt: show how the system reflows across ratios without collapsing into a single poster or a Meta-only set.\n4) Deliverables: at least a hero key visual plus social and display adaptations that stay on-system.\n5) Refs: when files are uploaded, pass each shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ads',
    cover: cover687('marketing-campaign-generator'), quickStartCover: quickStartCover('marketing-campaign-generator'), quickStartCoverFit: 'contain',
    featured: feat687('marketing-campaign-generator', [1, 2, 3, 4]), video: video687('marketing-campaign-generator'),
    presets: [P('kv', '主视觉 KV', 'Hero key visual', 'Style: campaign hero key visual, one big idea, slogan in quotes, strong motif and palette, platform-agnostic master.'), P('rednote-cover-maker', '社交延展', 'Social extension', 'Style: social extension frames of the same campaign system, adapted ratios, slogan in quotes, not a Meta-only pack.'), P('display', '展示广告', 'Display ads', 'Style: display ad adaptations of the same campaign motif and palette, short copy in quotes, clear hierarchy.'), P('ooh', '户外主画面', 'OOH master', 'Style: out-of-home campaign master of the same big idea, legible at distance, slogan in quotes, shared motif.')],
    inputs: REF_CARD_INPUTS_687 },

  // #634/#636 B .ai NEW5 production + #637 S4 soft wash pins (bc-refs hardMax layouts).
  // B .ai NEW5 — left column data-driven: single-video | carousel | single-still (not one hard-coded chrome).
  // C deferred.art5 production fills kept below (examples:[] / featured:[] until a C wash tip).
  { id: 'flash-cut-video', name: t('skills.flashCutVideo'), instructions: 'You are a production flash-cut director. Pipeline: landscape screenshot → multi-style still candidates → user picks one → short flash-cut video. This is not a UGC/TVC/poster-animation motion job.\n1) Intake: require a landscape 16:9 screenshot; preserve UI chrome and readable on-screen text; never invent a different product UI.\n2) Stills first: generate several still style directions from the same screenshot (clean product, neon flash, soft narrative, or the user\'s styleNotes); pause for an explicit pick before animating.\n3) Flash-cut only: animate solely the chosen still into a short beat-driven flash-cut clip; no long talking-head UGC, no TVC narrative arc, no poster Ken-Burns substitute.\n4) Craft: product or UI hero energy, high-contrast cuts, safe margins; put every on-art phrase in quotes.\n5) Refs: pass the screenshot shape id in refs (ref_modes content) on every generate_image and animate/video call.',
    category: 'ads', cover: cover637('flash-cut-video'), video: video637('flash-cut-video'),
    examples: [video637('flash-cut-video')], featured: feat637('flash-cut-video', [1, 2, 3, 4, 5]),
    presets: [P('clean', '干净产品风', 'Clean product', 'Style: clean product flash-cut from the screenshot, high-contrast UI still then short punchy beats, readable chrome, no long UGC.'), P('neon', '霓虹快闪', 'Neon flash', 'Style: neon flash-cut energy from the same screenshot, saturated accents, staccato cuts, UI text stays legible.'), P('soft', '柔光叙事', 'Soft narrative', 'Style: soft narrative flash-cut, gentle motion and light bloom, screenshot UI remains sharp and readable.')],
    inputs: [I('screenshot', ['截图', 'Screenshot'], 'image', true), I('styleNotes', ['风格确认', 'Style notes'], 'text', false, ['选定的闪剪风格或节奏', 'Chosen flash-cut style or pacing']), VISUAL] },
  { id: 'style-transfer', name: t('skills.styleTransfer'), instructions: 'You are a production adaptive style-transfer director. Analyze a style reference, then transfer that look onto the user subject while locking identity. Not a logo-material study and not a full brand VI kit.\n1) Dual intake: require contentImage + styleImage; lock subject identity, silhouette, face/logo marks and key proportions from the content ref.\n2) Style read: extract palette, stroke, lighting, grain and medium cues from the style ref only — never from inventing a new brand system.\n3) Controllable transfer: apply the selected medium preset (illustration / photo / graphic); keep the subject recognizable; do not redesign the logo or ship a multi-asset VI.\n4) Guardrails: no identity drift, no swapping the product, no unrelated scene rewrite unless transferNotes asks for it.\n5) Refs: pass both shape ids in refs (content + style as appropriate) on every generate_image call.',
    category: 'branding', cover: cover637('style-transfer'),
    examples: ex637('style-transfer', [1, 2, 3, 4]), featured: feat637('style-transfer', [1, 2, 3, 4, 5]),
    presets: [P('illustration', '插画迁移', 'Illustration', 'Style: illustration-medium transfer onto the content subject, style-ref palette and stroke, identity and silhouette locked.'), P('photo', '摄影迁移', 'Photography', 'Style: photographic look transfer matching style-ref lighting and grain, subject identity locked, no logo redesign.'), P('graphic', '平面迁移', 'Graphic', 'Style: flat graphic / poster transfer with bold shapes from the style ref, subject readable, single-mark discipline.')],
    inputs: [I('contentImage', ['内容图', 'Content image'], 'image', true), I('styleImage', ['风格参考', 'Style reference'], 'image', true), I('transferNotes', ['迁移说明', 'Transfer notes'], 'text', false, ['要保留或避开的元素', 'What to keep or avoid']), VISUAL] },
  { id: 'person-swap', name: t('skills.personSwap'), instructions: 'You are a production e-commerce person-swap artist. Keep pose and scene; swap person and outfit from three bound refs. Not multi-angle catalog capture and not a character-sheet redesign.\n1) Triple intake: require scenePose (pose/scene base), faceRef, and outfitRef — all three must be present before rendering.\n2) Lock: camera, pose, hands, props and background stay from the base; only identity and wardrobe change.\n3) Deliver: PDP-ready coherent set (hero + useful side/detail crops) with fabric and face readable.\n4) Guardrails: no multi-angle identity drift, no new character bible, no background rewrite; this is swap, not redesign.\n5) Refs: pass all three shape ids in refs on every generate_image call.',
    category: 'ecommerce', cover: cover637('person-swap'),
    examples: ex637('person-swap', [1]), featured: feat637('person-swap', [1, 2, 3]),
    presets: [P('hero', '主图换人', 'Hero swap', 'Style: hero PDP person swap, pose and scene locked from base, new face and outfit from refs.'), P('side', '侧面换人', 'Side swap', 'Style: side-angle person swap on the same locked set, identity from face ref, outfit locked.'), P('detail', '细节换人', 'Detail swap', 'Style: detail crop after person swap, fabric and face readable, scene and pose unchanged.')],
    inputs: [I('scenePose', ['场景姿势底图', 'Scene / pose base'], 'image', true), I('faceRef', ['人脸参考', 'Face reference'], 'image', true), I('outfitRef', ['穿搭参考', 'Outfit reference'], 'image', true), VISUAL] },
  { id: 'commerce-strategist', name: t('skills.commerceStrategist'), instructions: 'You are a production commerce visual strategist. Turn selling points into a confirmed visual strategy board first, then keyed frames. Not a lone main-image generator and not a full marketing-campaign KV system.\n1) Brief: read sellPoints (category, benefits, info hierarchy); optional refAssets inform palette and product truth.\n2) Strategy board first: draft information architecture, shot list and style anchors; confirm with the user before heavy renders.\n3) Then frames: produce keyed frames that follow the board — never a random single hero that ignores the board.\n4) Category honesty: 3C / beauty / food presets keep material, light and claim hierarchy truthful to the category.\n5) Refs: when assets are uploaded, pass shape ids in refs on every generate_image call.',
    category: 'ecommerce', cover: cover637('commerce-strategist'), video: video637('commerce-strategist'),
    examples: [video637('commerce-strategist')], featured: feat637('commerce-strategist', [1, 2, 3, 4, 5]),
    presets: [P('3c', '3C 数码', '3C electronics', 'Style: 3C commerce strategy board then hero frames, crisp tech cues, clear benefit ladder, honest materials.'), P('beauty', '美妆', 'Beauty', 'Style: beauty commerce strategy board then soft premium frames, honest claims hierarchy, clean skin/texture light.'), P('food', '食品', 'Food', 'Style: food commerce strategy board then appetite frames, warm light, clear IA, no fake claims.')],
    inputs: [I('sellPoints', ['卖点与品类', 'Selling points & category'], 'text', true, ['品类、核心卖点与要强调的信息层级', 'Category, key benefits and info hierarchy']), I('refAssets', ['参考素材', 'Reference assets'], 'image'), VISUAL] },
  { id: 'lifestyle-scene', name: t('skills.lifestyleScene'), instructions: 'You are a production e-commerce lifestyle scene designer. Ship textless immersive scenes where the product lives in home or daily-wear context. Distinct from white-bg / A+ listing sets on the product skill.\n1) Textless: prefer no on-art claims, badges or poster copy; if words appear they must be in quotes and sparse.\n2) Immersion: blend the product into real living / casual contexts with natural light and believable scale.\n3) Division of labor: this is scene cinema, not listing grids or A+ modules — leave catalog sets to product.\n4) Identity: keep product shape, label and materials locked when productImage is provided.\n5) Refs: pass product shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'ecommerce', cover: cover637('lifestyle-scene'),
    examples: ex637('lifestyle-scene', [1, 2]), featured: feat637('lifestyle-scene', [1, 2, 3]),
    presets: [P('home', '家居场景', 'Home scene', 'Style: textless home lifestyle scene, product naturally placed, soft daylight, no claim poster.'), P('wear', '日常穿搭', 'Daily wear', 'Style: textless daily-wear lifestyle scene, candid framing, product in use, never studio-staged.'), P('table', '桌面氛围', 'Tabletop mood', 'Style: textless tabletop lifestyle mood, shallow depth, product hero without copy.')],
    inputs: [I('productImage', ['商品图片', 'Product images'], 'image', true), I('sceneBrief', ['场景说明', 'Scene brief'], 'text', false, ['家居/穿搭/氛围偏好', 'Home / wear / mood preferences']), VISUAL] },
  // C deferred .art5 — #636 Phase2-S3 C production (instructions/inputs/presets). B wash landed via #637; C still examples:[].
  { id: 'naive-illustration', name: t('skills.naiveIllustration'), instructions: 'You are a production naive hand-drawn illustrator. Ship giant-object vs tiny-person contrast frames with cafe/worker wit. Not a social-media cover set and not a RedNote sticker pack.\n1) Modes: B/W line draft or soft flat-color object-play — follow the selected preset; keep the giant-vs-mini scale joke unmistakable.\n2) Subject: oversized everyday object (coffee cup, bag, phone, food) with a tiny worker/person interacting; friendly line, simple shapes, limited palette unless brief asks otherwise.\n3) Guardrails: never collapse into a generic social cover grid, fashion UGC set, or crayon-sketch children-book look; this is the scale-joke illustration lane.\n4) Copy: put every on-art phrase in quotes; prefer sparse witty labels over poster headlines.\n5) Refs: when refs are uploaded, pass shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'social', cover: cover673('naive-illustration'),
    examples: ex673('naive-illustration', [1, 2, 3, 4]), featured: feat673('naive-illustration', [1, 2, 3, 4, 5]),
    presets: [P('line', '黑白线稿', 'B/W line', 'Style: naive B/W line illustration, giant object vs tiny person, witty cafe/worker energy, clean strokes.'), P('object', '实物互动', 'Object play', 'Style: naive soft flat-color illustration with interactive oversized object play, friendly limited palette.')],
    inputs: NEARMISS_INPUTS },
  { id: 'logo-abstract', name: t('skills.logoAbstract'), instructions: 'You are a production minimal geometric logo designer. Distill a photo into one scalable geometric mark. Not a 3D material study and not a full brand VI kit.\n1) Intake: require the reference photo; lock the subject traits called out in markNotes when present.\n2) Distill: reduce to a single geometric symbol on a plain ground — two-color preference, strict grid, silhouette that survives tiny sizes.\n3) Scope: one mark only; no stationery system, no packaging, no multi-asset VI board (leave those to brand); distinct from logo-material finish studies.\n4) Presentation: plain ground, optional tiny construction notes; put any on-art words in quotes.\n5) Refs: pass the photo shape id in refs (ref_modes content) on every generate_image call.',
    category: 'branding', cover: cover673('logo-abstract'),
    examples: ex673('logo-abstract', [1, 2, 3, 4]), featured: feat673('logo-abstract', [1, 2, 3, 4, 5]),
    presets: [P('circle', '圆形几何', 'Circle geometry', 'Style: minimal circular geometric logo mark distilled from the photo, two-color, scalable silhouette.'), P('angular', '折线几何', 'Angular geometry', 'Style: angular geometric logo mark from the photo, strict grid, plain ground, single-mark discipline.')],
    inputs: NEARMISS_INPUTS },
  { id: 'photo-split-poster', name: t('skills.photoSplitPoster'), instructions: 'You are a production photo-split abstract poster designer. Keep the exact layout: top half original photo, bottom half abstract geometry sampled from its colors. Not a generic flat poster without the photo half.\n1) Intake: require the photo; sample palette strictly from it.\n2) Layout lock: horizontal split — photo above, geometric abstract below; hard or soft edge per preset; never drop the photo half.\n3) Craft: sparse typography if any; every on-art phrase in quotes; prefer portrait/poster ratios suited to ads.\n4) Guardrails: do not morph into a full campaign KV system or a lifestyle scene without the split grammar.\n5) Refs: pass the photo shape id in refs (ref_modes content) on every generate_image call.',
    category: 'ads', cover: cover673('photo-split-poster'),
    examples: ex673('photo-split-poster', [1]), featured: feat673('photo-split-poster', [1, 2]),
    presets: [P('hard', '硬切对半', 'Hard split', 'Style: hard horizontal split poster, photo above, geometric abstract below, palette sampled from the photo.'), P('soft', '柔边对半', 'Soft split', 'Style: soft-edge split poster, photo above, abstract geometry below, shared palette from the photo.')],
    inputs: NEARMISS_INPUTS },
  { id: 'ppt-visual', name: t('skills.pptVisual'), instructions: 'You are a production premium PPT / deck visual designer. Ship modular presentation pages with a shared style library — not print posters and not marketing campaign KVs.\n1) Brief: read deckBrief for topic, page types and style; optional refs set the look library.\n2) Page types: cover, section divider, comparison (and closing when asked) as coherent 16:9 deck frames with one type scale and module system.\n3) Website-chip intent: this lights the website category; keep product-deck language, not printable poster art.\n4) Copy: short on-slide lines in quotes; clear hierarchy; generous margins for projection.\n5) Refs: when refs are uploaded, pass shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'website', cover: cover673('ppt-visual'),
    examples: ex673('ppt-visual', [1]), featured: feat673('ppt-visual', [1, 2]),
    presets: [P('cover', '封面页', 'Cover slide', 'Style: premium deck cover slide 16:9, strong hierarchy, short title in quotes, shared module system.'), P('section', '章节页', 'Section slide', 'Style: section divider slide, modular system coherent with cover, 16:9 projection-safe.'), P('compare', '对比页', 'Comparison slide', 'Style: comparison module slide, clear columns, premium deck language, shared style library.')],
    inputs: NEARMISS_INPUTS },
  { id: 'promo-ecommerce', name: t('skills.promoEcommerce'), instructions: 'You are a production e-commerce promo key-visual designer. Ship big-sale KV plus reusable promo chrome (ribbons, frames, badges). Not a white-bg listing main image and not a full multi-platform marketing-campaign system.\n1) Intake: require productImage and promoBrief (sale theme, offer, dates); lock product identity from the ref.\n2) KV: bold promo hierarchy with product hero, clear claim ladder; put price/claim words in quotes; keep legal honesty.\n3) Chrome: deliver matching reusable promo components (corner badges, borders, ribbons) consistent with the KV.\n4) Division of labor: leave white-bg / A+ listing sets to product; leave brand-wide campaign systems to marketing-campaign.\n5) Refs: pass product shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'ecommerce', cover: cover673('promo-ecommerce'),
    examples: ex673('promo-ecommerce', [1]), featured: feat673('promo-ecommerce', [1, 2]),
    presets: [P('kv', '大促主视觉', 'Promo KV', 'Style: ecommerce promo key visual, bold sale hierarchy, product hero locked from ref, claims in quotes.'), P('badge', '促销组件', 'Promo chrome', 'Style: matching promo badges, ribbons and frames for the same sale system, reusable chrome.')],
    inputs: NEARMISS_INPUTS },
  // D style4 (KEEP for full 15)
  { id: 'yingzao', name: t('skills.yingzao'), instructions: 'Yingzao local editorial poster: real heritage streets / local food travel photos into Chinese display-type edit posters.\n1) Never invent architecture without a photo basis.\n2) Pair the photo with careful Chinese display typography in quotes.\n3) Editorial poster mood; keep place honesty.\n4) Prefer 3:4 or 4:5 social crops.\n5) Refs: pass photo shape ids in refs on every generate_image call.',
    category: 'social', cover: cover812('yingzao'),
    examples: ex812('yingzao', [1, 2]), featured: feat812('yingzao', [1, 2]),
    presets: [P('street', '街巷编辑', 'Street edit', 'Style: local street editorial poster from a real photo, Chinese display type in quotes.'), P('food', '在地食物', 'Local food', 'Style: local food travel editorial poster, honest photo base, display type in quotes.')],
    inputs: [I('placePhoto', ['在地照片', 'Place photo'], 'image', true), I('editNotes', ['编辑说明', 'Edit notes'], 'text', false, ['标题与语气', 'Title and tone']), VISUAL] },
  { id: 'crt-interface', name: t('skills.crtInterface'), instructions: 'CRT retro interface illustration: theme → early CRT computer UI look.\n1) Scanlines, phosphor glow, chunky widgets; multiple colorway presets.\n2) Keep the theme readable inside the faux UI.\n3) Not a flat modern dashboard.\n4) On-screen strings in quotes.\n5) Refs: when refs are uploaded, pass shape ids in refs on every generate_image call.',
    category: 'social', cover: cover812('crt-interface'),
    examples: ex812('crt-interface', [1, 2]), featured: feat812('crt-interface', [1, 2]),
    presets: [P('green', '绿色磷光', 'Green phosphor', 'Style: green phosphor CRT interface illustration of the theme, scanlines, chunky widgets.'), P('amber', '琥珀磷光', 'Amber phosphor', 'Style: amber CRT interface illustration, warm glow, early computer UI chrome.'), P('blue', '冷蓝终端', 'Cold blue terminal', 'Style: cold blue CRT terminal UI illustration, scanlines, readable theme labels in quotes.')],
    inputs: [I('theme', ['主题', 'Theme'], 'text', true, ['界面主题或产品名', 'UI theme or product name']), I('refs', ['参考', 'References'], 'image'), VISUAL] },
  { id: 'crayon-sketch', name: t('skills.crayonSketch'), instructions: 'Rough crayon / oil-pastel sketch: turn a realistic subject into children-book crayon energy.\n1) Distinct from naive giant-object cafe illustration.\n2) Visible crayon strokes, soft wax texture, playful proportion.\n3) Keep subject recognizable.\n4) Minimal text; any words in quotes.\n5) Refs: pass subject shape id in refs on every generate_image call.',
    category: 'social', cover: cover812('crayon-sketch'),
    examples: ex812('crayon-sketch', [1, 2]), featured: feat812('crayon-sketch', [1, 2]),
    presets: [P('wax', '蜡笔涂鸦', 'Crayon doodle', 'Style: rough crayon doodle of the subject, wax texture, playful child-book energy.'), P('pastel', '油画棒', 'Oil pastel', 'Style: oil-pastel sketch of the subject, thick strokes, soft blend, recognizable form.')],
    inputs: [I('subject', ['主体图', 'Subject'], 'image', true), I('notes', ['风格说明', 'Style notes'], 'text', false, ['可留空', 'Optional']), VISUAL] },
  { id: 'fabric-collage', name: t('skills.fabricCollage'), instructions: 'Fabric collage: mix ≥5 textile materials with real stitch and frayed-edge craft.\n1) Not a flat paper collage poster — emphasize cloth, thread and DIY handwork.\n2) Show mixed weaves, knits and trims in one composition.\n3) Keep tactile honesty; soft studio or craft-table light.\n4) Minimal text; words in quotes if any.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'social', cover: cover812('fabric-collage'),
    examples: ex812('fabric-collage', [1, 2]), featured: feat812('fabric-collage', [1, 2]),
    presets: [P('craft', '手工桌面', 'Craft table', 'Style: fabric collage on a craft table, ≥5 textiles, visible stitches and frayed edges.'), P('wall', '布艺墙饰', 'Textile wall', 'Style: textile wall collage, mixed fabrics, handmade stitch character, tactile depth.')],
    inputs: [I('brief', ['主题说明', 'Theme brief'], 'text', true, ['拼贴主题与材质偏好', 'Collage theme and material prefs']), I('refs', ['参考', 'References'], 'image'), VISUAL] },
  // #640/#642/#643 Phase3 — 19 NEW skills; cover643 pins; NEARMISS_INPUTS (Upload+Additional); examples/featured empty until fuller gold; no competitor copy. Dropped-13 out.
  { id: 'taobao-product', name: t('skills.taobaoProduct'), instructions: 'You are a production Taobao listing visual designer. Ship a Chinese PDP set — not an Amazon white-bg catalog set.\n1) Brief: product, selling points and module list from productImage + sellPoints; keep product identity locked.\n2) Modules: main image, carousel frames, lifestyle scene and detail-page benefit blocks with Chinese claim hierarchy.\n3) Division: this is Taobao page system work; leave Amazon/A+ listing grids to the product skill.\n4) Copy: put every on-art Chinese phrase in quotes; mobile-legible. Any promo copy the user asks for (e.g. 「买一送一」) MUST be written verbatim inside quotes in that image prompt as on-image text, e.g. sticker in the top-right corner reading "买一送一", large bold, exact characters, clearly legible; never drop or paraphrase it, and check the result shows it.\n5) Main image: 1:1, product above center filling over 60% of the frame, selling-point sticker fixed in a corner; category locked to the uploaded product.\n6) Refs: pass product shape ids in refs (ref_modes content) on every generate_image call.',
    category: 'ecommerce', cover: cover643('taobao-product'), examples: ex643('taobao-product', [1, 2, 3, 4, 5, 6, 7, 8]), featured: [],
    video: pinned('805/reuse/taobao-product', 'b2ec2a5c7aeb294257087216057de4bb4105d944', 'cover.mp4'), /* #805 hover */
    presets: [P('main', '主图', 'Main image', 'Style: Taobao 1:1 main image, clean product hero, Chinese claim space reserved, high thumb-stop contrast.'), P('scene', '场景图', 'Scene', 'Style: Taobao lifestyle scene with product in use, Chinese benefit callout in quotes.'), P('detail', '详情模块', 'Detail module', 'Style: Taobao detail-page benefit module, stacked claims in quotes, product truth locked.')],
    inputs: NEARMISS_INPUTS },
  { id: 'before-after', name: t('skills.beforeAfter'), instructions: 'You are a production before/after visual designer. Ship ONE comparison card, not separate images and not a copy of the reference.\n1) One image only: one card with two separate photo panels of the same subject placed side by side (left before, right after; stacked only when the brief says so), with a visible gap between them. Each panel is a complete photo. Never split one face down the middle and never mirror one photo into two symmetric halves. Never emit 2 or 3 solo images. count is 1.\n2) Lock: the same person, the same camera, and the same light in both panels. Only the effect changes (treatment, remodel, makeup, fitness). Keep the user\'s own words for what changes. Describe both panels as finished states: Before is a slight, everyday version of that change, still noticeable at thumbnail size. Describe Before\'s darkness or unevenness only as a soft shade slightly deeper than the person\'s own surrounding skin tone; do not name a color for it and do not use intensifiers like "distinct", "clearly visible" or "deep". Describe After\'s area only as the person\'s own surrounding skin tone, even and natural, with texture kept. After is a modest, realistic improvement of the same change, with natural texture kept. Describe only the change the user named, at the intensity the user stated; if the user gave no intensity, keep it slight and everyday. Do not add symptoms, colors, causes or intensifiers the user did not mention.\n3) Labels: readable "Before" and "After" in quotes, one on or under each panel. Typography: use the typography the user specifies; otherwise match the headline and label typography of the reference. When the user specifies no typography, set the labels as small, thin-weight, widely letter-spaced grey sans-serif capitals "BEFORE" and "AFTER". Render each headline sentence on its own line; never draw separator characters such as slashes.\n4) Copy: when the user gives text, use it word for word and add no other text. Never invent brand names, product names, percentages or efficacy numbers.\n5) Size: default ratio "16:9", width 1920, height 1080. When the user names a ratio in their message, use that ratio. With a reference and no ratio from the user, the server sets the ratio from the card inside the reference. The server sets the exact pixels. Pass skill "before-after", the ratio, and the pixels on the one generate_image call. Never fall back to a square default.\n6) Refs: when a reference is uploaded, pass it in refs. Keep identity from it. Do not redraw a different person and do not return the reference unchanged.\n7) Camera: with a reference, state in the prompt which features its frame includes and where it cuts, and copy that angle and crop exactly in both panels; never widen or tighten it. Only when there is no reference: frontal, eye-level, head-and-shoulders, identical framing in both panels.\n8) Path: one generate_image, then wait_generation, then done. Do not call list_models. Do not call expand_image. Do not call create_frame. Do not outpaint.',
    category: 'ads', cover: cover643('before-after'), examples: ex643('before-after', [1, 2, 3, 4, 5, 6, 7, 8]), featured: [],
    video: pinned('805/reuse/before-after', 'b2ec2a5c7aeb294257087216057de4bb4105d944', 'cover.mp4'), /* #805 hover */
    presets: [P('beauty', '美妆对比', 'Beauty', 'Style: one 16:9 comparison card 1920x1080, two side-by-side photos of the same person, beauty before and after, same camera and light, readable Before and After labels.'), P('home', '家装对比', 'Home remodel', 'Style: one 16:9 comparison card 1920x1080, two side-by-side photos of the same interior, matched camera, labeled panels.'), P('fitness', '身材对比', 'Body / fitness', 'Style: one 16:9 comparison card 1920x1080, two side-by-side photos of the same person, fitness before and after, same light, labeled panels.')],
    inputs: NEARMISS_INPUTS },
  { id: 'anim-2d', name: t('skills.anim2d'), instructions: 'You are a production 2D animation converter. Pipeline: still or layered art → short 2D animated clip. Not UGC/TVC motion and not flash-cut screenshot video.\n1) Intake: require primary visual; optional layers or styleNotes.\n2) Confirm duration and ratio with the user before animating.\n3) Animate with readable 2D motion (loops OK); keep line and color honest to the still.\n4) Scope: short 2D piece only — no long narrative TVC, no flash-cut UI beats.\n5) Refs: pass shape ids in refs on every generate_image / animate call.',
    category: 'ads', cover: cover643('anim-2d'), examples: ex643('anim-2d', [1, 2, 3], '51ee77b3dd3979e6c249c0390b931a9a520da1c0'), featured: [],
    presets: [P('clean', '干净动效', 'Clean motion', 'Style: clean 2D animation from the still, short loop, readable motion, locked palette.'), P('punchy', '节奏动效', 'Punchy motion', 'Style: punchy 2D animation beats from the still, short runtime, high energy.')],
    inputs: NEARMISS_INPUTS },
  { id: 'creator-identity', name: t('skills.creatorIdentity'), instructions: 'You are a production creator identity designer for personal channels — not a full corporate VI kit.\n1) Brief: nickname, persona and channels from creatorInfo + refs.\n2) Kit: avatar, channel/cover set, palette and social templates that share one look.\n3) Presets: YouTube, RedNote/Xiaohongshu, podcast as asked.\n4) Scope: personal creator system; do not invent a multi-industry brand bible.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'branding', cover: cover643('creator-identity'), examples: ex643('creator-identity', [1], '3e2df6b2192a6600f3b32d394f8fd5ab820ca98b'),
    // #805: owner/product/QA PASS creator v4 still 782×432 (sha 4928eeb8). MAE≈36 vs REFERENCE. Cover and examples stay. WaveSpeed unused.
    featured: [pinned('805/reuse/creator-identity', 'a9865d28d584068861020b7eda74ddd6e4daab75', 'featured.png')],
    video: pinned('805/reuse/creator-identity', 'b2ec2a5c7aeb294257087216057de4bb4105d944', 'cover.mp4'), /* #805 hover */
    presets: [P('youtube', 'YouTube套件', 'YouTube kit', 'Style: creator YouTube identity kit — avatar, banner-safe cover, palette chips, consistent persona.'), P('xhs', '小红书套件', 'RedNote kit', 'Style: creator RedNote identity kit — avatar, cover, palette, feed-ready frames.'), P('podcast', '播客套件', 'Podcast kit', 'Style: creator podcast identity kit — avatar, show cover, palette, simple lockups.')],
    inputs: NEARMISS_INPUTS },
  { id: 'product-website', name: t('skills.productWebsite'), instructions: 'You are a production product-website designer for hardware / consumer electronics. Ship landing modules with hero + specs — not a SaaS component library.\n1) Brief: product, specs and brand cues from siteBrief + refs.\n2) Modules: hero, spec grid and supporting sections that share one visual system.\n3) Division: hardware product site language; leave SaaS UI kits to web-product.\n4) Copy: short on-art lines in quotes.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'website', cover: cover643('product-website'), examples: ex643('product-website', [1, 2, 3]),
    // #805: homepage featured reuses furniture example 02 @ WASH_643. No new file.
    featured: [pinned('643/wash/product-website/examples', WASH_643, '02.webp')],
    presets: [P('hero', '英雄首屏', 'Hero', 'Style: hardware product site hero, strong product shot, short headline in quotes, 16:9.'), P('specs', '规格模块', 'Specs module', 'Style: product specs module, clear grid, hardware truth, coherent with hero.')],
    inputs: NEARMISS_INPUTS },
  { id: 'studio-model', name: t('skills.studioModel'), instructions: 'You are a production studio model apparel photographer. Ship studio-lit lookbook stills — not street Fashion UGC and not lifestyle cinema.\n1) Brief: garment, model cues and shot list from garmentRef + brief.\n2) Product in frame when asked; keep fabric and fit honest.\n3) Division: studio apparel catalog energy — not candid UGC, not home lifestyle scenes.\n4) Refs: pass shape ids in refs on every generate_image call. Every generate_image call must pass skill: "studio-model".\n5) Before generating, call ask_user twice, in order (two steps). Do not combine both cards into one ask_user call. allow_skip true on both. Do not set defaults or recommended — none are preselected. The card already letters options; do not add a lettered chip for the other row, set allow_other true. Derive every question prompt and every option from the uploaded garment plus this skill\'s question structure and order; never invent garment features that are not visible in the upload. Use zh prompts, labels and placeholders when the chat is zh or the user wrote Chinese; English equivalents only if the locale is en. Option counts must follow the question: do not pad a short question to four chips (gender is two options plus the free-text other row, not four options). Structure and order (fill color, cut, neckline, surface design and studio backdrop from the upload at ask time; do not bake this garment into these instructions):\nFirst card — call ask_user once with questions[] of three questions, all page 1, page_count 3, so the header is 1 of 3. Put every question on page 1 so the card lists all three in one scrollable card; page_count 3 only drives the header 1 of 3. Do not put these three questions on separate pages and do not paginate with 下一步 into 2 of 3 or 3 of 3. If the card scrolls, the footer is Skip + Next until the bottom, then Skip + Submit (Submit is disabled when nothing is selected):\n- id "gender", page 1: ask which model gender should appear. Word the prompt from the garment\'s observed cut or style when that is visible. Options: exactly A 女模特, B 男模特; do not add a third or fourth chip. allow_other true so the other row is C, placeholder "以上都不符合，我自己补充...（自填）".\n- id "selling_points", page 1: prompt "详情页这张图，你最想让买家第一眼看到什么？". Build 3–4 options that are selling points visible on the uploaded garment; never invent features that are not on the garment. allow_other true, placeholder "以上都不符合，我自己补充...（自填）".\n- id "ethnicity", page 1: prompt "模特族裔：". Options: A 亚洲人, B 白人, C 黑人, allow_other true so the other row is D, placeholder "以上都不符合，我自己补充...（自填）".\nSecond card — after the first card is answered or skipped, call ask_user once more with a single question, page_count 1, no 1 of N pager; the footer is only Skip and Submit:\n- id "studio_direction", page 1: prompt exactly "选一个棚拍方向继续生成：". Offer exactly 3 options, each stating a background + a pose (framing words such as 半身 are optional; 正面 is allowed). Append "（推荐）" to option A\'s label text only; do not set recommended, defaults, or any preselect — none are preselected. allow_other true so the last option is "以上都不符合，我自己描述方向…". Compose the three background+pose pairs from this skill\'s on-body studio purpose and the garment in front of you; do not write a fixed backdrop or pose into these instructions.\nIf the user skips or does not answer a question, use the user\'s own words for it when present; otherwise take the first option.\n6) Default output is 1 image of the same model (not 4). Every generate_image call must include skill: "studio-model". The generate_image prompt must contain only the user\'s words, the card answers, the reference garment, and this skill\'s inherent layout purpose (an e-commerce detail-page on-body studio still). Do not invent a lens, lighting setup, backdrop color, frame crop, shot length, or intensifier the user, a card answer or the reference did not give. Do not write "even soft studio lighting" or "full-length". Do not state head angle, gaze direction or subject position unless the user\'s words, a card answer, a reference or this skill\'s base-image layout give one.',
    category: 'ecommerce', cover: cover643('studio-model'), examples: ex643('studio-model', [1, 2], '9ca3c35db7868e9fe73fb98bf85058c8fa2e048e'), featured: [],
    // #805: wash first frame (grey hoodie / cream cargo). Not gold, not the competitor original, not old HOLD.
    video: pinned('805/reuse/studio-model', '44a5caa051ad8c4bd51152afba8ef853e9c77fd8', 'cover.mp4'),
    presets: [P('full', '全身', 'Full body', 'Style: studio full-body apparel shot, controlled light, garment truth, clean backdrop.'), P('half', '半身', 'Half body', 'Style: studio half-body apparel shot, fabric readable, soft controlled light.'), P('detail', '特写', 'Detail', 'Style: studio apparel detail close-up, stitch and material honest, controlled light.')],
    inputs: NEARMISS_INPUTS },
  { id: 'youtube-channel-banner', name: t('skills.youtubeChannelBanner'), instructions: 'You are a production YouTube channel-art designer. Ship 2560×1440 channel banners with safe areas — not a single-video thumbnail and not a promo banner ad. This skill follows the reference YouTube Channel Banner flow (review-assets d7672d03): card 1, a three-direction board, card 2, then the final.\n1) Model: every generate_image call must pass skill: "youtube-channel-banner" and banner_stage (board, base or direct). The skill runs on GPT Image 2.6 Sunburst (text-to-image; edit when an uploaded logo or avatar is passed in refs). The server makes every step one 16:9 image at 2k (2048×1152); do not pass width, height, ratio, count, model or quality.\n2) Card 1 — before any generate_image, call ask_user once with questions[] of three questions, all page 1, page_count 3, so the header is 1 of 3. Put every question on page 1 so the card lists all three in one scrollable card; do not paginate with 下一步. allow_skip true. Do not set defaults or recommended — none are preselected. The card already letters options; set allow_other true on every question so the last row is free text. Use these zh prompts, labels and placeholders verbatim when the chat is zh or the user wrote Chinese; English equivalents only if the locale is en:\n- id "yt_delivery", page 1, prompt "这次横幅想怎么交付？（影响后续步骤与文字精度）", options [{id:"A", label:"先出三方向选择板，再做终稿"}, {id:"B", label:"直接出一张终稿，文字用精确排版渲染"}, {id:"C", label:"直接出一张终稿，文字由图像模型生成"}], placeholder "其它想法（比如一次出多个方向终稿）..."\n- id "yt_banner_text", page 1, prompt "横幅上实际要出现哪些文字？". Build exactly three options live from the user\'s own words: A = channel name ＋ tagline ＋ schedule, B = channel name ＋ tagline, C = 只有 <channel name>. Copy the user\'s original words verbatim first: if the user already gave the banner text or phrases, options A and B must reuse those exact characters, including 和, spaces and punctuation; do not tighten, rewrite or convert them to · (e.g. the user writes 「AI 绘画教程和创意工作流」 → the option keeps 「AI 绘画教程和创意工作流」; forbidden: 「AI 绘画教程·创意工作流」). Only when the agent composes a description the user did not write, join two descriptive phrases with a middle dot · instead of 和/与/、 (e.g. 「品牌叙事·视觉实验」), and write a two-day schedule the agent writes itself as 每周X/Y更新 (e.g. 「每周二/五更新」). The same · and / punctuation applies to English equivalents the agent writes. Join the lines with " ＋ ". Add no words the user didn\'t give; never invent a tagline, date, handle, URL or contact. Once an option is picked, that option\'s lines go into the image prompt word for word, punctuation included. placeholder "自己指定文案（含大小写、符号、换行）..."\n- id "yt_brand_assets", page 1, prompt "有需要放进去的品牌资产吗？（Logo／头像／真人）", options [{id:"A", label:"没有，纯图形＋文字构成识别"}, {id:"B", label:"有 Logo／头像，我上传给你"}, {id:"C", label:"需要预留真人出镜位置"}], placeholder "其它（比如指定参考图／配色）..."\nIf the user skips or does not answer a question, use the user\'s own words for it when present; otherwise take the first option.\n3) Direction board (yt_delivery A): call generate_image once with banner_stage "board". The prompt names the picked copy in quotes, punctuation included, the brand colors and the style the user asked for; the server adds the board structure: three stacked 16:3 banners (top, middle, bottom) that differ in structure — brand-led layout with generous white space, full-frame scene, modular grid — sharing the same brand colors, Chinese sans-serif and copy. After it is delivered, reply with exactly one line per direction (顶部 / 中部 / 底部: what its structure is), then one line naming the shared brand system. Then card 2.\n4) Card 2 — call ask_user once more with questions[] of two questions, both page 1, page_count 2, so the header is 1 of 2. allow_skip true, allow_other true on both, no defaults, no recommended flag. Use these zh prompts, labels and placeholders verbatim when the chat is zh or the user wrote Chinese; English equivalents (same ids, same A/B order, same meaning) only if the locale is en — the server locks this fixed card-2 text in the card language, and the direction options stay your live copy:\n- id "yt_direction", page 1, prompt "选哪个方向做 2560×1440 终稿？". Exactly three options A/B/C for the board\'s top / middle / bottom direction: label "方向 A：<short name>", description one line on why it fits (where it sits on the board and how it reads on TV, desktop and phone). Write that label prefix, short name and description in the card language (en label "Direction A: <short name>"). Put "（推荐）" at the start of the description of the one you recommend, on that one description only; do not put it in the label; nothing is preselected. In the en UI use "(Recommended)" for that marker instead of "（推荐）". placeholder "想调整（说哪里改）或让我直接定..."\n- id "yt_text_mode", page 1, prompt "终稿的文字怎么上？（中文＋三行信息，精度差异较大）", options [{id:"A", label:"精确排版（推荐）"}, {id:"B", label:"图像模型直出"}], placeholder "其它要求..."\n5) Final, 精确排版 (yt_text_mode A, or yt_delivery B): call generate_image once with banner_stage "base", and pass channel_name, tagline and schedule exactly as picked on card 1, punctuation included (leave out lines the user did not pick). Describe only the chosen direction\'s main graphic, brand colors, texture and mood; never put the banner copy or any quoted text in this prompt (the server adds the no-text, no-fake-UI clause and keeps the left and center of the middle band light and empty). The server dry-runs the 2560×1440 text layout before any model call; if the copy does not fit, the tool returns a card (id "yt_shorten_copy") asking the user to shorten it and does not generate — call ask_user with that card as returned, then retry generate_image with the shortened copy; do not invent a shorter line yourself. After wait_generation, call compose_banner_text with base = that result\'s URL or shape id, skill "youtube-channel-banner", the same channel_name, tagline and schedule, and brand_color = the board\'s main brand color as hex. The server upscales the base to exactly 2560×1440 and sets the three lines left-aligned inside the YouTube safe area. Do not add the text with add_text, do not ask the image model to draw it, do not edit or expand the composite, and do not regenerate the base when compose_banner_text succeeds.\n6) Final, 图像模型直出 (yt_text_mode B, or yt_delivery C): call generate_image once with banner_stage "direct" and the picked copy in quotes, punctuation included. The model draws the text; there is no compositing and no fallback.\n7) yt_delivery B or C skips the board and card 2; use the brand-led, generous-white-space structure for the final.\n8) Brand assets: yt_brand_assets B — pass the uploaded logo or avatar in refs on generate_image. C — keep a clear area for a person on the right of the middle band instead of the main graphic.\n9) Never invent dates, accounts, handles, contact details, fake UI, panel labels or prompt text on any image.',
    category: 'social', cover: cover643('youtube-channel-banner'), examples: ex643('youtube-channel-banner', [1, 2, 3, 4, 5, 6, 7, 8, 9], '5ff0d28d04a9447c649bd775430e990b2690184e'),
    // #805: QA PASS free v1 still 1584×396 (sha 69caf1f4). Cover and examples stay. WaveSpeed unused.
    featured: [pinned('805/reuse/youtube-channel-banner', '9af921cda0daa221b75250e5d4c96e39c261a481', 'featured.png')],
    video: pinned('805/reuse/youtube-channel-banner', 'b2ec2a5c7aeb294257087216057de4bb4105d944', 'cover.mp4'), /* #805 hover */
    presets: [P('series', '系列识别', 'Series identity', 'Style: YouTube channel banner 2560×1440, series identity, safe-area protected title/face.'), P('face', '人像安全区', 'Face safe area', 'Style: YouTube channel banner with face in safe area, niche cue, high contrast.')],
    inputs: NEARMISS_INPUTS },
  { id: 'ai-model', name: t('skills.aiModel'), instructions: 'You are a production AI model identity designer. Lock a reusable virtual model (face/body/ethnicity cues) then dress them across outfits and scenes — not a one-shot person-swap and not a character sheet bible.\n1) Intake: modelSpec + outfit/scene refs; freeze identity across frames.\n2) Consistency: same face, body and skin language when wardrobe/scene changes.\n3) Deliver: multi-outfit / multi-scene set that reads as one model.\n4) Division: reusable identity — leave triple-ref pose swap to person-swap; leave turnaround sheets to character.\n5) Refs: pass skill: "ai-model" and shape ids in refs on every generate_image call (the skill runs on its registered model, GPT Image 2.6 Sunburst).\n6) Angles: every outfit/scene frame after the identity anchor changes angle and light.\n7) Before generating, call ask_user once with one card of three questions (questions[] + page_count 3, allow_skip true). Show all three even if the user already said e.g. 一张 or 3:4. Put every question on page 1 so the card lists all three in one scrollable card; page_count 3 only drives the header 1 of 3. Do not put questions on separate pages and do not paginate with 下一步. Do not set defaults or recommended — none are preselected. The card already letters options and draws Skip / Next, or Skip / Submit when scrolled to the bottom; do not add a D/C chip, set allow_other true so the other row is D (or C on the third question). Use these zh prompts, labels and placeholders verbatim when the chat is zh or the user wrote Chinese; English equivalents only if the locale is en:\n- id "look", page 1, prompt "模特长相方向（性别 / 气质 / 人种 / 肤色）选哪一档？", options [{id:"A", label:"女 · 清冷东方 · 中国 · 象牙白"}, {id:"B", label:"女 · 甜美少女 · 中国 · 瓷白"}, {id:"C", label:"男 · 干净少年感 · 东亚 · 自然肤色"}], allow_other true, placeholder "其他（请写：性别 / 气质 / 国籍人种 / 肤色）..."\n- id "backdrop", page 1, prompt "头肩底图的背景用哪个？", options [{id:"A", label:"纯白"}, {id:"B", label:"浅灰"}, {id:"C", label:"米白暖调"}], allow_other true, placeholder "其他（颜色或渐变说明）..."\n- id "output", page 1, prompt "出图方式要哪种？", options [{id:"A", label:"直接出 1 张 3:4 成品"}, {id:"B", label:"先出 4 张面孔候选让我挑"}], allow_other true, placeholder "其他想法..."\nIf the user skips or does not answer a question, use the user\'s own words for it when present (一张 and 3:4 map to output A); otherwise take the first option.\n8) The generate_image prompt must contain only the user\'s words plus the card answers. Do not invent a lens, outfit, makeup, hair style, or lighting setup the user did not name. Do not state head angle, gaze direction or subject position unless the user\'s words, a card answer, a reference or this skill\'s base-image layout give one. As a detail-page base image, leave clear empty space for later copy: subject off to one side with generous headroom.\n9) After images are delivered, offer 换装, 换背景, or 高清放大.',
    category: 'ecommerce', cover: cover643('ai-model'), examples: ex643('ai-model', [1, 2, 3, 4, 5, 6], '604e9be57c96010fc6183f89d02c971f612d10e7'),
    // #805: signed v7 still 402×505 (sha b82e07a4). Not the REFERENCE and not LR-v7. Cover and examples stay.
    featured: [pinned('805/reuse/ai-model', '7fbb71bdce30a57f35c367bc949981c00fb2fc10', 'featured.png')],
    presets: [P('lock', '锁定身份', 'Lock identity', 'Style: establish reusable virtual model identity, clear face/body cues, neutral studio.'), P('outfit', '多着装', 'Multi outfit', 'Style: same AI model identity in a new outfit, identity locked, catalog-ready.'), P('scene', '多场景', 'Multi scene', 'Style: same AI model identity in a new scene, identity locked, coherent light.')],
    inputs: NEARMISS_INPUTS },
  { id: 'product-to-packaging', name: t('skills.productToPackaging'), instructions: 'You are a production product-to-packaging system designer. Start from a product photo and invent pack structure + hero art + shelf — distinct from brief-first packaging.\n1) Intake: require productImage; optional packNotes.\n2) Deliver: structure/dieline logic, front hero, and shelf row when asked (box/bottle/pouch presets).\n3) Identity: keep product silhouette and label cues honest to the upload.\n4) Cross-link: this starts from product truth; brief-only packaging stays on packaging.\n5) Card — this skill follows the reference Product to Packaging System flow (review-assets e304e2fa). Before any generate_image, call ask_user once with questions[] of three questions, all page 1, page_count 3, so the header is 1 of 3. allow_skip true, allow_other true on every question so the last row is free text. Do not set defaults or recommended — none are preselected and none is marked 推荐. Write the card in the ask-card language; the server writes the fixed titles, the question 3 options and the placeholders in that language (zh verbatim below, English equivalents when it is en):\n- id "pk_product", page 1, prompt "这款产品具体是什么？品牌名/产品名怎么定（直接决定包装上的文案与必要信息版面）" where the noun in front of 具体是什么 is written live from the photo, and 这款产品 is only the fallback when it cannot be identified; options: three guesses at what the product is, written from the photo, like "护肤精华油 / Serum（30ml 滴管瓶）"; placeholder "自己填：品类 ＋ 品牌名 ＋ 产品名（不给的话我会先提案一版）..."\n- id "pk_color", page 1, prompt "包装的主色方向选哪个？", options: three main-color directions written from the photo, like "琥珀棕 ＋ 暖沙白，延续产品照片"; placeholder "其它方向..."\n- id "pk_scope", page 1, prompt "这套包装要交付到哪个范围？（可多选）", min_selections 1, max_selections 4, exactly four options in this order: A 核心三件, B 延伸件, C 变体家族, D 技术件, each label "<scope>：<parts> ＋ <parts>" naming the parts for this product (a box or pouch has no 瓶标 or 多香型); for the dropper bottle they were {id:"A", label:"核心三件：外盒 ＋ 瓶标 ＋ 内托"}, {id:"B", label:"延伸件：运输箱 ＋ 手提袋 ＋ 封条/感谢卡"}, {id:"C", label:"变体家族：同系列多支 / 多香型陈列"}, {id:"D", label:"技术件：标注尺寸的结构的构图纸 ＋ 平面刀版稿"}; placeholder "其它，请直接输入..."\nIf the user skips or does not answer a question, use the user\'s own words for it when present; otherwise take the first option.\n6) Output: default 4 images, one generate_image call per image with count 1 and skill: "product-to-packaging", the product shape id in refs on every call (no refs when there is no product photo). Image 1 is the anchor: the package and the product together in one key visual. Call wait_generation for it, then make images 2-4 as extensions of the anchor: add the anchor image shape id to refs and keep its colors, logotype, graphic motif and materials. Images 2-4 show what the user chose in pk_scope. One scope: the parts named in that option across the three images (for the dropper bottle, A 核心三件 was the outer box from several angles, the bottle label close up, the unboxing with the inner tray). Several scopes: the three images go to the scopes round-robin in A-D order, and a free-text answer counts as one more scope after D. More than three scopes with A among them: image 1, the anchor, is A and the other scopes take images 2-4 in order (round-robin if more than three remain), so A+B+C+D is A / B / C / D. pk_scope skipped or not answered: A. The ask_user result lists what each of the 4 images shows in image_plan; make them in that order. The server adds a "This image shows:" line to images 2-4. The server sets the ratio (image 1 3:4, images 2-4 4:3), the model and the size, so do not pass model, width, height, ratio or resolution.',
    category: 'ecommerce', cover: cover643('product-to-packaging'), examples: ex643('product-to-packaging', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14], '6b1cfa37e4eafc72841e70a26909750c2ff44399'),
    // #805: homepage featured reuses example 02 at its existing pin. No new file.
    featured: [pinned('643/wash/product-to-packaging/examples', '6b1cfa37e4eafc72841e70a26909750c2ff44399', '02.webp')],
    presets: [P('box', '盒装', 'Box', 'Style: product-to-box packaging system, structure + front hero from the product photo.'), P('bottle', '瓶装', 'Bottle', 'Style: product-to-bottle packaging, label hierarchy from the product photo.'), P('pouch', '袋装', 'Pouch', 'Style: product-to-pouch packaging, material and seal cues from the product photo.')],
    inputs: NEARMISS_INPUTS },
  { id: 'game-art', name: t('skills.gameArt'), instructions: 'You are a production mobile-game UI designer. Ship ONE portrait game-UI screenshot — not key art, not a character splash, and not a store-cover illustration.\n1) Deliverable lock: every image is a phone screen at ratio "9:16", width 1024, height 1824. Default a full shell: a title bar, a scrollable list or cards, at least one button, and a bottom navigation bar (bottom navigation is required on home and list pages). If the user clearly asks for a sub-page (a match, stage-select, results, or settings screen), that page may use its own chrome and may omit the bottom nav, but the deliverable is still a game UI, not an illustration. Pass skill "game-art", ratio "9:16", width 1024, height 1824 on the one generate_image call. Never 1024x1024.\n2) If the user asks for a character, key art, a store cover, or a scene, put that subject inside the UI (a hero card, a list row, or a banner slot). Do not ship a standalone illustration.\n3) Style follows the user theme while the layout stays a game UI screen. Do not use the skill cover key visual (the promotional character poster with module cards) as the layout or style reference; follow the example UI family (title bar, list or cards, buttons).\n4) Copy: use the names and copy the user gives. If the user gives none, invent fresh copy that fits the user\'s theme. Do not copy the reference image\'s title or any whole word or phrase from it. Do not draw 「」 or other bracket marks around titles. Labels must be large enough to read, with no gibberish. No extra text may appear beyond the intended copy, including extra buttons and labels. All cards, thumbnails and copy stay in the single game category the user named (Go/围棋 by default); every board, thumbnail, and piece stays in that category (for Go, a 围棋 board with black and white stones only). Do not draw xiangqi / 象棋 pieces or characters such as 帅 or 将. Do not draw poker or playing cards, and do not use a card-game theme. Platform or festival decoration (maple, moonlight, ink wash) may stay as a technique, but must not pull the UI out of that single category or clone the gold title.\n5) Path: one generate_image (count 1), then wait_generation, then done. Do not call list_models. Do not call expand_image. Do not call create_frame.\n6) Refs: when refs are uploaded, pass them in refs on that generate_image call.',
    category: 'ads', cover: cover643('game-art'), examples: ex643('game-art', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], 'd325f4a0f7ddedcef4c47052bc725c30c681856b'), featured: [],
    presets: [P('concept', '界面首页', 'UI home', 'Style: one 9:16 mobile game UI home screen, 1024x1824, title bar, feature cards, a primary button, bottom nav. Not key art.'), P('kv', '界面列表', 'UI list', 'Style: one 9:16 mobile game UI list screen, 1024x1824, title bar, list cards, a button, bottom nav. Not a standalone illustration.'), P('event', '界面活动', 'UI event', 'Style: one 9:16 mobile game UI event screen, 1024x1824, title bar, event cards, a button, bottom nav. Not a poster.')],
    inputs: NEARMISS_INPUTS },
  { id: 'portrait-studio', name: t('skills.portraitStudio'), instructions: 'You are a production portrait-studio photographer. Ship single-subject portrait stills with controllable beauty and lens — not ecommerce apparel catalog.\n1) Brief: subject cues, beauty and location from portraitBrief + refs.\n2) Craft: studio or environmental light; focal-length feel as asked.\n3) Subject: single person primary; honest skin and styling.\n4) Division: portrait craft — leave apparel product-in-hand studio sets to studio-model.\n5) Reference photo: this skill follows the reference Professional Portrait Generation Tool flow (review-assets 7fc60c86) and needs a photo of the person. If the user attached no reference photo, do not call ask_user: call generate_image once with skill: "portrait-studio" and no refs. The server does not generate; it returns status needs_input with user_message, the upload request in the ask-card language (zh "请先上传一张人物照片作为参考图，我再为你生成专业形象照。", en "Please upload a photo of the person as the reference first, then I\'ll make the professional portraits."). Reply with that user_message verbatim and stop; nothing is generated or charged.\n6) Card — with a reference photo, before any generate_image, call ask_user once with questions[] of three questions, all page 1, page_count 3, so the header is 1 of 3. allow_skip true, allow_other true on every question so the last row is free text. Do not set defaults or recommended — none are preselected and none is marked 推荐. Use these zh prompts, labels and placeholders verbatim when the ask-card language is zh; the server writes the same card in the ask-card language (English equivalents when it is en):\n- id "ps_shots", page 1, prompt "这组专业形象照想要几张、什么景别组合？", options [{id:"A", label:"3 张：面部特写 + 半身 + 七分身"}, {id:"B", label:"4 张：特写 + 半身 + 七分身 + 全身"}, {id:"C", label:"只要 1 张半身标准照"}], placeholder "其它张数或景别，我来写..."\n- id "ps_outfit", page 1, prompt "服装方向怎么定？（人物长相、发型与身材比例都会锁定参考图不变）", options [{id:"A", label:"保留原有休闲造型"}, {id:"B", label:"换成商务正装"}, {id:"C", label:"简约轻正装"}], placeholder "其它服装，我来描述..."\n- id "ps_scene", page 1, prompt "场景与背景用哪种？", options [{id:"A", label:"纯色棚拍背景"}, {id:"B", label:"现代办公空间"}, {id:"C", label:"沿用参考图的建筑空间"}], placeholder "其它场景，我来描述..."\nIf the user skips or does not answer a question, use the user\'s own words for it when present; otherwise take the first option.\n7) Output: default 3 images (ps_shots A: face close-up, half body, three-quarter body); B is 4 images (close-up, half body, three-quarter body, full body); C is 1 half-body standard photo. One generate_image call per image with count 1, skill: "portrait-studio", the same reference photo in refs, and shot set to that image\'s shot size (closeup, half, three_quarter or full). The prompt is the same on every call: one English description of the person, outfit and background, with no shot size or pose in it. The server adds the shot-size and pose lines, so only shot size and pose change between the images. Face, hairstyle and body proportions stay as in the reference photo; the outfit and scene follow the card answers. Every image is 3:4 portrait; the server sets the model and size, so do not pass model, width, height or resolution.\n8) Replies and redo (server-written, post each verbatim once): after the card is answered and before any generate_image, look at the reference photo and call portrait_studio_plan once with refs, the three answers (shots, outfit, scene: A/B/C or the user\'s own words), locked (what stays from the reference: face features, hair, skin tone, build; short items in the reply language), outfit_desc (the reference outfit in a few words) and reference_background. Post its user_message (what is locked and what changes, lighting, lens, pose, then that generation starts), then make one generate_image per returned slot with that slot\'s shot. When wait_generation has placed every slot, call portrait_studio_done with the placed image ids in slot order and post its user_message as the final reply (the shot-size table, the parameters used and the closing check). Do not list any other parameter, film stock or price.\n9) Redo one image: when the user says one image is off (e.g. 「半身那张脸不像」, 「重做第2张」, "redo #2"), call portrait_studio_redo once with slot (the image number) or shot (the shot size the user named) and an optional English fix. It starts exactly one generate_image for that image (same reference, shot, outfit and background), placed next to the original. Post its user_message, call wait_generation with its ids, and stop. Never regenerate, delete or replace the other images or the original, and never call generate_image yourself for a redo.\n10) Follow-up after the set is done: if the user asks to swap the background color (米白 / 深灰, ivory / dark gray) or add a landscape version (横版构图), call portrait_studio_followup once with kind "background" (and color ivory or dark_gray) or kind "landscape", and slot or shot if they named one image (otherwise the first). It starts exactly one generate_image, placed next to the original, which is kept. Post its user_message, call wait_generation with its ids, and stop. Never delete or replace the original set, and never call generate_image yourself for this follow-up.',
    category: 'social', cover: cover643('portrait-studio'), examples: ex643('portrait-studio', [1, 2, 3, 4, 5, 6], 'd182b5cc030a87cc1911108b735df2cb2c3863fc'),
    // #805: QA PASS free v1 still 378×459 (sha e599e39c). Cover and examples stay. WaveSpeed unused.
    featured: [pinned('805/reuse/portrait-studio', '9af921cda0daa221b75250e5d4c96e39c261a481', 'featured.png')],
    presets: [P('studio', '棚拍人像', 'Studio portrait', 'Style: studio portrait, controlled light, beauty-true, single subject.'), P('env', '环境人像', 'Environmental', 'Style: environmental portrait, natural or location light, single subject, lens character.')],
    inputs: NEARMISS_INPUTS },
  { id: 'premium-website', name: t('skills.premiumWebsite'), instructions: 'You are a production premium website art director. Ship luxury brand site direction and first-screen frames — not SaaS component docs and not hardware spec pages.\n1) Brief: brand, tone and pages from siteBrief + refs.\n2) Art direction: refined typography, photography treatment and hero modules.\n3) Division: premium brand site — leave product-spec hardware sites to product-website; leave SaaS UI kits to web-product.\n4) Copy: sparse elegant lines in quotes.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'website', cover: cover643('premium-website'), examples: ex643('premium-website', [1, 2, 3, 4, 5, 6, 7], '4ccecac30c1cdf3e79826de5614edc5514e150a4'),
    // #805: homepage featured reuses example 07 at its existing pin. No new file.
    featured: [pinned('643/wash/premium-website/examples', '4ccecac30c1cdf3e79826de5614edc5514e150a4', '07.webp')],
    presets: [P('hero', '高端首屏', 'Premium hero', 'Style: premium brand site hero, art-directed photography, sparse headline in quotes.'), P('system', '艺术方向板', 'Art direction board', 'Style: premium web art-direction board, type/palette/photo language, cohesive.')],
    inputs: NEARMISS_INPUTS },
  { id: 'animated-poster', name: t('skills.animatedPoster'), instructions: 'You are a production animated-poster designer. Still poster composition first, then a short looping motion poster — not a static print poster and not a long motion ad.\n1) Still first: lock a strong poster hierarchy; confirm specs.\n2) Animate: short loop; keep type sharp; subtle scene motion.\n3) Scope: motion poster only — leave long UGC/TVC to motion.\n4) Copy: on-art phrases in quotes.\n5) Refs: pass refs in refs on every generate_image / animate call.',
    category: 'ads', cover: pinned('805/reuse/animated-poster', 'a6beae7242511404f6f295265f64d6b7ef00f49b', 'cover.webp'), quickStartCoverFit: 'contain', examples: ex643('animated-poster', [1, 2], '54cc1199ee8eeaaee36c69d04cdbad21f345c8fd'), featured: [],
    // #805: wash first-frame remake from cover-single.webp (not gold/LR).
    video: pinned('805/reuse/animated-poster', '359b05ded3e5649acb69cf8aab33b13db454546b', 'cover.mp4'),
    presets: [P('loop', '短循环', 'Short loop', 'Style: animated poster short loop, type locked, subtle motion, poster hierarchy.'), P('punch', '节奏海报', 'Punchy poster', 'Style: punchy animated poster, short beats, high contrast, readable title.')],
    inputs: NEARMISS_INPUTS },
  { id: 'pose-fission', name: t('skills.poseFission'), instructions: 'You are a production ecommerce pose-fission artist. Same person, outfit, scene and light in one run; change only pose and angle — opposite of person-swap (which changes person/outfit and keeps pose).\n1) Intake: require baseImage; lock identity, outfit (items, fabric, accessories), location and light direction from it.\n2) Plan first, then confirm: before any generate_image, show a Question card in Chinese with one line per image (default 4) giving 景别切线, 角度度数, 机位高度, 构图, 镜头 and 光向, ending 「是否生成这 4 张？」 with options A 开始生成 / B 换一组 / C 其他. Generate only after A.\n3) Plan rules: 4 different poses and angles, no repeats; at most 1 frontal 0° shot. A near-frontal full-length standing frame may be relatively centered (gold ex-01). Do not forbid a frontal or centered frame for that shot.\n4) Framing — always a frame edge, never a bare label (no full body / waist-up / half body / close-up / 半身): full-length = "full-length framing: clear headroom above the top of the head, both feet fully inside the frame with floor visible below the soles" (35mm f/2.8); waist = "framing crops at the waistline / navel: bottom edge of the frame cuts exactly at the navel, nothing below the navel is in frame, hips and thighs NOT visible; the figure from top of head to navel fills the full frame height" (画面下边缘切在腰线/肚脐处；画面下边缘切在肚脐处，肚脐以下不入画，人物头顶到肚脐占满画面高度, 50mm f/2); chest = "framing crops at mid-chest: bottom edge of the frame cuts across the chest, waist NOT visible"; shoulders = "tight framing: bottom edge of the frame cuts at the collarbones / shoulder line, chest NOT visible, face fills the upper two thirds" (85mm f/1.8, eyes in sharp focus).\n5) Angles in degrees: 0° = "head and body at 0°, facing camera directly"; 45° = "head turned 45° from camera (three-quarter view), far eye still visible near the nose bridge"; 90° profile (正侧面 90°，看不到对侧眼睛) = "strict 90° side profile: nose, lips and chin in silhouette, the far eye is NOT visible"; look-back (头转向肩后 90°，下巴越过肩线) = "body facing away from camera, head turned 90° back over the shoulder, chin passes beyond the shoulder line, looking back toward camera"; 180° = "body and head at 180°, back to camera, face not visible"; head-down (低头) = "head tilted down, chin tucked, gaze lowered, face still visible". Camera height: camera at eye level / low camera at waist height angled up / camera slightly above eye level.\n6) Prompt: one generate_image call per plan line; prefix every prompt with: Edit the reference photo. Single 3:4 photorealistic editorial fashion photograph, one frame only, not a collage, grid or contact sheet. Same person, same identity, same outfit, same location and light as reference; change only pose and angle. Commercial fashion model, refined makeup and styling, as attractive as the reference. Keep the reference\'s hard directional light: same light direction (<from camera left/right/back>), same contrast ratio and deep shadows; dappled light and cast shadows fall across the face and the clothing (保留金标的硬光方向和斑驳投影，落在脸部和衣服上). Editorial color grade, fine film grain. Natural skin texture, visible pores, real fabric wrinkles; realistic does not mean unattractive. No flat lighting, no white backdrop, no heavy filter or skin smoothing. Then append that line\'s exact framing, pose, angle, camera and composition sentences so each image traces to its plan line.\n7) Delivery: exactly the planned number of separate 3:4 single images — never a grid; retry a failed image, but total generate_image calls ≤ planned + 2.\n8) Calls: pass skill: "pose-fission" and the base shape id in refs on every generate_image call (the skill runs on its registered model, Nano Banana Pro edit at 2K). Leave triple-ref person/outfit swap to person-swap.\n9) Size: every still is 3:4, width 1536, height 2048. Pass ratio "3:4", width 1536, height 2048, and count 1. Each call must use a different pose and angle so the arguments differ. Do not repeat the same arguments. Never 1024x1024, never a white backdrop, never a grid.',
    category: 'ecommerce', cover: cover643('pose-fission'), examples: ex643('pose-fission', [1, 2, 3, 4], 'f699d4a67dc167f0cc11b736ac9fdbf34bb1ee32'), featured: [],
    presets: [P('stand', '站姿裂变', 'Standing set', 'Style: same-scene pose fission, one 3:4 still 1536x2048, standing angle only, person outfit scene and light locked.'), P('sit', '坐姿裂变', 'Seated set', 'Style: same-scene pose fission, one 3:4 still 1536x2048, seated angle only, identity and light locked.'), P('gesture', '手势裂变', 'Gesture set', 'Style: same-scene pose fission, one 3:4 still 1536x2048, gesture angle only, background locked.')],
    inputs: NEARMISS_INPUTS },
  { id: 'live-promo-decor', name: t('skills.livePromoDecor'), instructions: 'You are a production live-commerce decor designer. Ship overlay packs (bg, stickers, price tags, badges) — not a big-promo KV hero.\n1) Brief: category, offer and overlay needs from liveBrief + refs.\n2) Pack: background, lower-thirds, price tags and corner badges that stack cleanly.\n3) Division: live decor kit — leave campaign KV heroes to promo-ecommerce.\n4) Copy: price/CTA text in quotes; high contrast on stream.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'ecommerce', cover: cover643('live-promo-decor'), examples: ex643('live-promo-decor', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], '497c6feeb559cc2c053a28fc9b45b3b11b595037'),
    // #805: recropped fan-light sticker 387×350, sha 56c05f4c. Not the 322×260 clip. Cover and examples stay.
    featured: [pinned('805/reuse/live-promo-decor', 'e1eb48ba0d2d6511264725c29bd2beebd61816aa', 'featured.webp')],
    video: pinned('805/reuse/live-promo-decor', 'b2ec2a5c7aeb294257087216057de4bb4105d944', 'cover.mp4'), /* #805 hover */
    presets: [P('bg', '直播背景', 'Live background', 'Style: live-stream background decor, product-safe center, high contrast edges.'), P('price', '价签贴片', 'Price tag', 'Style: live price-tag overlay, bold numerals in quotes, stream-safe contrast.'), P('badge', '角标装饰', 'Corner badge', 'Style: live corner badge / sticker pack, stackable, readable on video.')],
    inputs: NEARMISS_INPUTS },
  { id: 'linkedin-banner', name: t('skills.linkedinBanner'), instructions: 'You are a production LinkedIn banner designer. Ship one 1584x396 professional banner — not YouTube channel art and not a square post.\n1) One image: call generate_image exactly once with skill "linkedin-banner", width 1584, height 396, count 1. Do not pass model. Do not pass 1:1 or 16:9. A model that cannot submit those pixels is refused before any image is made; it is not swapped and the banner is not stretched. Do not call list_models. Do not call expand_image. Do not call create_frame. Do not outpaint.\n2) The canvas matches the banner: 1584 by 396. The generator card is the frame. The deliverable is only this banner strip — do not draw LinkedIn page chrome (navigation, feed, or the avatar circle) into the image.\n3) Copy: a two-level title in quotes — a main headline, with a job subtitle directly under it (a role · field line). Short professional lines, large, high contrast, real words. No gibberish. Invent original lines of similar length. Do not copy gold headlines such as "Turning Data Into Decisions", "Signals to Strategy", "Where Capital Meets Conviction", or "Investing in a Brighter Tomorrow".\n4) Safe area (#708 framing for this wide banner, not a portrait): on a personal banner the left quarter is covered by the profile photo, so leave the avatar safe area EMPTY — no face, no avatar circle, and no critical type or graphics there. Put the two-level title in the right two thirds. Keep type off the extreme edges. Do not draw a face into the safe area. A person, if any, must stay far smaller than the safe area and must not be a frontal-centered hero.\n5) Refs: pass refs in refs on that single generate_image call.',
    category: 'social', cover: cover643('linkedin-banner'), examples: ex643('linkedin-banner', [1]),
    // #805: featured is the reviewed 1904×556 layout still (sha ef9d950e). Not a 1584×396 generation sample; cover and examples stay.
    featured: [pinned('805/reuse/linkedin-banner', 'b6e408ace4835f14282a32d4e19c79e143cb4f53', 'featured.png')],
    video: pinned('805/reuse/linkedin-banner', 'b2ec2a5c7aeb294257087216057de4bb4105d944', 'cover.mp4'), /* #805 hover */
    presets: [P('personal', '个人横幅', 'Personal', 'Style: one LinkedIn personal banner 1584x396, two-level title (headline + job subtitle) in the right two thirds in quotes, avatar safe area empty (no face drawn there), no LinkedIn page chrome, no second image and no outpaint.'), P('company', '公司横幅', 'Company', 'Style: one LinkedIn company banner 1584x396, two-level title (headline + subtitle) in the right two thirds in quotes, left-quarter safe area empty (no face or logo drawn there), no LinkedIn page chrome, no second image and no outpaint.')],
    inputs: NEARMISS_INPUTS },
  { id: 'logo-animation', name: t('skills.logoAnimation'), instructions: 'You are a production logo-animation designer. Animate a logo into a short brand intro or loop — not a static material study and not a geometric mark redesign.\n1) Intake: require logoImage; confirm intro vs loop.\n2) Motion: clean entrance or seamless loop; keep geometry identical to the mark.\n3) Division: motion logo — leave material stills to logo-material; leave abstract mark invention to logo-abstract.\n4) Finish: safe margins; no redesign of paths.\n5) Refs: pass logo shape id in refs on every generate_image / animate call.',
    category: 'branding', cover: cover643('logo-animation'), examples: ex643('logo-animation', [1, 2, 3, 4], '12d051fe4c9ce81405b4dd4e81094e21501ae9c4'),
    // #805: owner/product/QA PASS logo v4r still 743×445 (sha 23ea2786). MAE≈33 vs REFERENCE. Cover and examples stay. WaveSpeed unused.
    featured: [pinned('805/reuse/logo-animation', 'a9865d28d584068861020b7eda74ddd6e4daab75', 'featured.png')],
    video: pinned('805/reuse/logo-animation', 'b2ec2a5c7aeb294257087216057de4bb4105d944', 'cover.mp4'), /* #805 hover */
    presets: [P('intro', '入场动画', 'Intro', 'Style: logo intro animation, clean entrance, geometry locked to the mark.'), P('loop', '循环动画', 'Loop', 'Style: logo loop animation, seamless cycle, mark paths unchanged.')],
    inputs: NEARMISS_INPUTS },
  { id: 'restaurant-website', name: t('skills.restaurantWebsite'), instructions: 'You are a production restaurant website designer. Ship landing visuals for menu, atmosphere and reserve modules — not a generic SaaS product site.\n1) Brief: cuisine, tone and modules from restaurantBrief + refs.\n2) Modules: hero mood, menu board and reserve/CTA section sharing one look.\n3) Division: restaurant hospitality site — leave SaaS kits to web-product.\n4) Copy: dish/CTA lines in quotes.\n5) Refs: pass refs in refs on every generate_image call.',
    category: 'website', cover: cover643('restaurant-website'), examples: ex643('restaurant-website', [1, 2, 3, 4, 5, 6, 7], '9ca6d4ee7eb6488bb2c430affa86cfae75613485'),
    // #805: homepage featured reuses example 07 at its existing pin. No new file.
    featured: [pinned('643/wash/restaurant-website/examples', '9ca6d4ee7eb6488bb2c430affa86cfae75613485', '07.webp')],
    video: pinned('805/reuse/restaurant-website', 'b2ec2a5c7aeb294257087216057de4bb4105d944', 'cover.mp4'), /* #805 hover */
    presets: [P('mood', '氛围首屏', 'Mood hero', 'Style: restaurant site mood hero, hospitality photography, sparse headline in quotes.'), P('menu', '菜单模块', 'Menu module', 'Style: restaurant menu module visual, readable dishes, coherent with hero.')],
    inputs: NEARMISS_INPUTS },
  { id: 'clothing-swap', name: t('skills.clothingSwap'), instructions: 'You are a production AI clothing-swap artist. Keep the person; swap garments from a dual ref (person + clothing) — not a triple-ref person-swap.\n1) Intake: require an uploaded person ref (image 1) + a garment ref (image 2).\n2) Ask once: before any generate_image, call ask_user exactly once with ONE question about how to replace the upper-body garment. Generate the options live from what the person in image 1 is wearing; do not hard-code option labels. Include a free-text other row (allow_other). Nothing is preselected: do not set defaults or recommended. Never ask gender, ethnicity, or angle. Write the question, every option, and the free-text placeholder in the UI language when the user typed no text; in the language of the user when they typed text. Use question id "upper_body_swap". page_count 1.\n3) Lock: keep the person, pose, composition, background, and all other clothing from image 1; only the chosen upper-body garment changes.\n4) Prompt: describe only the garment swap. Garment description comes only from image 2. Do not invent or write angle, shot-size, or background words. Do not change pose or framing. Do not transcribe or spell out any text, letters, or words printed on the garment. Instead, say the T-shirt pattern is kept as in image 2, written in the prompt language (for example "T 恤图案照第二张图保留" or "Keep the T-shirt pattern as shown in image 2"). Preserving the lighting of the original photo (for example "consistent lighting with the original photo") is allowed.\n5) Deliver: one try-on still with fabric truth and clean edges. Output aspect follows image 1 (the person photo); the server reads its size and sets width, height and ratio, so do not pass them. Call generate_image exactly once with skill: "clothing-swap", refs in order [person image 1, garment image 2], count=1.\n6) Division: outfit swap on a fixed person — leave scene+face+outfit triple swap to person-swap.',
    category: 'ecommerce', cover: cover643('clothing-swap'), examples: ex643('clothing-swap', [1, 2]),
    // #805: homepage featured reuses washed example 02 @ WASH_643 (1776×2368, sha a2a5f482). Same bytes, no new wash file; cover and examples stay.
    featured: [pinned('643/wash/clothing-swap/examples', WASH_643, '02.webp')],
    presets: [P('casual', '日常换装', 'Casual', 'Style: AI clothing swap casual look, person locked, garment from ref, clean edges.'), P('formal', '正装换装', 'Formal', 'Style: AI clothing swap formal look, person locked, fabric honest.'), P('street', '街头换装', 'Street', 'Style: AI clothing swap streetwear look, person locked, outfit from ref.')],
    inputs: NEARMISS_INPUTS },
  { id: 'interior-architectural-visualization', name: t('skills.interiorArchitecturalVisualization'), instructions: 'Produce photoreal interior or architecture renders: eye-level wide shot, natural light, accurate materials, 16:9. Add a detail vignette at 4:3.',
    cover: cover687('interior-architectural-visualization'), quickStartCover: quickStartCover('interior-architectural-visualization'), featured: feat687('interior-architectural-visualization', [1, 2]), video: video687('interior-architectural-visualization'),
    inputs: REF_CARD_INPUTS_687 },
])

export const skillAtom = atom<Skill | null>('skill', null)
/** #673 — the plain sentence shown in the composer when a hidden skill is attached from an old session / card / link. */
export const skillNoticeAtom = atom<string | null>('skill notice', null)
/** #673 — the one place a skill reaches the composer from saved work (deep link, resend, try-it). A hidden skill is
 *  refused: no chip, the notice is shown, and the caller must not send (no agent turn, no paid submit, no request). */
export function attachSkill(s: Skill | null): boolean {
  if (s && hiddenSkillNotice(s)) { skillAtom.set(null); skillNoticeAtom.set(hiddenSkillNotice(s)); return false }
  skillNoticeAtom.set(null)
  skillAtom.set(s)
  return true
}
/** #673 — same refusal for a send that already holds a skill (safety net in sendToAgent). True = blocked. */
export function blockHiddenSkill(s: Pick<Skill, 'id' | 'custom'> | null | undefined): boolean {
  const notice = hiddenSkillNotice(s)
  if (notice) skillNoticeAtom.set(notice)
  return !!notice
}

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

/** #673 — what pickers show (home, Skills page, + menu, / picker, agent list). Lookups by id keep using loadSkills(). */
export async function loadListedSkills(): Promise<Skill[]> {
  return listedSkills(await loadSkills())
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
/** #705: marker the agent loop treats as a hard stop (bot/agent_loop.py NON_RETRYABLE_MARK). */
export const SKILL_NON_RETRYABLE = '[non-retryable]'

/** #960: skill reads are paged so the agent's 4000-char tool-result cap can never drop the tail
 *  (card specs used to land past the cut). A page is the real text from `offset`, never a summary;
 *  `next_offset` is exactly how to continue. 3000 keeps the page plus its envelope under the cap
 *  and keeps the YouTube card 1 spec (ends at ~2900 chars) whole on page 1. */
export const SKILL_READ_PAGE = 3000
export const SKILL_READ_MAX_PAGE = 3000
const SKILL_READ_PAGE_NOTE = 'This is one page of the real skill text, not a summary. When has_more is true, '
  + 'call skill action="read" again with the same id/name (and the same path for a bundled file) plus '
  + 'offset=next_offset to read the rest. One page is never the whole skill; read until has_more is false.'
const SKILL_READ_PAST_END = 'offset is at or past the end of the text; total_chars is its full length.'

function skillReadPage(text: string, args: Record<string, unknown>) {
  const total = text.length
  const wantsOffset = Math.floor(Number(args.offset))
  const wantsLimit = Math.floor(Number(args.limit))
  const explicit = Number.isFinite(wantsOffset) || Number.isFinite(wantsLimit)
  if (!explicit && total <= SKILL_READ_PAGE) return null
  const offset = Math.min(total, Math.max(0, Number.isFinite(wantsOffset) ? wantsOffset : 0))
  const limit = Math.max(1, Math.min(SKILL_READ_MAX_PAGE, Number.isFinite(wantsLimit) && wantsLimit > 0 ? wantsLimit : SKILL_READ_PAGE))
  const end = Math.min(total, offset + limit)
  return {
    content: text.slice(offset, end),
    offset,
    total_chars: total,
    next_offset: end < total ? end : null,
    has_more: end < total,
    note: offset >= total && total > 0 ? SKILL_READ_PAST_END : SKILL_READ_PAGE_NOTE,
  }
}

export async function skillTool(args: Record<string, unknown>): Promise<unknown> {
  const skills = await loadSkills()
  const listed = listedSkills(skills)
  if (args.action === 'list') return { skills: listed.map((s) => ({ id: s.id, name: s.name, description: s.description ?? '', custom: !!s.custom })) }
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
  // #705: an empty read used to fall through to `unknown skill undefined` and the agent retried it in a loop.
  if (!id && !(typeof args.name === 'string' && args.name.trim())) {
    throw new Error(`${SKILL_NON_RETRYABLE} skill read needs a non-empty id or name (e.g. id="linkedin-banner"); do not retry this call — use action="list" for ids`)
  }
  // #733: a read resolves by id OR display name (either field); hiding (#673) only affects entry points / pick-lists,
  // never the agent's own read by id or name.
  const keys = [id, typeof args.name === 'string' ? args.name.trim() : ''].filter(Boolean)
  const norm = (v: string) => v.trim().toLowerCase()
  const skill = skills.find((s) => keys.includes(s.id)) ?? skills.find((s) => keys.includes(s.name))
    ?? skills.find((s) => keys.some((k) => norm(k) === norm(s.id) || norm(k) === norm(s.name)))
  if (!skill) throw new Error(`unknown skill ${JSON.stringify(id || args.name)} — available: ${listed.map((s) => `${s.name} (${s.id})`).join(', ')}`)
  if (args.path) {
    const content = skill.files?.[String(args.path)]
    if (content == null) throw new Error(`skill ${skill.name} has no file ${args.path}; files: ${Object.keys(skill.files ?? {}).join(', ') || '(none)'}`)
    const page = skillReadPage(content, args)
    if (page) return { id: skill.id, name: skill.name, path: args.path, ...page }
    return { id: skill.id, name: skill.name, path: args.path, content }
  }
  const output = SKILL_OUTPUT[skill.id]
  const page = skillReadPage(skill.instructions, args)
  if (page) {
    // files stay (the agent needs the path names); images are display assets that were already
    // past the old cut for long skills, and dropping them keeps the page under the result cap.
    return { id: skill.id, name: skill.name, description: skill.description ?? '', files: Object.keys(skill.files ?? {}), ...page, ...(output ? { output } : {}) }
  }
  return { id: skill.id, name: skill.name, description: skill.description ?? '', instructions: skill.instructions, files: Object.keys(skill.files ?? {}), images: Object.values(skill.images ?? {}), ...(output ? { output } : {}) }
}

/** #460/#461 — Explore wall + conversational creator (form kept as fallback). */
const FAV_KEY = 'comfyart.skillFavourites'
/** #581 — local per-browser usage counts (id → n). Increment only on a real run start; never seed. */
const USAGE_KEY = 'comfyart.skillUsage'

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

/** #581 — map of skill id → local run count. Empty on a fresh install. */
export function loadSkillUsage(): Record<string, number> {
  try {
    const raw = localStorage.getItem(USAGE_KEY)
    const obj = raw ? JSON.parse(raw) as unknown : {}
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return {}
    const out: Record<string, number> = {}
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      if (typeof k === 'string' && typeof v === 'number' && Number.isFinite(v) && v > 0) out[k] = Math.floor(v)
    }
    return out
  } catch {
    return {}
  }
}

export function getSkillUsage(id: string): number {
  return loadSkillUsage()[id] ?? 0
}

/** #581 — bump when the user actually starts a run (dialog 「开始制作」 or direct newProject({ skill })). */
/** #748 — OUR per-template stats: +1 per successful 「开始制作」 with that template (localStorage). Never copied from any reference API. */
const TEMPLATE_USAGE_KEY = 'comfyart.skillTemplateUsage'
function loadTemplateUsage(): Record<string, number> {
  try { const v = JSON.parse(localStorage.getItem(TEMPLATE_USAGE_KEY) ?? '{}'); return v && typeof v === 'object' ? v : {} } catch { return {} }
}
export function getTemplateUsage(skillId: string, presetId: string): number {
  return loadTemplateUsage()[`${skillId}/${presetId}`] ?? 0
}
export function recordTemplateUse(skillId: string, presetId: string): number {
  const map = loadTemplateUsage(); const k = `${skillId}/${presetId}`
  map[k] = (map[k] ?? 0) + 1
  try { localStorage.setItem(TEMPLATE_USAGE_KEY, JSON.stringify(map)) } catch { /* private mode */ }
  return map[k]
}
/** Inverse of recordTemplateUse: drop the last +1 (used when run() throws after we already counted). */
export function unrecordTemplateUse(skillId: string, presetId: string): void {
  const map = loadTemplateUsage(); const k = `${skillId}/${presetId}`
  const n = (map[k] ?? 0) - 1
  if (n <= 0) delete map[k]
  else map[k] = n
  try { localStorage.setItem(TEMPLATE_USAGE_KEY, JSON.stringify(map)) } catch { /* private mode */ }
}
export function recordSkillUse(id: string): number {
  const map = loadSkillUsage()
  const next = (map[id] ?? 0) + 1
  map[id] = next
  localStorage.setItem(USAGE_KEY, JSON.stringify(map))
  return next
}

/** #581 — stable deep link (`?skill=<id>`) matching handoff.ts. */
/** #601 — examples filmstrip index label matching gold `01`…`10`. */
export function filmstripIndexLabel(oneBased: number): string {
  return String(oneBased).padStart(2, '0')
}

export function skillShareUrl(id: string, href = typeof location !== 'undefined' ? location.href : ''): string {
  const url = new URL(href || 'http://localhost/')
  for (const k of ['ask', 'mode', 'ref', 'tool', 'createSkill', 'editSkill', 'preset']) url.searchParams.delete(k)
  url.searchParams.set('skill', id)
  return url.toString()
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
export const QUICK_START_VIDEO_FIRST: ReadonlySet<string> = new Set(['motion-poster-generator'])
/** #580 cut 2 — home quick-start row image: optional `quickStartCover` override; default = video skills' first frame,
 *  else the Skills-module `cover`. Fit is dual (#602): cover full-bleed or contain + letterbox via skillQuickStartCoverFit. */
export function skillQuickStartCover(skill: Skill): { src: string; own: 'bundled' | 'userdata' | 'video' } | null {
  if (skill.quickStartCover) return { src: skill.quickStartCover, own: 'bundled' }
  if (QUICK_START_VIDEO_FIRST.has(skill.id) && skill.video) return { src: skill.video, own: 'video' }
  return skillCover(skill)
}

/** #602 — resolve quick-start cover fit. Defaults to `cover` unless the skill marks `contain` (letterbox plate). */
export function skillQuickStartCoverFit(skill: Skill): 'cover' | 'contain' {
  return skill.quickStartCoverFit === 'contain' ? 'contain' : 'cover'
}

export function skillVideo(skill: Skill): string | null {
  return skill.video || null
}

/** #575 — Explore / home cover hover contract: muted loop on enter/focus; leave/blur → pause + seek 0 (still/first frame under). */
export function skillCoverVideoHover(video: HTMLVideoElement | null | undefined, phase: 'enter' | 'leave'): void {
  if (!video) return
  if (phase === 'enter') {
    void video.play().catch(() => {})
    return
  }
  video.pause()
  try { video.currentTime = 0 } catch { /* seek may throw before metadata */ }
}

/** #575 — preset template video when design pins one; else null (still path via presetImage). */
export function presetVideo(_skill: Skill, preset: SkillPreset): string | null {
  return preset.video || null
}

/** #494/#489/#581 — author line: built-ins show BRAND.name (logo); personal / imported skills say 个人. Card footer appends real usage separately. */
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

/** #494-2 product rule: the selected preset's `prompt` is appended AFTER the skill's instructions.
 *  #978: `activePreset` marks the attachment so the send boundary can also deliver the template prompt
 *  interpolated with this run's values (`selectedPresetPrompt`). */
export function withPreset(skill: Skill, presetId?: string | null): Skill {
  const p = presetId ? skill.presets?.find((x) => x.id === presetId) : undefined
  return p?.prompt ? { ...skill, instructions: `${skill.instructions.trimEnd()}\n\n${p.prompt}`, activePreset: p.id } : skill
}

/** #978 — placeholders a template prompt can carry: `{{input_key}}` of that template's own text fields.
 *  Image fields are references, not variables. Unknown names and empty values are dropped (never `{{x}}`). */
const PRESET_PLACEHOLDER_RE = /\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}/g
/** A placeholder directly preceded by its own label (`Motion: {{motion_brief}}`): when the value is empty the
 *  label goes with it, so an unfilled optional field never leaves a `Motion: Look:` shell in the prompt. */
const PRESET_LABEL_PLACEHOLDER_RE = /([^\s:：]{1,16})[:：][ \t]*\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}/g

/** #978 — read this run's template input values back from the sent text. `skillRunParams` writes every filled
 *  text/select field as `label: value`; that text is the only run state that survives the new-project handoff
 *  (and any edit the user made before sending), so it is the value source. A field whose label is absent stays out. */
export function presetInputValues(preset: SkillPreset, text: string): Record<string, string> {
  const fields = (preset.inputs ?? []).filter((f) => f.type !== 'image')
  const values: Record<string, string> = {}
  if (!fields.length || !text) return values
  let key: string | null = null
  let buf: string[] = []
  const flush = () => {
    if (!key) return
    const value = buf.join('\n').trim()
    if (value) values[key] = value
  }
  for (const line of text.split(/\r?\n/)) {
    const m = /^\s*([^:：]{1,80})[:：]\s*([\s\S]*)$/.exec(line)
    const hit = m ? fields.find((f) => f.label.zh === m[1].trim() || (f.label.en ?? '') === m[1].trim()) : undefined
    if (hit) { flush(); key = hit.key; buf = [m![2]] }
    else if (key) buf.push(line)
  }
  flush()
  return values
}

/** #978 — replace `{{key}}` with this run's value; a missing/blank/unknown variable becomes '' (and a labeled
 *  one takes its label with it), so a template prompt never reaches the agent with `{{x}}`, `undefined`, an empty
 *  slot or a `Motion: Look:` shell. Whitespace/punctuation left behind is collapsed. */
export function interpolatePresetPrompt(prompt: string, values: Record<string, string>): string {
  const fill = (key: string) => (values[key] ?? '').trim()
  return prompt
    .replace(PRESET_LABEL_PLACEHOLDER_RE, (_m, label: string, key: string) => {
      const value = fill(key)
      return value ? `${label}: ${value}` : ''
    })
    .replace(PRESET_PLACEHOLDER_RE, (_m, key: string) => fill(key))
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/[ \t]+([,.;:!?，。；：！？])/g, '$1')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

/** #978 — the selected template's instruction block for this run, ready for the message body.
 *  Null when this attachment carries no template (no preset / unknown preset / skill without presets). */
export function selectedPresetPrompt(skill: Skill, text: string): { id: string; prompt: string } | null {
  const preset = skill.activePreset ? skill.presets?.find((p) => p.id === skill.activePreset) : undefined
  if (!preset?.prompt) return null
  const prompt = interpolatePresetPrompt(preset.prompt, presetInputValues(preset, text))
  return prompt ? { id: preset.id, prompt } : null
}

/** #644 design: 「N 个模板」 = the thumbnails the dialog really shows — the Examples strip plus preset tiles with media
 *  (same sources as SkillRunDialog). Presets without media add no thumbnail and are not counted. */
export function skillThumbCount(skill: Skill): number {
  return (skill.examples?.length ?? 0) + (skill.presets ?? []).filter((p) => !!(p.image || p.video)).length
}

/** #541/#581 — design-spec meta under the description. Real data only: template count from presets[];
 *  usage from local `loadSkillUsage` (never seeded). No presets and no usage → null. */
export function skillMeta(skill: Skill): { templates: number; usage: number } | null {
  // #569 ruling kept: effect skills (no presets) show no 「N 个模板」 line; template skills count real thumbnails (#644)
  const templates = skill.presets?.length ? skillThumbCount(skill) : 0
  const usage = getSkillUsage(skill.id)
  if (!templates && !usage) return null
  return { templates, usage }
}

/** #581 — modal meta copy: 「已使用 N 次 · N 个模板」 when usage>0; else template-count-only (or usage-only). */
export function skillMetaLabel(meta: { templates: number; usage: number }): string {
  if (meta.usage > 0 && meta.templates > 0) return t('skillRun.usageAndTemplates', meta.usage, meta.templates)
  if (meta.usage > 0) return t('skillRun.usageCount', meta.usage)
  return t('skillRun.templateCount', meta.templates)
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
      skill.examples.forEach((image, i) => {
        if (image && !isSkillMediaVideo(image)) q.push({ skill, preset: null, image, key: `${skill.id}:ex${i}` })
      })
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

/** #748 §C — left tiles: explicit skill.media[] wins; else derived from presets (image/video; preset.stack → stack children). */
export function skillMedia(skill: Skill): SkillMediaItem[] {
  const own = (m: SkillMediaItem): SkillMediaItem => (m.presetId ? { ...m, usedCount: getTemplateUsage(skill.id, m.presetId) } : m)
  if (skill.media?.length) return skill.media.map(own)
  return skillMediaRaw(skill).map(own)
}
function skillMediaRaw(skill: Skill): SkillMediaItem[] {
  // TEMP(#748) placeholder until skill/get → media[] script: examples carousel items (no presetId) + preset tiles.
  const ex = (skill.examples ?? []).map((url): SkillMediaItem => ({ type: isSkillMediaVideo(url) ? 'video' : 'image', url }))
  return [...ex, ...(skill.presets ?? []).filter((p) => !!(p.image || p.video)).map((p): SkillMediaItem => {
    const url = presetImage(skill, p) ?? p.image ?? ''
    if (p.stack?.length) return { type: 'stack', url, presetId: p.id, name: p.name, children: p.stack.map((c) => ({ type: 'image', url: c })) }
    return { type: p.video ? 'video' : 'image', url: p.video ? (presetVideo(skill, p) ?? url) : url, ...(p.video ? { cover: url } : {}), presetId: p.id, name: p.name }
  })]
}
/** #748 — 当前模板 row data from the selected media item (click only; hover never changes it). */
export function selectedMedia(skill: Skill, presetId: string | null): SkillMediaItem | null {
  return skillMedia(skill).find((m) => m.presetId && m.presetId === presetId) ?? null
}
