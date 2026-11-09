import { useEffect, useRef, type ReactNode } from 'react'

import { Button } from './Button'

/** Cancel sits first. The primary or danger action sits last. Labels stay visible. */
export function ConfirmActions({
  cancelLabel,
  okLabel,
  danger = false,
  okDisabled = false,
  okIcon,
  onCancel,
  onOk,
  cancelTestId,
  okTestId,
}: {
  cancelLabel: string
  okLabel: string
  danger?: boolean
  okDisabled?: boolean
  okIcon?: ReactNode
  onCancel: () => void
  onOk: () => void
  cancelTestId?: string
  okTestId?: string
}) {
  const cancelRef = useRef<HTMLButtonElement>(null)
  useEffect(() => { cancelRef.current?.focus() }, [])
  return (
    <div className="ca-panel__foot ca-confirm-actions" role="group">
      <Button ref={cancelRef} variant="secondary" data-testid={cancelTestId} onClick={onCancel}>{cancelLabel}</Button>
      <Button variant={danger ? 'danger' : 'primary'} icon={okIcon} disabled={okDisabled} data-testid={okTestId} onClick={onOk}>{okLabel}</Button>
    </div>
  )
}
