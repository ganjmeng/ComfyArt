import { createPortal } from 'react-dom'
import { atom, useValue } from 'tldraw'

import { Modal } from './Modal'
import { t } from '../i18n'

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
  if (!ask) return null
  const close = () => confirmAtom.set(null)
  const dismiss = () => { close(); ask.cancel?.() }
  // #145: portal to <body> like Popover, so the existing .ca-modal z-index (2000) is compared with .ca-pop (1000)
  // instead of being trapped in .ca-root's stacking context, where any open popover covered it
  return createPortal(
    <Modal title={ask.title} className={['ca-rename ca-confirm', ask.className].filter(Boolean).join(' ')} closable={ask.closable ?? false} backdropClose={ask.backdropClose ?? true} onClose={dismiss}>
      <div className="ca-rename__body" data-testid="confirm-dialog">
        {ask.note ? <div>{ask.note}</div> : null}
        <div>{ask.desc}</div>
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
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary" onClick={dismiss}>{ask.cancelLabel ?? t('common.cancel')}</button>
          <button type="button" className={ask.danger ? 'ca-panel__primary ca-panel__danger' : 'ca-panel__primary'} onClick={() => { close(); ask.run() }}>{ask.ok}</button>
        </div>
      </div>
    </Modal>,
    document.body,
  )
}
