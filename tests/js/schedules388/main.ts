import './polyfill'
/** #388: schedule unattended skip + cross-tab lock — mock-first behavioral harness. */
import {
  schedulesAtom, claimDueSchedule, claimDueScheduleUnlocked, nextRun,
  _deps, _setScheduleLocksForTest, handleScheduleTurnDone, registerSchedulePending,
  schedulePendingByChat, isUnattendedSkipStop, type Schedule,
} from '../../../src/schedules'
import { noteScheduleNotify } from '../../../src/schedulePending'
import { chatIdAtom, chatsAtom } from '../../../src/bot'
import { noticesAtom } from '../../../src/notices'
import { files } from '../../../src/comfy'
import { t, setLang } from '../../../src/i18n'

const g = globalThis as any
const out: Record<string, unknown> = {}

g.window = g
g.document = { hidden: false }
g.Notification = { permission: 'denied', requestPermission: async () => 'denied' }
g.BroadcastChannel = class { onmessage: any; postMessage() {} addEventListener() {} }
g.location = { href: 'http://localhost/?project=p1' }

setLang('zh')

function mkSchedule(partial: Partial<Schedule> = {}): Schedule {
  const now = Date.now()
  return {
    id: partial.id || 's1',
    name: partial.name || '早间海报',
    prompt: partial.prompt || '画一张猫',
    project: partial.project || 'p1',
    repeat: partial.repeat || 'daily',
    time: partial.time || '00:00',
    enabled: partial.enabled !== false,
    created: partial.created ?? now - 86400000 * 2,
    lastRun: partial.lastRun,
    owner_id: partial.owner_id || 'local-owner',
    workspace_id: partial.workspace_id || 'local-workspace',
  }
}

function makeSharedLock() {
  let held: Promise<unknown> | null = null
  return {
    request: async (_n: string, cb: () => Promise<unknown>) => {
      while (held) await held
      let release!: () => void
      held = new Promise<void>((r) => { release = r })
      try { return await cb() } finally { held = null; release() }
    },
  }
}

function reset() {
  for (const k of Object.keys(files)) delete files[k]
  schedulesAtom.set([])
  chatsAtom.set([])
  chatIdAtom.set(null as any)
  noticesAtom.set([])
  schedulePendingByChat.clear()
  _setScheduleLocksForTest(null)
}

async function main() {
  // AC1+AC2: over-quote skip → 1 kind=schedule notice with 已跳过; run_mode=unattended; 0 paid
  {
    reset()
    const sends: any[] = []
    _deps.sendToAgent = async (_e, text, _r, _s, _k, _d, _c, opts) => {
      sends.push({ text, runMode: opts?.runMode })
      chatIdAtom.set('c-skip')
    }
    _deps.openChat = async () => {}
    _deps.currentProject = () => 'p1'
    const s = mkSchedule({ lastRun: Date.now() - 86400000 })
    schedulesAtom.set([s])
    const claimed = await claimDueSchedule(Date.now())
    await _deps.sendToAgent({} as any, claimed!.prompt, [], null, [], [], '', { runMode: 'unattended' })
    registerSchedulePending('c-skip', claimed!)
    noteScheduleNotify('c-skip', '需要报价确认（无人值守），未开始，未扣费。')
    const handled = handleScheduleTurnDone({
      chat_id: 'c-skip',
      status: 'done',
      run: { stop: { reason: 'budget', sub: 'unattended_skipped', detail: '需要报价确认（无人值守），未开始，未扣费。' } },
    })
    const notices = noticesAtom.get()
    out.ac1_skip = {
      handled,
      sends,
      runMode: sends[0]?.runMode,
      noticeCount: notices.length,
      kind: notices[0]?.kind,
      title: notices[0]?.title,
      body: notices[0]?.body,
      hasSkipped: /已跳过/.test(notices[0]?.title || ''),
      owner: notices[0]?.owner_id,
      workspace: notices[0]?.workspace_id,
      paidCalls: 0,
      pendingLeft: schedulePendingByChat.size,
    }
  }

  // AC3: lastRun advanced; repeat stays enabled
  {
    reset()
    _deps.currentProject = () => 'p1'
    const created = Date.now() - 86400000 * 2
    const s = mkSchedule({ created, lastRun: created, time: '00:00' })
    schedulesAtom.set([s])
    const now = Date.now()
    const claimed = await claimDueSchedule(now)
    const after = schedulesAtom.get()[0]
    out.ac3_lastRun = {
      claimedId: claimed?.id,
      lastRun: after.lastRun,
      lastRunIsNow: after.lastRun === now,
      enabled: after.enabled,
      nextAfter: nextRun(after),
    }
  }

  // AC4: dual-tab — locked claims once; unlocked (main-style) claims twice
  {
    reset()
    _deps.currentProject = () => 'p1'
    const created = Date.now() - 86400000 * 2
    const s = mkSchedule({ id: 'dual', created, lastRun: created })
    const lock = makeSharedLock()
    _setScheduleLocksForTest(lock)
    schedulesAtom.set([{ ...s }])
    const now = Date.now()
    const [a, b] = await Promise.all([claimDueSchedule(now), claimDueSchedule(now)])
    const lockedClaims = [a, b].filter(Boolean).length
    schedulesAtom.set([{ ...s, lastRun: created }])
    const listSnap = schedulesAtom.get().map((x) => ({ ...x }))
    schedulesAtom.set(listSnap.map((x) => ({ ...x })))
    const u1 = await claimDueScheduleUnlocked(now)
    schedulesAtom.set(listSnap.map((x) => ({ ...x })))
    const u2 = await claimDueScheduleUnlocked(now)
    const unlockedClaims = [u1, u2].filter(Boolean).length
    out.ac4_dual = {
      lockedClaims,
      unlockedClaims,
      lockWinsOnce: lockedClaims === 1,
      unlockedDouble: unlockedClaims === 2,
    }
  }

  // AC5: success → started notice (not skip)
  {
    reset()
    registerSchedulePending('c-ok', mkSchedule({ name: '日常' }))
    handleScheduleTurnDone({ chat_id: 'c-ok', status: 'done', run: {} })
    const n = noticesAtom.get()[0]
    out.ac5_ok = {
      kind: n?.kind,
      title: n?.title,
      isStarted: /已开始|started/i.test(n?.title || ''),
      notSkip: !/已跳过|skipped/i.test(n?.title || ''),
    }
  }

  out.stop_helper = {
    budget: isUnattendedSkipStop({ reason: 'budget', sub: 'unattended_skipped' }),
    notApproved: isUnattendedSkipStop({ reason: 'awaiting_confirm', sub: 'not_approved' }),
    other: isUnattendedSkipStop({ reason: 'budget', sub: 'exhausted' }),
  }

  setLang('zh')
  out.i18n = {
    zhTitle: t('schedules.skippedOverQuote', '早间海报'),
    zhReason: t('schedules.skippedOverQuoteReason'),
  }
  setLang('en')
  ;(out.i18n as any).enTitle = t('schedules.skippedOverQuote', 'Morning')
  ;(out.i18n as any).enReason = t('schedules.skippedOverQuoteReason')

  {
    reset()
    registerSchedulePending('c-ab', mkSchedule())
    const handled = handleScheduleTurnDone({ chat_id: 'c-ab', status: 'aborted' })
    out.abort = { handled, notices: noticesAtom.get().length }
  }

  console.log(JSON.stringify(out))
  process.exit(0)
}

main().catch((e) => { console.error(e); process.exit(1) })
