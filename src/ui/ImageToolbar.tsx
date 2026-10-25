import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { ALL_TOOLS, DEFAULT_PINNED, MENU_GEN, MENU_MAIN, MORE_TOOLS, isFixed, migratePrefs, withFixed, type BarPrefs } from './toolbarPrefs'
import { createPortal } from 'react-dom'
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
import { useEscape } from './escape'

const GAP = 22
const EDGE = 8
const AUTO_LAYERS = 4
const BAR_KEY = 'comfyart.toolbar'
function readPrefs(): BarPrefs { return migratePrefs(readLocal(BAR_KEY)) }

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
  const [moreTools, setMoreTools] = useState(false)
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
  const toggle = (m: string) => (o: boolean) => { setMenu(o ? m : null); setInMore(null); setMoreTools(false) }
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
  const menuItem = (t: Tool) => <Item key={t.id} icon={t.icon} label={t.label} onClick={t.menu ? () => setInMore(t.id) : close(t.run!)} />
  const groups = [MENU_MAIN, MENU_GEN].map((ids) => unpinned.filter((t) => ids.includes(t.id)))
  const moreList = unpinned.filter((t) => MORE_TOOLS.includes(t.id))

  return (
    <div ref={bar} className="ca-bar ca-toolbar" style={{ left, top }} onPointerDown={(e) => e.stopPropagation()}>
      {pinned.map(barTool)}
      <Popover open={menu === 'more'} onOpenChange={toggle('more')} align="end" bar=".ca-toolbar" contentKey={inMore ?? (moreTools ? 'tools' : '')} trigger={({ open, toggle: flip }) => <Btn icon={Icons.more} hint={t('imageToolbar.more')} open={open} onClick={flip} />}>
        {moreView?.menu ? moreView.menu : (
        <div className="ca-menu ca-menu--image">
          {frame?.type === 'frame' && <Item icon={Icons.frame} label={t('imageToolbar.fillArtboard')} onClick={close(() => fitFrame(true))} />}
          {frame?.type === 'frame' && <Item icon={Icons.frame} label={t('imageToolbar.fitArtboard')} onClick={close(() => fitFrame(false))} />}
          {originalOf(shape) && <Item icon={Icons.restore} label={t('imageToolbar.restoreOriginal')} onClick={close(() => restoreOriginal(editor, shape))} />}
          {groups.map((g, i) => g.length > 0 && (
            <div key={i} className="ca-menu__group">
              {(i > 0 || frame?.type === 'frame' || !!originalOf(shape)) && <div className="ca-menu__sep" />}
              {g.map(menuItem)}
            </div>
          ))}
          {moreList.length > 0 && <>
            <div className="ca-menu__sep" />
            <button type="button" className="ca-menu__item ca-menu__sub" aria-expanded={moreTools} data-open={moreTools || undefined} onClick={() => setMoreTools(!moreTools)}>
              <span className="ca-icon">{Icons.more}</span><span className="ca-menu__grow">{t('imageToolbar.moreTools')}</span><span className="ca-icon ca-menu__chev">{Icons.chevron}</span>
            </button>
            {moreTools && <div className="ca-menu__nested">{moreList.map(menuItem)}</div>}
          </>}
          <div className="ca-menu__sep" />
          <Item icon={Icons.grid} label={t('imageToolbar.customizeToolbar')} onClick={() => { setMenu(null); setCustomize(true) }} />
        </div>
        )}
      </Popover>
      <div className="ca-bar__sep" />
      <Btn icon={Icons.download} hint={t('common.download')} onClick={() => download(src, name)} />
      {customize && createPortal(<CustomizeDialog tools={tools} onClose={() => setCustomize(false)} />, document.body)}
    </div>
  )
}

function PreviewBtn({ tool, names, hints, onUnpin }: { tool: Tool; names: boolean; hints: boolean; onUnpin: () => void }) {
  const fixed = isFixed(tool.id)
  return (
    <span className={`ca-bar__btn ca-cz__tool${fixed ? '' : ' ca-cz__tool--rm'}`} data-tool={tool.id} title={names ? undefined : tool.label}>
      <span className="ca-icon">{tool.icon}</span>
      {names && <span className="ca-cz__label">{tool.label}{hints && tool.hint && <span className="ca-bar__hint">{tool.hint}</span>}</span>}
      {!fixed && <button type="button" className="ca-cz__x" title={t('imageToolbar.unpin')} aria-label={`${t('imageToolbar.unpin')} ${tool.label}`} onClick={onUnpin}>{Icons.close}</button>}
    </span>
  )
}

export function CustomizeDialog({ tools, onClose }: { tools: Tool[]; onClose: () => void }) {
  const init = prefsAtom.get()
  const [pinned, setPinned] = useState<string[]>(init.pinned)
  const [names, setNames] = useState(init.names)
  const [fit, setFit] = useState(0)
  const barRef = useRef<HTMLDivElement>(null)
  useEscape(true, onClose)
  const byId = new Map(tools.map((x) => [x.id, x]))
  const cards = ALL_TOOLS.map((id) => byId.get(id)).filter((x): x is Tool => !!x)
  const shown = cards.filter((x) => pinned.includes(x.id) && x.when !== false)
  const fixedShown = shown.filter((x) => isFixed(x.id))
  const btn = (x: Tool) => <PreviewBtn key={x.id} tool={x} names={names && fit < 2} hints={fit < 1} onUnpin={() => flip(x.id)} />
  const flip = (id: string) => !isFixed(id) && setPinned((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))
  const save = () => { setPrefs({ pinned: withFixed(pinned), names }); onClose() }
  useLayoutEffect(() => setFit(0), [pinned, names])
  useEffect(() => { void document.fonts?.ready.then(() => setFit(0)) }, [])
  useLayoutEffect(() => {
    const el = barRef.current
    if (fit >= 2 || !el?.parentElement) return
    // measure children, not scrollWidth
    const cs = getComputedStyle(el), kids = [...el.children] as HTMLElement[]
    const need = kids.reduce((a, c) => a + c.offsetWidth, 0) + (parseFloat(cs.columnGap) || 0) * Math.max(0, kids.length - 1) + parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight) + parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth)
    if (need > el.parentElement.clientWidth - 16 + 0.5) setFit(fit + 1)
  })
  return (
    <div className="ca-modal ca-cz-modal" onPointerDown={(e) => { e.stopPropagation(); if (e.target === e.currentTarget) onClose() }}>
      <div className="ca-modal__card ca-cz" role="dialog" aria-modal="true" aria-label={t('imageToolbar.customizeToolbar')}>
        <div className="ca-cz__head">
          <div>
            <div className="ca-cz__title">{t('imageToolbar.customizeToolbar')}</div>
            <div className="ca-cz__sub">{t('imageToolbar.chooseToolsToShowOn')}</div>
          </div>
          <button type="button" className="ca-panel__icon ca-cz__reset" title={t('imageToolbar.restoreDefaults')} onClick={() => { setPinned(DEFAULT_PINNED); setNames(true) }}>{Icons.resetCcw}</button>
          <button type="button" className="ca-panel__icon" title={t('common.close')} onClick={onClose}>{Icons.close}</button>
        </div>
        <div className="ca-cz__preview">
          <div ref={barRef} className="ca-bar ca-cz__bar">
            {fixedShown.map(btn)}
            {fixedShown.length > 0 && <div className="ca-bar__sep" />}
            {shown.filter((x) => !isFixed(x.id)).map(btn)}
            <span className="ca-bar__btn" title={t('imageToolbar.more')}><span className="ca-icon">{Icons.more}</span></span>
            <div className="ca-bar__sep" />
            <span className="ca-bar__btn" title={t('common.download')}><span className="ca-icon">{Icons.download}</span></span>
          </div>
        </div>
        <div className="ca-cz__grid">
          {cards.map((x) => {
            const on = pinned.includes(x.id)
            return (
              <button key={x.id} type="button" className="ca-cz__card" data-tool={x.id} aria-pressed={on} aria-disabled={isFixed(x.id) || undefined} onClick={() => flip(x.id)}>
                <span className="ca-icon">{x.icon}</span><span className="ca-menu__grow">{x.label}</span>
                <span className="ca-icon ca-cz__pin" data-on={on || undefined}>{on ? Icons.pinSolid : Icons.pinOutline}</span>
              </button>
            )
          })}
        </div>
        <div className="ca-cz__foot">
          <label className="ca-cz__switch"><input type="checkbox" role="switch" checked={names} onChange={(e) => setNames(e.target.checked)} /><span className="ca-cz__track" />{t('imageToolbar.showToolNames')}</label>
          <span className="ca-menu__grow" />
          <button type="button" className="ca-panel__secondary ca-cz__btn" onClick={onClose}>{t('common.cancel')}</button>
          <button type="button" className="ca-panel__primary ca-cz__btn" onClick={save}>{t('common.save')}</button>
        </div>
      </div>
    </div>
  )
}
