import { strFromU8, strToU8, unzipSync, zipSync } from 'fflate'
import PptxGenJS from 'pptxgenjs'
import { getColorValue, renderPlaintextFromRichText, type Box, type Editor, type TLImageShape, type TLNoteShape, type TLShape, type TLShapeId } from 'tldraw'

import { alphaOf } from './palette'
import { download } from './psd'
import type { RichDoc } from './richText'
import { TEXT, type TextShape } from './shapes/TextShape'
import { VECTOR, type VectorShape } from './shapes/VectorShape'

const SLIDE_W = 13.333
const PT_PER_IN = 72
const CONTAINERS = ['frame', 'group']

type Slide = ReturnType<PptxGenJS['addSlide']>
interface Place { x: number; y: number; w: number; h: number }

function slidesOf(editor: Editor, ids: TLShapeId[]): TLShapeId[][] {
  const frames = ids.filter((id) => editor.getShape(id)?.type === 'frame')
  if (!frames.length) return [ids]
  return frames.sort((a, b) => {
    const [p, q] = [editor.getShapePageBounds(a)!, editor.getShapePageBounds(b)!]
    return p.y - q.y || p.x - q.x
  }).map((id) => [id])
}

function leaves(editor: Editor, ids: TLShapeId[]): TLShape[] {
  const out: TLShape[] = []
  const walk = (id: TLShapeId) => {
    const s = editor.getShape(id)
    if (!s || s.meta.hidden) return
    if (CONTAINERS.includes(s.type)) editor.getSortedChildIdsForParent(id).forEach(walk)
    else out.push(s)
  }
  ids.forEach(walk)
  return out
}

function boundsOf(editor: Editor, ids: TLShapeId[]) {
  const b = ids.map((id) => editor.getShapePageBounds(id)!)
  const [x, y] = [Math.min(...b.map((r) => r.x)), Math.min(...b.map((r) => r.y))]
  return { x, y, w: Math.max(...b.map((r) => r.maxX)) - x, h: Math.max(...b.map((r) => r.maxY)) - y }
}

const dataUrl = (blob: Blob) => new Promise<string>((resolve) => {
  const r = new FileReader()
  r.onload = () => resolve(String(r.result))
  r.readAsDataURL(blob)
})

const hex = (color: string) => color.replace('#', '').slice(0, 6).toUpperCase()
const transparency = (color: string) => Math.round((1 - alphaOf(color)) * 100)

function textRuns(doc: RichDoc, k: number): PptxGenJS.TextProps[] {
  const paragraphs = doc.content ?? []
  return paragraphs.flatMap((para, i) => {
    const nodes = para.content ?? [{ type: 'text', text: '' }]
    return nodes.map((n, j) => {
      const style = n.marks?.find((m) => m.type === 'textStyle')?.attrs ?? {}
      const size = parseFloat(style.fontSize)
      return {
        text: n.type === 'hardBreak' ? '\n' : n.text ?? '',
        options: {
          ...(style.color ? { color: hex(style.color) } : {}),
          ...(style.fontFamily ? { fontFace: String(style.fontFamily).replace(/['"]/g, '') } : {}),
          ...(size ? { fontSize: size * k * PT_PER_IN } : {}),
          ...(n.marks?.some((m) => m.type === 'bold') ? { bold: true } : {}),
          ...(n.marks?.some((m) => m.type === 'italic') ? { italic: true } : {}),
          ...(n.marks?.some((m) => m.type === 'underline') ? { underline: { style: 'sng' as const } } : {}),
          ...(j === nodes.length - 1 && i < paragraphs.length - 1 ? { breakLine: true } : {}),
        },
      }
    })
  })
}

// #176: pptxgenjs 4.0.1 emits an <a:pPr> before every run of a multi-run paragraph (it fills each run with the text
// box's align/indent/bullet), which is invalid OOXML (pPr must be the single first child of <a:p>) and makes PowerPoint
// offer a repair. Align is set once on the text box (never per run); after writing, keep only each paragraph's first pPr.
const PPR = /<a:pPr\b[^>]*?(?:\/>|>[\s\S]*?<\/a:pPr>)/g
export function onePprPerParagraph(xml: string) {
  return xml.replace(/<a:p>[\s\S]*?<\/a:p>/g, (p) => {
    let seen = false
    return p.replace(PPR, (m) => (seen ? '' : ((seen = true), m)))
  })
}

function fixParagraphs(data: Uint8Array) {
  const files = unzipSync(data)
  for (const name of Object.keys(files)) {
    if (/^ppt\/(slides|slideLayouts|slideMasters|notesSlides)\/[^/]+\.xml$/.test(name)) files[name] = strToU8(onePprPerParagraph(strFromU8(files[name])))
  }
  return zipSync(files)
}

async function render(editor: Editor, ids: TLShapeId[], scale: number) {
  return dataUrl((await editor.toImage(ids, { format: 'png', scale, background: false })).blob)
}

async function addObject(editor: Editor, pptx: PptxGenJS, slide: Slide, s: TLShape, at: Place, k: number, scale: number) {
  if (s.rotation) return slide.addImage({ data: await render(editor, [s.id], scale), ...at })
  if (s.type === 'image' && !(s as TLImageShape).props.crop) {
    const asset = editor.getAsset((s as TLImageShape).props.assetId!)
    if (asset?.props.src) {
      const flip = (s as TLImageShape).props.flipX || (s as TLImageShape).props.flipY
      return slide.addImage({ data: flip ? await render(editor, [s.id], scale) : await dataUrl(await (await fetch(asset.props.src)).blob()), ...at })
    }
  }
  if (s.type === TEXT) {
    const p = (s as TextShape).props
    return slide.addText(p.rich ? textRuns(p.rich, k) : p.text, {
      ...at, fontFace: p.font.split(',')[0].replace(/['"]/g, '').trim(), fontSize: p.size * k * PT_PER_IN,
      color: hex(p.color), bold: p.weight >= 600, align: p.align as 'left' | 'center' | 'right', valign: 'top', margin: 0, fit: 'none',
    })
  }
  if (s.type === 'note') {
    const n = s as TLNoteShape
    const colors = editor.getCurrentTheme().colors[editor.getColorMode()]
    return slide.addText(renderPlaintextFromRichText(editor, n.props.richText), {
      ...at, fill: { color: hex(getColorValue(colors, n.props.color, 'noteFill')) }, color: hex(getColorValue(colors, n.props.color, 'noteText')),
      fontSize: 22 * n.props.scale * k * PT_PER_IN, align: 'center', valign: 'middle', margin: 8,
    })
  }
  if (s.type === VECTOR) {
    const p = (s as VectorShape).props
    if ((p.kind === 'rect' || p.kind === 'ellipse') && p.fillType === 'solid' && p.dash === 'solid' && p.blend === 'normal') {
      const shape = p.kind === 'ellipse' ? pptx.ShapeType.ellipse : p.radius ? pptx.ShapeType.roundRect : pptx.ShapeType.rect
      return slide.addShape(shape, {
        ...at,
        ...(p.fill ? { fill: { color: hex(p.fill), transparency: transparency(p.fill) } } : { fill: { type: 'none' } as never }),
        ...(p.stroke && p.strokeWidth ? { line: { color: hex(p.stroke), transparency: transparency(p.stroke), width: p.strokeWidth * k * PT_PER_IN } } : {}),
        ...(p.kind === 'rect' && p.radius ? { rectRadius: Math.min(0.5, p.radius / Math.min(p.w, p.h)) } : {}),
      })
    }
  }
  return slide.addImage({ data: await render(editor, [s.id], scale), ...at })
}

export async function exportPptx(editor: Editor, ids: TLShapeId[], editable: boolean, scale: number, name: string) {
  const groups = slidesOf(editor, ids)
  const first = boundsOf(editor, groups[0])
  const slideH = SLIDE_W * first.h / first.w
  const pptx = new PptxGenJS()
  pptx.defineLayout({ name: 'COMFYART', width: SLIDE_W, height: slideH })
  pptx.layout = 'COMFYART'
  for (const group of groups) {
    const { x: x0, y: y0, w, h } = boundsOf(editor, group)
    const k = Math.min(SLIDE_W / w, slideH / h)
    const [ox, oy] = [(SLIDE_W - w * k) / 2, (slideH - h * k) / 2]
    const place = (b: Box): Place => ({ x: ox + (b.x - x0) * k, y: oy + (b.y - y0) * k, w: b.w * k, h: b.h * k })
    const slide = pptx.addSlide()
    if (!editable) {
      slide.addImage({ data: await dataUrl((await editor.toImage(group, { format: 'png', scale, background: true })).blob), x: ox, y: oy, w: w * k, h: h * k })
      continue
    }
    const frame = group.length === 1 ? editor.getShape(group[0]) : null
    if (frame?.type === 'frame') slide.background = { color: 'FFFFFF' }
    for (const s of leaves(editor, group)) await addObject(editor, pptx, slide, s, place(editor.getShapePageBounds(s)!), k, scale)
  }
  const data = (await pptx.write({ outputType: 'uint8array' })) as Uint8Array
  download(new Blob([fixParagraphs(data) as BlobPart], { type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation' }), `${name}.pptx`)
}
