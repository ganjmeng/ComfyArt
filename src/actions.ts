import type { Box, Editor, TLImageShape, TLVideoShape } from 'tldraw'

import { loadImage } from './adjust'
import { queuePrompt, uploadImage, viewUrl, waitForImages } from './comfy'
import type { CommentShape } from './shapes/CommentShape'
import { resultsAtom, spawnHolder, startJob, type ErrorSink, type MediaKind } from './jobs'
import { notify } from './notices'
import { anglePrompt, annotated, layersGraph, samGraph, type Built, type Crop } from './workflows'
import { workflowConfigAtom } from './customWorkflows'
import { nearestRatio } from './generate'
import { VIDEO_RATIOS } from './genOptions'
import { t } from './i18n'
import { canvasBlob } from './canvasBlob'
import { wsBuilt } from './wavespeed'

export interface Pads { l: number; t: number; r: number; b: number }
export interface Stroke { points: [number, number][]; r: number }

type MediaShape = TLImageShape | TLVideoShape
interface Source { image: string; name: string; w: number; h: number }

function source(editor: Editor, shape: MediaShape): Source | null {
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== shape.type || !asset.props.src) return null
  return { image: annotated(asset.props.src), name: asset.props.name || (shape.type === 'video' ? t('common.video') : t('common.image')), w: asset.props.w, h: asset.props.h }
}

function run(
  editor: Editor,
  shape: MediaShape,
  label: string,
  onError: ErrorSink,
  build: (src: Source) => Promise<Built>,
  opts: { size?: [number, number]; kind?: MediaKind; placer?: string; extra?: (src: Source) => Record<string, unknown> } = {},
) {
  const src = source(editor, shape)
  if (!src) return
  const holder = spawnHolder(editor, shape, opts.size)
  void startJob(editor, holder, build(src), {
    name: `${src.name} · ${label}`,
    kind: opts.kind,
    placer: opts.placer,
    extra: opts.extra?.(src),
  }, onError)
  return holder
}

const cloud = (b: Built) => Promise.resolve(b)
const keep = 'Keep everything else in the image unchanged.'

export const upscale = (e: Editor, s: TLImageShape, factor: number, err: ErrorSink) =>
  run(e, s, t('common.upscale'), err, (src) => cloud(wsBuilt({ feature: 'upscale_image', custom: 'upscale', image: src.image, params: { target_resolution: factor === 4 ? '4k' : '2k', target_megapixels: Math.round(src.w * src.h * factor * factor / 1e6) || 4 } })))

export const creativeUpscale = (e: Editor, s: TLImageShape, factor: number, style: string, strength: number, err: ErrorSink) =>
  run(e, s, t('common.upscale'), err, (src) => cloud(wsBuilt({ feature: 'upscale_image', model: 'recraft-ai/recraft-creative-upscale', image: src.image, prompt: style, params: { creativity: strength, target_resolution: factor === 4 ? '4k' : '2k' } })))

export const cutout = (e: Editor, s: TLImageShape, err: ErrorSink) =>
  run(e, s, t('common.removeBackground'), err, (src) => cloud(wsBuilt({ feature: 'remove_background', custom: 'cutout', image: src.image, png: true })))

export const quickEdit = (e: Editor, s: TLImageShape, prompt: string, err: ErrorSink) =>
  run(e, s, t('common.quickEdit'), err, (src) => cloud(wsBuilt({ feature: 'image_edit', custom: 'edit', image: src.image, prompt, width: src.w, height: src.h })))

export const editText = (e: Editor, s: TLImageShape, edits: [string, string][], err: ErrorSink) =>
  run(e, s, t('common.editText'), err, (src) => cloud(wsBuilt({ feature: 'image_edit', custom: 'edit', image: src.image, width: src.w, height: src.h, prompt:
    `${edits.map(([from, to]) => (to ? `Change the text "${from}" to "${to}" in the same font, color, size and position` : `Remove the text "${from}" and fill its area with the surrounding background`)).join('. ')}. Keep everything else in the image unchanged.` })))

export const angles = (e: Editor, s: TLImageShape, h: number, v: number, z: number, err: ErrorSink) =>
  run(e, s, t('common.multiAngle'), err, (src) => cloud(wsBuilt({ feature: 'change_angle', custom: 'angles', image: src.image, prompt: workflowConfigAtom.get().angles ? anglePrompt(h, v, z) : undefined, params: { horizontal_angle: Math.round(h), vertical_angle: Math.round(v), distance: z > 1.25 ? 0 : z < 0.8 ? 2 : 1 } })))

export const expand = (e: Editor, s: TLImageShape, pads: Pads, prompt: string, err: ErrorSink) => {
  const src = source(e, s)
  if (!src) return
  const k = s.props.w / src.w
  return run(e, s, t('common.expand'), err, () => cloud(wsBuilt({ feature: 'expand_image', custom: 'expand', image: src.image, prompt, width: src.w + pads.l + pads.r, height: src.h + pads.t + pads.b })),
    { size: [(src.w + pads.l + pads.r) * k, (src.h + pads.t + pads.b) * k] })
}

export const animate = (e: Editor, s: TLImageShape, prompt: string, err: ErrorSink, loop = true) =>
  run(e, s, t('common.animateImage'), err, (src) => cloud(wsBuilt({ feature: 'image_to_video', custom: 'animate', image: src.image, last_image: loop ? src.image : undefined, prompt: prompt || 'Subtle seamless motion. Keep the composition, text and layout unchanged.', duration: 3, ratio: nearestRatio(src.w / src.h, VIDEO_RATIOS) })))

export const upscaleVideo = (e: Editor, s: TLVideoShape, long: number, err: ErrorSink) =>
  run(e, s, t('actions.upscaleVideo'), err, (src) => cloud(wsBuilt({ feature: 'upscale_video', video: src.image, params: { target_resolution: long >= 3840 ? '4k' : long >= 2560 ? '2k' : '1080p' } })), { kind: 'video' })

export const cutoutVideo = (e: Editor, s: TLVideoShape, err: ErrorSink) =>
  run(e, s, t('common.removeBackground'), err, async (src) => wsBuilt({ feature: 'remove_video_background', video: src.image }), { kind: 'video' })

export const extendVideo =(e: Editor, s: TLVideoShape, prompt: string, duration: number, err: ErrorSink) =>
  run(e, s, t('common.extendVideo'), err, (src) => cloud(wsBuilt({ feature: 'extend_video', video: src.image, prompt: prompt || 'Continue the shot naturally.', duration })), { kind: 'video' })

export const styleTransfer = (e: Editor, s: TLImageShape, style: string, ref: string | null, err: ErrorSink) =>
  run(e, s, t('common.styleTransfer'), err, (src) => cloud(wsBuilt({ feature: 'image_edit', custom: 'style', image: src.image, images: ref ? [annotated(ref)] : undefined, width: src.w, height: src.h,
    prompt: `Redraw this image in ${style || 'the style of the second image'}${ref && style ? ', matching the style of the second image' : ''}. Keep the composition and subject.` })))

export const splitLayers = (e: Editor, s: TLImageShape, layers: number, prompt: string, err: ErrorSink) =>
  run(e, s, t('common.splitLayers'), err, (src) => layersGraph(src.image, layers, prompt),
    { placer: 'layers', extra: (src) => ({ source: src.image, base: src.name }) })

export function drawStrokes(ctx: CanvasRenderingContext2D, strokes: Stroke[], w: number, h: number) {
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  for (const s of strokes) {
    ctx.lineWidth = s.r * 2 * w
    ctx.beginPath()
    s.points.forEach(([u, v], i) => (i ? ctx.lineTo(u * w, v * h) : ctx.moveTo(u * w, v * h)))
    if (s.points.length === 1) ctx.lineTo(s.points[0][0] * w + 0.01, s.points[0][1] * h)
    ctx.stroke()
  }
}

export async function maskFile(w: number, h: number, paint: (ctx: CanvasRenderingContext2D) => void): Promise<string> {
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const ctx = c.getContext('2d')!
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, w, h)
  ctx.globalCompositeOperation = 'destination-out'
  paint(ctx)
  const ref = await uploadImage(await canvasBlob(c), `mask-${Date.now()}.png`)
  return `${ref.subfolder ? `${ref.subfolder}/` : ''}${ref.filename} [${ref.type}]`
}

const eraseWith = (e: Editor, s: TLImageShape, err: ErrorSink, paint: (ctx: CanvasRenderingContext2D, src: Source) => void) =>
  run(e, s, t('common.eraser'), err, async (src) => wsBuilt({ feature: 'erase_region', custom: 'erase', image: src.image, mask: await maskFile(src.w, src.h, (ctx) => paint(ctx, src)) }))

export const erase = (e: Editor, s: TLImageShape, strokes: Stroke[], err: ErrorSink) =>
  eraseWith(e, s, err, (ctx, src) => drawStrokes(ctx, strokes, src.w, src.h))

export const eraseRegion = (e: Editor, s: TLImageShape, r: Crop, err: ErrorSink) =>
  eraseWith(e, s, err, (ctx) => ctx.fillRect(r.x, r.y, r.w, r.h))

const TOUCH_PAD = 0.25
const TOUCH_MIN = 384
const TOUCH_POINT = 0.3

export function cropAround(region: Crop, w: number, h: number): Crop {
  const grow = (len: number, full: number) => Math.min(full, Math.max(len * (1 + TOUCH_PAD * 2), TOUCH_MIN))
  const cw = Math.min(w, Math.round(grow(region.w, w) / 8) * 8)
  const ch = Math.min(h, Math.round(grow(region.h, h) / 8) * 8)
  const clamp = (v: number, size: number, full: number) => Math.round(Math.min(Math.max(v, 0), full - size))
  return { x: clamp(region.x + region.w / 2 - cw / 2, cw, w), y: clamp(region.y + region.h / 2 - ch / 2, ch, h), w: cw, h: ch }
}

export function inpaint(e: Editor, shape: TLImageShape, mask: HTMLCanvasElement, feather: number, prompt: string, err: ErrorSink) {
  const src = source(e, shape)
  if (!src) return
  const bounds = maskBounds(mask)
  if (!bounds) return
  const k = src.w / mask.width
  void feather // the cloud edit model blends the region itself
  const holder = spawnHolder(e, shape)
  void startJob(e, holder, (async () => {
    return regionEdit(src, { x: bounds.x * k, y: bounds.y * k, w: bounds.w * k, h: bounds.h * k }, prompt)
  })(), { name: t('actions.inpaint', src.name) }, err)
  return holder
}

function regionEdit(src: Source, r: Crop, prompt: string): Promise<Built> {
  const box = `x ${Math.round(r.x)}-${Math.round(r.x + r.w)}, y ${Math.round(r.y)}-${Math.round(r.y + r.h)} (image is ${src.w}x${src.h} px)`
  return cloud(wsBuilt({ feature: 'image_edit', custom: 'inpaint', image: src.image, width: src.w, height: src.h, prompt: `Only inside the area ${box}: ${prompt}. ${keep}` }))
}

function moveEdit(src: Source, what: string, dx: number, dy: number): Promise<Built> {
  const dir = `${Math.round(Math.abs(dx))} px ${dx < 0 ? 'left' : 'right'} and ${Math.round(Math.abs(dy))} px ${dy < 0 ? 'up' : 'down'}`
  return cloud(wsBuilt({ feature: 'image_edit', image: src.image, width: src.w, height: src.h, prompt: `Move ${what} ${dir} (image is ${src.w}x${src.h} px), fill the old spot with matching background. ${keep}` }))
}

export function editRegion(e: Editor, shape: TLImageShape, region: Crop, prompt: string, err: ErrorSink) {
  const src = source(e, shape)
  if (!src) return
  const holder = spawnHolder(e, shape)
  void startJob(e, holder, (async () => {
    return regionEdit(src, region, prompt)
  })(), { name: t('actions.localEdit', src.name) }, err)
  return holder
}

export function moveObject(e: Editor, shape: TLImageShape, mask: HTMLCanvasElement, dx: number, dy: number, err: ErrorSink) {
  const src = source(e, shape)
  const bounds = maskBounds(mask)
  if (!src || !bounds) return
  const k = src.w / mask.width
  const from = { x: Math.round(bounds.x * k), y: Math.round(bounds.y * k), w: Math.round(bounds.w * k), h: Math.round(bounds.h * k) }
  const to = { x: Math.round(from.x + dx * k), y: Math.round(from.y + dy * k) }
  const holder = spawnHolder(e, shape)
  void startJob(e, holder, (async () => {
    return moveEdit(src, `the object at x ${from.x}-${from.x + from.w}, y ${from.y}-${from.y + from.h}`, to.x - from.x, to.y - from.y)
  })(), { name: t('actions.moveObject', src.name) }, err)
  return holder
}

export function moveTarget(e: Editor, shape: TLImageShape, target: { text: string } | { x: number; y: number }, dx: number, dy: number, err: ErrorSink) {
  const src = source(e, shape)
  if (!src) return
  const holder = spawnHolder(e, shape)
  void startJob(e, holder, (async () => {
    return moveEdit(src, 'text' in target ? `the ${target.text}` : `the object at pixel (${Math.round(target.x)}, ${Math.round(target.y)})`, dx, dy)
  })(), { name: t('actions.moveObject', src.name) }, err)
  return holder
}

export function maskBounds(mask: HTMLCanvasElement): Crop | null {
  const { data, width, height } = mask.getContext('2d')!.getImageData(0, 0, mask.width, mask.height)
  let [l, t, r, b] = [width, height, -1, -1]
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (data[(y * width + x) * 4 + 3] < 16) continue
      if (x < l) l = x
      if (x > r) r = x
      if (y < t) t = y
      if (y > b) b = y
    }
  }
  return r < 0 ? null : { x: l, y: t, w: r - l + 1, h: b - t + 1 }
}

export function lumaToAlpha(img: CanvasImageSource, w: number, h: number): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const ctx = c.getContext('2d', { willReadFrequently: true })!
  ctx.drawImage(img, 0, 0, w, h)
  const px = ctx.getImageData(0, 0, w, h)
  for (let i = 0; i < px.data.length; i += 4) {
    px.data[i + 3] = px.data[i]
    px.data[i] = px.data[i + 1] = px.data[i + 2] = 255
  }
  ctx.putImageData(px, 0, 0)
  return c
}

export interface Mark { image: string; src: string; box: Crop }
export type MarkState = Mark | 'loading' | 'none'

export const markOf = (comment: CommentShape) => comment.meta.mark as MarkState | undefined
export const extraPointsOf = (comment: CommentShape) => (comment.meta.points as [number, number][] | undefined) ?? []

export async function markObject(e: Editor, comment: CommentShape) {
  const box = e.getShapePageBounds(comment)!
  const shape = imageUnder(e, box)
  const src = shape && source(e, shape)
  if (!shape || !src) return
  const set = (mark: MarkState) => e.getShape(comment.id) && e.updateShape<CommentShape>({ id: comment.id, type: comment.type, meta: { ...e.getShape(comment.id)!.meta, mark: mark as any } })
  set('loading')
  try {
    const b = e.getShapePageBounds(shape)!
    const k = src.w / b.w
    const pts: [number, number][] = [[box.center.x, box.center.y], ...extraPointsOf(e.getShape<CommentShape>(comment.id) ?? comment)]
    const { graph, result } = samGraph(src.image, { points: pts.map(([x, y]) => ({ x: (x - b.x) * k, y: (y - b.y) * k })) })
    const [ref] = await waitForImages(await queuePrompt(graph), result)
    const url = viewUrl(await uploadImage(await (await fetch(viewUrl(ref))).blob(), `mark-${Date.now()}.png`))
    const found = maskBounds(lumaToAlpha(await loadImage(url), src.w, src.h))
    set(found ? { image: shape.id, src: url, box: found } : 'none')
  } catch {
    set('none')
  }
}

export function imageUnder(editor: Editor, box: Box): TLImageShape | null {
  const hits = editor.getCurrentPageShapesSorted().filter((s): s is TLImageShape => {
    if (s.type !== 'image') return false
    return editor.getShapePageBounds(s)?.containsPoint(box.center) ?? false
  })
  return hits.at(-1) ?? null
}

export function commentTarget(e: Editor, comment: CommentShape) {
  const box = e.getShapePageBounds(comment)!
  const shape = imageUnder(e, box)
  const src = shape && source(e, shape)
  if (!shape || !src) return null
  const b = e.getShapePageBounds(shape)!
  const k = src.w / b.w
  const mark = markOf(comment)
  const marked = comment.props.kind === 'point' && !!mark && typeof mark === 'object' ? mark : null
  const side = Math.min(src.w, src.h) * TOUCH_POINT
  const region: Crop = marked ? marked.box : comment.props.kind === 'point'
    ? { x: (box.center.x - b.x) * k - side / 2, y: (box.center.y - b.y) * k - side / 2, w: side, h: side }
    : { x: (box.x - b.x) * k, y: (box.y - b.y) * k, w: box.w * k, h: box.h * k }
  return { shape, src, marked, region }
}

export function touchEdit(e: Editor, comment: CommentShape, err: ErrorSink) {
  const target = commentTarget(e, comment)
  if (!target) return
  const { shape, src, region } = target
  const holder = spawnHolder(e, shape)
  void startJob(e, holder, (async () => {
    return regionEdit(src, region, comment.props.text)
  })(), { name: t('actions.localEdit', src.name) }, err).then(() => {
    const r = resultsAtom.get()[holder]
    if (r) void notify({ kind: 'comment', title: r.error ? t('actions.commentEditFailed') : t('actions.commentEditDone'), body: comment.props.text.trim() || undefined, srcs: r.srcs })
  })
  return holder
}
