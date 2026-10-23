import { useState } from 'react'

import { errorText } from '../jobs'
import { CONTROL_RESOLUTIONS, DEFAULT_CONTROL, previewControl, type RefControl, type RefMode } from '../refModes'
import { Chips } from './Chips'
import { t } from '../i18n'

export function RefControls({ src, mode, value, onChange, onError }: { src: string; mode: RefMode; value: RefControl | undefined; onChange: (c: RefControl) => void; onError: (msg: string) => void }) {
  const c = value ?? DEFAULT_CONTROL
  const [preview, setPreview] = useState<{ key: string; url: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (patch: Partial<RefControl>) => onChange({ ...c, ...patch })
  const key = `${mode.id}:${c.res}`
  const extract = async () => {
    setBusy(true)
    try {
      setPreview({ key, url: await previewControl(src, mode, c.res) })
    } catch (e) {
      onError(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="ca-refctl">
      <label className="ca-panel__row"><span>{t('refControls.start')}</span><input type="range" min={0} max={c.end} value={c.start} onChange={(e) => set({ start: Number(e.target.value) })} /><span className="ca-panel__val">{c.start}%</span></label>
      <label className="ca-panel__row"><span>{t('refControls.end')}</span><input type="range" min={c.start} max={100} value={c.end} onChange={(e) => set({ end: Number(e.target.value) })} /><span className="ca-panel__val">{c.end}%</span></label>
      {mode.node && 'resolution' in mode.node[1] && (
        <div className="ca-panel__row">
          <span>{t('refControls.resolution')}</span>
          <Chips value={c.res} options={CONTROL_RESOLUTIONS.map((r) => [r, String(r)] as const)} onPick={(r) => set({ res: r })} gen />
        </div>
      )}
      <div className="ca-panel__row">
        <span>{t('refControls.fit')}</span>
        <div className="ca-gen__chips">
          <button type="button" className="ca-gen__chip" data-on={c.resize === 'crop' || undefined} onClick={() => set({ resize: 'crop' })}>{t('refControls.crop')}</button>
          <button type="button" className="ca-gen__chip" data-on={c.resize === 'stretch' || undefined} onClick={() => set({ resize: 'stretch' })}>{t('refControls.stretch')}</button>
        </div>
      </div>
      {mode.node && (
        <>
          <button type="button" className="ca-menu__item" disabled={busy} onClick={() => void extract()}>
            <span className="ca-menu__grow">{busy ? t('refControls.extracting') : preview ? t('refControls.reextract') : t('refControls.preview')}</span>
          </button>
          {preview && <img className="ca-refctl__preview" src={preview.url} alt="" data-stale={preview.key !== key || undefined} />}
        </>
      )}
    </div>
  )
}
