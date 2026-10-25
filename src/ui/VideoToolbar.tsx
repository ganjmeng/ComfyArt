import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useEditor, type TLVideoShape } from 'tldraw'

import * as actions from '../actions'
import { genInfoOf, remix } from '../generate'
import { DURATIONS } from '../genOptions'
import { VIDEO_TARGETS } from '../videoGraphs'
import { Icons } from './icons'
import { Popover } from './Popover'
import { useElementSize, useOnlySelected, useSelectionRect, type ScreenRect } from './selection'
import { videoEditorAtom } from './VideoEditor'
import { t } from '../i18n'
import { isEnter } from './keys'
import { useEscape } from './escape'

const GAP = 22
const EDGE = 8

type Mode = 'extend'
type Err = (msg: string) => void

function place(editor: ReturnType<typeof useEditor>, rect: ScreenRect, w: number, h: number) {
  const host = editor.getContainer().getBoundingClientRect()
  const left = Math.min(Math.max(rect.l, EDGE), host.width - w - EDGE)
  let top = rect.b + 12
  if (top + h > host.height - 72) top = Math.max(EDGE, rect.t - h - 34)
  return { left, top }
}

function ExtendPanel({ shape, rect, onClose, onError }: { shape: TLVideoShape; rect: ScreenRect; onClose: () => void; onError: Err }) {
  const editor = useEditor()
  const panel = useRef<HTMLDivElement>(null)
  const size = useElementSize(panel, { w: 480, h: 150 })
  const [prompt, setPrompt] = useState('')
  const [duration, setDuration] = useState(DURATIONS[0])

  const submit = () => {
    void actions.extendVideo(editor, shape, prompt.trim(), duration, onError)
    onClose()
  }
  const { left, top } = place(editor, rect, size.w, size.h)

  return (
    <div ref={panel} className="ca-panel" data-wide style={{ left, top }} onPointerDown={(e) => e.stopPropagation()} onWheel={(e) => e.stopPropagation()}>
      <textarea
        autoFocus
        className="ca-panel__prompt"
        value={prompt}
        placeholder={t('videoToolbar.describeWhatHappensNextOptional')}
        onChange={(e) => setPrompt(e.target.value)}
        onKeyDown={(e) => {
          e.stopPropagation()
          if (isEnter(e) && !e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
      />
      <div className="ca-panel__foot">
        <div className="ca-panel__chips">
          {DURATIONS.map((d) => (
            <button key={d} type="button" className="ca-panel__chip" data-on={duration === d || undefined} onClick={() => setDuration(d)}>+{d}s</button>
          ))}
        </div>
        <button type="button" className="ca-panel__primary" onClick={submit}>{t('common.generate')}</button>
      </div>
    </div>
  )
}

export function VideoToolbar({ onError }: { onError: Err }) {
  const editor = useEditor()
  const shape = useOnlySelected<TLVideoShape>('video')
  const rect = useSelectionRect()
  const bar = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [mode, setMode] = useState<Mode | null>(null)
  const [upscale, setUpscale] = useState(false)

  useLayoutEffect(() => {
    if (bar.current) setWidth(bar.current.offsetWidth)
  })

  useEffect(() => setMode(null), [shape?.id])

  useEscape(!!mode, () => setMode(null))

  if (!shape || !rect) return null
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== 'video' || !asset.props.src) return null
  const { src, name } = asset.props

  if (mode === 'extend') return <ExtendPanel shape={shape} rect={rect} onClose={() => setMode(null)} onError={onError} />

  const host = editor.getContainer().getBoundingClientRect()
  const left = Math.min(Math.max((rect.l + rect.r) / 2 - width / 2, EDGE), host.width - width - EDGE)
  let top = rect.t - GAP - 44
  if (top < EDGE) top = rect.b + GAP

  return (
    <div ref={bar} className="ca-bar ca-toolbar" style={{ left, top }} onPointerDown={(e) => e.stopPropagation()}>
      <button type="button" className="ca-bar__btn" onClick={() => videoEditorAtom.set(shape.id)}>
        <span className="ca-icon">{Icons.trim}</span><span>{t('videoToolbar.cropVideo')}</span>
      </button>
      <button type="button" className="ca-bar__btn" onClick={() => setMode('extend')}>
        <span className="ca-icon">{Icons.extend}</span><span>{t('common.extendVideo')}</span>
      </button>
      <Popover
        open={upscale}
        onOpenChange={setUpscale}
        trigger={({ open, toggle }) => (
          <button type="button" className="ca-bar__btn" data-open={open || undefined} onClick={toggle}>
            <span className="ca-icon">{Icons.upscale}</span><span>{t('common.upscale')}</span>
          </button>
        )}
      >
        <div className="ca-menu ca-menu--bar">
          {VIDEO_TARGETS.map(([label, long]) => {
            const over = Math.max(asset.props.w, asset.props.h) >= long
            return (
              <button key={label} type="button" className="ca-menu__item" disabled={over} title={over ? t('videoToolbar.theOriginalVideoAlreadyExceeds') : undefined} onClick={() => { setUpscale(false); actions.upscaleVideo(editor, shape, long, onError) }}>
                <span className="ca-menu__grow">{label}</span><span className="ca-menu__key">{over ? t('videoToolbar.exceeded') : `${Math.round(asset.props.w * long / Math.max(asset.props.w, asset.props.h))}×${Math.round(asset.props.h * long / Math.max(asset.props.w, asset.props.h))}`}</span>
              </button>
            )
          })}
        </div>
      </Popover>
      <button type="button" className="ca-bar__btn" onClick={() => actions.cutoutVideo(editor, shape, onError)}>
        <span className="ca-icon">{Icons.cutout}</span><span>{t('common.removeBackground')}</span>
      </button>
      {genInfoOf(shape)?.prompt && (
        <button type="button" className="ca-bar__btn" onClick={() => remix(editor, shape)}>
          <span className="ca-icon">{Icons.genVideo}</span><span>{t('imageToolbar.remix')}</span>
        </button>
      )}
      <div className="ca-bar__sep" />
      <a className="ca-bar__btn" href={src} download={name} title={t('common.download')}>
        <span className="ca-icon">{Icons.download}</span>
      </a>
    </div>
  )
}
