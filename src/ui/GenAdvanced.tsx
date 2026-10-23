import { useEffect, useState } from 'react'
import { useValue } from 'tldraw'

import { lorasOf, negativeOf, seedOf } from '../generate'
import { randomSeed } from '../workflows'
import { DEFAULT_LORA_STRENGTH, loadLoras, loraFavoritesAtom, loraLabel, lorasAtom, toggleFavorite } from '../loras'
import { hasNegative, type ModelDef } from '../models'
import type { GeneratorShape } from '../shapes/GeneratorShape'
import { t } from '../i18n'
import { Icons } from './icons'
import { Popover } from './Popover'

type Tab = 'model' | 'favorites' | 'all'

export function AdvancedPill({ shape, model, setMeta }: { shape: GeneratorShape; model: ModelDef; setMeta: (patch: Record<string, unknown>) => void }) {
  const [open, setOpen] = useState(false)
  const [adding, setAdding] = useState(false)
  const [tab, setTab] = useState<Tab>('model')
  const [query, setQuery] = useState('')
  const all = useValue(lorasAtom)
  const favorites = useValue(loraFavoritesAtom)
  const hasLora = model.lora !== undefined
  const current = tab === 'model' && !model.lora ? 'all' : tab
  useEffect(() => { if (open && hasLora) void loadLoras() }, [open, hasLora])

  const seed = seedOf(shape)
  const showNegative = hasNegative(model)
  const negative = showNegative ? negativeOf(shape) : ''
  const loras = lorasOf(shape)
  const count = (seed != null ? 1 : 0) + (negative ? 1 : 0) + (hasLora ? loras.length : 0)
  const needle = query.trim().toLowerCase()
  const listed = (all ?? [])
    .filter((l) => (current === 'model' ? l.family === model.lora : tab === 'favorites' ? favorites.includes(l.name) : true))
    .filter((l) => !needle || l.name.toLowerCase().includes(needle))
    .filter((l) => !loras.some((p) => p.name === l.name))

  return (
    <Popover open={open} onOpenChange={setOpen} side="top" trigger={({ open: o, toggle }) => (
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
        {hasLora && (
          <>
            <div className="ca-gen__label">LoRA</div>
            {loras.map((l) => (
              <div key={l.name} className="ca-adv__lora">
                <span className="ca-adv__name" title={l.name}>{loraLabel(l.name)}</span>
                <input type="range" min={0} max={200} value={l.strength} onChange={(e) => setMeta({ loras: loras.map((x) => (x.name === l.name ? { ...x, strength: Number(e.target.value) } : x)) })} />
                <span className="ca-panel__val">{l.strength}</span>
                <button type="button" className="ca-panel__icon" title={t('common.remove')} onClick={() => setMeta({ loras: loras.filter((x) => x.name !== l.name) })}>{Icons.close}</button>
              </div>
            ))}
            {!adding && (
              <button type="button" className="ca-menu__item" onClick={() => setAdding(true)}><span className="ca-icon">{Icons.plus}</span><span className="ca-menu__grow">{t('genAdvanced.addLora')}</span></button>
            )}
            {adding && (
              <div className="ca-adv__picker">
                <div className="ca-gen__chips">
                  {([['model', t('genAdvanced.forThisModel')], ['favorites', t('genAdvanced.favorites')], ['all', t('common.all')]] as [Tab, string][]).filter(([k]) => k !== 'model' || model.lora).map(([k, label]) => (
                    <button key={k} type="button" className="ca-gen__chip" data-on={current === k || undefined} onClick={() => setTab(k)}>{label}</button>
                  ))}
                </div>
                <input className="ca-assets__search" value={query} placeholder={t('assetPicker.search')} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.stopPropagation()} />
                <div className="ca-adv__list">
                  {all === null && <div className="ca-compose__empty">{t('assetPicker.loading')}</div>}
                  {all !== null && !listed.length && <div className="ca-compose__empty">{current === 'model' ? t('genAdvanced.noLorasForModel') : t('genAdvanced.noLoras')}</div>}
                  {listed.map((l) => (
                    <div key={l.name} className="ca-adv__row">
                      <button type="button" className="ca-adv__star" data-on={favorites.includes(l.name) || undefined} title={t('genAdvanced.favorite')} onClick={() => void toggleFavorite(l.name)}>★</button>
                      <button type="button" className="ca-menu__item ca-adv__pick" title={l.name} onClick={() => { setMeta({ loras: [...loras, { name: l.name, strength: DEFAULT_LORA_STRENGTH }] }); setAdding(false) }}>
                        <span className="ca-menu__grow">{loraLabel(l.name)}</span>
                        {model.lora && l.family !== model.lora && <span className="ca-model__tag">{l.family ? t('genAdvanced.otherModel') : t('genAdvanced.unknownModel')}</span>}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Popover>
  )
}
