import { createShapeId, type Editor, type TLShape, type TLShapeId } from 'tldraw'

import { defaultTarget, refKind, uploadImage, validTarget, viewUrl, type PromptGraph, type RefKind } from './comfy'
import type { LoraPick } from './loras'
import { freeSpot, spawnHolder, startJob, type ErrorSink, type GenInfo } from './jobs'
import { GENERATOR, type GeneratorShape } from './shapes/GeneratorShape'
import { agentModels, isCloudModel, isVideo, modelOf } from './models'
import { modelIn, wsBuilt } from './wavespeed'
import { t } from './i18n'
import { PALETTE_MODE, applyRefs, refControlsOf, refHints, refLimit, refModesOf, refStrengthsOf, usableRefs } from './refModes'
import { paletteImage, palettePrompt } from './palette'
import { annotated, randomSeed, type Built } from './workflows'
import { MAX_VIDEO_REF_KINDS, VIDEO_AREAS, videoSize, type Scene } from './videoGraphs'
import { SHOTS, STYLES, VIDEO_RATIOS } from './genOptions'

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

export function createGenerator(editor: Editor, video = false, props: Partial<GeneratorShape['props']> = {}, focus = true, from?: [number, number]): TLShapeId {
  const id = createShapeId()
  const ratio = props.ratio ?? (video ? VIDEO_RATIOS[0] : '1:1')
  const workflow = props.workflow || agentModels(video)[0].id
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

export const negativeOf = (shape: GeneratorShape) => (shape.meta.negative as string | undefined) ?? ''
export const seedOf = (shape: GeneratorShape) => (shape.meta.seed as number | null | undefined) ?? null
export const runOnOf = (shape: GeneratorShape) => validTarget(shape.meta.runOn) ?? defaultTarget()
export const lorasOf = (shape: GeneratorShape) => (shape.meta.loras as LoraPick[] | undefined) ?? []

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
  const model = isVideo(workflow) ? null : modelOf(workflow) ?? agentModels(false)[0]
  const colors = isVideo(workflow) ? [] : colorsOf(shape)
  const picked = model ? usableRefs(model, refs, refModesOf(shape)).slice(0, refLimit(model)) : []
  const palette = colors.length && model?.refs && picked.length < refLimit(model)
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
    const base = { prompt, ratio, duration, resolution: shape.props.resolution || '768p', seed: seedOf(shape) ?? undefined }
    const scenes = scenesOf(shape).filter((sc) => sc.prompt.trim())
    if (scenes.length) {
      // storyboard: the backend runs one cloud task per scene with the current model
      const scened = scenes.map((sc) => ({ prompt: [sc.prompt, suffix].filter(Boolean).join(', '), duration: sc.duration }))
      return refs[0]
        ? wsBuilt({ ...base, feature: 'image_to_video', model: modelIn('image_to_video', workflow), image: annotated(refs[0]), scenes: scened })
        : wsBuilt({ ...base, feature: 'text_to_video', model: modelIn('text_to_video', workflow), scenes: scened })
    }
    const mode = videoModeOf(shape)
    const motion = motionOf(shape)
    const speech = speechOf(shape)
    if (mode === 'refs' && refs.length) {
      const by = (k: RefKind) => refs.filter((r) => refKind(r) === k).map(annotated)
      return wsBuilt({ ...base, feature: 'reference_to_video', reference_images: by('image'), reference_videos: by('video'), reference_audios: by('audio') })
    }
    if (mode === 'motion' && refs[0] && motion) return wsBuilt({ ...base, feature: 'motion_control', image: annotated(refs[0]), video: annotated(motion) })
    if (mode === 'lipsync' && refs[0] && speech) return wsBuilt({ ...base, feature: 'lip_sync', image: annotated(refs[0]), audio: annotated(speech) })
    const last = lastFrameOf(shape)
    if (refs.length || last) {
      return wsBuilt({ ...base, feature: 'image_to_video', model: modelIn('image_to_video', workflow), image: annotated(refs[0] ?? last!), last_image: refs[0] && last ? annotated(last) : undefined })
    }
    return wsBuilt({ ...base, feature: 'text_to_video', model: modelIn('text_to_video', workflow) })
  }
  if (isVideo(workflow)) throw new Error(t('jobs.notInCloud'))
  const [width, height] = targetSize(shape.props)
  if (model && isCloudModel(model.id)) {
    const base = baseOf(shape)
    const images = [...(base ? [base.src] : []), ...refs].map(annotated)
    const { controls, prep } = applyRefs(picked, refStrengthsOf(shape), refControlsOf(shape))
    const seed = seedOf(shape) ?? undefined
    if (controls.length && !base) {
      // structure refs (canny/depth/pose/...): a WaveSpeed control model follows their maps, like upstream ControlNet
      return wsBuilt({ feature: 'structure_control', prompt, width, height, seed, png: transparent, controls: controls.map(({ src, ...knobs }) => ({ ...knobs, image: annotated(src) })) })
    }
    const prepOf = new Map(picked.map((r, i) => [r.src, prep[i]]))
    const refPrep = [...(base ? [null] : []), ...refs.map((r) => prepOf.get(r) ?? null)]
    // reference images go to the image-edit feature; its default model is used unless the agent picked one
    return images.length
      ? wsBuilt({ feature: 'image_edit', prompt, images, width, height, seed, png: transparent, prep: refPrep.some(Boolean) ? refPrep : undefined })
      : wsBuilt({ feature: 'text_to_image', model: model.id, prompt, width, height, seed: seedOf(shape) ?? undefined, png: transparent })
  }
  // local diffusion models are gone: cloud image models are handled above
  throw new Error(model ? t('jobs.notInCloud') : 'unknown image model')
}

/** The price-relevant part of a generator's cloud job, without uploading any media (for the cost estimate). */
export function estimateInputsOf(shape: GeneratorShape): Record<string, unknown> | null {
  const { ratio, workflow, duration } = shape.props
  const refs = refsOf(shape)
  if (isVideo(workflow)) {
    if (!isCloudModel(workflow)) return null
    const base = { ratio, duration, resolution: shape.props.resolution || '768p' }
    const scenes = scenesOf(shape).filter((sc) => sc.prompt.trim())
    if (scenes.length) {
      const feature = refs[0] ? 'image_to_video' : 'text_to_video'
      return { ...base, feature, model: modelIn(feature, workflow), image: refs[0] ? 'ref' : undefined, scenes: scenes.map((sc) => ({ prompt: sc.prompt, duration: sc.duration })) }
    }
    const mode = videoModeOf(shape)
    if (mode === 'refs' && refs.length) return { ...base, feature: 'reference_to_video' }
    if (mode === 'motion' && refs[0] && motionOf(shape)) return { ...base, feature: 'motion_control' }
    if (mode === 'lipsync' && refs[0] && speechOf(shape)) return { ...base, feature: 'lip_sync' }
    if (refs.length || lastFrameOf(shape)) return { ...base, feature: 'image_to_video', model: modelIn('image_to_video', workflow) }
    return { ...base, feature: 'text_to_video', model: modelIn('text_to_video', workflow) }
  }
  const model = modelOf(workflow) ?? agentModels(false)[0]
  if (!model || !isCloudModel(model.id)) return null
  const [width, height] = targetSize(shape.props)
  return refs.length || baseOf(shape) ? { feature: 'image_edit', width, height } : { feature: 'text_to_image', model: model.id, width, height }
}

export function generate(editor: Editor, shape: GeneratorShape, onError: ErrorSink) {
  const kind = isVideo(shape.props.workflow) ? 'video' : 'image'
  const name = shape.props.prompt || scenesOf(shape)[0]?.prompt || ''
  const seed = seedOf(shape) ?? randomSeed()
  const built = generateGraph(shape).then((b) => { applySeed(b.graph, seed); return b })
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
