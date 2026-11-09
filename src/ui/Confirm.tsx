import { useRef } from 'react'
import { createPortal } from 'react-dom'
import { atom, useValue } from 'tldraw'

import { t } from '../i18n'
import { ConfirmActions } from './ConfirmActions'
import { firstGate } from './firstAction'
import { Icons } from './icons'
import { Modal } from './Modal'

export interface PlanLine { text: string; price: string }
interface Ask {
  title: string
  note?: string
  desc: string
  ok: string
  /** secondary button label; default 「取消」 */
  cancelLabel?: string
  danger?: boolean
  /** show the header ✕; default false (confirm dialogs have none) */
  closable?: boolean
  /** backdrop click dismisses (= cancel); default true. #393 over-quote: false, the backdrop does nothing */
  backdropClose?: boolean
  /** extra class on the card */
  className?: string
  run: () => void
  cancel?: () => void
  lines?: PlanLine[]
  totalLabel?: string
  total?: string
}

export const confirmAtom = atom<Ask | null>('confirm', null)

export function Confirm() {
  const ask = useValue(confirmAtom)
  const gate = useRef(firstGate())
  const seen = useRef(ask)
  if (seen.current !== ask) {
    seen.current = ask
    gate.current = firstGate()
  }
  if (!ask) return null
  const close = () => confirmAtom.set(null)
  // Close first, then the callback. The gate makes a second click, Escape, or backdrop a no-op.
  const finish = (fn?: () => void) => {
    if (!gate.current()) return
    close()
    fn?.()
  }
  const dismiss = () => finish(ask.cancel)
  // #145: portal to <body> like Popover, so the existing .ca-modal z-index (2000) is compared with .ca-pop (1000)
  // instead of being trapped in .ca-root's stacking context, where any open popover covered it
  return createPortal(
    <Modal dialog title={ask.title} className={['ca-rename ca-confirm', ask.className].filter(Boolean).join(' ')} closable={ask.closable ?? false} backdropClose={ask.backdropClose ?? true} onClose={dismiss}>
      <div className="ca-rename__body" data-testid="confirm-dialog">
        {ask.note ? <p className="ca-confirm__note">{ask.note}</p> : null}
        <p className="ca-confirm__desc" data-testid="confirm-desc">{ask.desc}</p>
        {ask.lines?.length ? ask.lines.map((line, i) => (
          <div key={i} className="ca-keys__row">
            <span className="ca-lib__name">{line.text}</span>
            <span className="ca-panel__val">{line.price}</span>
          </div>
        )) : null}
        {ask.total != null && ask.total !== '' ? (
          <div className="ca-keys__row ca-plan__head">
            <span className="ca-lib__name">{ask.totalLabel}</span>
            <span className="ca-panel__val">{ask.total}</span>
          </div>
        ) : null}
        <ConfirmActions
          cancelLabel={ask.cancelLabel ?? t('common.cancel')}
          okLabel={ask.ok}
          danger={ask.danger}
          okIcon={ask.danger ? Icons.trash : undefined}
          onCancel={dismiss}
          onOk={() => finish(ask.run)}
          cancelTestId="confirm-cancel"
          okTestId="confirm-ok"
        />
      </div>
    </Modal>,
    document.body,
  )
}
