/** #388: pending unattended schedule turns + outcome notice (keeps bot↔schedules cycle-free). */
import { notify } from './notices'
import { OWNER_DEFAULT, WORKSPACE_DEFAULT } from './memoryStore'
import { t } from './i18n'

export interface SchedulePending {
  scheduleId: string
  name: string
  prompt: string
  owner_id: string
  workspace_id: string
  project_id: string
  notifyText?: string
}

/** chat_id → pending unattended schedule turn. */
export const schedulePendingByChat = new Map<string, SchedulePending>()

export function registerSchedulePending(
  chatId: string,
  s: { id: string; name: string; prompt: string; project?: string; owner_id?: string; workspace_id?: string },
) {
  schedulePendingByChat.set(chatId, {
    scheduleId: s.id,
    name: s.name,
    prompt: s.prompt,
    owner_id: s.owner_id || OWNER_DEFAULT,
    workspace_id: s.workspace_id || WORKSPACE_DEFAULT,
    project_id: s.project || 'local',
  })
}

export function noteScheduleNotify(chatId: string, text: string) {
  const p = schedulePendingByChat.get(chatId)
  if (p) p.notifyText = text
}

export function isSchedulePending(chatId: string): boolean {
  return schedulePendingByChat.has(chatId)
}

export function isUnattendedSkipStop(stop: { reason?: string; sub?: string } | null | undefined): boolean {
  if (!stop?.reason) return false
  return (stop.reason === 'awaiting_confirm' && stop.sub === 'not_approved')
    || (stop.reason === 'budget' && stop.sub === 'unattended_skipped')
}

/** turn_done for a schedule chat — exactly one kind=schedule notice; suppress task/suggestion. */
export function handleScheduleTurnDone(e: {
  chat_id: string
  status?: string
  error?: string
  run?: { stop?: { reason?: string; sub?: string; detail?: string } } | null
}): boolean {
  const pending = schedulePendingByChat.get(e.chat_id)
  if (!pending) return false
  schedulePendingByChat.delete(e.chat_id)
  if (e.status === 'aborted') return true
  const stop = e.run?.stop
  const skipped = isUnattendedSkipStop(stop)
    || /已跳过|未扣费|没有人确认|unattended|not_approved|skipped/i.test(pending.notifyText || e.error || '')
  if (skipped) {
    const reason = pending.notifyText
      || stop?.detail
      || e.error
      || t('schedules.skippedOverQuoteReason')
    void notify({
      kind: 'schedule',
      title: t('schedules.skippedOverQuote', pending.name),
      body: reason,
      chat: e.chat_id,
      owner_id: pending.owner_id,
      workspace_id: pending.workspace_id,
    })
  } else {
    void notify({
      kind: 'schedule',
      title: t('schedules.scheduledTaskStarted', pending.name),
      body: pending.prompt,
      chat: e.chat_id,
      owner_id: pending.owner_id,
      workspace_id: pending.workspace_id,
    })
  }
  return true
}
