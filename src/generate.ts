import { createShapeId, type Editor, type TLShape, type TLShapeId } from 'tldraw'

import { defaultTarget, refKind, uploadImage, validTarget, viewUrl, type PromptGraph, type RefKind } from './comfy'
import { supportsLora, type LoraPick } from './loras'
import { freeSpot, spawnHolder, startJob, type ErrorSink, type GenInfo } from './jobs'
import { GENERATOR, type GeneratorShape } from './shapes/GeneratorShape'
import { agentModels, AUTO_IMAGE, AUTO_VIDEO, defaultOf, FEATURE_MODELS, featurePicks, hasNegative, isCloudModel, isVideo, modelOf, refCap, type ModelDef } from './models'
import { CUSTOM_GENERATE } from './customWorkflows'
import { modelIn, WS_NODE, wsBuilt } from './wavespeed'
import { t } from './i18n'
import { PALETTE_MODE, applyRefs, refControlsOf, refHints, refLimit, refModesOf, refStrengthsOf, usableRefs } from './refModes'
import { paletteImage, palettePrompt } from './palette'
import { annotated, randomSeed, type Built } from './workflows'
import { MAX_VIDEO_REF_KINDS, VIDEO_AREAS, videoSize, type Scene } from './videoGraphs'
import { durationNote, SHOTS, STYLES, VIDEO_RATIOS, videoResolution } from './genOptions'
import { GIF_STILL_REFUSAL, gifHasStill, gifModelId, gifSpec, type GifSpec } from './gifFile'
import { svgModelId, svgSpec, type SvgSpec } from './svgFile'

export function scenesOf(shape: GeneratorShape): Scene[] {
  return (shape.meta.scenes as Scene[] | undefined) ?? []
}

export function capRefs(srcs: string[]): string[] {
  const count: Record<RefKind, number> = { image: 0, video: 0, audio: 0 }
  return srcs.filter((src) => count[refKind(src)]++ < MAX_VIDEO_REF_KINDS[refKind(src)])
}

export type VideoMode = 'frames' | 'refs' | 'motion' | 'lipsync'
const VIDEO_MODES: VideoMode[] = ['refs', 'motion', 'lipsync']
export const videoModeOf = (shape: GeneratorShape): VideoMode => (VIDEO_MODES.includes(shape.meta.videoMode as VideoMode) ? shape.meta.videoMode as VideoMode : 'frames')
export const motionOf = (shape: GeneratorShape) => (shape.meta.motion as string | undefined) ?? null
export const speechOf = (shape: GeneratorShape) => (shape.meta.speech as string | undefined) ?? null

const SHORT_SIDE: Record<string, number> = { '1K': 1024, '2K': 2048 }

function ratioOf(ratio: string): number {
  const [a, b] = ratio.split(':').map(Number)
  return a / b
}

export function nearestRatio(aspect: number, ratios: string[]): string {
  return ratios.reduce((a, b) => Math.abs(Math.log(ratioOf(b) / aspect)) < Math.abs(Math.log(ratioOf(a) / aspect)) ? b : a)
}

const snap16 =(v: number) => Math.round(v / 16) * 16

export function targetSize({ ratio, resolution, workflow, cw, ch }: GeneratorShape['props']): [number, number] {
  const r = ratioOf(ratio)
  if (isVideo(workflow)) return videoSize(r, VIDEO_AREAS[resolution] ?? VIDEO_AREAS['768p'])
  if (resolution === 'custom') return [snap16(cw), snap16(ch)]
  const short = SHORT_SIDE[resolution] ?? 1024
  return r >= 1 ? [snap16(short * r), short] : [short, snap16(short / r)]
}

/** #707: a skill canvas (1584×396 and other exact pixels) is not snapped to a multiple of 16. */
/** #707: a skill size lock names a catalog model that is not on the reference product dropdown. */
function sizeLockModel(shape: { meta?: { sizeLockModel?: unknown } }): ModelDef | undefined {
  const id = typeof shape.meta?.sizeLockModel === 'string' ? shape.meta.sizeLockModel : ''
  return id ? { id, label: id, desc: '', files: [], cloud: true, lora: null, refs: 'qwen', control: 'wavespeed' } : undefined
}

export function pixelSizeOf(shape: { props: GeneratorShape['props']; meta?: { pixelSize?: unknown } }): [number, number] {
  const raw = shape.meta?.pixelSize
  if (Array.isArray(raw) && raw.length >= 2) {
    const w = Math.round(Number(raw[0]))
    const h = Math.round(Number(raw[1]))
    if (w > 0 && h > 0) return [w, h]
  }
  return targetSize(shape.props)
}

/** #159: a video card never carries the image default '1K': the model's default/first tier (480p when unknown). */
export function videoResOf(p: Pick<GeneratorShape['props'], 'resolution' | 'workflow'>): string {
  const m = modelOf(p.workflow)
  return videoResolution(p.resolution, m?.resolutions, m?.defaults?.resolution)
}

export function createGenerator(editor: Editor, video = false, props: Partial<GeneratorShape['props']> = {}, focus = true, from?: [number, number]): TLShapeId {
  const id = createShapeId()
  const ratio = props.ratio ?? (video ? VIDEO_RATIOS[0] : '1:1')
  const workflow = props.workflow || (video ? AUTO_VIDEO : AUTO_IMAGE)
  if (video) props = { ...props, resolution: videoResOf({ resolution: props.resolution ?? '', workflow }) }
  const [w, h] = targetSize({ ...editor.getShapeUtil<GeneratorShape>(GENERATOR).getDefaultProps(), ...props, ratio, workflow })
  const [x, y] = freeSpot(editor, w, h, from)
  editor.createShape({ id, type: GENERATOR, x, y, props: { ...props, w, h, ratio, workflow } })
  if (focus) {
    editor.setCurrentTool('select')
    editor.select(id)
    // A card bigger than the viewport (e.g. a 16:9 video card at ~85% zoom) would only be panned and stay clipped; fit it instead
    const vp = editor.getViewportPageBounds(), pad = 64 / editor.getZoomLevel()
    if (w + pad * 2 > vp.w || h + pad * 2 > vp.h) editor.zoomToBounds({ x, y, w, h }, { inset: 64, animation: { duration: 200 } })
    else editor.zoomToSelectionIfOffscreen(64, { animation: { duration: 200 } })
  }
  return id
}

export function refsOf(shape: GeneratorShape): string[] {
  return (shape.meta.refs as string[] | undefined) ?? []
}

export const BASE_STRENGTH = 60

export function baseOf(shape: GeneratorShape): { src: string; strength: number } | null {
  const src = shape.meta.base as string | undefined
  return src ? { src, strength: (shape.meta.strength as number | undefined) ?? BASE_STRENGTH } : null
}

export function lastFrameOf(shape: GeneratorShape): string | null {
  return (shape.meta.lastFrame as string | undefined) ?? null
}

export function colorsOf(shape: GeneratorShape): string[] {
  return (shape.meta.colors as string[] | undefined) ?? []
}

/** User picks for the secondary tabs of the model menu (image_edit, image_to_video); empty while Auto is on. */
// Auto on: never reuse an earlier manual pick (#95 product ruling) -- the agent's pick or the feature default
export const featureModelsOf = (shape: GeneratorShape) => featurePicks(shape.props.workflow, shape.meta.featureModels)
/** The image-edit model reference images go to: the user's pick on that tab, else the feature default (#134: backend `default`). */
export const editModelOf = (shape: GeneratorShape) => {
  const list = FEATURE_MODELS.image_edit ?? []
  return list.find((m) => m.id === featureModelsOf(shape).image_edit) ?? defaultOf('image_edit', list)
}
/** Input images beyond what the edit model accepts (#95): null when all fit, else how many are sent. */
export const refOverflow = (shape: GeneratorShape) => refCap(editModelOf(shape), (baseOf(shape) ? 1 : 0) + refsOf(shape).length)
export const negativeOf = (shape: GeneratorShape) => (shape.meta.negative as string | undefined) ?? ''
/** #201: the negative prompt for this model, or undefined when its schema has no negative_prompt. */
export const negativeFor = (shape: GeneratorShape, model: ModelDef | null | undefined) => (hasNegative(model) && negativeOf(shape).trim()) || undefined
export const seedOf = (shape: GeneratorShape) => (shape.meta.seed as number | null | undefined) ?? null
export const runOnOf = (shape: GeneratorShape) => validTarget(shape.meta.runOn) ?? defaultTarget()
export const lorasOf = (shape: GeneratorShape) => (shape.meta.loras as LoraPick[] | undefined) ?? []

/** #202: the model a generator's WS job runs on (its pick, else the feature default), for LoRA support. */
function runModelOf(inputs: Record<string, unknown>) {
  const feature = String(inputs.feature ?? '')
  const list = FEATURE_MODELS[feature] ?? []
  return list.find((m) => m.id === inputs.model) ?? (inputs.model ? modelOf(String(inputs.model)) : defaultOf(feature, list))
}
/** #202: whether the generator's current job would run on a model that takes `loras`. */
export function loraSupported(shape: GeneratorShape) {
  const inputs = estimateBase(shape)
  return !!inputs && supportsLora(runModelOf(inputs))
}
/** #202: names of the curated models (same kind as the card) that take `loras`, for the greyed hint. */
export function loraModelNames(shape: GeneratorShape) {
  const feats = isVideo(shape.props.workflow) ? ['text_to_video', 'image_to_video'] : ['text_to_image', 'image_edit']
  return [...new Set(feats.flatMap((f) => (FEATURE_MODELS[f] ?? []).filter(supportsLora).map((m) => m.label)))]
}
/** #202: the card's LoRAs go with the job (never dropped: a model without `loras` makes the backend say so). */
function applyLoras(graph: PromptGraph, shape: GeneratorShape) {
  const loras = lorasOf(shape)
  if (!loras.length) return
  for (const node of Object.values(graph)) if (node.class_type === WS_NODE) node.inputs.loras = loras
}

function applySeed(graph: PromptGraph, seed: number) {
  for (const node of Object.values(graph)) {
    if (node.class_type === 'RandomNoise') node.inputs.noise_seed = seed
    if (node.class_type === 'KSampler') node.inputs.seed = seed
  }
}

async function generateGraph(shape: GeneratorShape): Promise<Built> {
  const { ratio, workflow, duration, transparent, style } = shape.props
  const suffix = (isVideo(workflow) ? SHOTS : STYLES).find(([k]) => k === style)?.[2]
  const refs = refsOf(shape)
  const model = isVideo(workflow) ? null : sizeLockModel(shape) ?? modelOf(workflow) ?? agentModels(false)[0]
  const colors = isVideo(workflow) ? [] : colorsOf(shape)
  const picked = model ? usableRefs(model, refs, refModesOf(shape)).slice(0, refLimit(model)) : []
  const palette = colors.length && model?.refs && model.id !== CUSTOM_GENERATE && picked.length < refLimit(model)
    ? viewUrl(await uploadImage(await paletteImage(colors), `palette-mosaic-${colors.join('').replace(/#/g, '')}.png`))
    : null
  const used = palette ? [...picked, { src: palette, mode: PALETTE_MODE }] : picked
  const hints = refHints(used)
  const prompt = [
    [shape.props.prompt, suffix, transparent && 'isolated subject on a plain white background'].filter(Boolean).join(', '),
    ...hints,
    colors.length > 0 && palettePrompt(colors),
  ].filter(Boolean).join(' ')
  if (isVideo(workflow) && isCloudModel(workflow)) {
    // #128: the confirm dialog states the actual duration when the agent asked for one the model doesn't take
    const note = durationNote(shape.meta?.durationAsked, duration, modelOf(workflow)?.durations?.map(Number))
    const base = { prompt, ratio, duration, ...(note ? { duration_note: note } : {}), resolution: videoResOf(shape.props), seed: seedOf(shape) ?? undefined, negative_prompt: negativeFor(shape, modelOf(workflow)) }
    const scenes = scenesOf(shape).filter((sc) => sc.prompt.trim())
    if (scenes.length) {
      // storyboard: the backend runs one cloud task per scene with the current model
      const scened = scenes.map((sc) => ({ prompt: [sc.prompt, suffix].filter(Boolean).join(', '), duration: sc.duration }))
      return refs[0]
        ? wsBuilt({ ...base, feature: 'image_to_video', model: modelIn('image_to_video', featureModelsOf(shape).image_to_video ?? workflow), image: annotated(refs[0]), scenes: scened })
        : wsBuilt({ ...base, feature: 'text_to_video', model: modelIn('text_to_video', workflow), scenes: scened })
    }
    const mode = videoModeOf(shape)
    const motion = motionOf(shape)
    const speech = speechOf(shape)
    if (mode === 'refs' && refs.length) {
      const by = (k: RefKind) => refs.filter((r) => refKind(r) === k).map(annotated)
      return wsBuilt({ ...base, feature: 'reference_to_video', reference_images: by('image'), reference_videos: by('video'), reference_audios: by('audio') })
    }
    if (mode === 'motion' && refs[0] && motion) return wsBuilt({ ...base, feature: 'motion_control', custom: 'motion', image: annotated(refs[0]), video: annotated(motion) })
    if (mode === 'lipsync' && refs[0] && speech) return wsBuilt({ ...base, feature: 'lip_sync', custom: 'lipsync', image: annotated(refs[0]), audio: annotated(speech) })
    const last = lastFrameOf(shape)
    if (refs.length || last) {
      return wsBuilt({ ...base, feature: 'image_to_video', custom: 'video', model: modelIn('image_to_video', featureModelsOf(shape).image_to_video ?? workflow), image: annotated(refs[0] ?? last!), last_image: refs[0] && last ? annotated(last) : undefined })
    }
    return wsBuilt({ ...base, feature: 'text_to_video', custom: 'video', model: modelIn('text_to_video', workflow) })
  }
  if (isVideo(workflow)) throw new Error(t('jobs.notInCloud'))
  const [width, height] = pixelSizeOf(shape)
  if (model?.id === CUSTOM_GENERATE) {
    // custom text-to-image: @image/@image2 get the first two refs; @base/@strength get the base image
    const start = baseOf(shape)
    const [image, image2] = picked.map((r) => annotated(r.src))
    return wsBuilt({
      feature: 'text_to_image', custom: 'generate', model: CUSTOM_GENERATE, prompt, width, height,
      image, image2, images: image2 ? [image2] : undefined,
      base: start ? annotated(start.src) : undefined, strength: start ? start.strength / 100 : undefined,
      seed: seedOf(shape) ?? undefined, png: transparent,
    })
  }
  if (model && (model.cloud || isCloudModel(model.id))) {
    const base = baseOf(shape)
    // #868: models without refs/control (Krea 2 Turbo) keep leftover chips greyed and stay on t2i
    const images = [...(base ? [base.src] : []), ...(model.refs || model.control ? refs : [])].map(annotated)
    const { controls, prep } = applyRefs(picked, refStrengthsOf(shape), refControlsOf(shape))
    const seed = seedOf(shape) ?? undefined
    const negative_prompt = negativeFor(shape, model)
    const sizeLock = shape.meta?.sizeLockModel
      ? { size_lock: true as const, ...(shape.meta?.sizeLockMode === 'ratio' ? { size_lock_mode: 'ratio' as const } : {}) }
      : {}
    const gif = gifSpec(shape.meta)
    const svg = svgSpec(shape.meta)
    if (svg) {
      // #826: SVG stays on 2.6 text-to-image, n=1. References and edit are refused.
      if (images.length || shape.props.count !== 1) throw new Error(images.length ? t('wsErr.svgEdit') : t('wsErr.svgCount'))
      return wsBuilt({
        feature: 'text_to_image', model: svgModelId(model.auto ? undefined : model.id), prompt, width, height,
        seed, negative_prompt, params: imageParams(shape, model, null, svg), ...sizeLock,
      })
    }
    if (gif) {
      if (gifHasStill({ image: images[0], images, base: base?.src, refs })) throw new Error(GIF_STILL_REFUSAL)
      return wsBuilt({
        feature: 'text_to_image', model: gifModelId(model.auto ? undefined : model.id), prompt, width, height,
        seed, negative_prompt, params: imageParams(shape, model, gif), ...sizeLock,
      })
    }
    if (controls.length && !base) {
      // structure refs (canny/depth/pose/...): a WaveSpeed control model follows their maps, like upstream ControlNet
      return wsBuilt({ feature: 'structure_control', prompt, width, height, seed, png: transparent, controls: controls.map(({ src, ...knobs }) => ({ ...knobs, image: annotated(src) })), ...sizeLock })
    }
    const prepOf = new Map(picked.map((r, i) => [r.src, prep[i]]))
    const cap = refOverflow(shape) ?? images.length
    const refPrep = [...(base ? [null] : []), ...refs.map((r) => prepOf.get(r) ?? null)].slice(0, cap)
    images.splice(cap)
    // reference images go to the image-edit feature; its default model is used unless the agent picked one
    const askedEdit = featureModelsOf(shape).image_edit
    const editModel = modelIn('image_edit', askedEdit) ?? (askedEdit && askedEdit === model.id ? askedEdit : undefined)
    // Skill-pinned tier (edit_resolution) must be sent on both edit and t2i.
    // Sunburst has no size/width/height; the submitted fields are resolution + aspect_ratio.
    const pinnedRes = typeof shape.meta.editResolution === 'string' ? { resolution: shape.meta.editResolution } : {}
    return images.length
      ? wsBuilt({ feature: 'image_edit', model: editModel, prompt, images, width, height, ...pinnedRes, seed, negative_prompt, png: transparent, prep: refPrep.some(Boolean) ? refPrep : undefined, ...sizeLock })
      : wsBuilt({ feature: 'text_to_image', model: model.auto ? undefined : model.id, prompt, params: imageParams(shape, model, null, svgSpec(shape.meta)), width, height, ...pinnedRes, seed: seedOf(shape) ?? undefined, negative_prompt, png: transparent, ...sizeLock })
  }
  // local diffusion models are gone: cloud image models are handled above
  throw new Error(model ? t('jobs.notInCloud') : 'unknown image model')
}

/** The price-relevant part of a generator's cloud job, without uploading any media (for the cost estimate). */
export function estimateInputsOf(shape: GeneratorShape): Record<string, unknown> | null {
  const inputs = estimateBase(shape)
  const loras = lorasOf(shape)
  // #202: quoted with the LoRAs it is submitted with, so the quote is the charge
  return inputs && loras.length ? { ...inputs, loras } : inputs
}

function estimateBase(shape: GeneratorShape): Record<string, unknown> | null {
  const { ratio, workflow, duration } = shape.props
  const refs = refsOf(shape)
  if (isVideo(workflow)) {
    if (!isCloudModel(workflow)) return null
    const base = { ratio, duration, resolution: videoResOf(shape.props) }
    const scenes = scenesOf(shape).filter((sc) => sc.prompt.trim())
    if (scenes.length) {
      const feature = refs[0] ? 'image_to_video' : 'text_to_video'
      return { ...base, feature, model: modelIn(feature, workflow), image: refs[0] ? 'ref' : undefined, scenes: scenes.map((sc) => ({ prompt: sc.prompt, duration: sc.duration })) }
    }
    const mode = videoModeOf(shape)
    if (mode === 'refs' && refs.length) return { ...base, feature: 'reference_to_video' }
    if (mode === 'motion' && refs[0] && motionOf(shape)) return { ...base, feature: 'motion_control' }
    if (mode === 'lipsync' && refs[0] && speechOf(shape)) return { ...base, feature: 'lip_sync' }
    if (refs.length || lastFrameOf(shape)) return { ...base, feature: 'image_to_video', model: modelIn('image_to_video', featureModelsOf(shape).image_to_video ?? workflow) }
    return { ...base, feature: 'text_to_video', model: modelIn('text_to_video', workflow) }
  }
  const model = sizeLockModel(shape) ?? modelOf(workflow) ?? agentModels(false)[0]
  if (!model || !(model.cloud || isCloudModel(model.id))) return null
  const [width, height] = pixelSizeOf(shape)
  const gif = gifSpec(shape.meta)
  const svg = svgSpec(shape.meta)
  if (svg) {
    if (refs.length || baseOf(shape) || shape.props.count !== 1) return null
    return { feature: 'text_to_image', model: svgModelId(model.auto ? undefined : model.id), width, height, params: imageParams(shape, model, null, svg) }
  }
  if (gif) {
    const base = baseOf(shape)
    if (gifHasStill({ base: base?.src, refs })) return null
    return { feature: 'text_to_image', model: gifModelId(model.auto ? undefined : model.id), width, height, params: imageParams(shape, model, gif) }
  }
  const askedEdit = featureModelsOf(shape).image_edit
  const editModel = modelIn('image_edit', askedEdit) ?? (askedEdit && askedEdit === model.id ? askedEdit : undefined)
  const useRefs = !!(model.refs || model.control)
  const pinnedRes = typeof shape.meta?.editResolution === 'string' ? { resolution: shape.meta.editResolution } : {}
  return (useRefs && refs.length) || baseOf(shape) ? { feature: 'image_edit', model: editModel, width, height, ...pinnedRes } : { feature: 'text_to_image', model: model.auto ? undefined : model.id, width, height, ...pinnedRes, params: imageParams(shape, model, null) }
}

function imageParams(shape: GeneratorShape, model: { qualities?: string[]; complexities?: string[] } | null | undefined, gif: GifSpec | null, svg: SvgSpec | null = null): Record<string, unknown> | undefined {
  const params: Record<string, unknown> = {}
  // #189: quality is sent only when the user picked a tier the schema lists. 'standard' (the card default) is not a tier.
  if (model?.qualities?.includes(shape.props.quality)) params.quality = shape.props.quality
  const complexity = shape.meta.complexity
  if (typeof complexity === 'string' && complexity && (model?.complexities?.includes(complexity) || ['low', 'medium', 'high'].includes(complexity))) params.complexity = complexity
  if (gif) Object.assign(params, gif)
  if (svg) params.output_format = 'svg'
  return Object.keys(params).length ? params : undefined
}

export function generate(editor: Editor, shape: GeneratorShape, onError: ErrorSink) {
  const kind = isVideo(shape.props.workflow) ? 'video' : 'image'
  const name = shape.props.prompt || scenesOf(shape)[0]?.prompt || ''
  const seed = seedOf(shape) ?? randomSeed()
  const built = generateGraph(shape).then((b) => { applySeed(b.graph, seed); applyLoras(b.graph, shape); return b })
  return startJob(editor, shape.id, built, { name: name.slice(0, 32), kind, extra: { seed }, runOn: runOnOf(shape) }, onError)
}

export function genInfoOf(shape: TLShape): GenInfo | null {
  return (shape.meta.gen as GenInfo | undefined) ?? null
}

function settingsOf(info: GenInfo): Partial<GeneratorShape['props']> {
  return {
    prompt: info.prompt ?? '',
    ...(info.ratio ? { ratio: info.ratio } : {}),
    ...(info.resolution ? { resolution: info.resolution } : {}),
    ...(info.duration ? { duration: info.duration } : {}),
    ...(info.workflow ? { workflow: info.workflow } : {}),
    ...info.settings,
  }
}

const inputsOf = (info: GenInfo) => info.inputs ?? (info.refs ? { refs: info.refs } : {})

export function remix(editor: Editor, shape: TLShape) {
  const info = genInfoOf(shape)
  if (!info?.prompt) return
  const id = createGenerator(editor, isVideo(info.workflow ?? ''), settingsOf(info))
  editor.updateShape<GeneratorShape>({ id, type: GENERATOR, meta: inputsOf(info) })
}

export function regenerate(editor: Editor, shape: TLShape, onError: ErrorSink) {
  const info = genInfoOf(shape)
  if (!info?.prompt) return
  const holder = spawnHolder(editor, shape)
  editor.updateShape<GeneratorShape>({ id: holder, type: GENERATOR, props: { ...settingsOf(info), count: 1 }, meta: { temp: true, ...inputsOf(info) } })
  return generate(editor, editor.getShape<GeneratorShape>(holder)!, onError)
}
