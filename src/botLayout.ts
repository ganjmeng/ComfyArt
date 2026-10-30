import { createShapeId, type Editor, type TLFrameShape, type TLShape, type TLShapeId } from 'tldraw'

import { settingsAtom } from './bot'
import { placeInChatFrame } from './chatFrame'
import { placeHtml } from './embeds'
import { genInfoOf } from './generate'
import { type ErrorSink, fileSrc, GAP, jobOf, mediaAsset } from './jobs'
import { describeItem, itemImages, libraryAtom, linkedKit } from './library'
import { correct, forget, MEMORY_SAVED_NOTE, memoryAtom, upsertMemory } from './memory'
import { buildSlides } from './slides'
import { exportImage } from './shapes/ArtboardShape'
import { COMMENT } from './shapes/CommentShape'
import { HTML, type HtmlShape } from './shapes/EmbedShapes'
import { GENERATOR, type GeneratorShape } from './shapes/GeneratorShape'
import { TEXT, type TextShape } from './shapes/TextShape'
import { VECTOR, type VectorShape } from './shapes/VectorShape'
import { skillTool } from './skills'
import { t } from './i18n'

export type Args = Record<string, any>
export type Handler = (editor: Editor, args: Args, onError: ErrorSink, chat: string) => unknown

const MAX_SHAPES = 300
const VIEW_MAX_PX = 1024
const PAGE_TEXT_CAP = 3000

export function shapeOf(editor: Editor, id: unknown): TLShape {
  const shape = typeof id === 'string' ? editor.getShape(id as TLShapeId) : undefined
  if (!shape) throw new Error(`no shape ${JSON.stringify(id)} — use ids from get_canvas`)
  return shape
}

function nameOf(editor: Editor, shape: TLShape): string {
  if (shape.type === 'frame') return (shape as TLFrameShape).props.name
  if (shape.type === TEXT) return (shape as TextShape).props.text.slice(0, 200)
  return mediaAsset(editor, shape)?.props.name || (shape.props as { name?: string }).name || ''
}

function describe(editor: Editor, shape: TLShape) {
  const b = editor.getShapePageBounds(shape)!
  const parent = editor.getShape(shape.parentId as TLShapeId)
  const gen = genInfoOf(shape)
  const job = jobOf(shape)
  const media = mediaAsset(editor, shape)
  return {
    id: shape.id,
    type: shape.type === GENERATOR ? (job ? 'generating' : 'generator') : shape.type,
    name: nameOf(editor, shape) || undefined,
    x: Math.round(b.x), y: Math.round(b.y), width: Math.round(b.w), height: Math.round(b.h),
    ...(parent?.type === 'frame' ? { frame: parent.id } : {}),
    ...(media?.props.src ? { url: media.props.src, pixels: `${media.props.w}x${media.props.h}` } : fileSrc(editor, shape) ? { url: fileSrc(editor, shape) } : {}),
    ...(gen?.prompt ? { prompt: gen.prompt.slice(0, 300) } : {}),
    ...(shape.type === GENERATOR ? { prompt: (shape as GeneratorShape).props.prompt.slice(0, 300) } : {}),
    ...(typeof shape.meta.pageText === 'string' ? { page_text: shape.meta.pageText.slice(0, PAGE_TEXT_CAP) } : {}),
  }
}

function pageOf(editor: Editor, page: unknown) {
  if (!page) return editor.getCurrentPage()
  const found = editor.getPages().find((p) => p.id === page || p.name === page)
  if (!found) throw new Error(`no page ${JSON.stringify(page)}`)
  return found
}

function toPageShapes(editor: Editor, ids: TLShapeId[]) {
  return ids.map((id) => editor.getShape(id)!).filter(Boolean)
}

async function blobBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer())
  let s = ''
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(s)
}

function textProps(args: Args): Partial<TextShape['props']> {
  return {
    text: String(args.text ?? ''),
    ...(args.font_size ? { size: Number(args.font_size) } : {}),
    ...(args.color ? { color: String(args.color) } : {}),
    ...(args.font ? { font: String(args.font) } : {}),
    ...(args.align ? { align: String(args.align) } : {}),
    ...(args.width ? { w: Number(args.width), autoSize: false } : {}),
  }
}

export const LAYOUT_HANDLERS: Record<string, Handler> = {
  get_canvas: (editor, args) => {
    const page = pageOf(editor, args.page)
    const ids = [...editor.getPageShapeIds(page.id)]
    const shapes = toPageShapes(editor, ids).filter((s) => s.type !== COMMENT).slice(0, MAX_SHAPES).map((s) => describe(editor, s))
    const kit = linkedKit(editor.getDocumentSettings().meta.brandKit)
    return {
      project: editor.getDocumentSettings().name || undefined,
      pages: editor.getPages().map((p) => ({ id: p.id, name: p.name, current: p.id === editor.getCurrentPageId() })),
      page: page.id,
      shapes,
      truncated: ids.length > MAX_SHAPES || undefined,
      selection: editor.getSelectedShapeIds(),
      brand_kit: kit ? { id: kit.id, name: kit.name } : null,
    }
  },
  view_canvas: async (editor, args) => {
    const ids = Array.isArray(args.ids) && args.ids.length ? args.ids.map((id: string) => shapeOf(editor, id).id) : [...editor.getCurrentPageShapeIds()]
    if (!ids.length) throw new Error('the page is empty')
    const shapes = toPageShapes(editor, ids)
    const bounds = shapes.map((s) => editor.getShapePageBounds(s)!).reduce((a, b) => a.union(b))
    const maxPx = Math.min(2048, Number(args.max_px) || VIEW_MAX_PX)
    const { blob, width, height } = await exportImage(editor, ids, { format: 'png', background: true, scale: Math.min(1, maxPx / Math.max(bounds.w, bounds.h)) })
    return { width, height, bounds: { x: Math.round(bounds.x), y: Math.round(bounds.y), width: Math.round(bounds.w), height: Math.round(bounds.h) }, png: await blobBase64(blob) }
  },
  brand_kits: (editor) => {
    const linked = linkedKit(editor.getDocumentSettings().meta.brandKit)
    return {
      linked: linked?.id ?? null,
      items: libraryAtom.get().map((k) => ({ id: k.id, kind: k.kind, name: k.name, summary: describeItem(k), images: itemImages(k) })),
    }
  },
  place_html: (editor, args, _onError, chat) => {
    const id = placeHtml(editor, String(args.html), String(args.name ?? t('botCommands.webPage')))
    editor.updateShape<HtmlShape>({
      id, type: HTML,
      ...(args.x != null ? { x: Number(args.x) } : {}),
      ...(args.y != null ? { y: Number(args.y) } : {}),
      props: { ...(args.width ? { w: Number(args.width) } : {}), ...(args.height ? { h: Number(args.height) } : {}) },
    })
    if (chat && args.x == null && args.y == null) placeInChatFrame(editor, id, chat)
    return { id }
  },
  create_slides: (editor, args, onError) => {
    if (!Array.isArray(args.slides) || !args.slides.length) throw new Error('slides must be a non-empty array')
    const before = new Set(editor.getCurrentPageShapeIds())
    const ids = buildSlides(editor, String(args.title ?? t('botCommands.presentation')), args.slides.map((s: Args) => ({
      title: String(s.title ?? ''), bullets: Array.isArray(s.bullets) ? s.bullets.map(String) : [], image: s.image ? String(s.image) : undefined,
    })), onError)
    const frames = [...editor.getCurrentPageShapeIds()].filter((id) => !before.has(id) && editor.getShape(id)?.type === 'frame')
    return { frames, ids, note: ids.length ? 'images are generating: call wait_generation with ids' : undefined }
  },
  add_text: (editor, args) => {
    const id = createShapeId()
    const center = editor.getViewportPageBounds().center
    editor.createShape<TextShape>({ id, type: TEXT, x: Number(args.x ?? center.x), y: Number(args.y ?? center.y), props: textProps(args) })
    if (args.frame) {
      const frame = shapeOf(editor, args.frame)
      editor.reparentShapes([id], frame.id)
      editor.updateShape({ id, type: TEXT, x: Number(args.x ?? GAP), y: Number(args.y ?? GAP) })
    }
    return { id }
  },
  add_shape: (editor, args) => {
    const kinds = ['rect', 'ellipse', 'polygon', 'star']
    if (!kinds.includes(args.kind)) throw new Error(`kind must be one of ${kinds.join(', ')}`)
    const id = createShapeId()
    const center = editor.getViewportPageBounds().center
    editor.createShape<VectorShape>({
      id, type: VECTOR, x: Number(args.x ?? center.x), y: Number(args.y ?? center.y),
      props: { kind: args.kind, w: Number(args.width) || 200, h: Number(args.height) || 200, ...(args.fill ? { fill: String(args.fill) } : {}), stroke: args.stroke ? String(args.stroke) : '', ...(args.sides ? { sides: Number(args.sides) } : {}) },
    })
    if (args.frame) {
      editor.reparentShapes([id], shapeOf(editor, args.frame).id)
      editor.updateShape({ id, type: VECTOR, x: Number(args.x ?? GAP), y: Number(args.y ?? GAP) })
    }
    return { id }
  },
  create_frame: (editor, args) => {
    const id = createShapeId()
    const w = Number(args.width) || 1080
    const h = Number(args.height) || 1080
    const center = editor.getViewportPageBounds().center
    editor.createShape<TLFrameShape>({ id, type: 'frame', x: Number(args.x ?? center.x - w / 2), y: Number(args.y ?? center.y - h / 2), props: { w, h, name: String(args.name ?? t('common.artboard')) } })
    if (Array.isArray(args.children) && args.children.length) editor.reparentShapes(args.children.map((c: string) => shapeOf(editor, c).id), id)
    return { id }
  },
  update_shapes: (editor, args) => {
    if (!Array.isArray(args.updates)) throw new Error('updates must be an array')
    const updated: string[] = []
    editor.run(() => {
      for (const u of args.updates as Args[]) {
        const shape = shapeOf(editor, u.id)
        if (u.frame !== undefined) editor.reparentShapes([shape.id], u.frame ? shapeOf(editor, u.frame).id : editor.getCurrentPageId())
        const current = editor.getShape(shape.id)!
        const point = u.x != null || u.y != null
          ? editor.getPointInParentSpace(shape.id, { x: Number(u.x ?? editor.getShapePageBounds(current)!.x), y: Number(u.y ?? editor.getShapePageBounds(current)!.y) })
          : null
        const props: Record<string, unknown> = {}
        if (u.width != null && 'w' in current.props) props.w = Number(u.width)
        if (u.height != null && 'h' in current.props) props.h = Number(u.height)
        if (u.name != null && current.type === 'frame') props.name = String(u.name)
        if (u.text != null && current.type === TEXT) Object.assign(props, { text: String(u.text), rich: null })
        if (u.color != null && current.type === TEXT) props.color = String(u.color)
        if (u.color != null && current.type === VECTOR) props.fill = String(u.color)
        editor.updateShape({
          id: shape.id, type: current.type,
          ...(point ? { x: point.x, y: point.y } : {}),
          ...(u.rotation != null ? { rotation: (Number(u.rotation) * Math.PI) / 180 } : {}),
          ...(u.opacity != null ? { opacity: Number(u.opacity) } : {}),
          ...(Object.keys(props).length ? { props } : {}),
        })
        updated.push(shape.id)
      }
    })
    return { updated }
  },
  delete_shapes: (editor, args) => {
    const ids = (args.ids ?? []).map((id: string) => shapeOf(editor, id).id)
    editor.deleteShapes(ids)
    return { deleted: ids }
  },
  focus: (editor, args) => {
    const shapes = (args.ids ?? []).map((id: string) => shapeOf(editor, id))
    const page = shapes[0] && editor.getAncestorPageId(shapes[0])
    if (page) editor.setCurrentPage(page)
    editor.select(...shapes.map((s: TLShape) => s.id))
    editor.zoomToSelection({ animation: { duration: 200 } })
    return { selected: shapes.map((s: TLShape) => s.id) }
  },
  memory: async (_editor, args) => {
    if (settingsAtom.get()['memory-enabled'] === false && args.action !== 'forget') throw new Error('the user turned memory off; do not read or save memories')
    if (args.action === 'list') return { memories: memoryAtom.get().map((m) => ({ text: m.text, category: m.category ?? 'about' })) }
    if (args.action === 'add') {
      // #423: dedupe before write (same fact → skip, changed fact → update); one row per turn is merged server-side
      const r = await upsertMemory([{ text: String(args.text ?? ''), category: args.category }], t('botCommands.chat'))
      const written = [...r.added, ...r.updated.map((u) => u.memory)]
      return {
        saved: true, added: args.text, memory_ids: written.map((m) => m.id), updated_ids: r.updated.map((u) => u.memory.id), texts: written.map((m) => m.text),
        ...(r.updated.length ? { updated: r.updated.map((u) => `${u.old} → ${u.memory.text}`) } : {}),
        ...(r.unchanged.length ? { unchanged: r.unchanged.map((m) => m.text) } : {}),
        note: MEMORY_SAVED_NOTE,
      }
    }
    // #381: exact text only; several matches write nothing and come back as candidates for the user to pick
    if (args.action === 'correct') { const r = await correct([{ old: String(args.old ?? ''), new: String(args.new ?? '') }], t('botCommands.chat')); return { corrected: r.changed, ...(r.candidates ? { ambiguous: r.candidates.map((m) => m.text), note: 'several memories match; the user is choosing one, nothing was changed' } : {}), ...(r.rejected ? { rejected: r.rejected } : {}) } }
    if (args.action === 'forget') { const r = await forget([String(args.text ?? '')], t('botCommands.chat')); return { forgotten: r.changed, ...(r.candidates ? { ambiguous: r.candidates.map((m) => m.text), note: 'several memories match; the user is choosing one, nothing was changed' } : {}), ...(r.rejected ? { rejected: r.rejected } : {}) } }
    throw new Error('action must be list, add, correct or forget')
  },
  skill: async (_editor, args) => skillTool(args),
}
