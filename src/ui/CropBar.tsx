import { useEffect, useRef, useState } from 'react'
import { useEditor, useValue, Vec, type Editor, type TLImageShape } from 'tldraw'

import { Icons } from './icons'
import { Popover } from './Popover'
import { useElementSize } from './selection'
import { t } from '../i18n'
import { isEnter } from './keys'

const EDGE = 8
const GAP = 16

interface Frac { x: number; y: number; w: number; h: number }

const PRESETS: [string, number, string][] = [
  ['free', 0, ''], ['original', -1, ''],
  ['1:1', 1, 'Instagram'], ['4:5', 4 / 5, 'Instagram'], ['3:4', 3 / 4, t('cropBar.xiaohongshu')], ['9:16', 9 / 16, 'Story · TikTok'],
  ['16:9', 16 / 9, 'YouTube'], ['2:3', 2 / 3, 'Pinterest'], ['3:2', 3 / 2, ''], ['1.91:1', 1.91, 'Facebook · X'],
]

const presetLabel = (id: string) => (id === 'free' ? t('cropBar.free') : id === 'original' ? t('cropBar.original') : id)

function fracOf(shape: TLImageShape): Frac {
  const c = shape.props.crop
  return c ? { x: c.topLeft.x, y: c.topLeft.y, w: c.bottomRight.x - c.topLeft.x, h: c.bottomRight.y - c.topLeft.y } : { x: 0, y: 0, w: 1, h: 1 }
}

function setFrac(editor: Editor, shape: TLImageShape, next: Frac) {
  const cur = fracOf(shape)
  const [fullW, fullH] = [shape.props.w / cur.w, shape.props.h / cur.h]
  const off = Vec.Rot({ x: (next.x - cur.x) * fullW, y: (next.y - cur.y) * fullH }, shape.rotation)
  editor.updateShape<TLImageShape>({
    id: shape.id, type: 'image', x: shape.x + off.x, y: shape.y + off.y,
    props: { w: fullW * next.w, h: fullH * next.h, crop: { topLeft: { x: next.x, y: next.y }, bottomRight: { x: next.x + next.w, y: next.y + next.h } } },
  })
}

function centered(cur: Frac, w: number, h: number): Frac {
  const clamp = (v: number, size: number) => Math.min(Math.max(v, 0), 1 - size)
  return { x: clamp(cur.x + cur.w / 2 - w / 2, w), y: clamp(cur.y + cur.h / 2 - h / 2, h), w, h }
}

function PxInput({ value, onCommit }: { value: number; onCommit: (v: number) => void }) {
  const [text, setText] = useState(String(value))
  useEffect(() => setText(String(value)), [value])
  const commit = () => {
    const v = Math.round(Number(text))
    if (v > 0) onCommit(v)
    else setText(String(value))
  }
  return (
    <input
      className="ca-crop__input"
      value={text}
      inputMode="numeric"
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { e.stopPropagation(); if (isEnter(e)) commit() }}
    />
  )
}

export function CropBar() {
  const editor = useEditor()
  const shape = useValue('cropping image', () => {
    const id = editor.getCroppingShapeId()
    const s = id ? editor.getShape(id) : null
    return s?.type === 'image' ? (s as TLImageShape) : null
  }, [editor])
  const rect = useValue('crop rect', () => {
    if (!shape) return null
    const b = editor.getShapePageBounds(shape.id)
    if (!b) return null
    const a = editor.pageToViewport({ x: b.minX, y: b.minY })
    const z = editor.pageToViewport({ x: b.maxX, y: b.maxY })
    return { l: a.x, t: a.y, r: z.x, b: z.y }
  }, [editor, shape?.id])
  const [preset, setPreset] = useState('free')
  const [open, setOpen] = useState(false)
  const bar = useRef<HTMLDivElement>(null)
  const size = useElementSize(bar, { w: 420, h: 44 })

  useEffect(() => setPreset('free'), [shape?.id])

  if (!shape || !rect) return null
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== 'image') return null
  const { w: iw, h: ih } = asset.props
  const cur = fracOf(shape)
  const [pw, ph] = [Math.round(cur.w * iw), Math.round(cur.h * ih)]
  const ratio = PRESETS.find(([id]) => id === preset)?.[1] ?? 0

  const apply = (id: string) => {
    setPreset(id)
    setOpen(false)
    const r = PRESETS.find(([p]) => p === id)![1]
    if (r === -1) return setFrac(editor, shape, { x: 0, y: 0, w: 1, h: 1 })
    if (!r) return
    const w = Math.min(iw, ih * r)
    setFrac(editor, shape, centered(cur, w / iw, w / r / ih))
  }
  const resize = (wpx: number, hpx: number) => {
    const w = Math.min(wpx, iw)
    const h = Math.min(hpx, ih)
    setFrac(editor, shape, centered(cur, w / iw, h / ih))
  }
  const setW = (v: number) => (ratio > 0 ? resize(Math.min(v, iw, ih * ratio), Math.min(v, iw, ih * ratio) / ratio) : resize(v, ph))
  const setH = (v: number) => (ratio > 0 ? resize(Math.min(v, ih, iw / ratio) * ratio, Math.min(v, ih, iw / ratio)) : resize(pw, v))
  const done = () => {
    editor.setCroppingShape(null)
    editor.setCurrentTool('select.idle')
  }

  const host = editor.getContainer().getBoundingClientRect()
  const left = Math.min(Math.max((rect.l + rect.r) / 2 - size.w / 2, EDGE), host.width - size.w - EDGE)
  let top = rect.b + GAP
  if (top + size.h > host.height - 72) top = Math.max(EDGE, rect.t - GAP - size.h)

  return (
    <div ref={bar} className="ca-bar ca-toolbar ca-crop" style={{ left, top }} onPointerDown={(e) => e.stopPropagation()}>
      <Popover
        open={open}
        onOpenChange={setOpen}
        trigger={({ open: o, toggle }) => (
          <button type="button" className="ca-bar__btn" data-open={o || undefined} onClick={toggle}>
            <span className="ca-icon">{Icons.crop}</span><span>{presetLabel(preset)}</span><span className="ca-icon">{Icons.chevron}</span>
          </button>
        )}
      >
        <div className="ca-menu ca-menu--bar">
          {PRESETS.map(([id, , hint]) => (
            <button key={id} type="button" className="ca-menu__item" onClick={() => apply(id)}>
              <span className="ca-menu__grow">{presetLabel(id)}</span>
              {hint && <span className="ca-menu__key">{hint}</span>}
              <span className="ca-icon ca-customize__check">{preset === id && Icons.check}</span>
            </button>
          ))}
        </div>
      </Popover>
      <div className="ca-bar__sep" />
      <label className="ca-crop__field">W<PxInput value={pw} onCommit={setW} /></label>
      <label className="ca-crop__field">H<PxInput value={ph} onCommit={setH} /></label>
      <span className="ca-crop__unit">px</span>
      <div className="ca-bar__sep" />
      <button type="button" className="ca-bar__btn" onClick={() => apply('original')}>{t('cropBar.reset')}</button>
      <button type="button" className="ca-bar__btn ca-crop__done" onClick={done}>{t('common.done')}</button>
    </div>
  )
}
