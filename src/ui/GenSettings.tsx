import { useCallback, useState } from 'react'

import { DURATIONS, QUALITIES, RATIOS, RESOLUTIONS, SHOTS, STYLES, VIDEO_RATIOS, VIDEO_RESOLUTIONS } from '../genOptions'
import { FEATURE_MODELS, IMAGE_FEATURES, type ModelDef, VIDEO_FEATURES } from '../models'
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

export function SettingsPill({ p, video, quality, tiers, caps, update }: { p: GeneratorShape['props']; video: boolean; quality: boolean; tiers?: string[]; caps?: ModelDef; update: Update }) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen} side="top" trigger={({ open: o, toggle }) => (
      <button type="button" className="ca-gen__pill" data-open={o || undefined} onClick={toggle}><span className="ca-gen__pilltext">{settingsSummary(p, video)}</span><span className="ca-gen__chev">{Icons.chevron}</span></button>
    )}>
      <GenSettings p={p} video={video} quality={quality} tiers={tiers} caps={caps} update={update} />
    </Popover>
  )
}

/**
 * Generator model menu (#95), in the upstream model-preferences style: an Auto switch (on by default; the
 * agent / feature default picks and the list is greyed), per-feature tabs and a flat list of name + one-line
 * description. The cost is only shown next to send. Quality tiers appear in the settings once a model is picked.
 */
export function ModelPill({ video, model, picks, onPick, onAuto }: {
  video: boolean; model: ModelDef; picks?: Record<string, string>
  onPick: (feature: string, id: string) => void; onAuto: (on: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  // without picks (chat composer) only the main feature's tab is shown
  const all = video ? VIDEO_FEATURES : IMAGE_FEATURES
  const tabs = picks ? all : all.slice(0, 1)
  const [tab, setTab] = useState(tabs[0])
  const feature = tabs.includes(tab) ? tab : tabs[0]
  const auto = !!model.auto
  const list = FEATURE_MODELS[feature] ?? []
  const current = feature === tabs[0] ? model.id : picks?.[feature] ?? list[0]?.id
  // keep the selected row in view when the (scrolling) menu opens
  const selected = useCallback((el: HTMLElement | null) => el?.scrollIntoView({ block: 'nearest' }), [])
  return (
    <Popover open={open} onOpenChange={setOpen} side="top" align="end" trigger={({ open: o, toggle }) => (
      <button type="button" className="ca-gen__pill" data-open={o || undefined} title={model.auto ? model.label : `${model.label} (${model.id})`} onClick={toggle}>
        <span className="ca-gen__pilltext">{model.label}</span><span className="ca-gen__chev">{Icons.chevron}</span>
      </button>
    )}>
      <div className="ca-menu ca-modelprefs ca-models" data-testid="model-menu">
        <div className="ca-modelprefs__head">
          <span className="ca-menu__grow">{t('genPanel.model')}</span>
          <span className="ca-chat__hint">{t('common.auto')}</span>
          <button type="button" className="ca-switch" role="switch" aria-checked={auto} data-on={auto || undefined} onClick={() => onAuto(!auto)}><span /></button>
        </div>
        <div className="ca-panel__chips">
          {tabs.map((f) => <button key={f} type="button" className="ca-panel__chip" data-on={f === feature || undefined} onClick={() => setTab(f)}>{t(`genPanel.feature.${f}`)}</button>)}
        </div>
        {auto && <div className="ca-chat__hint">{t('genPanel.autoDesc')}</div>}
        <div className="ca-models__list">
          {list.map((m) => {
            const on = !auto && m.id === current
            return (
              <button key={m.id} ref={on ? selected : undefined} type="button" className="ca-menu__item ca-modelprefs__row" disabled={auto} data-on={on || undefined} onClick={() => { onPick(feature, m.id); if (feature === tabs[0]) setOpen(false) }}>
                <span className="ca-menu__grow ca-model"><span>{m.label}</span><span className="ca-model__desc">{m.desc}</span></span>
                {on && <span className="ca-icon">{Icons.check}</span>}
              </button>
            )
          })}
        </div>
      </div>
    </Popover>
  )
}

export function GenSettings({ p, video, quality, tiers, caps, update }: { p: GeneratorShape['props']; video: boolean; quality: boolean; tiers?: string[]; caps?: ModelDef; update: Update }) {
  // only what the selected model's schema accepts (#95); no enum in the schema means the full list
  const only = <T,>(all: T[], ok?: T[]) => (ok?.length ? all.filter((v) => ok.map(String).includes(String(v))) : all)
  const ratios = only(video ? VIDEO_RATIOS : RATIOS, caps?.ratios)
  const shownRatios = ratios.length ? ratios : (video ? VIDEO_RATIOS : RATIOS)
  const durations = only(DURATIONS, caps?.durations)
  const vres = only(VIDEO_RESOLUTIONS, caps?.resolutions)
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
            {shownRatios.map((r) => (
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
          <Chips value={(vres.length ? vres : VIDEO_RESOLUTIONS).includes(p.resolution) ? p.resolution : (vres.length ? vres : VIDEO_RESOLUTIONS)[0]} options={(vres.length ? vres : VIDEO_RESOLUTIONS).map((r) => [r, r] as [string, string])} onPick={(r) => update({ resolution: r })} gen />
        </>
      )}
      <div className="ca-gen__label">{video ? t('common.duration') : t('genSettings.count')}</div>
      {video
        ? <Chips value={p.duration} options={(durations.length ? durations : DURATIONS).map((d) => [d, `${d}s`] as [number, string])} onPick={(d) => update({ duration: d })} gen />
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
          {!!tiers?.length && (
            <>
              <div className="ca-gen__label">{t('genPanel.tiers')}</div>
              <Chips value={p.quality} options={tiers.map((q) => [q, q[0].toUpperCase() + q.slice(1)] as [string, string])} onPick={(q) => update({ quality: q })} gen />
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
