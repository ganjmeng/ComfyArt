import { t } from '../i18n'

export interface AngleSlot {
  id: string
  kind?: string
  panel?: string
  state?: string
  retry?: boolean
}

export interface AngleProgressBlock {
  type?: string
  preview?: number
  final_total?: number
  final_done?: number
  phase?: string
  batch_retry?: boolean
  slots?: AngleSlot[]
}

const STATE_KEY: Record<string, string> = {
  delivered: 'bot.angleSlotDelivered',
  generating: 'bot.angleSlotGenerating',
  pending_query: 'bot.angleSlotPending',
  failed: 'bot.angleSlotFailed',
  waiting: 'bot.angleSlotWaiting',
}

/** Confirmed multi-angle card. The counts are the server block, not the model plan. */
export function AngleProgress({ block, onRetry }: { block: AngleProgressBlock; onRetry?: (slot: AngleSlot) => void }) {
  const total = Number(block.final_total || 0)
  const done = Number(block.final_done || 0)
  if (!total) return null
  const head = block.phase === 'confirmed'
    ? t('bot.angleConfirmed', Number(block.preview || 1), total)
    : block.phase === 'generating'
      ? t('bot.angleGenerating', done, total)
      : t('bot.angleCount', done, total)
  return (
    <div className="ca-angle" data-phase={block.phase || 'partial'} data-testid="angle-progress">
      <div className="ca-angle__head">
        <span>{t('bot.plan')}</span>
        <span className="ca-chat__status" data-testid="angle-progress-count">{head}</span>
      </div>
      {(block.slots ?? []).map((slot) => {
        const state = slot.state || 'waiting'
        const name = slot.kind === 'preview' ? t('bot.anglePreview') : t('bot.angleFinal', slot.panel || slot.id)
        const failed = state === 'failed' && slot.retry !== false
        return (
          <div key={slot.id} className="ca-angle__row" data-state={state} data-testid={`angle-slot-${slot.id}`}>
            <span>{name}</span>
            <span data-testid={`angle-state-${slot.id}`}>{t(STATE_KEY[state] ?? 'bot.angleSlotWaiting')}</span>
            {failed ? (
              <button type="button" className="ca-angle__retry" data-testid={`angle-retry-${slot.id}`} onClick={() => onRetry?.(slot)}>
                {t('bot.angleRetry')}
              </button>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
