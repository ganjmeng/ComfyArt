/** #494-2 — a skill's OWN input dialog: every field, label, placeholder, default and required flag comes from the
 *  skill's `inputs[]`; the preset strip from `presets[]`. Nothing here names a skill. New component because main had
 *  no form that renders a data schema (SkillForm edits SKILL.md; the composer has no per-skill fields). Built on the
 *  shared Modal + the existing panel input / select / ref-tile classes. */
import { useState } from 'react'

import { uploadSkillImage, loc, missingInputs, presetImage, skillDefaults, skillPreset, skillRunParams, type Skill } from '../skills'
import { newProject } from '../projects'
import { t } from '../i18n'
import { Icons } from './icons'
import { Modal } from './Modal'

export function SkillRunDialog({ skill, presetId, onClose, onDetail, run = newProject }: {
  skill: Skill; presetId?: string | null; onClose: () => void; onDetail?: () => void
  /** injectable for tests; default leaves for a new project exactly like main's card click */
  run?: (params: Record<string, string | string[]>) => void
}) {
  const [values, setValues] = useState(() => skillDefaults(skill))
  const [preset, setPreset] = useState(() => skillPreset(skill, presetId)?.id ?? null)
  const [uploading, setUploading] = useState<string | null>(null)
  const missing = missingInputs(skill, values)
  const set = (key: string, v: string) => setValues((cur) => ({ ...cur, [key]: v }))
  const stop = (e: React.KeyboardEvent) => e.stopPropagation()
  return (
    <Modal title={skill.name} className="ca-rename ca-skillrun" onClose={onClose}>
      <div className="ca-rename__body ca-skillrun__body" data-testid="skill-run-dialog" data-skill={skill.id}>
        {!!skill.presets?.length && (
          <div className="ca-skillrun__presets" role="radiogroup" data-testid="skill-run-presets">
            {skill.presets.map((p) => {
              const img = presetImage(skill, p)
              return (
                <button key={p.id} type="button" role="radio" aria-checked={preset === p.id} data-on={preset === p.id || undefined}
                  className="ca-skillrun__preset" data-testid="skill-run-preset" data-preset={p.id} onClick={() => setPreset(p.id)}>
                  {img ? <img src={img} alt="" /> : <span className="ca-icon">{Icons.skill}</span>}
                  <span>{loc(p.name)}</span>
                </button>
              )
            })}
          </div>
        )}
        {(skill.inputs ?? []).map((f) => {
          const id = `skill-run-${f.key}`
          const label = <label className="ca-skillform__label" htmlFor={id}>{loc(f.label)}{f.required && <span className="ca-skillrun__req" aria-hidden="true"> *</span>}</label>
          const ph = f.placeholder ? loc(f.placeholder) : ''
          const common = { id, 'data-testid': 'skill-run-field', 'data-key': f.key, 'data-type': f.type, required: f.required, 'aria-required': f.required || undefined }
          if (f.type === 'select') return (
            <div key={f.key}>{label}
              <select {...common} className="ca-panel__input" value={values[f.key] ?? ''} onChange={(e) => set(f.key, e.target.value)} onKeyDown={stop}>
                {f.options?.map((o) => <option key={o.value} value={o.value}>{loc(o.label)}</option>)}
              </select>
            </div>
          )
          if (f.type === 'textarea') return (
            <div key={f.key}>{label}<textarea {...common} className="ca-panel__prompt ca-panel__prompt--boxed" rows={3} placeholder={ph} value={values[f.key] ?? ''} onChange={(e) => set(f.key, e.target.value)} onKeyDown={stop} /></div>
          )
          if (f.type === 'image') return (
            <div key={f.key}>{label}
              <div className="ca-gen__refs" {...common}>
                {values[f.key]
                  ? <span className="ca-gen__ref"><img src={values[f.key]} alt="" /><button type="button" title={t('common.remove')} onClick={() => set(f.key, '')}>{Icons.close}</button></span>
                  : <label className="ca-gen__refadd"><span className="ca-icon">{Icons.plus}</span><span>{uploading === f.key ? t('skillRun.uploading') : t('skillsDialog.addImage')}</span>
                      <input id={id} type="file" accept="image/*" hidden onChange={(e) => {
                        const file = e.target.files?.[0]; e.target.value = ''
                        if (!file) return
                        setUploading(f.key)
                        void uploadSkillImage(file, skill.id).then((src) => set(f.key, src)).finally(() => setUploading(null))
                      }} /></label>}
              </div>
            </div>
          )
          return <div key={f.key}>{label}<input {...common} className="ca-panel__input" placeholder={ph} value={values[f.key] ?? ''} onChange={(e) => set(f.key, e.target.value)} onKeyDown={stop} /></div>
        })}
      </div>
      <div className="ca-panel__foot">
        {onDetail && <button type="button" className="ca-panel__secondary" data-testid="skill-run-detail" onClick={onDetail}>{t('skillRun.detail')}</button>}
        <span className="ca-menu__grow" />
        <button type="button" className="ca-panel__secondary" onClick={onClose}>{t('common.cancel')}</button>
        <button type="button" className="ca-panel__primary" data-testid="skill-run-go" disabled={missing.length > 0 || !!uploading}
          onClick={() => run(skillRunParams(skill, values, preset))}>{t('skillRun.generate')}</button>
      </div>
    </Modal>
  )
}
