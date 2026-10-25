/** #227: tool-row state. A cost-confirm cancel (#127) is neither success nor failure. */
export type StepState = 'running' | 'error' | 'cancelled' | 'done'

interface StepResult { status?: string; text?: string }

const CANCEL_RE = /"cancelled"\s*:\s*true|"status"\s*:\s*"declined"|已取消该生成，未扣费|Cancelled this generation; nothing was charged|已取消：未确认费用|Cancelled: cost not confirmed/

export function stepState(result?: StepResult): StepState {
  if (!result) return 'running'
  if (result.status === 'cancelled') return 'cancelled' // #232: set by the server for declined / refused paid steps
  if (CANCEL_RE.test(result.text ?? '')) return 'cancelled'
  if (result.status === 'error') return 'error'
  return 'done'
}
