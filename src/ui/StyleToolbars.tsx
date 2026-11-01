import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { useEditor, useValue, type TLImageShape, type TLShapeId } from 'tldraw'

import { thumbUrl } from '../comfy'
import { download } from '../psd'
import { richEditorAtom, richVersionAtom } from '../richText'
import { TEXT, type TextShape } from '../shapes/TextShape'
import { BLEND_MODES, VECTOR, type GradientStop, type VectorShape } from '../shapes/VectorShape'
import { ColorPicker } from './ColorPicker'
import { FieldSelect } from './FieldSelect'
import { FontPicker } from './FontPicker'
import { Icons } from './icons'
import { Popover } from './Popover'
import { useOnlySelected, useSelectionRect } from './selection'
import { Chips } from './Chips'
import { t } from '../i18n'

const GAP = 22
const EDGE = 8
const WEIGHTS: [number, string][] = [[100, 'Thin'], [300, 'Light'], [400, 'Regular'], [500, 'Medium'], [600, 'SemiBold'], [700, 'Bold'], [900, 'Black']]
const SIZES = [12, 14, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128, 160, 200]
const SIZE_NAMES: Record<number, string> = { 12: t('styleToolbars.small'), 16: t('common.default'), 20: t('styleToolbars.regular'), 32: t('styleToolbars.large'), 48: t('styleToolbars.xLarge'), 64: t('styleToolbars.xxLarge'), 96: t('styleToolbars.huge') }
const ALIGNS: [string, keyof typeof Icons][] = [['left', 'alignLeft'], ['center', 'alignCenterH'], ['right', 'alignRight']]
const DECORATIONS: [string, string][] = [['none', t('common.none')], ['underline', t('styleToolbars.underline')], ['line-through', t('styleToolbars.strikethrough')]]
const CASES: [string, string][] = [['none', t('styleToolbars.asTyped')], ['uppercase', t('styleToolbars.uppercase')], ['lowercase', t('styleToolbars.lowercase')], ['capitalize', t('styleToolbars.capitalize')]]
const FILLS: [string, string][] = [['solid', t('styleToolbars.solid')], ['linear', t('styleToolbars.linear')], ['radial', t('styleToolbars.radial')], ['image', t('common.image')]]
const STROKE_ALIGNS: [string, string][] = [['inside', t('styleToolbars.inside')], ['center', t('styleToolbars.center')], ['outside', t('styleToolbars.outside')]]
const DASHES: [string, string][] = [['solid', t('nativeStyleBar.solid')], ['dashed', t('nativeStyleBar.dashed')], ['dotted', t('nativeStyleBar.dotted')]]

export function Section({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      trigger={({ open: o, toggle }) => (
        <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={title} data-open={o || undefined} onClick={toggle}>{icon}</button>
      )}
    >
      <div className="ca-menu ca-bg ca-style">{children}</div>
    </Popover>
  )
}

function useBar(rect: ReturnType<typeof useSelectionRect>) {
  const editor = useEditor()
  const bar = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    if (bar.current && bar.current.offsetWidth !== width) setWidth(bar.current.offsetWidth)
  })
  if (!rect) return { bar, style: {} }
  const host = editor.getContainer().getBoundingClientRect()
  const left = Math.min(Math.max((rect.l + rect.r) / 2 - width / 2, EDGE), host.width - width - EDGE)
  let top = rect.t - GAP - 44
  if (top < EDGE) top = rect.b + GAP
  return { bar, style: { left, top } }
}

export function Pick<T extends string | number>({ value, options, label, onPick, width }: { value: T; options: [T, string][]; label: ReactNode; onPick: (v: T) => void; width?: number }) {
  const [open, setOpen] = useState(false)
  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      trigger={({ open: o, toggle }) => (
        <button type="button" className="ca-bar__btn ca-pick" style={{ minWidth: width }} data-open={o || undefined} onClick={toggle}>
          <span className="ca-menu__grow">{label}</span><span className="ca-icon ca-pick__chev">{Icons.chevron}</span>
        </button>
      )}
    >
      <div className="ca-menu ca-pick__menu">
        {options.map(([v, text]) => (
          <button key={String(v)} type="button" className="ca-menu__item" onClick={() => { setOpen(false); onPick(v) }}>
            <span className="ca-menu__grow">{text}</span>{v === value && <span className="ca-icon">{Icons.check}</span>}
          </button>
        ))}
      </div>
    </Popover>
  )
}

export function Num({ value, label, onChange, min = 0 }: { value: number; label: string; onChange: (v: number) => void; min?: number }) {
  return (
    <label className="ca-num">
      <span>{label}</span>
      <input
        type="number"
        min={min}
        value={Math.round(value)}
        onChange={(e) => { const v = Number(e.target.value); if (Number.isFinite(v) && v >= min) onChange(v) }}
        onKeyDown={(e) => e.stopPropagation()}
      />
    </label>
  )
}

async function downloadShape(editor: ReturnType<typeof useEditor>, id: TLShapeId, name: string) {
  const { blob } = await editor.toImage([id], { format: 'png', scale: 2, background: false })
  download(blob, `${name}.png`)
}

export function TextToolbar({ onError }: { onError: (msg: string) => void }) {
  const editor = useEditor()
  const shape = useOnlySelected<TextShape>(TEXT)
  const rect = useSelectionRect()
  const { bar, style } = useBar(rect)
  const [fontOpen, setFontOpen] = useState(false)
  const [more, setMore] = useState(false)
  const editing = useValue('text editing', () => !!shape && editor.getEditingShapeId() === shape.id, [editor, shape?.id])
  const rich = useValue(richEditorAtom)
  useValue(richVersionAtom)
  if (!shape || !rect) return null
  const p = shape.props
  const set = (patch: Partial<TextShape['props']>) => editor.updateShape<TextShape>({ id: shape.id, type: TEXT, props: patch })
  const run = editing && rich && !rich.state.selection.empty ? rich : null
  const marks = run?.getAttributes('textStyle') ?? {}
  const color = marks.color ?? p.color
  const font = String(marks.fontFamily ?? p.font).replace(/"/g, '')
  const size = parseFloat(marks.fontSize) || p.size
  const weight = run ? (run.isActive('bold') ? 700 : p.weight) : p.weight
  const setColor = (c: string) => (run ? run.chain().focus().setColor(c).run() : set({ color: c }))
  const setFont = (f: string) => (run ? run.chain().focus().setFontFamily(`"${f}"`).run() : set({ font: f }))
  const setSize = (s: number) => (run ? run.chain().focus().setFontSize(`${s}px`).run() : set({ size: s }))
  const setWeight = (w: number) => (run ? run.chain().focus()[w >= 600 ? 'setBold' : 'unsetBold']().run() : set({ weight: w }))
  const toggle = (mark: 'Bold' | 'Italic' | 'Underline') => rich?.chain().focus()[`toggle${mark}`]().run()

  return (
    <div ref={bar} className="ca-bar ca-toolbar" style={style} onPointerDown={(e) => e.stopPropagation()} onMouseDown={(e) => { if (editing && !(e.target instanceof HTMLInputElement)) e.preventDefault() }}>
      <ColorPicker value={color} title={t('styleToolbars.textColor')} onChange={(c) => c && setColor(c)} />
      <ColorPicker
        value={p.stroke}
        title={t('styleToolbars.stroke')}
        allowNone
        onChange={(c) => set({ stroke: c })}
        trigger={({ open, toggle }) => (
          <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('styleToolbars.stroke')} data-open={open || undefined} onClick={toggle}>
            <span className="ca-tools__ring" style={{ borderColor: p.stroke || 'var(--ca-muted)' }} />
          </button>
        )}
      />
      <div className="ca-bar__sep" />
      <Popover
        open={fontOpen}
        onOpenChange={setFontOpen}
        trigger={({ open, toggle }) => (
          <button type="button" className="ca-bar__btn ca-pick" style={{ minWidth: 130 }} data-open={open || undefined} onClick={toggle}>
            <span className="ca-menu__grow ca-pick__font" style={{ fontFamily: `"${font}"` }}>{font}</span><span className="ca-icon ca-pick__chev">{Icons.chevron}</span>
          </button>
        )}
      >
        <FontPicker value={[font]} onError={onError} onPick={([f]) => { setFontOpen(false); setFont(f) }} />
      </Popover>
      <Pick value={weight} width={100} label={WEIGHTS.find(([w]) => w === weight)?.[1] ?? weight} options={WEIGHTS} onPick={setWeight} />
      <Pick value={size} width={64} label={Math.round(size)} options={SIZES.map((s) => [s, SIZE_NAMES[s] ? `${s} · ${SIZE_NAMES[s]}` : String(s)])} onPick={setSize} />
      {editing && rich && (
        <>
          <button type="button" className="ca-bar__btn ca-bar__btn--icon ca-rich__mark" title={t('styleToolbars.bold')} data-on={rich.isActive('bold') || undefined} onClick={() => toggle('Bold')}><b>B</b></button>
          <button type="button" className="ca-bar__btn ca-bar__btn--icon ca-rich__mark" title={t('styleToolbars.italic')} data-on={rich.isActive('italic') || undefined} onClick={() => toggle('Italic')}><i>I</i></button>
          <button type="button" className="ca-bar__btn ca-bar__btn--icon ca-rich__mark" title={t('styleToolbars.underline')} data-on={rich.isActive('underline') || undefined} onClick={() => toggle('Underline')}><u>U</u></button>
        </>
      )}
      <div className="ca-bar__sep" />
      <Pick value={p.align} label={<span className="ca-icon">{Icons[ALIGNS.find(([a]) => a === p.align)?.[1] ?? 'alignLeft']}</span>} options={ALIGNS.map(([a]) => [a, { left: t('multiToolbar.alignLeft'), center: t('styleToolbars.center'), right: t('multiToolbar.alignRight') }[a]!] as [string, string])} onPick={(a) => set({ align: a })} />
      <Popover
        open={more}
        onOpenChange={setMore}
        trigger={({ open, toggle }) => (
          <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('styleToolbars.textSettings')} data-open={open || undefined} onClick={toggle}><span className="ca-icon">{Icons.spacing}</span></button>
        )}
      >
        <div className="ca-menu ca-bg ca-style">
          <div className="ca-gen__label">{t('styleToolbars.decoration')}</div>
          <Chips value={p.decoration} options={DECORATIONS} onPick={(v) => set({ decoration: v })} />
          <div className="ca-gen__label">{t('styleToolbars.case')}</div>
          <Chips value={p.transform} options={CASES} onPick={(v) => set({ transform: v })} />
          <Num label={t('styleToolbars.letterSpacing')} value={p.letter} min={-20} onChange={(v) => set({ letter: v })} />
          <label className="ca-num"><span>{t('styleToolbars.lineHeight')}</span>
            <input type="number" step={0.1} min={0.5} value={p.line} onChange={(e) => { const v = Number(e.target.value); if (v >= 0.5) set({ line: v }) }} onKeyDown={(e) => e.stopPropagation()} />
          </label>
        </div>
      </Popover>
      <div className="ca-bar__sep" />
      <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('common.download')} onClick={() => void downloadShape(editor, shape.id, p.text.slice(0, 20) || 'text')}>
        <span className="ca-icon">{Icons.download}</span>
      </button>
    </div>
  )
}


function fillPreview(p: VectorShape['props']) {
  const stops = [...p.stops].sort((a, b) => a.offset - b.offset).map((s) => `${s.color} ${Math.round(s.offset * 100)}%`).join(', ')
  if (p.fillType === 'linear') return `linear-gradient(${p.angle + 90}deg, ${stops})`
  if (p.fillType === 'radial') return `radial-gradient(${stops})`
  if (p.fillType === 'image' && p.image) return `center / cover url("${p.image}")`
  return p.fill
}

function FillEditor({ editor, p, set }: { editor: ReturnType<typeof useEditor>; p: VectorShape['props']; set: (patch: Partial<VectorShape['props']>) => void }) {
  const images = useValue('fill images', () => editor.getCurrentPageShapes().flatMap((s) => {
    const a = s.type === 'image' && (s as TLImageShape).props.assetId ? editor.getAsset((s as TLImageShape).props.assetId!) : null
    return a?.type === 'image' && a.props.src ? [a.props.src] : []
  }).filter((src, i, all) => all.indexOf(src) === i).slice(-15), [editor])
  const setStop = (i: number, patch: Partial<GradientStop>) => set({ stops: p.stops.map((s, j) => (j === i ? { ...s, ...patch } : s)) })
  return (
    <>
      <Chips value={p.fillType} options={FILLS} onPick={(v) => set({ fillType: v })} />
      {p.fillType === 'solid' && <div className="ca-style__row"><ColorPicker value={p.fill} title={t('common.color')} alpha onChange={(c) => c && set({ fill: c })} /></div>}
      {(p.fillType === 'linear' || p.fillType === 'radial') && (
        <>
          {p.stops.map((s, i) => (
            <div key={i} className="ca-style__row">
              <ColorPicker value={s.color} title={t('styleToolbars.stopColor')} alpha onChange={(c) => c && setStop(i, { color: c })} />
              <Num label={t('styleToolbars.position')} value={s.offset * 100} onChange={(v) => setStop(i, { offset: Math.min(100, v) / 100 })} />
              {p.stops.length > 2 && <button type="button" className="ca-panel__icon" title={t('common.delete')} onClick={() => set({ stops: p.stops.filter((_, j) => j !== i) })}>{Icons.close}</button>}
            </div>
          ))}
          <div className="ca-style__row">
            <button type="button" className="ca-panel__chip" onClick={() => set({ stops: [...p.stops, { offset: 0.5, color: p.stops.at(-1)?.color ?? p.fill }] })}>{t('styleToolbars.addStop')}</button>
            {p.fillType === 'linear' && <Num label={t('styleToolbars.angle')} value={p.angle} min={-360} onChange={(v) => set({ angle: v })} />}
          </div>
        </>
      )}
      {p.fillType === 'image' && (
        <div className="ca-mockpanel__grid">
          {images.map((src) => <button key={src} type="button" className="ca-mockpanel__cell" data-on={p.image === src || undefined} onClick={() => set({ image: src })}><img src={thumbUrl(src)} alt="" /></button>)}
        </div>
      )}
      <div className="ca-gen__label">{t('styleToolbars.blendMode')}</div>
      <FieldSelect
        value={p.blend}
        options={BLEND_MODES.map((m) => ({ id: m, label: m }))}
        onChange={(id) => set({ blend: id })}
        within=".ca-toolbar"
        menuClassName="ca-fieldselect__menu--toolbar"
        onKeyDown={(e) => e.stopPropagation()}
      />
    </>
  )
}

export function ShapeToolbar() {
  const editor = useEditor()
  const shape = useOnlySelected<VectorShape>(VECTOR)
  const rect = useSelectionRect()
  const { bar, style } = useBar(rect)
  const [lock, setLock] = useState(false)
  if (!shape || !rect) return null
  const p = shape.props
  const set = (patch: Partial<VectorShape['props']>) => editor.updateShape<VectorShape>({ id: shape.id, type: VECTOR, props: patch })
  const size = (key: 'w' | 'h', v: number) => {
    if (v < 1) return
    if (!lock) return set({ [key]: v })
    const k = v / p[key]
    set({ w: p.w * k, h: p.h * k })
  }

  return (
    <div ref={bar} className="ca-bar ca-toolbar" style={style} onPointerDown={(e) => e.stopPropagation()}>
      <Section title={t('styleToolbars.fill')} icon={<span className="ca-tools__dot" style={{ background: fillPreview(p) }} />}>
        <FillEditor editor={editor} p={p} set={set} />
      </Section>
      <Section title={t('styleToolbars.stroke')} icon={<span className="ca-tools__ring" style={{ borderColor: p.stroke || 'var(--ca-muted)' }} />}>
        <div className="ca-style__row">
          <ColorPicker value={p.stroke} title={t('styleToolbars.strokeColor')} allowNone alpha onChange={(c) => set({ stroke: c })} />
          <Num label={t('doodleBar.size')} value={p.strokeWidth} min={1} onChange={(v) => set({ strokeWidth: v })} />
        </div>
        <div className="ca-gen__label">{t('styleToolbars.position')}</div>
        <Chips value={p.strokeAlign} options={STROKE_ALIGNS} onPick={(v) => set({ strokeAlign: v })} />
        <div className="ca-gen__label">{t('styleToolbars.style')}</div>
        <Chips value={p.dash} options={DASHES} onPick={(v) => set({ dash: v })} />
      </Section>
      {p.kind === 'rect' && <Num label={t('styleToolbars.cornerRadius')} value={p.radius} onChange={(v) => set({ radius: v })} />}
      {(p.kind === 'polygon' || p.kind === 'star') && <Num label={p.kind === 'star' ? t('styleToolbars.points') : t('styleToolbars.sides')} value={p.sides} min={3} onChange={(v) => set({ sides: Math.min(v, 24) })} />}
      <div className="ca-bar__sep" />
      <Num label="W" value={p.w} min={1} onChange={(v) => size('w', v)} />
      <Num label="H" value={p.h} min={1} onChange={(v) => size('h', v)} />
      <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('styleToolbars.lockRatio')} data-on={lock || undefined} onClick={() => setLock(!lock)}>
        <span className="ca-icon">{Icons.link}</span>
      </button>
      <div className="ca-bar__sep" />
      <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('common.download')} onClick={() => void downloadShape(editor, shape.id, p.kind)}>
        <span className="ca-icon">{Icons.download}</span>
      </button>
    </div>
  )
}
