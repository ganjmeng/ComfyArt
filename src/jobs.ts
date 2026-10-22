import { AssetRecordType, atom, createShapeId, type Editor, type JsonValue, type TLAssetId, type TLImageAsset, type TLShape, type TLShapeId, type TLVideoAsset } from 'tldraw'

import { cancelPrompt, mediaMeta, promptHistory, queuePrompt, refKind, viewUrl, waitForImages, type ImageRef } from './comfy'
import { GENERATOR, type GeneratorShape } from './shapes/GeneratorShape'
import type { Built } from './workflows'
import { t } from './i18n'
import { takePendingModel, withModel } from './wavespeed'

export type MediaKind = 'image' | 'video' | 'audio' | 'model'

export interface Job {
  id: string
  node: string
  name: string
  kind: MediaKind
  placer?: string
  extra?: Record<string, unknown>
  partial?: string[]
}

export interface Media { ref: ImageRef; src: string; w: number; h: number; kind: MediaKind }
export type ErrorSink = (msg: string) => void
const rawText = (e: unknown) => (e instanceof Error ? e.message : String(e))
// WaveSpeed backend errors arrive in English; show them in the UI language.
export function localizeError(msg: string): string {
  if (/\(401\)|rejected the API key/.test(msg)) return t('jobs.wsKeyInvalid')
  const timeout = /WaveSpeed task timed out after (\d+)s/.exec(msg)
  if (timeout) return t('jobs.wsTimeout', timeout[1])
  const failed = /^WaveSpeed task (?:failed: (.*)|finished without output)$/s.exec(msg)
  if (failed) return t('jobs.wsFailed', failed[1] ?? t('jobs.noOutput'))
  return msg
}
export const errorText = (e: unknown) => localizeError(rawText(e))
export type Placer = (editor: Editor, holder: TLShape, media: Media[], job: Job, onError: ErrorSink) => Promise<void>

export const GAP = 40
const active = new Set<string>()
const settled = new Set<string>()
const placers: Record<string, Placer> = {}

export interface JobResult { srcs: string[]; error?: string }
export const resultsAtom = atom<Record<string, JobResult>>('job results', {})

function report(holderId: TLShapeId, result: JobResult) {
  resultsAtom.update((r) => ({ ...r, [holderId]: result }))
}

export function registerPlacer(name: string, placer: Placer) {
  placers[name] = placer
}

export type MediaAsset = (TLImageAsset | TLVideoAsset) & { props: { src: string } }

export function mediaAsset(editor: Editor, shape: TLShape | undefined): MediaAsset | null {
  const assetId = (shape?.props as { assetId?: TLAssetId | null } | undefined)?.assetId
  const asset = assetId ? editor.getAsset(assetId) : undefined
  return (asset?.type === 'image' || asset?.type === 'video') && asset.props.src ? asset as MediaAsset : null
}

export function fileSrc(editor: Editor, shape: TLShape | undefined): string | null {
  const src = mediaAsset(editor, shape)?.props.src ?? (shape?.props as { src?: unknown } | undefined)?.src
  return typeof src === 'string' && src ? src : null
}

export function jobOf(shape: TLShape): Job | null {
  return (shape.meta?.job as Job | undefined) ?? null
}

export async function toMedia(ref: ImageRef, kind: MediaKind): Promise<Media> {
  const src = viewUrl(ref)
  if (kind === 'image' && refKind(src) === 'video') kind = 'video' // cloud animations are MP4, not animated WebP
  if (kind === 'audio' || kind === 'model') return { ref, src, w: 0, h: 0, kind }
  const { w, h } = ref.metadata?.width && ref.metadata?.height && kind === 'image'
    ? { w: ref.metadata.width, h: ref.metadata.height }
    : await mediaMeta(src, kind)
  return { ref, src, w, h, kind }
}

export function placeMedia(editor: Editor, m: Media, name: string, x: number, y: number, w: number, parentId?: TLShape['parentId']): TLShapeId {
  const assetId = AssetRecordType.createId()
  editor.createAssets([{
    id: assetId,
    typeName: 'asset',
    type: m.kind,
    props: { name, src: m.src, w: m.w, h: m.h, mimeType: m.kind === 'video' ? 'video/mp4' : m.ref.filename.endsWith('.svg') ? 'image/svg+xml' : m.ref.filename.endsWith('.webp') ? 'image/webp' : 'image/png', isAnimated: m.kind === 'video' || m.ref.filename.endsWith('.webp') },
    meta: {},
  } as any])
  const id = createShapeId()
  editor.createShape({ id, type: m.kind, x, y, ...(parentId ? { parentId } : {}), props: { assetId, w, h: w * m.h / m.w } } as any)
  return id
}

export interface GenInfo {
  tool: string
  prompt?: string
  ratio?: string
  resolution?: string
  duration?: number
  workflow?: string
  refs?: string[]
  seed?: number
  settings?: Pick<GeneratorShape['props'], 'count' | 'quality' | 'style' | 'transparent' | 'cw' | 'ch'>
  inputs?: Record<string, JsonValue>
}

const GEN_INPUTS = ['refs', 'base', 'strength', 'colors', 'refModes', 'refStrengths', 'refControls', 'lastFrame', 'scenes', 'videoMode', 'motion', 'speech', 'negative', 'seed', 'loras', 'runOn']

function infoOf(holder: TLShape, job: Job): GenInfo {
  if (holder.type !== GENERATOR) return { tool: job.name }
  const p = (holder as GeneratorShape).props
  const scenes = holder.meta.scenes as { prompt: string }[] | null | undefined
  const prompt = p.prompt || scenes?.map((s) => s.prompt).join(' / ')
  if (!prompt) return { tool: job.name }
  const refs = holder.meta.refs as string[] | undefined
  const inputs = Object.fromEntries(GEN_INPUTS.filter((k) => holder.meta[k] != null).map((k) => [k, holder.meta[k]!]))
  return {
    tool: t('common.generate'), prompt, ratio: p.ratio, resolution: p.resolution, duration: p.duration, workflow: p.workflow,
    ...(typeof job.extra?.seed === 'number' ? { seed: job.extra.seed } : {}),
    ...(refs?.length ? { refs } : {}),
    settings: { count: p.count, quality: p.quality, style: p.style, transparent: p.transparent, cw: p.cw, ch: p.ch },
    inputs,
  }
}

const defaultPlacer: Placer = async (editor, holder, media, job) => {
  const w = (holder.props as { w: number }).w
  const gen = infoOf(holder, job)
  let x = holder.x
  const ids: TLShapeId[] = []
  editor.run(() => {
    editor.deleteShape(holder.id)
    for (const m of media) {
      const id = placeMedia(editor, m, job.name, x, holder.y, w, holder.parentId)
      editor.updateShape({ id, type: editor.getShape(id)!.type, meta: { gen: gen as any } })
      ids.push(id)
      x += w + GAP
    }
  }, { history: 'ignore' })
  selectResults(editor, holder, ids)
}

export function selectResults(editor: Editor, holder: TLShape, ids: TLShapeId[]) {
  if (!holder.meta.quiet) editor.select(...ids)
}

async function keepPartial(editor: Editor, holder: TLShape, job: Job): Promise<number> {
  if (!job.partial) return 0
  const outputs = (await promptHistory(job.id))?.outputs ?? {}
  const refs: ImageRef[] = job.partial.flatMap((node) => outputs[node]?.images ?? [])
  const media = await Promise.all(refs.map((r) => toMedia(r, 'video')))
  const w = (holder.props as { w: number }).w
  const b = editor.getShapePageBounds(holder)!
  let from: [number, number] = [b.maxX + GAP, b.minY]
  editor.run(() => {
    for (const m of media) {
      const [x, y] = freeSpot(editor, w, w * m.h / m.w, from)
      const p = editor.getPointInParentSpace(holder, { x, y })
      placeMedia(editor, m, job.name, p.x, p.y, w, holder.parentId)
      from = [x + w + GAP, y]
    }
  }, { history: 'ignore' })
  return media.length
}

async function finish(editor: Editor, holderId: TLShapeId, job: Job, onError: ErrorSink) {
  if (active.has(job.id)) return
  active.add(job.id)
  try {
    const refs = await waitForImages(job.id, job.node)
    settled.add(job.id)
    const media = await Promise.all(refs.map((r) => toMedia(r, refKind(viewUrl(r)) === 'video' ? 'video' : job.kind)))
    const holder = editor.getShape(holderId)
    if (!holder) return
    await (placers[job.placer ?? ''] ?? defaultPlacer)(editor, holder, media, job, onError)
    report(holderId, { srcs: media.map((m) => m.src) })
  } catch (e) {
    const holder = editor.getShape(holderId)
    const kept = holder ? await keepPartial(editor, holder, job).catch(() => 0) : 0
    if (holder?.meta.temp) editor.deleteShape(holderId)
    else if (holder) editor.updateShape({ id: holderId, type: holder.type, meta: { ...holder.meta, job: null, quiet: false } })
    const msg = errorText(e) + (kept ? ` ${t('jobs.partialKept', kept)}` : '')
    report(holderId, { srcs: [], error: msg })
    if (holder) onError(msg)
  } finally {
    active.delete(job.id)
    settled.delete(job.id)
  }
}

export async function startJob(
  editor: Editor,
  holderId: TLShapeId,
  build: Promise<Built>,
  opts: { name: string; kind?: MediaKind; placer?: string; extra?: Record<string, unknown>; runOn?: string },
  onError: ErrorSink,
) {
  const model = takePendingModel()
  try {
    const { graph, result, partial } = await build
    withModel(graph, model)
    const job: Job = {
      id: await queuePrompt(graph, opts.runOn),
      node: result,
      ...(partial ? { partial } : {}),
      name: opts.name,
      kind: opts.kind ?? 'image',
      ...(opts.placer ? { placer: opts.placer } : {}),
      ...(opts.extra ? { extra: opts.extra } : {}),
    }
    const holder = editor.getShape(holderId)
    if (!holder) return
    editor.updateShape({ id: holderId, type: holder.type, meta: { ...holder.meta, job: job as any } })
    await finish(editor, holderId, job, onError)
  } catch (e) {
    const holder = editor.getShape(holderId)
    if (holder?.meta.temp) editor.deleteShape(holderId)
    const msg = errorText(e)
    report(holderId, { srcs: [], error: msg })
    onError(msg)
  }
}

export function freeSpot(editor: Editor, w: number, h: number, from?: [number, number]): [number, number] {
  const center = editor.getViewportPageBounds().center
  const boxes = editor.getCurrentPageShapes().map((s) => editor.getShapePageBounds(s)!).filter(Boolean)
  let [x, y] = from ?? [center.x - w / 2, center.y - h / 2]
  for (let i = 0; i < 200; i++) {
    const hit = boxes.find((b) => x < b.maxX + GAP && x + w + GAP > b.minX && y < b.maxY + GAP && y + h + GAP > b.minY)
    if (!hit) break
    x = hit.maxX + GAP
  }
  return [x, y]
}

export function spawnHolder(editor: Editor, beside: TLShape, size?: [number, number]): TLShapeId {
  const b = editor.getShapePageBounds(beside)!
  const [w, h] = size ?? [b.w, b.h]
  const [x, y] = freeSpot(editor, w, h, [b.maxX + GAP, b.minY])
  const id = createShapeId()
  editor.createShape({ id, type: GENERATOR, x, y, props: { w, h }, meta: { temp: true } })
  return id
}

export function resumeJobs(editor: Editor, onError: ErrorSink) {
  for (const shape of editor.store.query.records('shape').get()) {
    const job = jobOf(shape)
    if (job) void finish(editor, shape.id, job, onError)
  }
  return editor.sideEffects.registerAfterDeleteHandler('shape', (shape) => {
    const job = jobOf(shape)
    if (job && active.has(job.id) && !settled.has(job.id)) cancelPrompt(job.id).catch((e) => onError(errorText(e)))
  })
}
