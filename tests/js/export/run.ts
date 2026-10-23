// #156: run the real export button once per format against a mock editor; write the produced files to OUT_DIR.
import { writeFileSync, readFileSync, readdirSync, renameSync } from 'node:fs'
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
}
const toImageCalls: unknown[] = []
const editor = {
  getShape: (id: string) => shapes[id] && { id, type: shapes[id].type, meta: {}, props: { w: shapes[id].w, h: shapes[id].h } },
  getShapePageBounds: (id: string) => { const s = shapes[id]; return { x: s.x, y: s.y, w: s.w, h: s.h, maxX: s.x + s.w, maxY: s.y + s.h } },
  getSelectedShapeIds: () => [],
  getDocumentSettings: () => ({ name: 'Export: test/1' }),
  getSortedChildIdsForParent: () => [],
  toImage: async (ids: string[], o: { format: string; scale: number }) => {
    toImageCalls.push({ ids, ...o })
    const s = shapes[ids[0]]
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

async function exportAs(format: string, ids: string[], scale: number) {
  exportAtom.set(ids as never)
  resetHooks([format, scale, false, false])
  const errors: string[] = []
  const tree = ExportDialog({ editor: editor as never, onError: (m: string) => errors.push(m) })
  const click = findPrimary(tree)
  if (!click) throw new Error('no export button')
  await click()
  await new Promise((r) => setTimeout(r, 50))
  return { errors, closed: exportAtom.get() === null }
}

const result: Record<string, unknown> = {}
for (const [fmt, ids, scale] of [['png', ['shape:f1'], 2], ['pdf', ['shape:f1'], 1]] as const) {
  const before = downloads.length
  const r = await exportAs(fmt, [...ids], scale)
  const files = downloads.slice(before).map((d) => d.name)
  for (const d of downloads.slice(before)) writeFileSync(path.join(out, `${fmt}-${d.name}`), Buffer.from(await d.blob.arrayBuffer()))
  result[fmt] = { ...r, files }
}
// pptxgenjs writeFile in node writes `${name}.pptx` to the cwd (OUT_DIR).
const r = await exportAs('pptx', ['shape:f1', 'shape:f2'], 1)
const pptxFiles = readdirSync(out).filter((f) => f.endsWith('.pptx'))
for (const f of pptxFiles) renameSync(path.join(out, f), path.join(out, `pptx-${f}`))
result.pptx = { ...r, files: pptxFiles }
console.log(JSON.stringify({ result, toImageCalls, net }))
