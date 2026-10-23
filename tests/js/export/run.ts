// #156: run the real export button once per format against a mock editor; write the produced files to OUT_DIR.
import { writeFileSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { ExportDialog, exportAtom } from '../../../src/ui/ExportDialog'
import { resetHooks } from './react'
import { downloads } from './psd'

const out = process.env.OUT_DIR!
const fix = process.env.FIXTURES!
const g = globalThis as Record<string, unknown>
const net: string[] = []
g.fetch = async (u: string) => { net.push(String(u)); throw new Error('network disabled in tests') }
g.FileReader = class { result: string | null = null; onload: (() => void) | null = null
  readAsDataURL(b: Blob) { void b.arrayBuffer().then((a) => { this.result = `data:${b.type};base64,${Buffer.from(a).toString('base64')}`; this.onload?.() }) } }

// Two frames 800x600 and 400x300 (page units); toImage returns fixture images sized w*scale x h*scale.
const shapes: Record<string, { type: string; x: number; y: number; w: number; h: number }> = {
  'shape:f1': { type: 'frame', x: 0, y: 0, w: 800, h: 600 },
  'shape:f2': { type: 'frame', x: 0, y: 700, w: 400, h: 300 },
  // #169: a frame holding a text box and a solid rect, for the editable-text PPT
  'shape:f3': { type: 'frame', x: 0, y: 1100, w: 800, h: 600 },
  'shape:t1': { type: 'ca-text', x: 100, y: 1200, w: 400, h: 100 },
  'shape:r1': { type: 'ca-vector', x: 100, y: 1400, w: 200, h: 100 },
}
const props: Record<string, Record<string, unknown>> = {
  'shape:t1': { text: 'Hello ComfyArt', font: "'Inter', sans-serif", size: 24, color: '#112233', weight: 700, align: 'left',
    rich: { type: 'doc', content: [
      { type: 'paragraph', content: [{ type: 'text', text: 'Hello ' }, { type: 'text', text: '可编辑文字' },
        { type: 'text', text: ' mixed', marks: [{ type: 'italic' }, { type: 'underline' }, { type: 'textStyle', attrs: { color: '#AA0000', fontSize: '12px', fontFamily: 'Georgia' } }] }] },
      { type: 'paragraph', content: [{ type: 'text', text: '第二段', marks: [{ type: 'textStyle', attrs: { color: '#00AA00' } }] }] },
    ] } },
  'shape:r1': { kind: 'rect', fillType: 'solid', dash: 'solid', blend: 'normal', fill: '#FF0000', stroke: '', strokeWidth: 0, radius: 0, w: 200, h: 100 },
}
const toImageCalls: unknown[] = []
const editor = {
  getShape: (id: string) => shapes[id] && { id, type: shapes[id].type, meta: {}, rotation: 0, props: { w: shapes[id].w, h: shapes[id].h, ...props[id] } },
  getShapePageBounds: (ref: string | { id: string }) => { const s = shapes[typeof ref === 'string' ? ref : ref.id]; return { x: s.x, y: s.y, w: s.w, h: s.h, maxX: s.x + s.w, maxY: s.y + s.h } },
  getSelectedShapeIds: () => [],
  getDocumentSettings: () => ({ name: 'Export: test/1' }),
  getSortedChildIdsForParent: (id: string) => (id === 'shape:f3' ? ['shape:t1', 'shape:r1'] : []),
  toImage: async (ids: string[], o: { format: string; scale: number }) => {
    toImageCalls.push({ ids, ...o })
    const s = shapes[ids[0]]
    if (o.format === 'svg') return { blob: new Blob([`<svg xmlns="http://www.w3.org/2000/svg" width="${s.w}" height="${s.h}" viewBox="0 0 ${s.w} ${s.h}"><rect width="${s.w}" height="${s.h}" fill="#1e3cc8"/></svg>`], { type: 'image/svg+xml' }), width: s.w, height: s.h }
    const [w, h] = [s.w * o.scale, s.h * o.scale]
    const ext = o.format === 'jpeg' ? 'jpg' : 'png'
    const bytes = readFileSync(path.join(fix, `${w}x${h}.${ext}`))
    return { blob: new Blob([bytes], { type: `image/${o.format}` }), width: w, height: h }
  },
}

function findPrimary(node: unknown): (() => unknown) | null {
  if (!node || typeof node !== 'object') return null
  const n = node as { type?: unknown; props?: Record<string, unknown> }
  if (n.props?.className === 'ca-panel__primary') return n.props.onClick as () => unknown
  const kids = n.props?.children
  for (const k of Array.isArray(kids) ? kids : [kids]) { const f = findPrimary(k); if (f) return f }
  if (typeof n.type === 'function') return findPrimary((n.type as (p: unknown) => unknown)(n.props))
  return null
}

function findChips(node: unknown, out: unknown[] = []): unknown[] {
  if (!node || typeof node !== 'object') return out
  const n = node as { type?: unknown; props?: Record<string, unknown> }
  if (n.type === 'Chips') out.push(n.props?.value)
  const kids = n.props?.children
  for (const k of Array.isArray(kids) ? kids : [kids]) findChips(k, out)
  if (typeof n.type === 'function') findChips((n.type as (p: unknown) => unknown)(n.props), out)
  return out
}

async function exportAs(format: string | null, ids: string[], scale: number) {
  exportAtom.set(ids as never)
  resetHooks(format === null ? [] : [format, scale, false, false])
  const errors: string[] = []
  const tree = ExportDialog({ editor: editor as never, onError: (m: string) => errors.push(m) })
  const click = findPrimary(tree)
  if (!click) throw new Error('no export button')
  await click()
  await new Promise((r) => setTimeout(r, 50))
  return { errors, closed: exportAtom.get() === null }
}

const result: Record<string, unknown> = {}
// #169: open the dialog with no state set -> its own defaults (format, scale) as shown in the Chips.
exportAtom.set(['shape:f1'] as never)
resetHooks([])
const defaults = findChips(ExportDialog({ editor: editor as never, onError: () => {} }))
for (const [fmt, ids, scale] of [['png', ['shape:f1'], 2], ['pdf', ['shape:f1'], 1], ['jpeg', ['shape:f1'], 2], ['svg', ['shape:f1'], 2]] as const) {
  const before = downloads.length
  const r = await exportAs(fmt, [...ids], scale)
  const files = downloads.slice(before).map((d) => d.name)
  for (const d of downloads.slice(before)) writeFileSync(path.join(out, `${fmt}-${d.name}`), Buffer.from(await d.blob.arrayBuffer()))
  result[fmt] = { ...r, files }
}
// #176: pptx now goes through download() too (written, then each paragraph's duplicate <a:pPr> stripped).
for (const [fmt, ids, scale] of [['pptx', ['shape:f1', 'shape:f2'], 1], ['pptx-text', ['shape:f3'], 2]] as const) {
  const before = downloads.length
  const r = await exportAs(fmt, [...ids], scale)
  const files = downloads.slice(before).map((d) => d.name)
  for (const d of downloads.slice(before)) writeFileSync(path.join(out, `${fmt}-${d.name}`), Buffer.from(await d.blob.arrayBuffer()))
  result[fmt] = { ...r, files }
}
// #169: clicking Export with untouched defaults uses 2x
const before = toImageCalls.length
result.default = { ...(await exportAs(null, ['shape:f1'], 0)), calls: toImageCalls.slice(before) }
console.log(JSON.stringify({ result, defaults, toImageCalls, net }))
