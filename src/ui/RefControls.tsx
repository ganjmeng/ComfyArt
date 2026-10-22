import { CONTROL_RESOLUTIONS, DEFAULT_CONTROL, type RefControl, type RefMode } from '../refModes'
import { Chips } from './Chips'
import { t } from '../i18n'

export function RefControls({ mode, value, onChange }: { src: string; mode: RefMode; value: RefControl | undefined; onChange: (c: RefControl) => void; onError: (msg: string) => void }) {
  const c = value ?? DEFAULT_CONTROL
  const set = (patch: Partial<RefControl>) => onChange({ ...c, ...patch })
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
    </div>
  )
}
