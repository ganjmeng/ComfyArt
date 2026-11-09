import { useEffect, useRef, useState } from 'react'

import { t } from '../i18n'

export type ChatConfirmLine = { text: string; price: string }

type Phase = 'idle' | 'submitting' | 'uncertain'

/** Agent PlanQuote / OverQuote: fee card inside the message stream (no modal / scrim). */
export function ChatInlineConfirm({
  title,
  desc,
  okLabel,
  cancelLabel,
  lines,
  totalLabel,
  total,
  onConfirm,
  onCancel,
  testId = 'chat-inline-confirm',
}: {
  title: string
  desc: string
  okLabel: string
  cancelLabel?: string
  lines?: ChatConfirmLine[]
  totalLabel?: string
  total?: string
  onConfirm: () => Promise<void> | void
  onCancel: () => void
  testId?: string
}) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [hidden, setHidden] = useState(false)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const live = useRef(true)
  useEffect(() => {
    live.current = true
    cancelRef.current?.focus()
    return () => { live.current = false }
  }, [])

  const busy = phase === 'submitting'
  const uncertain = phase === 'uncertain'
  const secondary = uncertain ? t('common.close') : (cancelLabel ?? t('common.cancel'))

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || hidden || busy) return
      e.preventDefault()
      e.stopPropagation()
      if (uncertain) {
        setHidden(true)
        return
      }
      onCancel()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [hidden, busy, uncertain, onCancel])

  if (hidden) return null

  const start = () => {
    if (phase !== 'idle') return
    setPhase('submitting')
    const timer = window.setTimeout(() => {
      if (live.current) setPhase((p) => (p === 'submitting' ? 'uncertain' : p))
    }, 30_000)
    void Promise.resolve()
      .then(onConfirm)
      .then(() => {
        window.clearTimeout(timer)
      }, () => {
        window.clearTimeout(timer)
        if (live.current) setPhase('uncertain')
      })
  }

  return (
    <div
      className="ca-chat-confirm"
      role="group"
      aria-label={title}
      data-testid={testId}
      data-phase={phase}
      onKeyDown={(e) => e.stopPropagation()}
    >
      <div className="ca-chat-confirm__title">{title}</div>
      <p className="ca-chat-confirm__desc" data-testid="chat-inline-confirm-desc">{desc}</p>
      {lines?.length ? lines.map((line, i) => (
        <div key={i} className="ca-keys__row">
          <span className="ca-lib__name">{line.text}</span>
          <span className="ca-panel__val">{line.price}</span>
        </div>
      )) : null}
      {total != null && total !== '' ? (
        <div className="ca-keys__row ca-plan__head">
          <span className="ca-lib__name">{totalLabel}</span>
          <span className="ca-panel__val">{total}</span>
        </div>
      ) : null}
      {busy || uncertain ? (
        <p role="status" aria-live="polite" className="ca-chat-confirm__status" data-testid="chat-inline-confirm-status">
          {t(busy ? 'jobs.submittingConfirm' : 'jobs.submissionUncertain')}
        </p>
      ) : null}
      <div className="ca-panel__foot ca-chat-confirm__actions">
        <button
          ref={cancelRef}
          type="button"
          className="ca-panel__secondary"
          disabled={busy}
          data-testid="chat-inline-confirm-cancel"
          onClick={() => {
            if (busy) return
            if (uncertain) {
              setHidden(true)
              return
            }
            onCancel()
          }}
        >
          {secondary}
        </button>
        <button
          type="button"
          className="ca-panel__primary"
          disabled={busy || uncertain}
          data-testid="chat-inline-confirm-ok"
          onClick={start}
        >
          {okLabel}
        </button>
      </div>
    </div>
  )
}
