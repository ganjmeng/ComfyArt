import { useMemo, useState } from 'react'

import { Icons } from './icons'
import { Popover } from './Popover'
import { t } from '../i18n'

const VISIBLE_CAP = 100

export function LlmModelSelect({
  value,
  models,
  typable,
  disabled,
  loading,
  onChange,
}: {
  value: string
  models: string[]
  typable?: boolean
  disabled?: boolean
  loading?: boolean
  onChange: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const q = query.trim().toLowerCase()
  const filtered = useMemo(() => {
    const rows = q ? models.filter((id) => id.toLowerCase().includes(q)) : models
    return q ? rows : rows.slice(0, VISIBLE_CAP)
  }, [models, q])
  const showCount = !q && models.length > VISIBLE_CAP

  if (typable) {
    return (
      <input
        className="ca-panel__input"
        type="text"
        autoComplete="off"
        data-testid="llm-model-input"
        value={value}
        disabled={disabled}
        placeholder={t('botSettings.modelComboboxHint')}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.stopPropagation()}
      />
    )
  }

  const label = value || t('botSettings.chooseModel')
  return (
    <div className="ca-fieldselect-wrap ca-llm-model" data-testid="llm-model-select">
      <Popover
        open={open}
        onOpenChange={(next) => { setOpen(next); if (!next) setQuery('') }}
        side="bottom"
        align="start"
        trigger={({ open: o, toggle }) => (
          <button
            type="button"
            className="ca-fieldselect"
            data-open={o || undefined}
            data-placeholder={!value || undefined}
            disabled={disabled || loading}
            title={label}
            onClick={toggle}
            onKeyDown={(e) => e.stopPropagation()}
          >
            <span className="ca-fieldselect__text">{loading ? t('botSettings.testing') : label}</span>
            <span className="ca-icon">{Icons.chevron}</span>
          </button>
        )}
      >
        <div className="ca-menu ca-fieldselect__menu ca-llm-model__menu">
          <label className="ca-llm-model__search">
            <span className="ca-icon">{Icons.search}</span>
            <input
              autoFocus
              value={query}
              placeholder={t('botSettings.searchModels')}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.stopPropagation()}
            />
          </label>
          {filtered.map((id) => (
            <button
              key={id}
              type="button"
              className="ca-menu__item"
              data-on={value === id || undefined}
              title={id}
              onClick={() => { onChange(id); setOpen(false); setQuery('') }}
            >
              <span className="ca-menu__grow">{id}</span>
              {value === id && <span className="ca-icon">{Icons.check}</span>}
            </button>
          ))}
          {showCount && (
            <div className="ca-llm-model__count">{t('botSettings.modelCountHint', String(models.length))}</div>
          )}
          {!filtered.length && <div className="ca-menu__empty">{t('botSettings.chooseModel')}</div>}
        </div>
      </Popover>
    </div>
  )
}
