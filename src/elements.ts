import { createShapeId, type Editor, type TLFrameShape, type TLImageShape } from 'tldraw'

import { maskFile } from './actions'
import { loadImage } from './adjust'
import { api, queuePrompt, viewUrl, waitForImages } from './comfy'
import { placeMedia, registerPlacer, selectResults, spawnHolder, startJob, type ErrorSink } from './jobs'
import { cropLayer, grow, pixels, type RegionLayer } from './layers'
import { ask, parseJson } from './llm'
import { TEXT, type TextShape } from './shapes/TextShape'
import { annotated, eraseGraph, samGraph } from './workflows'
import { t } from './i18n'
import { wsBodyError } from './wsErrors'

interface Line { box: [number, number][]; text: string; score: number }
interface TextLayer { text: string; cx: number; cy: number; w: number; h: number; angle: number; color: string; weight: number; font: string; align: string }

const MIN_SCORE = 0.6
const MASK_PAD = 0.2
const MAX_SIZE_PER_HEIGHT = 1.05
const TEXT_FILL = 0.94
const PROBE_SIZE = 100
const FONT = 'Arial'
const FAMILIES: Record<string, [string, string]> = { serif: ['Georgia', 'SimSun'], sans: ['Arial', 'Microsoft YaHei'], display: ['Impact', 'SimHei'], mono: ['Courier New', 'FangSong'], script: ['Georgia', 'KaiTi'] }
const CJK = /[぀-ヿ㐀-鿿가-힯]/
const STYLE_SYSTEM = 'You identify typography in design images. Reply with ONE JSON object and nothing else.'
const CENTER_TOLERANCE = 0.03
const RIGHT_MARGIN = 0.1
const BOLD_INK = 0.3
const OBJECT_PROMPTS = ['product', 'logo']
const MIN_OBJECT = 0.002
const OBJECT_GROW = 6

export async function readLines(src: string): Promise<Line[]> {
  const res = await api('/comfyart/ocr', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ src }) })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(wsBodyError(body, t('wsErr.failed')))
  return (body.lines as Line[]).filter((l) => l.score >= MIN_SCORE && l.text.trim())
}

const hex = (v: number) => Math.round(v).toString(16).padStart(2, '0')

function inkOf(ctx: CanvasRenderingContext2D, box: [number, number][]) {
  const xs = box.map((p) => p[0])
  const ys = box.map((p) => p[1])
  const [x, y] = [Math.max(0, Math.floor(Math.min(...xs))), Math.max(0, Math.floor(Math.min(...ys)))]
  const [w, h] = [Math.min(ctx.canvas.width, Math.ceil(Math.max(...xs))) - x, Math.min(ctx.canvas.height, Math.ceil(Math.max(...ys))) - y]
  const d = ctx.getImageData(x, y, Math.max(1, w), Math.max(1, h)).data
  let mean = 0
  for (let i = 0; i < d.length; i += 4) mean += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]
  mean /= d.length / 4
  const sums = [[0, 0, 0, 0], [0, 0, 0, 0]]
  for (let i = 0; i < d.length; i += 4) {
    const s = sums[0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2] > mean ? 1 : 0]
    s[0] += d[i]; s[1] += d[i + 1]; s[2] += d[i + 2]; s[3]++
  }
  const ink = sums[0][3] <= sums[1][3] ? sums[0] : sums[1]
  const n = Math.max(1, ink[3])
  return { color: `#${hex(ink[0] / n)}${hex(ink[1] / n)}${hex(ink[2] / n)}`, weight: ink[3] / (d.length / 4) > BOLD_INK ? 700 : 400 }
}

function alignOf(cx: number, w: number, width: number) {
  if (Math.abs(cx - width / 2) < width * CENTER_TOLERANCE) return 'center'
  return cx - w / 2 > width / 2 && cx + w / 2 > width * (1 - RIGHT_MARGIN) ? 'right' : 'left'
}

function layersOf(lines: Line[], img: HTMLImageElement): TextLayer[] {
  const c = document.createElement('canvas')
  c.width = img.naturalWidth
  c.height = img.naturalHeight
  const ctx = c.getContext('2d', { willReadFrequently: true })!
  ctx.drawImage(img, 0, 0)
  return lines.map(({ box, text }) => {
    const [p0, p1, p2, p3] = box
    const cx = (p0[0] + p1[0] + p2[0] + p3[0]) / 4
    const w = Math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    return {
      text, cx, w,
      cy: (p0[1] + p1[1] + p2[1] + p3[1]) / 4,
      h: Math.hypot(p2[0] - p1[0], p2[1] - p1[1]),
      angle: Math.atan2(p1[1] - p0[1], p1[0] - p0[0]),
      font: FONT,
      align: alignOf(cx, w, c.width),
      ...inkOf(ctx, box),
    }
  })
}

async function applyTypography(src: string, layers: TextLayer[]) {
  const list = layers.map((l, i) => `${i + 1}. "${l.text}"`).join('\n')
  const reply = parseJson(await ask(
    `For each numbered text line in this design, give its typeface category (serif, sans, display, mono or script) and weight (400 or 700). Reply {"lines": [{"n": 1, "family": "sans", "weight": 700}]}.\n${list}`,
    STYLE_SYSTEM, [src],
  ))
  for (const s of (reply?.lines as { n: number; family: string; weight: number }[] | undefined) ?? []) {
    const l = layers[s.n - 1]
    const family = FAMILIES[s.family]
    if (!l || !family) continue
    l.font = family[CJK.test(l.text) ? 1 : 0]
    if (s.weight === 400 || s.weight === 700) l.weight = s.weight
  }
}

function paintBoxes(ctx: CanvasRenderingContext2D, layers: TextLayer[], padding: number) {
  for (const l of layers) {
    const pad = l.h * padding
    ctx.save()
    ctx.translate(l.cx, l.cy)
    ctx.rotate(l.angle)
    ctx.fillRect(-l.w / 2 - pad, -l.h / 2 - pad, l.w + pad * 2, l.h + pad * 2)
    ctx.restore()
  }
}

async function objectLayers(src: string, w: number, h: number, texts: TextLayer[]) {
  const orig = pixels(await loadImage(src), w, h)
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const tctx = c.getContext('2d', { willReadFrequently: true })!
  paintBoxes(tctx, texts, MASK_PAD)
  const textMask = tctx.getImageData(0, 0, w, h).data
  const union = new Uint8ClampedArray(w * h * 4)
  const layers: RegionLayer[] = []
  for (const prompt of OBJECT_PROMPTS) {
    const sam = samGraph(annotated(src), { text: prompt })
    const [ref] = await waitForImages(await queuePrompt(sam.graph), sam.result)
    const m = pixels(await loadImage(viewUrl(ref)), w, h)
    const data = new Uint8ClampedArray(w * h * 4)
    let count = 0
    for (let p = 0; p < data.length; p += 4) {
      if (m[p] < 128 || textMask[p + 3] || union[p + 3]) continue
      data.set(orig.subarray(p, p + 3), p)
      data[p + 3] = union[p + 3] = 255
      count++
    }
    if (count < MIN_OBJECT * w * h) continue
    const layer = await cropLayer(data, w, h)
    if (layer) layers.push(layer)
  }
  return { layers, union }
}

export function editElements(editor: Editor, shape: TLImageShape, onError: ErrorSink) {
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== 'image' || !asset.props.src) return
  const { src, name, w, h } = asset.props
  const holder = spawnHolder(editor, shape)
  const extra: { layers: TextLayer[]; objects: RegionLayer[]; base: string; source: string } = { layers: [], objects: [], base: name, source: src }
  void startJob(editor, holder, (async () => {
    extra.layers = layersOf(await readLines(src), await loadImage(src))
    if (extra.layers.length) await applyTypography(src, extra.layers).catch(() => undefined)
    const { layers, union } = await objectLayers(src, w, h, extra.layers)
    extra.objects = layers
    if (!extra.layers.length && !layers.length) throw new Error(t('elements.nothingFound'))
    const mask = await maskFile(w, h, (ctx) => {
      paintBoxes(ctx, extra.layers, MASK_PAD)
      ctx.drawImage(grow(union, w, h, OBJECT_GROW), 0, 0)
    })
    return eraseGraph(annotated(src), mask)
  })(), { name: t('elements.jobName', name), placer: 'textLayers', extra }, onError)
  return holder
}

registerPlacer('textLayers', async (editor, holder, [plate], job) => {
  const { layers, objects, base, source } = job.extra as { layers: TextLayer[]; objects: RegionLayer[]; base: string; source: string }
  const fw = (holder.props as { w: number }).w
  const k = fw / plate.w
  const frame = createShapeId()
  editor.run(() => {
    editor.deleteShape(holder.id)
    editor.createShape<TLFrameShape>({ id: frame, type: 'frame', x: holder.x, y: holder.y, parentId: holder.parentId, props: { w: fw, h: plate.h * k, name: t('elements.frameName', base) }, meta: { elements: source } })
    placeMedia(editor, plate, t('elements.background', base), 0, 0, fw, frame)
    objects.forEach((o, i) => placeMedia(editor, o.media, t('elements.object', base, i + 1), o.x * k, o.y * k, o.media.w * k, frame))
    const measure = document.createElement('canvas').getContext('2d')!
    for (const l of layers) {
      measure.font = `${l.weight} ${PROBE_SIZE}px "${l.font}"`
      const size = Math.min(l.h * k * MAX_SIZE_PER_HEIGHT, (PROBE_SIZE * l.w * k * TEXT_FILL) / measure.measureText(l.text).width)
      const [cos, sin] = [Math.cos(l.angle), Math.sin(l.angle)]
      const [hw, hh] = [(l.w * k) / 2, size / 2]
      editor.createShape<TextShape>({
        id: createShapeId(), type: TEXT, parentId: frame,
        x: l.cx * k - hw * cos + hh * sin, y: l.cy * k - hw * sin - hh * cos, rotation: l.angle,
        props: { text: l.text, size, font: l.font, color: l.color, weight: l.weight, line: 1, align: l.align, autoSize: false, w: l.w * k },
      })
    }
  }, { history: 'ignore' })
  selectResults(editor, holder, [frame])
})
