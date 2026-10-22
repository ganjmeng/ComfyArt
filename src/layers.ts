import { AssetRecordType, createShapeId, type Editor, getIndicesBetween, type TLImageShape, type TLShapeId, Vec } from 'tldraw'

import { maskFile } from './actions'
import { queuePrompt, uploadImage, viewUrl, waitForImages } from './comfy'
import { type ErrorSink, errorText, type Media, placeMedia, registerPlacer, selectResults, spawnHolder, startJob } from './jobs'
import { annotated, eraseGraph, samBoxesGraph } from './workflows'
import { t } from './i18n'
import { canvasBlob } from './canvasBlob'

const SOLID = 200
const OPAQUE = 128

interface Raw { media: Media; data: Uint8ClampedArray; cover: number; diff: number }

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`cannot load ${src}`))
    img.src = src
  })
}

export function pixels(img: HTMLImageElement, w: number, h: number): Uint8ClampedArray {
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const ctx = c.getContext('2d', { willReadFrequently: true })!
  ctx.drawImage(img, 0, 0, w, h)
  return ctx.getImageData(0, 0, w, h).data
}

function measure(media: Media, data: Uint8ClampedArray, orig: Uint8ClampedArray): Raw {
  let covered = 0
  let solid = 0
  let diff = 0
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] > OPAQUE) covered++
    if (data[i + 3] <= SOLID) continue
    solid++
    diff += (Math.abs(data[i] - orig[i]) + Math.abs(data[i + 1] - orig[i + 1]) + Math.abs(data[i + 2] - orig[i + 2])) / 3
  }
  return { media, data, cover: covered / (data.length / 4), diff: solid ? diff / solid : 999 }
}

function overlap(a: Uint8ClampedArray, b: Uint8ClampedArray): number {
  let inter = 0
  let union = 0
  for (let i = 3; i < a.length; i += 4) {
    const x = a[i] > OPAQUE
    const y = b[i] > OPAQUE
    if (x && y) inter++
    if (x || y) union++
  }
  return union ? inter / union : 0
}

function canvasOf(data: Uint8ClampedArray, w: number, h: number): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const ctx = c.getContext('2d')!
  const img = ctx.createImageData(w, h)
  img.data.set(data)
  ctx.putImageData(img, 0, 0)
  return c
}

export function grow(data: Uint8ClampedArray, w: number, h: number, px: number): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const ctx = c.getContext('2d', { willReadFrequently: true })!
  ctx.filter = `blur(${px}px)`
  ctx.drawImage(canvasOf(data, w, h), 0, 0)
  const out = ctx.getImageData(0, 0, w, h)
  for (let i = 3; i < out.data.length; i += 4) out.data[i] = out.data[i] > 16 ? 255 : 0
  ctx.putImageData(out, 0, 0)
  return c
}

export async function cropLayer(data: Uint8ClampedArray, w: number, h: number) {
  let [l, t, r, b] = [w, h, -1, -1]
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (data[(y * w + x) * 4 + 3] <= 8) continue
      if (x < l) l = x
      if (x > r) r = x
      if (y < t) t = y
      if (y > b) b = y
    }
  }
  if (r < 0) return null
  const out = document.createElement('canvas')
  out.width = r - l + 1
  out.height = b - t + 1
  out.getContext('2d')!.drawImage(canvasOf(data, w, h), l, t, out.width, out.height, 0, 0, out.width, out.height)
  const ref = await uploadImage(await canvasBlob(out), `layer-${Date.now()}.png`)
  return { media: { ref, src: viewUrl(ref), w: out.width, h: out.height, kind: 'image' } as Media, x: l, y: t }
}

registerPlacer('replace', async (editor, holder, [m], job) => {
  const shape = holder as TLImageShape
  const assetId = AssetRecordType.createId()
  editor.createAssets([{
    id: assetId, typeName: 'asset', type: 'image',
    props: { name: job.name, src: m.src, w: m.w, h: m.h, mimeType: 'image/png', isAnimated: false },
    meta: {},
  }])
  editor.updateShape<TLImageShape>({ id: shape.id, type: 'image', props: { assetId }, meta: { ...shape.meta, job: null } })
})

registerPlacer('layers', async (editor, holder, media, job, onError) => {
  const imgs = await Promise.all(media.map((m) => loadImage(m.src)))
  const [w, h] = [imgs[0].naturalWidth, imgs[0].naturalHeight]
  const source = String(job.extra?.source ?? '')
  const sourceSrc = viewUrl(parseAnnotated(source))
  const sourceImg = await loadImage(sourceSrc)
  const orig = pixels(sourceImg, w, h)
  const raws = imgs.map((img, i) => measure(media[i], pixels(img, w, h), orig))

  const kept: Raw[] = []
  for (const r of [...raws].sort((a, b) => b.cover - a.cover)) {
    if (r.cover > 0.9 || r.cover < 0.002 || r.diff > 60) continue
    if (kept.some((k) => overlap(r.data, k.data) > 0.9)) continue
    kept.push(r)
  }
  kept.sort((a, b) => raws.indexOf(a) - raws.indexOf(b))
  const crops = (await Promise.all(kept.map((r) => cropLayer(r.data, w, h)))).filter((c) => !!c)

  const fw = (holder.props as { w: number }).w
  const scale = fw / w
  const base = String(job.extra?.base ?? t('common.image'))
  const frameId = createShapeId()
  let bgId: TLShapeId | null = null
  editor.run(() => {
    editor.deleteShape(holder.id)
    editor.createShape({ id: frameId, type: 'frame', parentId: holder.parentId, x: holder.x, y: holder.y, props: { w: fw, h: h * scale, name: t('layers.splitLayers', base) } })
    bgId = placeMedia(editor, { ...media[0], src: sourceSrc, w: sourceImg.naturalWidth, h: sourceImg.naturalHeight }, t('layers.background', base), 0, 0, fw, frameId)
    crops.forEach((c, i) => {
      placeMedia(editor, c.media, t('layers.layer', base, i + 1), c.x * scale, c.y * scale, c.media.w * scale, frameId)
    })
  }, { history: 'ignore' })
  selectResults(editor, holder, [frameId])

  if (!kept.length || !bgId) return
  const union = new Uint8ClampedArray(w * h * 4)
  for (const r of kept) for (let i = 3; i < union.length; i += 4) if (r.data[i] > 8) union[i] = 255
  const mask = await maskFile(sourceImg.naturalWidth, sourceImg.naturalHeight, (ctx) => {
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(grow(union, w, h, 4), 0, 0, sourceImg.naturalWidth, sourceImg.naturalHeight)
  })
  void startJob(editor, bgId, eraseGraph(source, mask), { name: t('layers.background', base), placer: 'replace' }, onError)
})

function parseAnnotated(a: string) {
  const m = /^(?:(.*)\/)?([^/]+) \[(\w+)\]$/.exec(a)
  return { filename: m?.[2] ?? a, subfolder: m?.[1] ?? '', type: m?.[3] ?? 'input' }
}

export interface RegionLayer { media: Media; x: number; y: number }

registerPlacer('regions', async (editor, holder, [bg], job) => {
  const layers = (job.extra?.layers ?? []) as RegionLayer[]
  const fw = (holder.props as { w: number }).w
  const scale = fw / bg.w
  const base = String(job.extra?.base ?? t('common.image'))
  const frameId = createShapeId()
  editor.run(() => {
    editor.deleteShape(holder.id)
    editor.createShape({ id: frameId, type: 'frame', parentId: holder.parentId, x: holder.x, y: holder.y, props: { w: fw, h: bg.h * scale, name: t('layers.splitLayers', base) } })
    placeMedia(editor, bg, t('layers.background', base), 0, 0, fw, frameId)
    layers.forEach((l, i) => placeMedia(editor, l.media, t('layers.layer', base, i + 1), l.x * scale, l.y * scale, l.media.w * scale, frameId))
  }, { history: 'ignore' })
  selectResults(editor, holder, [frameId])
})

export async function separateRegions(editor: Editor, shape: TLImageShape, boxes: [number, number, number, number][], onError: ErrorSink) {
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== 'image' || !asset.props.src) return
  const { w, h, name } = asset.props
  try {
    const rest = pixels(await loadImage(asset.props.src), w, h)
    const parts: RegionLayer[] = []
    for (const [bx, by, bw, bh] of boxes) {
      const data = new Uint8ClampedArray(w * h * 4)
      for (let y = Math.round(by * h); y < Math.min(h, Math.round((by + bh) * h)); y++) {
        for (let x = Math.round(bx * w); x < Math.min(w, Math.round((bx + bw) * w)); x++) {
          const p = (y * w + x) * 4
          if (rest[p + 3] <= 8) continue
          data.set(rest.subarray(p, p + 4), p)
          rest[p + 3] = 0
        }
      }
      const part = await cropLayer(data, w, h)
      if (part) parts.push(part)
    }
    if (!parts.length) throw new Error(t('layers.noVisiblePixels'))
    const left = await cropLayer(rest, w, h)
    const s = shape.props.w / w
    const at = (x: number, y: number) => {
      const p = Vec.Rot({ x: x * s, y: y * s }, shape.rotation).add(shape)
      return { x: p.x, y: p.y }
    }
    const siblings = editor.getSortedChildIdsForParent(shape.parentId).map((id) => editor.getShape(id)!)
    const next = siblings[siblings.findIndex((c) => c.id === shape.id) + 1]
    const indices = getIndicesBetween(shape.index, next?.index, parts.length)
    const taken = siblings.filter((c) => {
      const a = c.type === 'image' && (c as TLImageShape).props.assetId ? editor.getAsset((c as TLImageShape).props.assetId!) : null
      return a?.type === 'image' && a.props.name.startsWith(`${name} · `)
    }).length
    editor.markHistoryStoppingPoint('separate layers')
    editor.run(() => {
      parts.forEach((part, i) => {
        const id = placeMedia(editor, part.media, `${name} · ${taken + i + 1}`, 0, 0, part.media.w * s, shape.parentId)
        editor.updateShape({ id, type: 'image', ...at(part.x, part.y), rotation: shape.rotation, index: indices[i] })
      })
      if (!left) {
        editor.deleteShape(shape.id)
        return
      }
      const assetId = AssetRecordType.createId()
      editor.createAssets([{ id: assetId, typeName: 'asset', type: 'image', props: { name, src: left.media.src, w: left.media.w, h: left.media.h, mimeType: 'image/png', isAnimated: false }, meta: {} }])
      editor.updateShape<TLImageShape>({ id: shape.id, type: 'image', ...at(left.x, left.y), props: { assetId, w: left.media.w * s, h: left.media.h * s } })
    })
  } catch (e) {
    onError(errorText(e))
  }
}

export function regionSplit(editor: Editor, shape: TLImageShape, boxes: [number, number, number, number][], onError: ErrorSink) {
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== 'image' || !asset.props.src) return
  const { w, h, name } = asset.props
  const src = asset.props.src
  const holder = spawnHolder(editor, shape)
  void (async () => {
    try {
      const crops = boxes.map(([x, y, bw, bh]) => ({ x: Math.round(x * w), y: Math.round(y * h), w: Math.round(bw * w), h: Math.round(bh * h) }))
      const masks = await Promise.all(samBoxesGraph(annotated(src), crops).map(async ({ graph, result }) => (await waitForImages(await queuePrompt(graph), result))[0]))
      const orig = pixels(await loadImage(src), w, h)
      const union = new Uint8ClampedArray(w * h * 4)
      const layers: RegionLayer[] = []
      for (const [i, ref] of masks.entries()) {
        const m = pixels(await loadImage(viewUrl(ref)), w, h)
        const c = crops[i]
        const data = new Uint8ClampedArray(w * h * 4)
        for (let y = c.y; y < c.y + c.h && y < h; y++) {
          for (let x = c.x; x < c.x + c.w && x < w; x++) {
            const p = (y * w + x) * 4
            if (m[p] < 128) continue
            data.set(orig.subarray(p, p + 3), p)
            data[p + 3] = 255
            union[p + 3] = 255
          }
        }
        const layer = await cropLayer(data, w, h)
        if (layer) layers.push(layer)
      }
      if (!layers.length) throw new Error(t('layers.noObjectsDetectedInThe'))
      const mask = await maskFile(w, h, (ctx) => {
        ctx.filter = 'blur(6px)'
        const u = canvasOf(union, w, h)
        ctx.drawImage(u, 0, 0)
        ctx.drawImage(u, 0, 0)
      })
      await startJob(editor, holder, eraseGraph(annotated(src), mask), { name: t('layers.splitLayers', name), placer: 'regions', extra: { layers, base: name } as any }, onError)
    } catch (e) {
      editor.deleteShape(holder)
      onError(errorText(e))
    }
  })()
  return holder
}
