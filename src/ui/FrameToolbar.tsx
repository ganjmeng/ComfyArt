import { zipSync } from 'fflate'
import { useLayoutEffect, useRef, useState } from 'react'
import { useActions, useEditor, useValue, type Box, type Editor, type JsonObject, type TLFrameShape, type TLShape, type TLShapeId } from 'tldraw'

import { openChat } from '../bot'
import { refLinkedOf, setRefLinked } from '../chatFrame'
import { isBoard, renderBoard } from '../compose'
import { chatViewAtom } from './AgentPanel'
import { ComposePanel } from './ComposePanel'
import { createGenerator } from '../generate'
import { errorText, mediaAsset } from '../jobs'
import { download } from '../psd'
import { artboardStyle, type ArtboardStyle } from '../shapes/ArtboardShape'
import type { GeneratorShape } from '../shapes/GeneratorShape'
import { ColorPicker } from './ColorPicker'
import { exportAtom } from './ExportDialog'
import { slideshowAtom } from './Slideshow'
import { Icons } from './icons'
import { Popover } from './Popover'
import { useOnlySelected, useSelectionRect } from './selection'
import { Num, Section } from './StyleToolbars'
import { t } from '../i18n'

const GAP = 22
const EDGE = 8
const PAD = 24
const GEN_LONG = 1536
const SIZE_PRESETS: [string, number, number][] = [
  ['Instagram', 1080, 1080], [t('frameToolbar.instagramPortrait'), 1080, 1350], [t('frameToolbar.story'), 1080, 1920],
  [t('frameToolbar.youtubeThumbnail'), 1280, 720], [t('frameToolbar.presentation'), 1920, 1080],
  [t('frameToolbar.desktopWeb'), 1440, 1024], [t('frameToolbar.mobile'), 390, 844],
  ['A4', 2480, 3508], [t('frameToolbar.a4Landscape'), 3508, 2480],
]

type Sizing = 'fixed' | 'hug'
const sizingOf = (frame: TLFrameShape, axis: 'w' | 'h') => ((frame.meta[axis === 'w' ? 'wMode' : 'hMode'] as Sizing | undefined) ?? 'fixed')
const isAuto = (frame: TLFrameShape) => frame.meta.layout === 'auto'

function childBoxes(editor: Editor, frame: TLFrameShape) {
  return editor.getSortedChildIdsForParent(frame.id).map((id) => ({ s: editor.getShape(id)!, b: editor.getShapePageBounds(id)! }))
}

function moveTo(editor: Editor, s: TLShape, b: Box, x: number, y: number) {
  const local = editor.getPointInParentSpace(s.id, { x: b.x, y: b.y })
  editor.updateShape({ id: s.id, type: s.type, x: s.x + x - local.x, y: s.y + y - local.y })
}

function autoLayout(editor: Editor, frame: TLFrameShape) {
  const items = childBoxes(editor, frame).sort((a, b) => a.b.y - b.b.y || a.b.x - b.b.x)
  if (!items.length) return
  // #282: the reference area never shrinks on drop: items wrap inside its current width and it only grows downward
  const keep = !!frame.meta.refFrame
  const fixedW = keep || sizingOf(frame, 'w') === 'fixed'
  const cols = Math.ceil(Math.sqrt(items.length))
  const rows: typeof items[] = []
  for (const item of items) {
    const row = rows.at(-1)
    const used = row ? row.reduce((n, r) => n + r.b.w + PAD, PAD) : PAD
    if (row && (fixedW ? used + item.b.w + PAD <= frame.props.w : row.length < cols)) row.push(item)
    else rows.push([item])
  }
  let y = PAD
  let width = 0
  for (const row of rows) {
    let x = PAD
    for (const { s, b } of row) {
      moveTo(editor, s, b, x, y)
      x += b.w + PAD
    }
    width = Math.max(width, x)
    y += Math.max(...row.map(({ b }) => b.h)) + PAD
  }
  if (keep) {
    editor.updateShape<TLFrameShape>({ id: frame.id, type: 'frame', props: { w: Math.max(frame.props.w, width), h: Math.max(frame.props.h, y) } })
    return
  }
  editor.updateShape<TLFrameShape>({ id: frame.id, type: 'frame', props: { ...(fixedW ? {} : { w: width }), ...(sizingOf(frame, 'h') === 'hug' || !fixedW ? { h: y } : {}) } })
}

function hugContent(editor: Editor, frame: TLFrameShape) {
  const items = childBoxes(editor, frame)
  if (!items.length) return
  const origin = editor.getShapePageBounds(frame.id)!
  const w = Math.max(...items.map(({ b }) => b.maxX - origin.x)) + PAD
  const h = Math.max(...items.map(({ b }) => b.maxY - origin.y)) + PAD
  editor.updateShape<TLFrameShape>({ id: frame.id, type: 'frame', props: { ...(sizingOf(frame, 'w') === 'hug' ? { w } : {}), ...(sizingOf(frame, 'h') === 'hug' ? { h } : {}) } })
}

function relayout(editor: Editor, frame: TLFrameShape) {
  if (isAuto(frame)) autoLayout(editor, frame)
  else if (sizingOf(frame, 'w') === 'hug' || sizingOf(frame, 'h') === 'hug') hugContent(editor, frame)
}

export function registerFrameRules(editor: Editor) {
  let busy = false
  const pending = new Set<TLShapeId>()
  const flush = () => {
    busy = true
    editor.run(() => {
      for (const id of pending) {
        const frame = editor.getShape<TLFrameShape>(id)
        if (frame) relayout(editor, frame)
      }
    }, { history: 'ignore' })
    pending.clear()
    busy = false
  }
  const touch = (shape: TLShape) => {
    if (busy) return
    const parent = editor.getShape(shape.parentId as TLShapeId)
    if (parent?.type !== 'frame') return
    const frame = parent as TLFrameShape
    if (!isAuto(frame) && sizingOf(frame, 'w') === 'fixed' && sizingOf(frame, 'h') === 'fixed') return
    if (!pending.size) queueMicrotask(flush)
    pending.add(frame.id)
  }
  const stops = [
    editor.sideEffects.registerBeforeChangeHandler('shape', (prev, next) => {
      const ratio = next.meta.ratio as number | null | undefined
      if (next.type !== 'frame' || !ratio || prev.type !== 'frame') return next
      const [p, n] = [(prev as TLFrameShape).props, (next as TLFrameShape).props]
      if (p.w === n.w && p.h === n.h) return next
      const byWidth = Math.abs(n.w / p.w - 1) >= Math.abs(n.h / p.h - 1)
      return { ...next, props: { ...n, ...(byWidth ? { h: n.w / ratio } : { w: n.h * ratio }) } } as typeof next
    }),
    editor.sideEffects.registerAfterChangeHandler('shape', (prev, next) => { touch(next); if (prev.parentId !== next.parentId) touch(prev) }),
    editor.sideEffects.registerAfterCreateHandler('shape', touch),
    editor.sideEffects.registerAfterDeleteHandler('shape', touch),
  ]
  return () => stops.forEach((stop) => stop())
}

async function childFiles(editor: Editor, frame: TLFrameShape) {
  const files: { name: string; blob: Blob }[] = []
  for (const id of editor.getSortedChildIdsForParent(frame.id)) {
    const asset = mediaAsset(editor, editor.getShape(id))
    if (asset) files.push({ name: asset.props.name || 'download', blob: await (await fetch(asset.props.src)).blob() })
  }
  return files
}

async function downloadChildren(editor: Editor, frame: TLFrameShape) {
  for (const f of await childFiles(editor, frame)) download(f.blob, f.name)
}

async function downloadZip(editor: Editor, frame: TLFrameShape) {
  const used = new Set<string>()
  const entries: Record<string, Uint8Array> = {}
  for (const f of await childFiles(editor, frame)) {
    const ext = f.blob.type.split('/')[1]?.replace('jpeg', 'jpg') || 'png'
    let name = `${f.name.replace(/[\\/:*?"<>|]/g, '_')}.${ext}`
    for (let i = 2; used.has(name); i++) name = `${f.name}-${i}.${ext}`
    used.add(name)
    entries[name] = new Uint8Array(await f.blob.arrayBuffer())
  }
  download(new Blob([zipSync(entries, { level: 0 }) as BlobPart]), `${frame.props.name || t('common.artboard')}.zip`)
}

export function framesOnPage(editor: Editor) {
  return editor.getCurrentPageShapes().filter((s): s is TLFrameShape => s.type === 'frame' && s.parentId === editor.getCurrentPageId())
    .sort((a, b) => a.y - b.y || a.x - b.x).map((s) => s.id)
}

function generateInto(editor: Editor, frame: TLFrameShape) {
  const { w, h } = frame.props
  const k = GEN_LONG / Math.max(w, h)
  const id = createGenerator(editor, false, { resolution: 'custom', cw: Math.round(w * k), ch: Math.round(h * k) }, false)
  editor.reparentShapes([id], frame.id)
  editor.updateShape<GeneratorShape>({ id, type: 'generator', x: 0, y: 0, props: { w, h } })
  editor.select(id)
}

export function FrameToolbar({ onError }: { onError: (msg: string) => void }) {
  const editor = useEditor()
  const actions = useActions()
  const frame = useOnlySelected<TLFrameShape>('frame')
  const rect = useSelectionRect()
  const bar = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [presets, setPresets] = useState(false)
  const linked = useValue('ref linked', () => refLinkedOf(editor), [editor])
  useLayoutEffect(() => {
    if (bar.current && bar.current.offsetWidth !== width) setWidth(bar.current.offsetWidth)
  })
  if (!frame || !rect) return null
  const host = editor.getContainer().getBoundingClientRect()
  const left = Math.min(Math.max((rect.l + rect.r) / 2 - width / 2, EDGE), host.width - width - EDGE)
  let top = rect.t - GAP - 44
  if (top < EDGE) top = rect.b + GAP
  const size = (key: 'w' | 'h', v: number) => v >= 16 && editor.updateShape<TLFrameShape>({ id: frame.id, type: 'frame', props: { [key]: v } })
  const ratio = frame.meta.ratio as number | undefined
  const lock = () => editor.updateShape<TLFrameShape>({ id: frame.id, type: 'frame', meta: { ...frame.meta, ratio: ratio ? null : frame.props.w / frame.props.h } })
  const setMeta = (meta: Record<string, string>) => {
    editor.updateShape<TLFrameShape>({ id: frame.id, type: 'frame', meta: { ...frame.meta, ...meta } })
    relayout(editor, editor.getShape<TLFrameShape>(frame.id)!)
  }
  const sizing = (axis: 'w' | 'h') => (
    <button type="button" className="ca-panel__chip" title={axis === 'w' ? t('frameToolbar.widthOptions') : t('frameToolbar.heightOptions')} onClick={() => setMeta({ [axis === 'w' ? 'wMode' : 'hMode']: sizingOf(frame, axis) === 'fixed' ? 'hug' : 'fixed' })}>
      {sizingOf(frame, axis) === 'fixed' ? t('frameToolbar.fixed') : t('frameToolbar.fit')}
    </button>
  )
  const style = artboardStyle(frame)
  const setStyle = (patch: ArtboardStyle) => editor.updateShape<TLFrameShape>({ id: frame.id, type: 'frame', meta: { ...frame.meta, style: { ...style, ...patch } as JsonObject } })
  const play = () => {
    const frames = framesOnPage(editor)
    slideshowAtom.set({ ids: frames, index: Math.max(0, frames.indexOf(frame.id)) })
  }

  return (
    <div ref={bar} className="ca-bar ca-toolbar" style={{ left, top }} onPointerDown={(e) => e.stopPropagation()}>
      {typeof frame.meta.chatId === 'string' && (
        <button type="button" className="ca-bar__btn" title={t('chatFrame.locateChatTip')} onClick={() => { chatViewAtom.set('open'); openChat(frame.meta.chatId as string).catch((e) => onError(errorText(e))) }}>
          <span className="ca-icon">{Icons.agent}</span><span>{t('chatFrame.locateChat')}</span>
        </button>
      )}
      {frame.meta.refFrame === true && (
        <button type="button" className="ca-bar__btn" data-on={linked || undefined} title={linked ? t('chatFrame.linkedTip') : t('chatFrame.linkTip')} onClick={() => setRefLinked(editor, !linked)}>
          <span className="ca-icon">{Icons.agent}</span><span>{linked ? t('chatFrame.linked') : t('chatFrame.link')}</span>
        </button>
      )}
      <input className="ca-frame__name" value={frame.props.name} placeholder={t('common.artboard')} onChange={(e) => editor.updateShape<TLFrameShape>({ id: frame.id, type: 'frame', props: { name: e.target.value } })} onKeyDown={(e) => e.stopPropagation()} />
      <label className="ca-num"><span>W</span><input type="number" value={Math.round(frame.props.w)} disabled={sizingOf(frame, 'w') === 'hug'} onChange={(e) => size('w', Number(e.target.value))} onKeyDown={(e) => e.stopPropagation()} /></label>
      {sizing('w')}
      <label className="ca-num"><span>H</span><input type="number" value={Math.round(frame.props.h)} disabled={sizingOf(frame, 'h') === 'hug'} onChange={(e) => size('h', Number(e.target.value))} onKeyDown={(e) => e.stopPropagation()} /></label>
      {sizing('h')}
      <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('frameToolbar.lockAspectRatio')} data-on={!!ratio || undefined} onClick={lock}><span className="ca-icon">{ratio ? Icons.lock : Icons.unlock}</span></button>
      <Popover
        open={presets}
        onOpenChange={setPresets}
        trigger={({ open, toggle }) => <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('frameToolbar.sizePresets')} data-open={open || undefined} onClick={toggle}><span className="ca-icon">{Icons.chevron}</span></button>}
      >
        <div className="ca-menu">
          {SIZE_PRESETS.map(([label, w, h]) => (
            <button key={label} type="button" className="ca-menu__item" onClick={() => { setPresets(false); editor.updateShape<TLFrameShape>({ id: frame.id, type: 'frame', props: { w, h }, meta: { ...frame.meta, ratio: ratio ? w / h : null } }) }}>
              <span className="ca-menu__grow">{label}</span><span className="ca-menu__key">{w} × {h}</span>
            </button>
          ))}
        </div>
      </Popover>
      <Section title={t('frameToolbar.style')} icon={<span className="ca-tools__dot" style={{ background: style.fill || '#FFFFFF', borderRadius: Math.min(style.radius ?? 0, 6) }} />}>
        <div className="ca-style__row">
          <ColorPicker value={style.fill ?? ''} title={t('styleToolbars.fill')} allowNone onChange={(c) => setStyle({ fill: c })} />
          <ColorPicker value={style.stroke ?? ''} title={t('styleToolbars.strokeColor')} allowNone onChange={(c) => setStyle({ stroke: c })} />
          <Num label={t('styleToolbars.cornerRadius')} value={style.radius ?? 0} onChange={(v) => setStyle({ radius: v })} />
        </div>
      </Section>
      <div className="ca-bar__sep" />
      <div className="ca-panel__chips" title={t('frameToolbar.layout')}>
        <button type="button" className="ca-panel__chip" data-on={isAuto(frame) || undefined} onClick={() => setMeta({ layout: 'auto' })}>{t('common.auto')}</button>
        <button type="button" className="ca-panel__chip" data-on={!isAuto(frame) || undefined} onClick={() => setMeta({ layout: 'manual' })}>{t('frameToolbar.manual')}</button>
      </div>
      <button type="button" className="ca-bar__btn" onClick={() => actions['fit-frame-to-content']?.onSelect('toolbar')}><span className="ca-icon">{Icons.expand}</span><span>{t('frameToolbar.hugContents')}</span></button>
      <button type="button" className="ca-bar__btn" onClick={() => generateInto(editor, frame)}><span className="ca-icon">{Icons.genImage}</span><span>{t('common.generate')}</span></button>
      {isBoard(frame) && <button type="button" className="ca-bar__btn" onClick={() => renderBoard(editor, frame, onError)}><span className="ca-icon">{Icons.replace}</span><span>{frame.meta.elements ? t('elements.rerender') : t('compose.render')}</span></button>}
      {isBoard(frame) && <ComposePanel frame={frame} />}
      <div className="ca-bar__sep" />
      <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('frameToolbar.playFullscreen')} onClick={play}><span className="ca-icon">{Icons.play}</span></button>
      <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('frameToolbar.batchDownload')} onClick={() => void downloadChildren(editor, frame).catch((e) => onError(String(e)))}><span className="ca-icon">{Icons.download}</span></button>
      <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('frameToolbar.downloadAsZip')} onClick={() => void downloadZip(editor, frame).catch((e) => onError(String(e)))}><span className="ca-icon">{Icons.files}</span></button>
      <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('frameToolbar.exportArtboard')} onClick={() => exportAtom.set([frame.id])}><span className="ca-icon">{Icons.export}</span></button>
    </div>
  )
}
