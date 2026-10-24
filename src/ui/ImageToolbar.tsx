import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { atom, useEditor, useValue, type Editor, type TLImageShape } from 'tldraw'

import * as actions from '../actions'
import { extractText } from '../agent'
import { imageTo3d } from '../assetGen'
import { openCanvasChat } from '../canvasChat'
import { editElements } from '../elements'
import { createMockup } from '../mockup'
import { genInfoOf, regenerate, remix } from '../generate'
import { originalOf, restoreOriginal } from '../imageOps'
import { errorText } from '../jobs'
import { TEXT, type TextShape } from '../shapes/TextShape'
import { vectorize } from '../vectorize'
import { exportAtom } from './ExportDialog'
import { Icons } from './icons'
import { infoAtom } from './InfoDialog'
import { lightboxAtom } from './Lightbox'
import { enterMode, modeAtom, type Mode } from './mode'
import { Popover } from './Popover'
import { UpscaleMenu } from './UpscaleMenu'
import { useSelectedImage, useSelectionRect } from './selection'
import { readLocal, writeLocal } from '../localPrefs'
import { t } from '../i18n'
import { copyText } from '../clipboard'
import { isEnter } from './keys'

const GAP = 22
const EDGE = 8
const AUTO_LAYERS = 4
const BAR_KEY = 'comfyart.toolbar'
const DEFAULT_PINNED = ['chat', 'quick', 'upscale', 'cutout', 'erase']
const ALL_TOOLS = ['chat', 'quick', 'upscale', 'cutout', 'erase', 'layers', 'text', 'angles', 'animate', 'move', 'expand', 'adjust', 'crop', 'vectorize', 'elements', 'mockup', 'to3d', 'transform', 'inpaint', 'style', 'ocr', 'effects', 'smudge', 'regenerate', 'remix', 'copyPrompt', 'info', 'preview', 'export']

interface BarPrefs { pinned: string[]; names: boolean; seen: string[] }

function readPrefs(): BarPrefs {
  try {
    const stored = JSON.parse(readLocal(BAR_KEY) ?? 'null') as Partial<BarPrefs> | null
    if (!stored?.pinned) return { pinned: DEFAULT_PINNED, names: stored?.names ?? true, seen: ALL_TOOLS }
    const seen = stored.seen ?? []
    return { pinned: [...stored.pinned, ...DEFAULT_PINNED.filter((id) => !seen.includes(id) && !stored.pinned!.includes(id))], names: stored.names ?? true, seen: ALL_TOOLS }
  } catch {
    return { pinned: DEFAULT_PINNED, names: true, seen: ALL_TOOLS }
  }
}

const prefsAtom = atom<BarPrefs>('image toolbar', readPrefs())

function setPrefs(patch: Partial<BarPrefs>) {
  prefsAtom.set({ ...prefsAtom.get(), ...patch })
  writeLocal(BAR_KEY, JSON.stringify(prefsAtom.get()))
}

interface Tool { id: string; icon: ReactNode; label: string; hint?: string; run?: () => void; menu?: ReactNode; when?: boolean }

function download(src: string, name: string) {
  const a = document.createElement('a')
  a.href = src
  a.download = name
  a.click()
}

function Btn({ icon, label, hint, open, onClick }: { icon: ReactNode; label?: string; hint?: string; open?: boolean; onClick: () => void }) {
  const names = useValue('tool names', () => prefsAtom.get().names, [])
  const shown = names ? label : undefined
  return (
    <button type="button" className="ca-bar__btn" data-open={open || undefined} title={shown ? undefined : label ?? hint} onClick={onClick}>
      <span className="ca-icon">{icon}</span>
      {shown && <span>{shown}{hint && <span className="ca-bar__hint">{hint}</span>}</span>}
    </button>
  )
}

function Item({ icon, label, onClick }: { icon: ReactNode; label: string; onClick: () => void }) {
  return (
    <button type="button" className="ca-menu__item" onClick={onClick}>
      <span className="ca-icon">{icon}</span><span>{label}</span>
    </button>
  )
}

function TransformMenu({ editor, shape }: { editor: Editor; shape: TLImageShape }) {
  const deg = Math.round((((shape.rotation * 180) / Math.PI) % 360 + 360) % 360)
  const [text, setText] = useState(String(deg))
  useEffect(() => setText(String(deg)), [deg])
  const rotateTo = (d: number) => editor.rotateShapesBy([shape.id], (d * Math.PI) / 180 - shape.rotation)
  const commit = () => (Number.isFinite(Number(text)) && text.trim() ? rotateTo(Number(text)) : setText(String(deg)))
  return (
    <div className="ca-menu ca-transform">
      <button type="button" className="ca-bar__btn" title={t('common.flipHorizontal')} onClick={() => editor.flipShapes([shape.id], 'horizontal')}><span className="ca-icon">{Icons.flipH}</span></button>
      <button type="button" className="ca-bar__btn" title={t('common.flipVertical')} onClick={() => editor.flipShapes([shape.id], 'vertical')}><span className="ca-icon">{Icons.flipV}</span></button>
      <button type="button" className="ca-bar__btn" title={t('imageToolbar.rotateLeft')} onClick={() => rotateTo(deg - 90)}><span className="ca-icon ca-transform__ccw">{Icons.rotate}</span></button>
      <button type="button" className="ca-bar__btn" title={t('canvasMenu.rotate90')} onClick={() => rotateTo(deg + 90)}><span className="ca-icon">{Icons.rotate}</span></button>
      <div className="ca-bar__sep" />
      <label className="ca-crop__field" title={t('imageToolbar.angle')}>
        <input className="ca-crop__input" value={text} inputMode="numeric" onChange={(e) => setText(e.target.value)} onBlur={commit} onKeyDown={(e) => { e.stopPropagation(); if (isEnter(e)) commit() }} />°
      </label>
    </div>
  )
}

export function registerCropRule(editor: Editor) {
  return editor.sideEffects.registerAfterChangeHandler('instance_page_state', (_, next) => {
    const { croppingShapeId: id, selectedShapeIds: sel } = next
    if (!id || (sel.length === 1 && sel[0] === id)) return
    editor.setCroppingShape(null)
    if (editor.isIn('select.crop')) editor.setCurrentTool('select.idle')
  })
}

export function ImageToolbar({ onError }: { onError: (msg: string) => void }) {
  const editor = useEditor()
  const shape = useSelectedImage()
  const rect = useSelectionRect()
  const mode = useValue(modeAtom)
  const bar = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [menu, setMenu] = useState<string | null>(null)
  const [inMore, setInMore] = useState<string | null>(null)
  const [customize, setCustomize] = useState(false)
  const prefs = useValue(prefsAtom)

  useLayoutEffect(() => {
    if (bar.current) setWidth(bar.current.offsetWidth)
  })

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !shape || modeAtom.get()) return
      if (e.target instanceof Element && e.target.closest('input, textarea, [contenteditable="true"]')) return
      e.preventDefault()
      e.stopPropagation()
      enterMode('quick')
    }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [shape])

  if (!shape || !rect || mode) return null
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== 'image' || !asset.props.src) return null
  const { src, name, w: iw, h: ih } = asset.props

  const host = editor.getContainer().getBoundingClientRect()
  const left = Math.min(Math.max((rect.l + rect.r) / 2 - width / 2, EDGE), host.width - width - EDGE)
  let top = rect.t - GAP - 44
  if (top < EDGE) top = rect.b + GAP

  const close = (fn: () => void) => () => { setMenu(null); fn() }
  const genInfo = genInfoOf(shape)
  const ocr = async () => {
    try {
      const text = await extractText(editor, shape)
      if (!text) throw new Error(t('imageToolbar.noTextDetected'))
      const b = editor.getShapePageBounds(shape)!
      editor.createShape<TextShape>({ type: TEXT, x: b.maxX + 40, y: b.y, props: { text, size: 24, autoSize: false, w: b.w } })
      void copyText(text).catch(() => undefined)
    } catch (e) {
      onError(errorText(e))
    }
  }
  const toggle = (m: string) => (o: boolean) => { setMenu(o ? m : null); setCustomize(false); setInMore(null) }
  const mode$ = (m: Mode) => () => enterMode(m)
  const frame = editor.getShape(shape.parentId as any)
  const fitFrame = (cover: boolean) => {
    if (frame?.type !== 'frame') return
    const { w: fw, h: fh } = frame.props as { w: number; h: number }
    const k = (cover ? Math.max : Math.min)(fw / shape.props.w, fh / shape.props.h)
    const [w, h] = [shape.props.w * k, shape.props.h * k]
    editor.updateShape<TLImageShape>({ id: shape.id, type: 'image', x: (fw - w) / 2, y: (fh - h) / 2, rotation: 0, props: { w, h } })
  }
  const tools: Tool[] = [
    { id: 'chat', icon: Icons.comment, label: t('canvasChat.chat'), hint: 'Shift Enter', run: () => openCanvasChat(editor) },
    { id: 'quick', icon: Icons.quick, label: t('common.quickEdit'), hint: 'Tab', run: mode$('quick') },
    { id: 'upscale', icon: Icons.upscale, label: t('common.upscale'), menu: <UpscaleMenu editor={editor} shape={shape} w={iw} h={ih} onDone={() => setMenu(null)} onError={onError} /> },
    {
      id: 'layers', icon: Icons.layers, label: t('common.splitLayers'), menu: (
        <div className="ca-menu">
          <Item icon={Icons.layers} label={t('imageToolbar.autoSplit')} onClick={close(() => actions.splitLayers(editor, shape, AUTO_LAYERS, '', onError))} />
          <Item icon={Icons.text} label={t('imageToolbar.customSplit')} onClick={close(mode$('layers'))} />
          <Item icon={Icons.box} label={t('imageToolbar.separateRegions')} onClick={close(mode$('separate'))} />
        </div>
      ),
    },
    { id: 'cutout', icon: Icons.cutout, label: t('common.removeBackground'), run: () => actions.cutout(editor, shape, onError) },
    { id: 'erase', icon: Icons.erase, label: t('common.eraser'), run: mode$('erase') },
    { id: 'text', icon: Icons.text, label: t('common.editText'), run: mode$('text') },
    { id: 'angles', icon: Icons.angles, label: t('common.multiAngle'), run: mode$('angles') },
    { id: 'animate', icon: Icons.animate, label: t('common.animateImage'), run: mode$('animate') },
    { id: 'expand', icon: Icons.expand, label: t('common.expand'), run: mode$('expand') },
    { id: 'inpaint', icon: Icons.lasso, label: t('common.inpaint'), run: mode$('inpaint') },
    { id: 'style', icon: Icons.effects, label: t('common.styleTransfer'), run: mode$('style') },
    { id: 'move', icon: Icons.hand, label: t('common.moveObject'), run: mode$('move') },
    { id: 'ocr', icon: Icons.textTool, label: t('imageToolbar.extractText'), run: () => void ocr() },
    { id: 'crop', icon: Icons.crop, label: t('imageToolbar.crop'), run: () => editor.setCroppingShape(shape.id) },
    { id: 'adjust', icon: Icons.adjust, label: t('common.adjust'), run: mode$('adjust') },
    { id: 'effects', icon: Icons.effects, label: t('common.effects'), run: mode$('effects') },
    { id: 'smudge', icon: Icons.doodle, label: t('common.smudge'), run: mode$('smudge') },
    { id: 'vectorize', icon: Icons.polygon, label: t('imageToolbar.vectorize'), run: () => void vectorize(editor, shape).catch((e) => onError(String(e))) },
    { id: 'elements', icon: Icons.textTool, label: t('imageToolbar.editElements'), run: () => editElements(editor, shape, onError) },
    { id: 'mockup', icon: Icons.box, label: t('mockup.title'), run: () => createMockup(editor, shape, onError) },
    {
      id: 'to3d', icon: Icons.cube, label: t('imageToolbar.imageTo3d'), menu: (
        <div className="ca-menu">
          <Item icon={Icons.cube} label="TRELLIS.2" onClick={close(() => imageTo3d(editor, shape, onError, 'trellis2'))} />
          <Item icon={Icons.cube} label="Pixal3D" onClick={close(() => imageTo3d(editor, shape, onError, 'pixal3d'))} />
        </div>
      ),
    },
    { id: 'transform', icon: Icons.rotate, label: t('imageToolbar.flipAndRotate'), menu: <TransformMenu editor={editor} shape={shape} /> },
    { id: 'regenerate', icon: Icons.replace, label: t('common.regenerate'), run: () => void regenerate(editor, shape, onError), when: !!genInfo?.prompt },
    { id: 'remix', icon: Icons.genImage, label: t('imageToolbar.remix'), run: () => remix(editor, shape), when: !!genInfo?.prompt },
    { id: 'copyPrompt', icon: Icons.skill, label: t('imageToolbar.copyPrompt'), run: () => void copyText(genInfo!.prompt!), when: !!genInfo?.prompt },
    { id: 'info', icon: Icons.files, label: t('imageToolbar.generationInfo'), run: () => infoAtom.set(shape.id) },
    { id: 'preview', icon: Icons.preview, label: t('canvasMenu.viewLarger'), run: () => lightboxAtom.set(shape.id) },
    { id: 'export', icon: Icons.export, label: t('canvasMenu.export'), run: () => exportAtom.set([shape.id]) },
  ]
  const usable = tools.filter((t) => t.when !== false).sort((a, b) => ALL_TOOLS.indexOf(a.id) - ALL_TOOLS.indexOf(b.id))
  const pinned = usable.filter((t) => prefs.pinned.includes(t.id))
  const unpinned = usable.filter((t) => !prefs.pinned.includes(t.id))
  const barTool = (t: Tool) => (t.menu
    ? <Popover key={t.id} open={menu === t.id} onOpenChange={toggle(t.id)} trigger={({ open, toggle: tg }) => <Btn icon={t.icon} label={t.label} open={open} onClick={tg} />}>{t.menu}</Popover>
    : <Btn key={t.id} icon={t.icon} label={t.label} hint={t.hint} onClick={t.run!} />)
  const moreView = tools.find((t) => t.id === inMore)
  const pin = (id: string) => {
    const list = prefsAtom.get().pinned
    setPrefs({ pinned: list.includes(id) ? list.filter((x) => x !== id) : [...list, id] })
  }

  return (
    <div ref={bar} className="ca-bar ca-toolbar" style={{ left, top }} onPointerDown={(e) => e.stopPropagation()}>
      {pinned.map(barTool)}
      <Popover open={menu === 'more'} onOpenChange={toggle('more')} align="end" contentKey={customize ? 'customize' : inMore ?? ''} trigger={({ open, toggle: flip }) => <Btn icon={Icons.more} hint={t('imageToolbar.more')} open={open} onClick={flip} />}>
        {customize ? (
          <div className="ca-menu ca-customize">
            <div className="ca-gen__label">{t('imageToolbar.chooseToolsToShowOn')}</div>
            {usable.map((t) => (
              <button key={t.id} type="button" className="ca-menu__item" onClick={() => pin(t.id)}>
                <span className="ca-icon">{t.icon}</span><span className="ca-menu__grow">{t.label}</span>
                <span className="ca-icon ca-customize__check">{prefs.pinned.includes(t.id) && Icons.check}</span>
              </button>
            ))}
            <div className="ca-menu__sep" />
            <button type="button" className="ca-menu__item" onClick={() => setPrefs({ names: !prefsAtom.get().names })}><span className="ca-menu__grow">{t('imageToolbar.showToolNames')}</span><span className="ca-icon ca-customize__check">{prefs.names && Icons.check}</span></button>
            <button type="button" className="ca-menu__item" onClick={() => setPrefs({ pinned: DEFAULT_PINNED, names: true })}><span className="ca-menu__grow">{t('imageToolbar.restoreDefaults')}</span></button>
          </div>
        ) : moreView?.menu ? moreView.menu : (
        <div className="ca-menu ca-menu--image">
          {unpinned.map((t) => <Item key={t.id} icon={t.icon} label={t.label} onClick={t.menu ? () => setInMore(t.id) : close(t.run!)} />)}
          {frame?.type === 'frame' && <Item icon={Icons.frame} label={t('imageToolbar.fillArtboard')} onClick={close(() => fitFrame(true))} />}
          {frame?.type === 'frame' && <Item icon={Icons.frame} label={t('imageToolbar.fitArtboard')} onClick={close(() => fitFrame(false))} />}
          {originalOf(shape) && <Item icon={Icons.restore} label={t('imageToolbar.restoreOriginal')} onClick={close(() => restoreOriginal(editor, shape))} />}
          <div className="ca-menu__sep" />
          <Item icon={Icons.grid} label={t('imageToolbar.customizeToolbar')} onClick={() => setCustomize(true)} />
        </div>
        )}
      </Popover>
      <div className="ca-bar__sep" />
      <Btn icon={Icons.download} hint={t('common.download')} onClick={() => download(src, name)} />
    </div>
  )
}
