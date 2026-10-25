import { useEffect, useRef, useState } from 'react'
import { useEditor, useValue } from 'tldraw'

import * as actions from '../actions'
import { regionSplit, separateRegions } from '../layers'
import { ocrLines, ocrStatusAtom, type OcrStatus } from '../llm'
import { AnglePreview, type AngleView } from './AnglePreview'
import { Icons } from './icons'
import { boxesAtom, brushAtom, exitMode, modeAtom, OWN_PANEL, padsAtom, strokesAtom, type Mode } from './mode'
import { useElementSize, useSelectedImage, useSelectionRect } from './selection'
import { t } from '../i18n'
import { usd } from '../usd'
import { featurePrice, loadCloudModels } from '../wavespeed'
import { isEnter } from './keys'
import { useEscape } from './escape'

const GAP = 12
const EDGE = 8
const PROMPT_MODES: Mode[] = ['quick']
const TITLES: Record<Mode, string> = {
  quick: t('common.quickEdit'), text: t('common.editText'), erase: t('common.eraser'), angles: t('common.multiAngle'), expand: t('common.expand'), animate: t('common.animateImage'), layers: t('imageToolbar.customSplit'), separate: t('imageToolbar.separateRegions'), adjust: t('common.adjust'), effects: t('common.effects'), inpaint: t('common.inpaint'), style: t('common.styleTransfer'), move: t('common.moveObject'), smudge: t('common.smudge'),
}
const RATIO_GROUPS: [string, [string, number][]][] = [
  [t('modePanel.general'), [[t('modePanel.free'), 0], [t('modePanel.original'), -1], [t('modePanel.square'), 1], [t('modePanel.landscape'), 16 / 9], [t('modePanel.portrait'), 9 / 16], ['4:3', 4 / 3], ['3:4', 3 / 4]]],
  [t('modePanel.socialMedia'), [[t('modePanel.post'), 4 / 5], [t('modePanel.story'), 9 / 16], [t('modePanel.coverPhoto'), 820 / 312], [t('modePanel.profilePicture'), 1], [t('modePanel.thumbnail'), 16 / 9]]],
]
const EXPAND_LIMIT = 4096
type AngleValue = { h: number; v: number; z: number }
const ANGLE_HOME: AngleValue = { h: 45, v: 0, z: 5 }
const ANGLE_PRESETS: [string, Partial<AngleValue>][] = [
  [t('modePanel.chipFrontLeft'), { h: 315, v: 0 }], [t('modePanel.chipFrontRight'), { h: 45, v: 0 }], [t('modePanel.left'), { h: 270, v: 0 }], [t('modePanel.right'), { h: 90, v: 0 }], [t('modePanel.back'), { h: 180, v: 0 }],
  [t('modePanel.top'), { v: 50 }], [t('modePanel.chipLow'), { v: -25 }], [t('modePanel.chipClose'), { z: 8 }], [t('modePanel.chipMed'), { z: 5 }], [t('modePanel.wide'), { z: 1 }],
]
const ALL_ANGLES = [315, 45, 270, 90]
const READ_AZ: [number, string][] = [
  [0, 'modePanel.front'], [45, 'modePanel.frontRight'], [90, 'modePanel.right'], [135, 'modePanel.backRight'],
  [180, 'modePanel.back'], [225, 'modePanel.backLeft'], [270, 'modePanel.left'], [315, 'modePanel.frontLeft'],
]

const wrap360 = (d: number) => ((d % 360) + 360) % 360

function angleReading(a: AngleValue): string {
  const az = wrap360(a.h)
  const dist = (n: number) => Math.min(Math.abs(az - n), 360 - Math.abs(az - n))
  const azKey = READ_AZ.reduce((best, cur) => (dist(cur[0]) < dist(best[0]) ? cur : best))[1]
  const elKey = a.v <= -15 ? 'modePanel.readLow' : a.v <= 15 ? 'modePanel.readLevel' : a.v <= 45 ? 'modePanel.readElevated' : 'modePanel.readHigh'
  const zoomKey = a.z >= 7 ? 'modePanel.readClose' : a.z >= 3 ? 'modePanel.readMedium' : 'modePanel.readWide'
  return `${t(azKey)} · ${t(elKey)} · ${t(zoomKey)}`
}

function presetOn(angle: AngleValue, patch: Partial<AngleValue>) {
  return patch.h !== undefined && Math.round(wrap360(angle.h)) === patch.h
}

function sliderText(n: number, step: number) {
  if (step >= 1) return String(Math.round(n))
  const r = Math.round(n * 10) / 10
  return Number.isInteger(r) ? String(r) : r.toFixed(1)
}

function ocrStatusText(status: OcrStatus | undefined): string {
  if (!status) return t('modePanel.detectingText')
  if (status.stage === 'queued') return t('modePanel.ocrQueued')
  if (status.stage === 'loading') return t('modePanel.ocrLoading')
  if (status.stage === 'agent') return t('modePanel.ocrAgent')
  return t('modePanel.ocrReading', status.tokens)
}

function Slider({ label, value, min, max, step = 1, onChange }: { label: string; value: number; min: number; max: number; step?: number; onChange: (v: number) => void }) {
  return (
    <label className="ca-panel__row">
      <span>{label}</span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <span className="ca-panel__val">{value}</span>
    </label>
  )
}

function AngleSlider({ label, value, min, max, step = 1, onChange }: { label: string; value: number; min: number; max: number; step?: number; onChange: (v: number) => void }) {
  const pct = ((value - min) / (max - min)) * 100
  return (
    <label className="ca-angle__row">
      <span className="ca-angle__lab"><span>{label}</span><span className="ca-angle__val">{sliderText(value, step)}</span></span>
      <input type="range" min={min} max={max} step={step} value={value} style={{ ['--p' as string]: `${pct}%` }} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  )
}

export function ModePanel({ onError }: { onError: (msg: string) => void }) {
  const editor = useEditor()
  const mode = useValue(modeAtom)
  const shape = useSelectedImage()
  const rect = useSelectionRect()
  const strokes = useValue(strokesAtom)
  const brush = useValue(brushAtom)
  const pads = useValue(padsAtom)
  const boxes = useValue(boxesAtom)
  const ocrStatus = useValue(ocrStatusAtom)
  const panel = useRef<HTMLDivElement>(null)
  const focus = useRef<HTMLTextAreaElement & HTMLInputElement>(null)
  const size = useElementSize(panel, { w: 280, h: 200 })
  const [prompt, setPrompt] = useState('')
  const [from, setFrom] = useState('')
  const [angle, setAngle] = useState(ANGLE_HOME)
  const [angleView, setAngleView] = useState<AngleView>('object')
  const [angleInset, setAngleInset] = useState(true)
  const [anglePrice, setAnglePrice] = useState<number | null>(null)
  const [layers, setLayers] = useState(4)
  const [ratio, setRatio] = useState(t('modePanel.free'))
  const [scale, setScale] = useState(1)
  const [loop, setLoop] = useState(true)
  const [lines, setLines] = useState<string[] | null>(null)
  const [edits, setEdits] = useState<string[]>([])

  useEffect(() => {
    setPrompt('')
    setFrom('')
    setRatio(t('modePanel.free'))
    setScale(1)
    requestAnimationFrame(() => focus.current?.focus())
  }, [mode])

  useEffect(() => {
    if (mode !== 'angles') return
    let live = true
    const read = () => setAnglePrice(featurePrice('change_angle'))
    if (featurePrice('change_angle') != null) read()
    else loadCloudModels().then(() => { if (live) read() }).catch(() => {})
    return () => { live = false }
  }, [mode])

  useEffect(() => {
    if (mode !== 'text' || !shape) return
    const src = shape.props.assetId ? editor.getAsset(shape.props.assetId)?.props.src : null
    let alive = true
    setLines(null)
    if (!src) { setLines([]); return }
    ocrLines(src)
      .then((found) => { if (alive) { setLines(found); setEdits(found) } })
      .catch(() => alive && setLines([]))
    return () => { alive = false }
  }, [mode, shape?.id])

  useEffect(() => {
    if (shape) return
    exitMode()
  }, [shape])

  useEscape(!!mode, exitMode)

  if (!mode || OWN_PANEL.includes(mode) || !shape || !rect) return null
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== 'image') return null
  const [iw, ih] = [asset.props.w, asset.props.h]

  const host = editor.getContainer().getBoundingClientRect()
  const below = PROMPT_MODES.includes(mode)
  let left: number
  let top: number
  if (below) {
    left = Math.min(Math.max(rect.l, EDGE), host.width - size.w - EDGE)
    top = rect.b + GAP
    if (top + size.h > host.height - 72) top = Math.max(EDGE, rect.t - size.h - GAP)
  } else {
    const s = (rect.r - rect.l) / iw
    const right = rect.r + (mode === 'expand' ? pads.r * s : 0)
    left = right + GAP + size.w > host.width - EDGE ? Math.max(EDGE, rect.l - size.w - GAP) : right + GAP
    top = Math.min(Math.max(rect.t, EDGE), host.height - size.h - EDGE)
    if (mode === 'angles') {
      const dock = editor.getContainer().querySelector('.ca-dock')
      const dockTop = dock ? dock.getBoundingClientRect().top - host.top : host.height
      const bottom = dockTop - GAP
      // Full panel, no scroll. Shift it up so the generate button clears the dock.
      top = Math.min(top, Math.max(EDGE, bottom - size.h))
    }
  }

  const textEdits = (): [string, string][] => (lines ?? []).flatMap((line, i) => ((edits[i] ?? '').trim() !== line ? [[line, (edits[i] ?? '').trim()] as [string, string]] : []))
  const tooBig = Math.max(iw + pads.l + pads.r, ih + pads.t + pads.b) > EXPAND_LIMIT
  const canSubmit = (() => {
    switch (mode) {
      case 'quick': return !!prompt.trim()
      case 'text': return lines?.length ? textEdits().length > 0 : !!from.trim() && !!prompt.trim()
      case 'erase': return strokes.length > 0
      case 'separate': return boxes.length > 0
      case 'expand': return pads.l + pads.t + pads.r + pads.b > 0 && !tooBig
      default: return true
    }
  })()

  const submit = () => {
    if (!canSubmit) return
    const text = prompt.trim()
    const runs: Partial<Record<Mode, () => unknown>> = {
      quick: () => actions.quickEdit(editor, shape, text, onError),
      text: () => actions.editText(editor, shape, lines?.length ? textEdits() : [[from.trim(), text]], onError),
      animate: () => actions.animate(editor, shape, text, onError, loop),
      erase: () => actions.erase(editor, shape, strokesAtom.get(), onError),
      angles: () => actions.angles(editor, shape, angle.h, angle.v, angle.z, onError),
      expand: () => actions.expand(editor, shape, padsAtom.get(), text, onError),
      layers: () => (boxesAtom.get().length ? regionSplit(editor, shape, boxesAtom.get(), onError) : actions.splitLayers(editor, shape, layers, text, onError)),
      separate: () => separateRegions(editor, shape, boxesAtom.get(), onError),
    }
    void runs[mode]?.()
    exitMode()
  }

  const fitPads = (r: number, k: number) => {
    const target = r < 0 ? iw / ih : r
    const tw = Math.max(iw, ih * target) * k
    const th = Math.max(ih, iw / target) * k
    const px = Math.round((tw - iw) / 2)
    const py = Math.round((th - ih) / 2)
    padsAtom.set({ l: px, r: px, t: py, b: py })
  }
  const pickRatio = ([label, r]: [string, number]) => {
    setRatio(label)
    if (r) fitPads(r, scale)
    else padsAtom.set({ l: 0, t: 0, r: 0, b: 0 })
  }
  const pickScale = (k: number) => {
    setScale(k)
    const r = RATIO_GROUPS.flatMap(([, list]) => list).find(([label]) => label === ratio)?.[1] || -1
    if (ratio === t('modePanel.free')) setRatio(t('modePanel.original'))
    fitPads(r, k)
  }
  const allAngles = () => {
    for (const h of ALL_ANGLES) actions.angles(editor, shape, h, angle.v, angle.z, onError)
    exitMode()
  }

  const keys = (e: React.KeyboardEvent) => {
    e.stopPropagation()
    if (isEnter(e) && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div
      ref={panel}
      className={mode === 'angles' ? 'ca-panel ca-panel--angle' : 'ca-panel'}
      data-wide={below || undefined}
      style={{ left, top }}
      onPointerDown={(e) => e.stopPropagation()}
      onWheel={(e) => e.stopPropagation()}
    >
      {below ? (
        <>
          <textarea ref={focus} className="ca-panel__prompt" value={prompt} placeholder={t('modePanel.howShouldThisImageChange')} onChange={(e) => setPrompt(e.target.value)} onKeyDown={keys} />
          <div className="ca-panel__foot">
            <button type="button" className="ca-panel__primary" disabled={!canSubmit} onClick={submit}>{t('common.generate')}</button>
          </div>
        </>
      ) : (
        <>
          <div className="ca-panel__head">
            <span>{TITLES[mode]}</span>
            {mode === 'angles' && (
              <span className="ca-angle__tools">
                <button type="button" className="ca-panel__icon ca-angle__reset" title={t('modePanel.reset')} aria-label={t('modePanel.reset')} onClick={() => setAngle(ANGLE_HOME)}>
                  {Icons.reset}
                </button>
                <button type="button" className="ca-angle__preview" aria-pressed={angleView === 'camera' && angleInset} onClick={() => { if (angleView !== 'camera') { setAngleView('camera'); setAngleInset(true); return } setAngleInset((on) => !on) }}>
                  {t('modePanel.shotPreview')}
                </button>
              </span>
            )}
            {mode === 'erase' && (
              <button type="button" className="ca-panel__icon" title={t('common.undo')} disabled={!strokes.length} onClick={() => strokesAtom.set(strokes.slice(0, -1))}>
                {Icons.undo}
              </button>
            )}
          </div>
          {mode === 'erase' && <Slider label={t('modePanel.brush')} value={brush} min={4} max={160} onChange={(v) => brushAtom.set(v)} />}
          {mode === 'text' && (lines === null ? (
            <div className="ca-chat__hint ca-panel__status">{ocrStatusText(ocrStatus[asset.props.src ?? ''])}</div>
          ) : lines.length ? (
            <div className="ca-panel__lines">
              {lines.map((line, i) => (
                <input key={i} className="ca-panel__input" value={edits[i] ?? ''} title={line} data-changed={(edits[i] ?? '').trim() !== line || undefined} onChange={(e) => setEdits(edits.map((x, j) => (j === i ? e.target.value : x)))} onKeyDown={keys} />
              ))}
            </div>
          ) : (
            <>
              <div className="ca-chat__hint">{t('modePanel.noTextFound')}</div>
              <input ref={focus} className="ca-panel__input" value={from} placeholder={t('modePanel.originalText')} onChange={(e) => setFrom(e.target.value)} onKeyDown={keys} />
              <input className="ca-panel__input" value={prompt} placeholder={t('modePanel.newText')} onChange={(e) => setPrompt(e.target.value)} onKeyDown={keys} />
            </>
          ))}
          {mode === 'animate' && (
            <>
              <textarea ref={focus} className="ca-panel__prompt ca-panel__prompt--boxed" value={prompt} placeholder={t('modePanel.describeTheMotionYouWant')} onChange={(e) => setPrompt(e.target.value)} onKeyDown={keys} />
              <label className="ca-panel__row ca-gen__toggle" title={t('modePanel.firstAndLastFramesMatch')}><span>{t('modePanel.loop')}</span><input type="checkbox" checked={loop} onChange={(e) => setLoop(e.target.checked)} /></label>
            </>
          )}
          {mode === 'angles' && (
            <>
              <div className="ca-angle__seg" role="tablist">
                <button type="button" role="tab" aria-selected={angleView === 'object'} data-on={angleView === 'object' || undefined} onClick={() => setAngleView('object')}>{t('modePanel.subject')}</button>
                <button type="button" role="tab" aria-selected={angleView === 'camera'} data-on={angleView === 'camera' || undefined} onClick={() => setAngleView('camera')}>{t('modePanel.camera')}</button>
              </div>
              <div className="ca-angle">
                <AnglePreview value={angle} src={asset.props.src ?? null} onChange={setAngle} view={angleView} inset={angleView === 'camera' && angleInset} />
                <div className="ca-angle__read">{angleReading(angle)}</div>
                <div className="ca-angle__chips">
                  {ANGLE_PRESETS.map(([label, patch]) => (
                    <button key={label} type="button" className="ca-angle__chip" data-on={presetOn(angle, patch) || undefined} onClick={() => setAngle({ ...angle, ...patch })}>{label}</button>
                  ))}
                </div>
                <AngleSlider label={t('modePanel.horizontal')} value={angle.h} min={0} max={359} onChange={(v) => setAngle({ ...angle, h: v })} />
                <AngleSlider label={t('modePanel.vertical')} value={angle.v} min={-30} max={60} onChange={(v) => setAngle({ ...angle, v })} />
                <AngleSlider label={t('modePanel.distance')} value={angle.z} min={0} max={10} step={0.1} onChange={(v) => setAngle({ ...angle, z: v })} />
                <button type="button" className="ca-angle__four" onClick={allAngles}>
                  {t('modePanel.generate4AnglesAtOnce')}
                  {anglePrice != null && <span className="ca-angle__fee">{`≈$${usd(anglePrice * ALL_ANGLES.length)}`}</span>}
                </button>
              </div>
            </>
          )}
          {mode === 'layers' && (
            <>
              <div className="ca-chat__hint">{boxes.length ? t('modePanel.areasSelectedEachWillBecome', boxes.length) : t('modePanel.drawBoxesAroundAreasTo')}</div>
              {!boxes.length && <Slider label={t('modePanel.layers')} value={layers} min={2} max={8} onChange={setLayers} />}
              <textarea className="ca-panel__prompt ca-panel__prompt--boxed" value={prompt} placeholder={t('modePanel.describeTheImageOptionalTo')} onChange={(e) => setPrompt(e.target.value)} onKeyDown={(e) => e.stopPropagation()} />
            </>
          )}
          {mode === 'separate' && <div className="ca-chat__hint">{t('modePanel.drawBoxToSeparate')}</div>}
          {mode === 'expand' && (
            <>
              {RATIO_GROUPS.map(([group, list]) => (
                <div key={group}>
                  <div className="ca-gen__label">{group}</div>
                  <div className="ca-panel__chips">
                    {list.map((r) => (
                      <button key={r[0]} type="button" className="ca-panel__chip" data-on={ratio === r[0] || undefined} onClick={() => pickRatio(r)}>{r[0]}</button>
                    ))}
                  </div>
                </div>
              ))}
              <Slider label={t('modePanel.scale')} value={scale} min={1} max={3} step={0.1} onChange={pickScale} />
              <div className="ca-chat__hint">{tooBig ? t('modePanel.finalSizeExceedsTheExpand') : `${iw + pads.l + pads.r} × ${ih + pads.t + pads.b}`}</div>
              <textarea className="ca-panel__prompt ca-panel__prompt--boxed" value={prompt} placeholder={t('modePanel.describeTheExpandedAreaOptional')} onChange={(e) => setPrompt(e.target.value)} onKeyDown={(e) => e.stopPropagation()} />
            </>
          )}
          <div className="ca-panel__foot">
            <button type="button" className="ca-panel__secondary" onClick={exitMode}>{t('common.cancel')}</button>
            <button type="button" className="ca-panel__primary" disabled={!canSubmit} onClick={submit}>
              {mode === 'erase' ? t('modePanel.erase') : mode === 'separate' ? t('modePanel.separate') : t('common.generate')}
              {mode === 'angles' && anglePrice != null && <span className="ca-angle__fee">{`≈$${usd(anglePrice)}`}</span>}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
