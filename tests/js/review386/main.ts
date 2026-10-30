/** #386: event-driven canvas review + state machine — mock-first behavioral harness. */
import {
  REVIEW_TRANSITIONS, REVIEW_PHASES, REVIEW_EVENTS, transition, tryTransition,
  IllegalReviewTransition, type ReviewPhase, type ReviewEvent,
} from '../../../src/reviewMachine'
import {
  REVIEW_DEBOUNCE_MS, canvasSignature, createReviewController, setReviewAsk,
} from '../../../src/proactive'
import { botEnabledAtom, settingsAtom } from '../../../src/bot'
import { reviewFeedAtom, clearReviewFeed, setReviewFeedStore, type ReviewCard } from '../../../src/reviewFeed'
import { writeUserJson } from '../../../src/comfy'

const g = globalThis as any
const out: Record<string, unknown> = {}

// --- polyfills ---
const timers = new Map<number, { fn: () => void; at: number }>()
let now = 0
let tid = 1
g.window = g
g.setTimeout = (fn: () => void, ms = 0) => {
  const id = tid++
  timers.set(id, { fn, at: now + ms })
  return id
}
g.clearTimeout = (id: number) => { timers.delete(id) }
const locks = { request: async (_n: string, fn: () => Promise<unknown>) => fn() }
try {
  Object.defineProperty(g, 'navigator', { value: { locks }, configurable: true })
} catch {
  try { (g.navigator as any).locks = locks } catch { /* ignore */ }
}
if (!(g.navigator as any)?.locks) {
  // last resort: patch proactive path via globalThis.__locks
  ;(g as any).__locksPolyfill = locks
}
async function advance(ms: number) {
  now += ms
  const due = [...timers.entries()].filter(([, t]) => t.at <= now).sort((a, b) => a[1].at - b[1].at)
  for (const [id, t] of due) {
    timers.delete(id)
    t.fn()
  }
  // flush microtasks from runReview
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
}
async function flush() {
  for (let i = 0; i < 20; i++) await Promise.resolve()
}

// in-memory review feed
let memCards: ReviewCard[] = []
setReviewFeedStore({
  async read() { return memCards.slice() },
  async write(cards) { memCards = cards.slice() },
})

function resetSettings(daily = 10) {
  botEnabledAtom.set(true)
  settingsAtom.set({
    'proactive-review': true,
    'proactive-daily': daily,
    'proactive-memory': false,
    'proactive-skills': false,
    'memory-enabled': true,
  })
}

type Shape = { id: string; type: string; props: { w?: number; h?: number; assetId?: string; src?: string } }
function makeEditor(shapes: Shape[], bounds = { w: 800, h: 600 }) {
  const map = new Map(shapes.map((s) => [s.id, s]))
  return {
    getCurrentPageShapeIds: () => new Set(map.keys()),
    getShape: (id: string) => map.get(id),
    getCurrentPageBounds: () => bounds,
    store: { listen: () => () => {} },
    _set(shapes2: Shape[]) {
      map.clear()
      for (const s of shapes2) map.set(s.id, s)
    },
  } as any
}

const threeShapes = (): Shape[] => [
  { id: 's1', type: 'image', props: { w: 100, h: 100, assetId: 'a1', src: 'http://x/1.png' } },
  { id: 's2', type: 'image', props: { w: 120, h: 80, assetId: 'a2', src: 'http://x/2.png' } },
  { id: 's3', type: 'geo', props: { w: 50, h: 50 } },
]

async function resetProactiveState() {
  await writeUserJson('comfyart/proactive.json', {
    day: new Date().toLocaleDateString('sv'),
    runs: {}, prompts: [], skillMark: 0, reviewed: {}, seen: [],
    owner_id: 'local', workspace_id: 'local',
  })
  memCards = []
  reviewFeedAtom.set([])
  g.__notices = []
  g.__exportCalls = 0
  g.__askCalls = 0
}

// ========== 1. State machine table ==========
{
  const legal: string[] = []
  const illegal: string[] = []
  for (const phase of REVIEW_PHASES) {
    for (const event of REVIEW_EVENTS) {
      const expected = REVIEW_TRANSITIONS[phase][event]
      if (expected) {
        const got = transition(phase, event)
        if (got !== expected) throw new Error(`transition ${phase}+${event} → ${got}, want ${expected}`)
        const soft = tryTransition(phase, event)
        if (!soft.ok || soft.phase !== expected) throw new Error(`tryTransition miss ${phase}+${event}`)
        legal.push(`${phase}+${event}=${expected}`)
      } else {
        let threw = false
        try { transition(phase, event) } catch (e) {
          threw = e instanceof IllegalReviewTransition
        }
        if (!threw) throw new Error(`expected throw ${phase}+${event}`)
        const soft = tryTransition(phase, event)
        if (soft.ok || soft.phase !== phase) throw new Error(`tryTransition should soft-fail ${phase}+${event}`)
        illegal.push(`${phase}+${event}`)
      }
    }
  }
  out.machine = { legal: legal.length, illegal: illegal.length, sample: legal.slice(0, 5) }
}

// ========== 2. Signature covers image content ==========
{
  const ed = makeEditor(threeShapes())
  const a = canvasSignature(ed)
  // change src only (same id/type/assetId/size)
  ed._set([
    { id: 's1', type: 'image', props: { w: 100, h: 100, assetId: 'a1', src: 'http://x/1b.png' } },
    { id: 's2', type: 'image', props: { w: 120, h: 80, assetId: 'a2', src: 'http://x/2.png' } },
    { id: 's3', type: 'geo', props: { w: 50, h: 50 } },
  ])
  const b = canvasSignature(ed)
  out.signature_content = { a, b, changed: a !== b, covers_src: a.includes('http://x/1.png') && b.includes('http://x/1b.png') }
  // identical content → same sig
  ed._set(threeShapes())
  out.signature_stable = canvasSignature(ed) === a
}

// ========== helpers for behavioral ==========
async function setupCtrl(askResult: string | (() => Promise<string>) | Error = '{"issues":["typo"]}') {
  await resetProactiveState()
  resetSettings(10)
  now = 0
  timers.clear()
  setReviewAsk(async () => {
    g.__askCalls = (g.__askCalls ?? 0) + 1
    if (askResult instanceof Error) throw askResult
    if (typeof askResult === 'function') return askResult()
    return askResult
  })
  const ed = makeEditor(threeShapes())
  const errors: string[] = []
  const ctrl = createReviewController(ed, (m) => errors.push(m))
  return { ed, ctrl, errors }
}

// ========== 3. Debounce: 1 gen + 5 canvas changes → 1 export, 1 ask ==========
{
  const { ctrl } = await setupCtrl('{"issues":["a"]}')
  ctrl.trigger() // gen-done
  for (let i = 0; i < 5; i++) {
    await advance(500) // within debounce
    ctrl.trigger() // canvas change
  }
  out.debounce_mid = { phase: ctrl.phase, asks: g.__askCalls ?? 0, exports: g.__exportCalls ?? 0 }
  await advance(REVIEW_DEBOUNCE_MS + 10)
  await flush()
  await advance(0)
  await flush()
  out.debounce = {
    phase: ctrl.phase,
    asks: g.__askCalls ?? 0,
    exports: g.__exportCalls ?? 0,
    cards: reviewFeedAtom.get().length,
    notices: (g.__notices ?? []).length,
  }
}

// ========== 4. Reentrancy during reviewing → pending follow-up (AC3) ==========
{
  let resolveAsk!: (v: string) => void
  const askP = new Promise<string>((r) => { resolveAsk = r })
  const { ctrl } = await setupCtrl(() => askP)
  ctrl.trigger()
  await advance(REVIEW_DEBOUNCE_MS + 10)
  await flush()
  // should be reviewing (ask hanging)
  const midPhase = ctrl.phase
  ctrl.trigger() // while reviewing
  ctrl.trigger() // second while reviewing — still one pending
  const pendingDuring = ctrl.pending
  resolveAsk('{"issues":["b"]}')
  await flush()
  await flush()
  // follow-up scheduled
  const afterPhase = ctrl.phase
  const pendingAfter = ctrl.pending
  await advance(REVIEW_DEBOUNCE_MS + 10)
  await flush()
  out.reentrancy = {
    midPhase, pendingDuring, afterPhase, pendingAfter,
    asks: g.__askCalls ?? 0,
    exports: g.__exportCalls ?? 0,
    finalPhase: ctrl.phase,
  }
}

// ========== 5. Cancel invalidates in-flight ==========
{
  let resolveAsk!: (v: string) => void
  const askP = new Promise<string>((r) => { resolveAsk = r })
  const { ctrl } = await setupCtrl(() => askP)
  ctrl.trigger()
  await advance(REVIEW_DEBOUNCE_MS + 10)
  await flush()
  const mid = ctrl.phase
  ctrl.cancel()
  resolveAsk('{"issues":["should-not-post"]}')
  await flush()
  await flush()
  out.cancel = {
    mid, phase: ctrl.phase, pending: ctrl.pending,
    cards: reviewFeedAtom.get().length,
    asks: g.__askCalls ?? 0,
  }
}

// ========== 6. ask error → failed, no charge; can retrigger ==========
{
  const { ctrl } = await setupCtrl(new Error('vision down'))
  ctrl.trigger()
  await advance(REVIEW_DEBOUNCE_MS + 10)
  await flush()
  await flush()
  const afterFail = { phase: ctrl.phase, cards: reviewFeedAtom.get().length, asks: g.__askCalls ?? 0 }
  // retrigger with success
  setReviewAsk(async () => {
    g.__askCalls = (g.__askCalls ?? 0) + 1
    return '{"issues":["fixed"]}'
  })
  ctrl.trigger()
  await advance(REVIEW_DEBOUNCE_MS + 10)
  await flush()
  await flush()
  out.ask_fail_retry = {
    afterFail,
    afterRetry: {
      phase: ctrl.phase,
      cards: reviewFeedAtom.get().length,
      asks: g.__askCalls ?? 0,
      issue: reviewFeedAtom.get()[0]?.issues?.[0] ?? null,
    },
  }
}

// ========== 7. empty issues → succeed, no card ==========
{
  const { ctrl } = await setupCtrl('{"issues":[]}')
  ctrl.trigger()
  await advance(REVIEW_DEBOUNCE_MS + 10)
  await flush()
  await flush()
  out.empty_ok = {
    phase: ctrl.phase,
    cards: reviewFeedAtom.get().length,
    asks: g.__askCalls ?? 0,
    exports: g.__exportCalls ?? 0,
  }
}

// ========== 8. min shapes skip ==========
{
  await resetProactiveState()
  resetSettings(10)
  now = 0
  timers.clear()
  setReviewAsk(async () => { g.__askCalls++; return '{"issues":["x"]}' })
  const ed = makeEditor([
    { id: 's1', type: 'image', props: { w: 10, h: 10, assetId: 'a1', src: 'u' } },
    { id: 's2', type: 'geo', props: { w: 10, h: 10 } },
  ])
  const ctrl = createReviewController(ed)
  ctrl.trigger()
  await advance(REVIEW_DEBOUNCE_MS + 10)
  await flush()
  out.min_shapes = { phase: ctrl.phase, asks: g.__askCalls ?? 0, exports: g.__exportCalls ?? 0 }
}

// ========== 9. daily limit skip ==========
{
  await resetProactiveState()
  resetSettings(0) // daily 0
  now = 0
  timers.clear()
  g.__askCalls = 0
  g.__exportCalls = 0
  setReviewAsk(async () => { g.__askCalls++; return '{"issues":["x"]}' })
  const ed = makeEditor(threeShapes())
  const ctrl = createReviewController(ed)
  ctrl.trigger()
  await advance(REVIEW_DEBOUNCE_MS + 10)
  await flush()
  out.daily_limit = { phase: ctrl.phase, asks: g.__askCalls ?? 0, exports: g.__exportCalls ?? 0 }
}

// ========== 10. reviewFeed stamp has owner/workspace ==========
{
  await resetProactiveState()
  resetSettings(10)
  now = 0
  timers.clear()
  setReviewAsk(async () => '{"issues":["stamp-me"]}')
  const ed = makeEditor(threeShapes())
  const ctrl = createReviewController(ed)
  ctrl.trigger()
  await advance(REVIEW_DEBOUNCE_MS + 10)
  await flush()
  await flush()
  const card = reviewFeedAtom.get()[0]
  out.saas_stamp = {
    has_owner: !!card?.owner_id,
    has_workspace: !!card?.workspace_id,
    has_project: !!card?.project_id,
    owner: card?.owner_id ?? null,
    workspace: card?.workspace_id ?? null,
  }
  await clearReviewFeed()
}

process.stdout.write(JSON.stringify(out) + '\n')
