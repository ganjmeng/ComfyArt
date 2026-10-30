import { atom, type Editor } from 'tldraw'

import { errorText } from './jobs'
import { sendToAgent } from './agent'
import { chatIdAtom, chatsAtom, openChat } from './bot'
import { readUserJson, writeUserJson } from './comfy'
import type { ErrorSink } from './jobs'
import { currentProject } from './notices'
import { OWNER_DEFAULT, WORKSPACE_DEFAULT } from './memoryStore'
import { registerSchedulePending } from './schedulePending'
import { t } from './i18n'

export type Repeat = 'once' | 'daily' | 'weekly'
export interface Schedule {
  id: string
  name: string
  prompt: string
  project: string
  repeat: Repeat
  time: string
  date?: string
  weekdays?: number[]
  enabled: boolean
  created: number
  lastRun?: number
  /** #388 SaaS stubs — single-user defaults today. */
  owner_id?: string
  workspace_id?: string
}

const FILE = 'comfyart/schedules.json'
const TICK = 30000
const DAY = 86400000
const LOCK = 'comfyart-schedules'
const channel = new BroadcastChannel('comfyart-schedules')

export const schedulesAtom = atom<Schedule[]>('schedules', [])
export const schedulesOpenAtom = atom<{ prompt?: string } | null>('schedules open', null)
export const REPEAT_LABELS: Record<Repeat, string> = { once: t('schedules.once'), daily: t('schedules.daily'), weekly: t('schedules.weekly') }
export const WEEKDAYS = [t('schedules.sun'), t('schedules.mon'), t('schedules.tue'), t('schedules.wed'), t('schedules.thu'), t('schedules.fri'), t('schedules.sat')]

/** #388: Web Locks seam (dual-tab claim). Tests inject a shared mock. */
export type ScheduleLocks = { request: (name: string, cb: () => Promise<unknown>) => Promise<unknown> }
export let scheduleLocks: ScheduleLocks | null =
  typeof navigator !== 'undefined' && (navigator as Navigator & { locks?: ScheduleLocks }).locks
    ? (navigator as Navigator & { locks: ScheduleLocks }).locks
    : null
export function _setScheduleLocksForTest(api: ScheduleLocks | null) { scheduleLocks = api }

export {
  registerSchedulePending,
  schedulePendingByChat,
  handleScheduleTurnDone,
  isSchedulePending,
  noteScheduleNotify,
  isUnattendedSkipStop,
} from './schedulePending'

const read = () => readUserJson<Schedule[]>(FILE, [])

function stamp(s: Schedule): Schedule {
  return {
    ...s,
    owner_id: s.owner_id || OWNER_DEFAULT,
    workspace_id: s.workspace_id || WORKSPACE_DEFAULT,
  }
}

export async function loadSchedules() {
  const list = (await read()).map(stamp)
  schedulesAtom.set(list)
  return list
}

export async function saveSchedules(list: Schedule[]) {
  const stamped = list.map(stamp)
  schedulesAtom.set(stamped)
  await writeUserJson(FILE, stamped)
  channel.postMessage('changed')
}

channel.onmessage = () => void loadSchedules()

function at(day: Date, time: string) {
  const [h, m] = time.split(':').map(Number)
  const d = new Date(day)
  d.setHours(h, m, 0, 0)
  return d.getTime()
}

export function nextRun(s: Schedule): number | null {
  if (s.repeat === 'once') return s.lastRun || !s.date ? null : at(new Date(`${s.date}T00:00`), s.time)
  const from = s.lastRun ?? s.created
  const days = s.repeat === 'weekly' ? s.weekdays ?? [] : [0, 1, 2, 3, 4, 5, 6]
  for (let i = 0; i <= 7; i++) {
    const t = at(new Date(from + i * DAY), s.time)
    if (t > from && days.includes(new Date(t).getDay())) return t
  }
  return null
}

/** #388 test seam / injectable deps. */
export const _deps = {
  sendToAgent: sendToAgent as (
    editor: Editor, text: string, refs: never[], skill: null,
    kits?: never[], docs?: never[], context?: string,
    opts?: { runMode?: 'interactive' | 'unattended' },
  ) => Promise<void>,
  openChat: openChat as (id: string | null) => Promise<unknown>,
  currentProject: currentProject as typeof currentProject,
}

async function run(editor: Editor, s: Schedule) {
  await _deps.openChat(null)
  await _deps.sendToAgent(editor, s.prompt, [], null, [], [], '', { runMode: 'unattended' })
  const chatId = chatIdAtom.get()
  if (chatId) registerSchedulePending(chatId, s)
  // #388: notify only on turn_done (skip → 已跳过; ok → started). No immediate started.
}

export async function runNow(editor: Editor, s: Schedule) {
  await saveSchedules(schedulesAtom.get().map((x) => (x.id === s.id ? { ...x, lastRun: Date.now() } : x)))
  await run(editor, s)
}

/** Claim the next due schedule under the cross-tab lock; returns null if none / other tab won. */
export async function claimDueSchedule(now = Date.now()): Promise<Schedule | null> {
  const claim = async (): Promise<Schedule | null> => {
    const list = schedulesAtom.get()
    const due = list.find((s) => s.enabled && s.project === _deps.currentProject() && (nextRun(s) ?? Infinity) <= now)
    if (!due) return null
    await saveSchedules(list.map((s) => (s.id === due.id ? { ...s, lastRun: now, enabled: s.repeat !== 'once' && s.enabled } : s)))
    return schedulesAtom.get().find((s) => s.id === due.id) ?? { ...due, lastRun: now }
  }
  if (scheduleLocks?.request) {
    return (await scheduleLocks.request(LOCK, claim)) as Schedule | null
  }
  return claim()
}

/** Buggy main-style claim (no lock) — dual-tab tests prove AC4 red on main. */
export async function claimDueScheduleUnlocked(now = Date.now()): Promise<Schedule | null> {
  const list = schedulesAtom.get()
  const due = list.find((s) => s.enabled && s.project === _deps.currentProject() && (nextRun(s) ?? Infinity) <= now)
  if (!due) return null
  await saveSchedules(list.map((s) => (s.id === due.id ? { ...s, lastRun: now, enabled: s.repeat !== 'once' && s.enabled } : s)))
  return schedulesAtom.get().find((s) => s.id === due.id) ?? { ...due, lastRun: now }
}

export function startScheduler(editor: Editor, onError: ErrorSink) {
  let busy = false
  const tick = async () => {
    if (busy || chatsAtom.get().some((c) => c.busy)) return
    busy = true
    try {
      const due = await claimDueSchedule()
      if (!due) return
      await run(editor, due)
    } catch (e) {
      onError(errorText(e))
    } finally {
      busy = false
    }
  }
  void loadSchedules().then(tick, (e) => onError(errorText(e)))
  const timer = window.setInterval(() => void tick(), TICK)
  return () => clearInterval(timer)
}
