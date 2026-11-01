import { useEffect, useState, type ReactNode } from 'react'
import type { Editor, TLImageShape } from 'tldraw'

import * as actions from '../actions'
import { imageTo3d, MODEL3D_SPECS, type Model3d, type Model3dParam } from '../assetGen'
import { CUSTOM_MODEL3D } from '../customWorkflows'
import { Chips } from './Chips'
import { Pick } from './StyleToolbars'
import { Icons } from './icons'
import { t } from '../i18n'
import { estimateCost } from '../wavespeedKey'
import { uiCredits } from '../usd'

/** #570: the tool panel frame at the image's right (title + reset, body, 取消 / 立即使用 ⚡n). Upscale and 转 3D share it. */
/** Segmented switch shared by the #570 tool panels (to3d model, upscale mode and resolution). */
export function Seg<T extends string>({ label, value, options, onPick, attr = 'data-value' }: {
  label: string; value: T; options: { id: T; label: string; disabled?: boolean; title?: string }[]; onPick: (id: T) => void; attr?: string
}) {
  return (
    <div className="ca-seg" role="tablist" aria-label={label}>
      {options.map((o) => <button key={o.id} type="button" role="tab" className="ca-seg__btn" {...{ [attr]: o.id }} title={o.title} disabled={o.disabled} aria-selected={o.id === value} data-on={o.id === value || undefined} onClick={() => onPick(o.id)}>{o.label}</button>)}
    </div>
  )
}

export function ToolPanel({ tool, title, onReset, onCancel, onUse, credits, children }: {
  tool: string; title: string; onReset?: () => void; onCancel: () => void; onUse?: () => void; credits?: number | null; children: ReactNode
}) {
  return (
    <div className="ca-toolpanel" data-tool={tool} role="dialog" aria-label={title}>
      <div className="ca-toolpanel__head">
        <span className="ca-menu__grow">{title}</span>
        {onReset && <button type="button" className="ca-panel__icon" title={t('toolPanel.reset')} aria-label={t('toolPanel.reset')} onClick={onReset}>{Icons.resetCcw}</button>}
      </div>
      <div className="ca-toolpanel__body">{children}</div>
      <div className="ca-panel__foot ca-toolpanel__foot">
        <button type="button" className="ca-panel__secondary" onClick={onCancel}>{t('common.cancel')}</button>
        {onUse && <button type="button" className="ca-panel__primary" onClick={onUse}>{t('toolPanel.useNow')}{credits != null && <span className="ca-toolpanel__cost"> ⚡{credits}</span>}</button>}
      </div>
    </div>
  )
}

const initial = (ps: Model3dParam[]) => Object.fromEntries(ps.map((p) => [p.key, p.value]))

/** #570: 转 3D panel body — segmented model switch, preview, then the selected model's params from MODEL3D_SPECS. */
export function To3dPanel({ editor, shape, src, custom, onDone, onError }: { editor: Editor; shape: TLImageShape; src: string; custom?: string; onDone: () => void; onError: (msg: string) => void }) {
  const models = [...MODEL3D_SPECS, ...(custom ? [{ id: CUSTOM_MODEL3D as Model3d, label: custom.replace(/\.json$/, ''), params: [] as Model3dParam[] }] : [])]
  const [model, setModel] = useState<Model3d>(models[0].id)
  const spec = models.find((m) => m.id === model) ?? models[0]
  const [vals, setVals] = useState<Record<string, number>>(() => initial(spec.params))
  const [credits, setCredits] = useState<number | null>(null)
  useEffect(() => {
    let live = true
    void estimateCost({ feature: 'image_to_3d' }).then((e) => { if (live && e?.price != null) setCredits(uiCredits(e.price)) }).catch(() => undefined)
    return () => { live = false }
  }, [model])
  const pick = (id: Model3d) => { setModel(id); setVals(initial(models.find((m) => m.id === id)?.params ?? [])) }
  return (
    <ToolPanel tool="to3d" title={t('imageToolbar.imageTo3d')} credits={credits} onReset={() => pick(models[0].id)} onCancel={onDone}
      onUse={() => { onDone(); imageTo3d(editor, shape, onError, model, vals) }}>
      <Seg label={t('toolPanel.model')} attr="data-model" value={model} options={models.map((m) => ({ id: m.id, label: m.label }))} onPick={pick} />
      <div className="ca-toolpanel__preview"><img src={src} alt="" draggable={false} /></div>
      {spec.params.length > 0 && <div className="ca-toolpanel__params" data-count={spec.params.length}>
        {spec.params.map((p) => (
          <label key={p.key} className="ca-panel__row" data-param={p.key}>
            <span>{p.label}</span>
            <input type="range" min={p.min} max={p.max} step={p.step} value={vals[p.key] ?? p.value} onChange={(e) => setVals({ ...vals, [p.key]: Number(e.target.value) })} />
            <span className="ca-panel__val">{vals[p.key] ?? p.value}</span>
          </label>
        ))}
      </div>}
    </ToolPanel>
  )
}

const STYLES: [string, string][] = [
  [t('modePanel.general'), ''],
  [t('upscaleMenu.realisticPortrait'), 'realistic portrait photo, natural skin texture'],
  [t('common.anime'), 'anime style, clean line art'],
  [t('inpaintPanel.gameConceptArt'), 'game CG artwork'],
  [t('common.illustration'), 'artistic illustration'],
  [t('common.3d'), '3D render'],
]
const TARGETS: [string, number][] = [['2K', 2048], ['4K', 4096], ['8K', 8192]]

/** asPanel (#570 home handoff): the same controls inside the ToolPanel at the image's right — mode as the shared Seg, resolution as the app's Pick dropdown, height follows content, 取消 / 立即使用 ⚡n. */
export function UpscaleMenu({ editor, shape, w, h, onDone, onError, asPanel }: { editor: Editor; shape: TLImageShape; w: number; h: number; onDone: () => void; onError: (msg: string) => void; asPanel?: boolean }) {
  const [detail, setDetail] = useState(false)
  const [style, setStyle] = useState('')
  const [strength, setStrength] = useState(30)
  const long = Math.max(w, h)
  const usable = TARGETS.filter(([, target]) => target > long)
  const [pick, setPick] = useState(usable[0]?.[0] ?? '')
  const [credits, setCredits] = useState<number | null>(null)
  useEffect(() => {
    if (!asPanel) return
    let live = true
    void estimateCost({ feature: 'upscale_image' }).then((e) => { if (live && e?.price != null) setCredits(uiCredits(e.price)) }).catch(() => undefined)
    return () => { live = false }
  }, [asPanel])
  const go = (k: number) => {
    onDone()
    if (detail) actions.creativeUpscale(editor, shape, k, style, strength / 100, onError)
    else actions.upscale(editor, shape, k, onError)
  }
  const detailControls = detail && (
    <>
      <Chips value={style} options={STYLES.map(([label, value]) => [value, label] as const)} onPick={setStyle} />
      <label className="ca-panel__row"><span>{t('upscaleMenu.detailStrength')}</span><input type="range" min={10} max={70} value={strength} onChange={(e) => setStrength(Number(e.target.value))} /><span className="ca-panel__val">{strength}</span></label>
    </>
  )
  const modes = (
    <>
      <div className="ca-panel__chips">
        <button type="button" className="ca-panel__chip" data-on={!detail || undefined} onClick={() => setDetail(false)}>{t('upscaleMenu.faithfulToOriginal')}</button>
        <button type="button" className="ca-panel__chip" data-on={detail || undefined} onClick={() => setDetail(true)}>{t('upscaleMenu.enhanceDetails')}</button>
      </div>
      {detailControls}
    </>
  )
  if (asPanel) {
    const target = TARGETS.find(([label]) => label === pick)?.[1]
    const reset = () => { setDetail(false); setStyle(''); setStrength(30); setPick(usable[0]?.[0] ?? '') }
    return (
      <ToolPanel tool="upscale" title={t('common.upscale')} credits={credits} onReset={reset} onCancel={onDone} onUse={target ? () => go(target / long) : undefined}>
        <div className="ca-menu ca-upscale">
          <Seg label={t('toolPanel.mode')} attr="data-mode" value={detail ? 'detail' : 'faithful'} onPick={(id) => setDetail(id === 'detail')}
            options={[{ id: 'faithful', label: t('toolPanel.faithful') }, { id: 'detail', label: t('toolPanel.enhance') }]} />
          {detailControls}
          <div className="ca-toolpanel__res" data-res-pick title={t('toolPanel.resolution')}>
            <Pick value={pick} label={pick ? `${pick} ${Math.round(w * (target ?? 0) / long)}×${Math.round(h * (target ?? 0) / long)}` : t('toolPanel.resolution')} onPick={setPick}
              options={TARGETS.filter(([, tg]) => tg > long).map(([label, tg]) => [label, `${label} ${Math.round(w * tg / long)}×${Math.round(h * tg / long)}`] as [string, string])} />
          </div>
        </div>
      </ToolPanel>
    )
  }
  return (
    <div className="ca-menu ca-upscale">
      {modes}
      {TARGETS.map(([label, target]) => {
        const k = target / long
        return (
          <button key={label} type="button" className="ca-menu__item" disabled={target <= long} onClick={() => go(k)}>
            <span className="ca-menu__grow">{label}</span><span className="ca-menu__key">{Math.round(w * k)}×{Math.round(h * k)}</span>
          </button>
        )
      })}
    </div>
  )
}
