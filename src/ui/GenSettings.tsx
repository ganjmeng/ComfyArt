import { useState } from 'react'

import { DURATIONS, QUALITIES, RATIOS, RESOLUTIONS, SHOTS, STYLES, VIDEO_RATIOS, VIDEO_RESOLUTIONS } from '../genOptions'
import { isInstalled, type ModelDef } from '../models'
import type { GeneratorShape } from '../shapes/GeneratorShape'
import { Chips } from './Chips'
import { t } from '../i18n'
import { Icons } from './icons'
import { Popover } from './Popover'

const COUNTS = [1, 2, 3, 4]
const RES_LABELS: Record<string, string> = { '1K': '1K', '2K': '2K', custom: t('common.custom') }

function Dim({ label, value, onCommit }: { label: string; value: number; onCommit: (v: number) => void }) {
  const commit = (input: HTMLInputElement) => {
    const v = Math.round(Number(input.value))
    const next = input.value.trim() && Number.isFinite(v) ? Math.min(4096, Math.max(64, v)) : value
    input.value = String(next)
    if (next !== value) onCommit(next)
  }
  return (
    <label className="ca-num"><span>{label}</span><input key={value} type="number" min={64} max={4096} defaultValue={value} onBlur={(e) => commit(e.currentTarget)} onKeyDown={(e) => { e.stopPropagation(); if (e.key === 'Enter') e.currentTarget.blur() }} /></label>
  )
}

function RatioShape({ ratio }: { ratio: string }) {
  const [a, b] = ratio.split(':').map(Number)
  const k = 14 / Math.max(a, b)
  return <span className="ca-gen__shape" style={{ width: a * k, height: b * k }} />
}

export function settingsSummary(p: GeneratorShape['props'], video: boolean) {
  if (video) return `${p.ratio} · ${p.duration}s · ${VIDEO_RESOLUTIONS.includes(p.resolution) ? p.resolution : VIDEO_RESOLUTIONS[0]}${p.style ? ` · ${SHOTS.find(([k]) => k === p.style)?.[1]}` : ''}`
  const size = p.resolution === 'custom' ? `${p.cw}×${p.ch}` : `${p.resolution} · ${p.ratio}`
  return t('genSettings.summary', size, p.count, p.transparent ? t('genSettings.transparent') : '')
}

type Update = (patch: Partial<GeneratorShape['props']>) => void

export function SettingsPill({ p, video, quality, update }: { p: GeneratorShape['props']; video: boolean; quality: boolean; update: Update }) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen} side="top" trigger={({ open: o, toggle }) => (
      <button type="button" className="ca-gen__pill" data-open={o || undefined} onClick={toggle}><span className="ca-gen__pilltext">{settingsSummary(p, video)}</span><span className="ca-gen__chev">{Icons.chevron}</span></button>
    )}>
      <GenSettings p={p} video={video} quality={quality} update={update} />
    </Popover>
  )
}

export function ModelPill({ models, model, runOn, onPick }: { models: ModelDef[]; model: ModelDef; runOn?: string; onPick: (id: string) => void }) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen} side="top" align="end" trigger={({ open: o, toggle }) => (
      <button type="button" className="ca-gen__pill" data-open={o || undefined} onClick={toggle}>
        <span className="ca-gen__pilltext">{model.label}</span>{!isInstalled(model.id, runOn) && <span className="ca-model__tag">{t('modelPrefs.notInstalled')}</span>}<span className="ca-gen__chev">{Icons.chevron}</span>
      </button>
    )}>
      <div className="ca-menu ca-models">
        {models.map((m) => (
          <button key={m.id} type="button" className="ca-menu__item" onClick={() => { setOpen(false); onPick(m.id) }}>
            <span className="ca-menu__grow ca-model"><span>{m.label}{(m.refs || m.control) && <span className="ca-model__tag">{m.refs ? t('genPanel.tagReferences') : t('genPanel.tagStructure')}</span>}</span><span className="ca-model__desc">{m.desc}</span></span>
            {m.id === model.id && <span className="ca-icon">{Icons.check}</span>}
          </button>
        ))}
      </div>
    </Popover>
  )
}

export function GenSettings({ p, video, quality, update }: { p: GeneratorShape['props']; video: boolean; quality: boolean; update: Update }) {
  return (
    <div className="ca-menu ca-gen__settings">
      <div className="ca-gen__title">{video ? t('genSettings.videoSettings') : t('genSettings.imageSettings')}</div>
      {!video && (
        <>
          <div className="ca-gen__label">{t('genSettings.resolution')}</div>
          <Chips value={p.resolution} options={RESOLUTIONS.map((r) => [r, RES_LABELS[r]] as [string, string])} onPick={(r) => update({ resolution: r })} gen />
          {p.resolution === 'custom' && (
            <div className="ca-style__row">
              <Dim label="W" value={p.cw} onCommit={(cw) => update({ cw })} />
              <Dim label="H" value={p.ch} onCommit={(ch) => update({ ch })} />
            </div>
          )}
        </>
      )}
      {(video || p.resolution !== 'custom') && (
        <>
          <div className="ca-gen__label">{t('genSettings.aspectRatio')}</div>
          <div className="ca-gen__ratios">
            {(video ? VIDEO_RATIOS : RATIOS).map((r) => (
              <button key={r} type="button" className="ca-gen__ratio" data-on={p.ratio === r || undefined} onClick={() => update({ ratio: r })}>
                <RatioShape ratio={r} />
                <span>{r}</span>
              </button>
            ))}
          </div>
        </>
      )}
      {video && (
        <>
          <div className="ca-gen__label">{t('genSettings.resolution')}</div>
          <Chips value={VIDEO_RESOLUTIONS.includes(p.resolution) ? p.resolution : VIDEO_RESOLUTIONS[0]} options={VIDEO_RESOLUTIONS.map((r) => [r, r] as [string, string])} onPick={(r) => update({ resolution: r })} gen />
        </>
      )}
      <div className="ca-gen__label">{video ? t('common.duration') : t('genSettings.count')}</div>
      {video
        ? <Chips value={p.duration} options={DURATIONS.map((d) => [d, `${d}s`] as [number, string])} onPick={(d) => update({ duration: d })} gen />
        : <Chips value={p.count} options={COUNTS.map((n) => [n, String(n)] as [number, string])} onPick={(n) => update({ count: n })} gen />}
      {video && (
        <>
          <div className="ca-gen__label">{t('genSettings.cameraMotion')}</div>
          <Chips value={p.style} options={SHOTS.map(([k, label]) => [k, label] as [string, string])} onPick={(s) => update({ style: s })} gen />
        </>
      )}
      {!video && (
        <>
          {quality && (
            <>
              <div className="ca-gen__label">{t('genSettings.quality')}</div>
              <Chips value={p.quality} options={QUALITIES} onPick={(q) => update({ quality: q })} gen />
            </>
          )}
          <div className="ca-gen__label">{t('refModes.style')}</div>
          <Chips value={p.style} options={STYLES.map(([k, label]) => [k, label] as [string, string])} onPick={(s) => update({ style: s })} gen />
          <label className="ca-panel__row ca-gen__toggle"><span>{t('genSettings.transparentBackground')}</span><input type="checkbox" checked={p.transparent} onChange={(e) => update({ transparent: e.target.checked })} /></label>
        </>
      )}
    </div>
  )
}
