import { useEffect, useState } from 'react'
import { useValue } from 'tldraw'

import { loraModelNames, loraSupported, lorasOf, negativeOf, seedOf } from '../generate'
import { randomSeed } from '../workflows'
import { hasNegative, type ModelDef } from '../models'
import { DEFAULT_LORA_STRENGTH, forgetLora, MAX_LORAS, loadSavedLoras, loraLabel, loraUrl, MAX_LORA_STRENGTH, saveLora, savedLorasAtom, type LoraPick } from '../loras'
import type { GeneratorShape } from '../shapes/GeneratorShape'
import { t } from '../i18n'
import { Icons } from './icons'
import { Popover } from './Popover'

export function AdvancedPill({ shape, model, setMeta }: { shape: GeneratorShape; model: ModelDef; setMeta: (patch: Record<string, unknown>) => void }) {
  const [open, setOpen] = useState(false)
  const [url, setUrl] = useState('')
  const [urlError, setUrlError] = useState('')
  const saved = useValue(savedLorasAtom)
  // #202: LoRA goes in the WaveSpeed model's `loras` field; a model without it greys the panel out (never hidden)
  const hasLora = loraSupported(shape)
  useEffect(() => { if (open) void loadSavedLoras() }, [open])

  const seed = seedOf(shape)
  const showNegative = hasNegative(model)
  const negative = showNegative ? negativeOf(shape) : ''
  const loras = lorasOf(shape)
  const count = (seed != null ? 1 : 0) + (negative ? 1 : 0) + (hasLora ? loras.length : 0)
  const full = loras.length >= MAX_LORAS
  const addLora = (pick: LoraPick) => {
    if (loras.some((p) => p.name === pick.name)) return void saveLora(pick)
    if (full) return setUrlError(t('wsErr.loraTooMany'))  // #202: max 3 (WaveSpeed maxItems); a 4th is blocked, never sent
    setMeta({ loras: [...loras, pick] })
    void saveLora(pick)
  }
  const addUrl = () => {
    const ok = loraUrl(url)
    if (!ok) return setUrlError(t('wsErr.loraUrl'))
    setUrlError('')
    setUrl('')
    addLora({ name: ok, strength: DEFAULT_LORA_STRENGTH })
  }

  return (
    <Popover open={open} onOpenChange={setOpen} side="top" contentKey={`${hasLora}:${loras.length}:${saved?.length ?? 0}:${urlError}:${showNegative}:${seed != null}`} trigger={({ open: o, toggle }) => (
      <button type="button" className="ca-gen__pill" data-open={o || undefined} onClick={toggle}>
        <span className="ca-gen__pilltext">{t('genAdvanced.advanced')}{count ? ` · ${count}` : ''}</span><span className="ca-gen__chev">{Icons.chevron}</span>
      </button>
    )}>
      <div className="ca-menu ca-gen__settings ca-adv">
        <div className="ca-gen__label">{t('genAdvanced.seed')}</div>
        <div className="ca-style__row">
          <label className="ca-panel__row ca-gen__toggle"><span>{t('genAdvanced.random')}</span><input type="checkbox" checked={seed == null} onChange={(e) => setMeta({ seed: e.target.checked ? null : randomSeed() })} /></label>
          {seed != null && (
            <>
              <input className="ca-adv__seed" type="number" min={0} value={seed} onChange={(e) => setMeta({ seed: Math.max(0, Math.floor(Number(e.target.value) || 0)) })} onKeyDown={(e) => e.stopPropagation()} />
              <button type="button" className="ca-panel__icon" title={t('genAdvanced.newSeed')} onClick={() => setMeta({ seed: randomSeed() })}>{Icons.replace}</button>
            </>
          )}
        </div>
        {showNegative && (
          <>
            <div className="ca-gen__label">{t('genAdvanced.negativePrompt')}</div>
            <textarea className="ca-adv__negative" value={negative} placeholder={t('genAdvanced.negativeHint')} onChange={(e) => setMeta({ negative: e.target.value })} onKeyDown={(e) => e.stopPropagation()} />
          </>
        )}
        <div className="ca-gen__label">LoRA</div>
        {!hasLora && <div className="ca-landing__hint ca-adv__lora" data-testid="lora-unsupported">{t('genAdvanced.loraUnsupported')}{loraModelNames(shape).length ? `${t('genAdvanced.loraModelsSep')}${loraModelNames(shape).join(t('genAdvanced.loraModelsJoin'))}` : ''}</div>}
        <div data-off={!hasLora || undefined} className="ca-adv__block">
        {loras.map((l) => (
          <div key={l.name} className="ca-adv__lora">
            <span className="ca-adv__name" title={l.name}>{loraLabel(l.name)}</span>
            <input type="range" min={0} max={MAX_LORA_STRENGTH} value={l.strength} disabled={!hasLora} title={t('genAdvanced.loraWeight')}
              onChange={(e) => setMeta({ loras: loras.map((x) => (x.name === l.name ? { ...x, strength: Number(e.target.value) } : x)) })}
              onPointerUp={() => void saveLora(l)} />
            <span className="ca-panel__val">{l.strength}</span>
            <button type="button" className="ca-panel__icon" title={t('common.remove')} onClick={() => setMeta({ loras: loras.filter((x) => x.name !== l.name) })}>{Icons.close}</button>
          </div>
        ))}
        <div className="ca-style__row ca-adv__lora">
          <input className="ca-assets__search" value={url} disabled={!hasLora || full} placeholder={t('genAdvanced.loraUrlHint')} data-testid="lora-url"
            onChange={(e) => { setUrl(e.target.value); setUrlError('') }}
            onKeyDown={(e) => { e.stopPropagation(); if (e.key === 'Enter') addUrl() }} />
          <button type="button" className="ca-panel__icon" title={t('genAdvanced.addLora')} disabled={!hasLora || full || !url.trim()} onClick={addUrl}>{Icons.plus}</button>
        </div>
        {urlError ? <div className="ca-workflows__warn ca-adv__lora" role="alert" data-testid="lora-error">{urlError}</div>
          : <div className="ca-landing__hint ca-adv__lora">{t('genAdvanced.loraUrlHelp')}</div>}
        <div className="ca-gen__label">{t('genAdvanced.savedLoras')}</div>
        <div className="ca-adv__list">
          {saved !== null && !saved.length && <div className="ca-compose__empty">{t('genAdvanced.noSavedLoras')}</div>}
          {(saved ?? []).map((l) => (
            <div key={l.name} className="ca-adv__row">
              <button type="button" className="ca-menu__item ca-adv__pick" title={l.name} disabled={!hasLora || full || loras.some((p) => p.name === l.name)} onClick={() => addLora(l)}>
                <span className="ca-menu__grow">{loraLabel(l.name)}</span>
                <span className="ca-panel__val">{l.strength}</span>
              </button>
              <button type="button" className="ca-panel__icon" title={t('genAdvanced.forget')} onClick={() => void forgetLora(l.name)}>{Icons.close}</button>
            </div>
          ))}
        </div>
        </div>
      </div>
    </Popover>
  )
}
