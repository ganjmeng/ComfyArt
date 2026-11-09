/** Single-shot submission. A timeout is uncertainty, never permission to retry. */
export type SubmissionPhase = 'idle' | 'submitting' | 'uncertain' | 'succeeded'
export class ConfirmationSubmission {
  private phase: SubmissionPhase = 'idle'
  private listeners = new Set<() => void>()
  private submit: () => Promise<void>
  private options: {
    onPhase?: (phase: SubmissionPhase) => void
    onSuccess: () => void
    onFailure: (error: unknown) => void
    timeoutMs?: number
    schedule?: (fn: () => void, ms: number) => unknown
    unschedule?: (timer: unknown) => void
  }
  constructor(submit: () => Promise<void>, options: ConfirmationSubmission['options']) {
    this.submit = submit
    this.options = options
  }
  getSnapshot = (): SubmissionPhase => this.phase
  subscribe = (fn: () => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn) } }
  canClose = () => this.phase !== 'submitting'
  private set(phase: SubmissionPhase) {
    this.phase = phase
    this.options.onPhase?.(phase)
    for (const listener of this.listeners) listener()
  }
  start() {
    if (this.phase !== 'idle') return false
    this.set('submitting')
    const schedule = this.options.schedule ?? ((fn, ms) => setTimeout(fn, ms))
    const unschedule = this.options.unschedule ?? ((timer) => clearTimeout(timer as ReturnType<typeof setTimeout>))
    const timer = schedule(() => {
      if (this.phase === 'submitting') this.set('uncertain')
    }, this.options.timeoutMs ?? 30_000)
    // Keep the original request alive after timeout, including after the dialog closes.
    // A late acknowledgement still resolves the job; it must not close a different dialog.
    void Promise.resolve().then(this.submit).then(() => {
      unschedule(timer)
      this.set('succeeded')
      this.options.onSuccess()
    }, (error: unknown) => {
      unschedule(timer)
      this.set('uncertain')
      this.options.onFailure(error)
    })
    return true
  }
}

/** Only use for a real paid submit, never to turn an unknown quote into zero. */
export function canSubmitPricedConfirmation(price: number | null, unpriced = false) {
  return !unpriced && price != null && Number.isFinite(price) && price >= 0
}
