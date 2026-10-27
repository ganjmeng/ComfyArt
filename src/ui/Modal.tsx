import type { ReactNode } from 'react'

import { useEscape } from './escape'
import { Icons } from './icons'
import { t } from '../i18n'

/** `closable={false}`: no ✕ in the header (confirm-style dialogs; Esc / backdrop / 取消 still close). */
export function Modal({ title, className = 'ca-rename', onClose, children, closable = true }: { title: ReactNode; className?: string; onClose: () => void; children: ReactNode; closable?: boolean }) {
  useEscape(true, onClose)
  return (
    <div className="ca-modal" onPointerDown={(e) => { e.stopPropagation(); if (e.target === e.currentTarget) onClose() }}>
      <div className={['ca-modal__card', className].filter(Boolean).join(' ')}>
        <div className="ca-side__head">
          <span>{title}</span>
          {closable ? <button type="button" className="ca-panel__icon" title={t('common.close')} onClick={onClose}>{Icons.close}</button> : null}
        </div>
        {children}
      </div>
    </div>
  )
}
