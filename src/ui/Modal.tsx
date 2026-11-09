import { useId, type ReactNode } from 'react'

import { useEscape } from './escape'
import { Icons } from './icons'
import { t } from '../i18n'

/** `closable={false}`: no ✕ in the header (confirm-style dialogs; Esc / backdrop / 取消 still close).
 * `backdropClose={false}`: a click on the backdrop does nothing (#393 over-quote card).
 * `dialog`: expose role=dialog only for confirm-style callers. Other modals stay unchanged. */
export function Modal({ title, className = 'ca-rename', onClose, children, closable = true, backdropClose = true, dialog = false }: { title: ReactNode; className?: string; onClose: () => void; children: ReactNode; closable?: boolean; backdropClose?: boolean; dialog?: boolean }) {
  useEscape(true, onClose)
  const titleId = useId()
  return (
    <div className="ca-modal" onPointerDown={(e) => { e.stopPropagation(); if (backdropClose && e.target === e.currentTarget) onClose() }}>
      <div
        className={['ca-modal__card', className].filter(Boolean).join(' ')}
        role={dialog ? 'dialog' : undefined}
        aria-modal={dialog ? true : undefined}
        aria-labelledby={dialog ? titleId : undefined}
      >
        <div className="ca-side__head">
          <span id={titleId}>{title}</span>
          {closable ? <button type="button" className="ca-panel__icon" title={t('common.close')} aria-label={t('common.close')} onClick={onClose}>{Icons.close}</button> : null}
        </div>
        {children}
      </div>
    </div>
  )
}
