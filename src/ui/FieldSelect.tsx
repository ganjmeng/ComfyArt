import { useState, type KeyboardEvent } from 'react'

import { Icons } from './icons'
import { Popover } from './Popover'

/** #318: shared Popover field picker (replaces native select). */
export type FieldSelectOption = {
  id: string
  label: string
  title?: string
  disabled?: boolean
}

export function FieldSelect({
  value,
  options,
  onChange,
  placeholder,
  within,
  align = 'start',
  side = 'bottom',
  className,
  menuClassName,
  triggerClassName,
  onKeyDown,
}: {
  value: string
  options: FieldSelectOption[]
  onChange: (id: string) => void
  placeholder?: string
  within?: string
  align?: 'start' | 'center' | 'end'
  side?: 'top' | 'bottom'
  className?: string
  menuClassName?: string
  triggerClassName?: string
  onKeyDown?: (e: KeyboardEvent) => void
}) {
  const [open, setOpen] = useState(false)
  const selected = options.find((o) => o.id === value)
  const label = selected?.label ?? (value || placeholder || '')
  const title = selected?.title ?? selected?.label ?? (value || placeholder || '')
  const pick = (id: string) => {
    setOpen(false)
    onChange(id)
  }
  return (
    <div className={['ca-fieldselect-wrap', className].filter(Boolean).join(' ')}>
      <Popover open={open} onOpenChange={setOpen} side={side} align={align} within={within} trigger={({ open: o, toggle }) => (
        <button
          type="button"
          className={['ca-fieldselect', triggerClassName].filter(Boolean).join(' ')}
          data-open={o || undefined}
          title={title}
          onClick={toggle}
          onKeyDown={onKeyDown}
        >
          <span className="ca-fieldselect__text">{label}</span>
          <span className="ca-icon">{Icons.chevron}</span>
        </button>
      )}>
        <div className={['ca-menu', 'ca-fieldselect__menu', menuClassName].filter(Boolean).join(' ')}>
          {options.map((o) => {
            const on = value === o.id
            return (
              <button
                key={o.id || '__empty'}
                type="button"
                className="ca-menu__item"
                title={o.title ?? o.label}
                disabled={o.disabled}
                data-on={on || undefined}
                onClick={() => pick(o.id)}
              >
                <span className="ca-menu__grow">{o.label}</span>
                {on && <span className="ca-icon">{Icons.check}</span>}
              </button>
            )
          })}
        </div>
      </Popover>
    </div>
  )
}
