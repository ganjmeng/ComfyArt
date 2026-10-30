import type { Editor } from 'tldraw'

import type { TLShape } from 'tldraw'

import { api, readUserJson, uploadImage, viewUrl, writeUserJson } from './comfy'
import { botEnabledAtom, settingsAtom, type BotMessage } from './bot'
import { errorText, mediaAsset, onImagePlaced, type ErrorSink } from './jobs'
import { ask as askDefault, parseJson } from './llm'
import { announceMemoryUpdated } from './bot'
import { logMemory, memoryAtom, remember, toInputs } from './memory'
import { OWNER_DEFAULT, WORKSPACE_DEFAULT } from './memoryStore'
import { currentProject, notify } from './notices'
import { loadReviewFeed, postReviewCard } from './reviewFeed'
import { transition, tryTransition, type ReviewPhase } from './reviewMachine'
import { exportImage } from './shapes/ArtboardShape'
import { loadSkills, saveSkill, slug } from './skills'
import { onComfyEvent } from './ws'
import { lang, t } from './i18n'
import { memoryFallbackAllowed } from './proactiveQuota'

export type Ability = 'memory' | 'skills' | 'review'
interface State { day: string; runs: Partial<Record<Ability, number>>; prompts: string[]; skillMark: number; reviewed: Record<string, string>; seen: string[]; owner_id?: string; workspace_id?: string }

export const ABILITY_SETTINGS: Record<Ability, string> = { memory: 'proactive-memory', skills: 'proactive-skills', review: 'proactive-review' }
const FILE = 'comfyart/proactive.json'
const LOCK = 'comfyart-proactive'
const MAX_PROMPTS = 30
const SKILL_EVERY = 6
const MAX_SEEN = 50
/** #386: debounce window after 出图完成 / canvas change before export+ask. */
export const REVIEW_DEBOUNCE_MS = 5000
let askFn: typeof askDefault = askDefault
/** Test seam: swap the vision `ask` used by canvas review (no paid calls in CI). */
export function setReviewAsk(fn: typeof askDefault | null) { askFn = fn ?? askDefault }
export const REVIEW_MIN_SHAPES = 3
const REVIEW_PX = 1024
/** @deprecated alias — old one-shot timer; tests may still import the name. */
export const REVIEW_DELAY = REVIEW_DEBOUNCE_MS

const MEMORY_SYSTEM = 'You keep a long-term memory of a designer. From one exchange with their design agent, save only what the user told us: preferences, brands, requirements and facts they stated, and conclusions the user confirmed or chose in this exchange (e.g. picked palette 2, always 16:9). Never save the agent\'s guesses, plans the user has not confirmed, generated content itself, or one-off task details; every memory must trace back to one user sentence or choice. Ignore anything already remembered. Reply with ONE JSON object and nothing else: {"memories": [{"text": "<one short statement about the user, e.g. \\"Freelance illustrator based in Shanghai\\", in the user\'s language>", "category": "about|taste|work|assets"}]} (an empty list when there is nothing lasting).'
const SKILL_SYSTEM = 'You turn a designer\'s repeated way of working into a reusable skill for their design agent. You get their latest requests, numbered. If at least three of them follow the same workflow (same kind of deliverable, steps, format or style rules), write a skill for it; otherwise return null. Do not repeat an existing skill. Reply with ONE JSON object and nothing else: {"skill": null} or {"skill": {"name": "<short name in the user\'s language>", "instructions": "<step-by-step instructions for the agent, in English>", "samples": [<numbers of the requests it was learned from>]}}'
const REVIEW_SYSTEM = `You review a design canvas for a designer. The picture is cropped tightly around the content, so elements touching its edges are fine. Look for concrete problems: typos or garbled text in images, inconsistent colors or styles across a set, cut-off subjects inside an image, broken layouts, wrong aspect ratios, low-quality or deformed generations. Reply with ONE JSON object and nothing else: {"issues": ["<one problem and a fix, written in ${lang === 'zh' ? 'Simplified Chinese' : 'English'}>"]} (empty when nothing is wrong). At most 5 issues.`

const today = () => new Date().toLocaleDateString('sv')
const enabled = (a: Ability) => !!botEnabledAtom.get() && settingsAtom.get()[ABILITY_SETTINGS[a]] === true && (a !== 'memory' || settingsAtom.get()['memory-enabled'] !== false)
const dailyLimit = () => Number(settingsAtom.get()['proactive-daily']) || 0

async function withState<T>(fn: (s: State) => T | Promise<T>): Promise<T> {
  return navigator.locks.request(LOCK, async () => {
    const saved = await readUserJson<State>(FILE, { day: today(), runs: {}, prompts: [], skillMark: 0, reviewed: {}, seen: [], owner_id: OWNER_DEFAULT, workspace_id: WORKSPACE_DEFAULT })
    const state = saved.day === today() ? saved : { ...saved, day: today(), runs: {} }
    state.owner_id = state.owner_id || OWNER_DEFAULT
    state.workspace_id = state.workspace_id || WORKSPACE_DEFAULT
    const out = await fn(state)
    await writeUserJson(FILE, state)
    return out
  })
}

function take(state: State, a: Ability): boolean {
  if (!enabled(a) || (state.runs[a] ?? 0) >= dailyLimit()) return false
  state.runs[a] = (state.runs[a] ?? 0) + 1
  return true
}

export const runsToday = () => readUserJson<State | null>(FILE, null).then((s) => (s?.day === today() ? s.runs : {}))

async function exchange(chatId: string, messageId: string) {
  const res = await api(`/comfyart/bot/chats/${chatId}`)
  if (!res.ok) return null
  const { messages } = await res.json() as { messages: BotMessage[] }
  const reply = messages.find((m) => m.id === messageId)
  const user = messages.find((m) => m.id === reply?.parent_id)
  const text = (m?: BotMessage) => m?.blocks.filter((b) => b.type === 'text').map((b) => b.text ?? '').join('').trim() ?? ''
  return reply && user ? { user: text(user), reply: text(reply), wrote: turnWroteMemory(reply.blocks) } : null
}

/** #413: the turn already saved memory in-loop (memory tool -> memory_updated block). */
export const turnWroteMemory = (blocks: { type: string }[]) => blocks.some((b) => b.type === 'memory_updated')

async function learnMemory(ex: { user: string; reply: string }, chatId: string, messageId: string): Promise<number> {
  const known = memoryAtom.get().map((m) => `- ${m.text}`).join('\n')
  const raw = await askDefault(`Already remembered:\n${known || '(nothing)'}\n\nUser: ${ex.user}\n\nAgent: ${ex.reply.slice(0, 2000)}`, MEMORY_SYSTEM, [])
  const added = await remember(toInputs(parseJson(raw)?.memories), t('proactive.source'))
  if (added.length) await announceMemoryUpdated(chatId, messageId, added)
  return added.length
}

async function evolveSkill(prompts: string[]) {
  const existing = (await loadSkills()).map((s) => s.name).join(', ')
  const raw = await askDefault(`Existing skills: ${existing}\n\nLatest requests:\n${prompts.map((p, i) => `${i + 1}. ${p}`).join('\n')}`, SKILL_SYSTEM, [])
  const skill = parseJson(raw)?.skill as { name?: string; instructions?: string; samples?: number[] } | null | undefined
  if (!skill?.name || !skill.instructions) return
  const samples = (skill.samples ?? []).map((n) => prompts[n - 1]).filter(Boolean)
  await saveSkill({ id: `learned-${slug(skill.name)}`, name: skill.name, instructions: skill.instructions, custom: true, learned: samples })
  await logMemory([{ action: 'skill', text: skill.name, source: t('proactive.source') }])
  await notify({ kind: 'suggestion', title: t('proactive.skillLearned', skill.name), body: t('proactive.learnedFrom', samples.length, samples.slice(0, 3).join(' / ')) })
}

async function onTurnDone(e: { chat_id: string; message_id: string; status: string }) {
  if (e.status !== 'done' || !botEnabledAtom.get()) return
  const ex = await exchange(e.chat_id, e.message_id)
  if (!ex?.user) return
  const plan = await withState((s) => {
    if (s.seen.includes(e.message_id)) return null
    s.seen = [e.message_id, ...s.seen].slice(0, MAX_SEEN)
    s.prompts = [...s.prompts, ex.user].slice(-MAX_PROMPTS)
    // #424: do not take memory quota here — only after a real fallback write
    const memory = memoryFallbackAllowed(ex.wrote, s.runs.memory ?? 0, dailyLimit(), enabled('memory'))
    const due = s.prompts.length - Math.min(s.skillMark, s.prompts.length) >= SKILL_EVERY
    const skills = due && take(s, 'skills') ? s.prompts.slice(-SKILL_EVERY * 2) : null
    if (skills) s.skillMark = s.prompts.length
    return { memory, skills }
  })
  // #413: fallback only when the agent did not write memory with its tool this turn
  // #424: charge daily quota only after a real write (already-wrote → no charge; empty learn → no charge)
  if (plan?.memory) {
    const n = await learnMemory(ex, e.chat_id, e.message_id)
    if (n > 0) await withState((s) => { take(s, 'memory') })
  }
  if (plan?.skills) await evolveSkill(plan.skills)
}

/** #386: signature covers shape id + type + image src so replacing image content re-triggers. */
export function canvasSignature(editor: Editor): string {
  const ids = [...editor.getCurrentPageShapeIds()].sort()
  return ids.map((id) => {
    const shape = editor.getShape(id) as TLShape | undefined
    if (!shape) return String(id)
    const asset = mediaAsset(editor, shape)
    const src = asset?.props.src ?? ''
    const p = shape.props as { w?: number; h?: number; assetId?: string }
    return `${id}:${shape.type}:${p.assetId ?? ''}:${src}:${Math.round(p.w ?? 0)}x${Math.round(p.h ?? 0)}`
  }).join('|')
}


interface ReviewRuntime {
  phase: ReviewPhase
  timer: number
  /** Generation token — cancel bumps it so in-flight export/ask cannot post. */
  gen: number
  /** Triggers while exporting/reviewing → one follow-up after finish (AC3). */
  pending: boolean
  lastSig: string
}

async function runReview(editor: Editor, rt: ReviewRuntime, onError: ErrorSink) {
  const myGen = rt.gen
  const alive = () => myGen === rt.gen
  const finishFail = () => {
    if (!alive()) return
    if (rt.phase === 'exporting' || rt.phase === 'reviewing') rt.phase = transition(rt.phase, 'fail')
    if (rt.phase === 'failed') rt.phase = transition(rt.phase, 'ack')
    maybeFollowUp(editor, rt, onError)
  }
  const finishCancelOrSkip = () => {
    if (!alive()) return
    if (rt.phase === 'scheduled' || rt.phase === 'exporting' || rt.phase === 'reviewing') {
      rt.phase = transition(rt.phase, 'cancel')
    }
    maybeFollowUp(editor, rt, onError)
  }

  if (rt.phase !== 'scheduled') return
  const ids = [...editor.getCurrentPageShapeIds()]
  if (ids.length < REVIEW_MIN_SHAPES) { finishCancelOrSkip(); return }

  const project = currentProject()
  const sig = canvasSignature(editor)
  // Gate only — charge + remember signature after a successful ask (AC6: fail can retrigger).
  const allowed = await withState((s) => {
    if (s.reviewed[project] === sig) return false
    if (!enabled('review') || (s.runs.review ?? 0) >= dailyLimit()) return false
    return true
  })
  if (!alive()) return
  if (!allowed) { finishCancelOrSkip(); return }

  try {
    rt.phase = transition(rt.phase, 'start_export')
    const bounds = editor.getCurrentPageBounds()
    if (!bounds) throw new Error('no page bounds')
    const { blob } = await exportImage(editor, ids, {
      format: 'png', background: true,
      scale: Math.min(1, REVIEW_PX / Math.max(bounds.w, bounds.h)),
    })
    if (!alive()) return
    const uploaded = viewUrl(await uploadImage(blob, `review-${project || 'canvas'}.png`))
    if (!alive()) return

    rt.phase = transition(rt.phase, 'start_review')
    let raw: string
    try {
      raw = await askFn('Review this canvas.', REVIEW_SYSTEM, [uploaded])
    } catch {
      finishFail()
      return
    }
    if (!alive()) return

    const parsed = parseJson(raw)
    const issues = Array.isArray(parsed?.issues)
      ? (parsed!.issues as unknown[]).filter((x): x is string => typeof x === 'string')
      : null
    if (issues == null) { finishFail(); return }

    await withState((s) => { take(s, 'review'); s.reviewed[project] = sig })
    if (!alive()) return
    rt.lastSig = sig
    rt.phase = transition(rt.phase, 'succeed')
    if (issues.length) {
      await postReviewCard({ title: t('proactive.reviewTitle'), issues: issues.slice(0, 5), project_id: project })
      if (!alive()) return
      await notify({
        kind: 'suggestion',
        title: t('proactive.reviewTitle'),
        body: issues.slice(0, 5).map((x) => `• ${x}`).join('\n'),
      })
    }
    if (!alive()) return
    rt.phase = transition(rt.phase, 'ack')
    maybeFollowUp(editor, rt, onError)
  } catch (e) {
    if (!alive()) return
    finishFail()
    onError(errorText(e))
  }
}

function maybeFollowUp(editor: Editor, rt: ReviewRuntime, onError: ErrorSink) {
  if (!rt.pending) return
  rt.pending = false
  scheduleReview(editor, rt, onError)
}

function scheduleReview(editor: Editor, rt: ReviewRuntime, onError: ErrorSink) {
  if (!enabled('review')) return
  if (rt.phase === 'exporting' || rt.phase === 'reviewing') {
    rt.pending = true // AC3: at most one follow-up after current run
    return
  }
  if (rt.phase === 'notified' || rt.phase === 'failed') rt.phase = transition(rt.phase, 'ack')
  const step = tryTransition(rt.phase, 'schedule')
  if (!step.ok) return
  rt.phase = step.phase
  clearTimeout(rt.timer)
  rt.timer = window.setTimeout(() => {
    rt.timer = 0
    if (rt.phase !== 'scheduled') return
    void runReview(editor, rt, onError)
  }, REVIEW_DEBOUNCE_MS)
}

function cancelReview(rt: ReviewRuntime) {
  clearTimeout(rt.timer)
  rt.timer = 0
  rt.gen += 1 // invalidate in-flight
  rt.pending = false
  if (rt.phase !== 'idle') rt.phase = transition(rt.phase, 'cancel')
}

export function startProactive(editor: Editor, onError: ErrorSink) {
  const fail = (e: unknown) => onError(errorText(e))
  void loadReviewFeed().catch(fail)
  const rt: ReviewRuntime = { phase: 'idle', timer: 0, gen: 0, pending: false, lastSig: '' }

  const stopBot = onComfyEvent('comfyart-bot', (e: { event: string; chat_id: string; message_id: string; status: string }) => {
    if (e.event === 'turn_done') void onTurnDone(e).catch(fail)
  })

  const onTrigger = () => {
    if (!enabled('review')) return
    const ids = [...editor.getCurrentPageShapeIds()]
    if (ids.length < REVIEW_MIN_SHAPES) return
    // Skip identical content (signature) — AC4: unchanged → 0 ask
    const sig = canvasSignature(editor)
    if (sig && sig === rt.lastSig && (rt.phase === 'idle' || rt.phase === 'scheduled')) {
      // still allow re-arm only when content changed; identical while idle = no-op
      if (rt.phase === 'idle') return
    }
    scheduleReview(editor, rt, fail)
  }

  // Canvas change (document scope) — debounce inside scheduleReview
  const stopStore = editor.store.listen(() => { onTrigger() }, { scope: 'document' })
  // 出图完成
  const stopPlaced = onImagePlaced(() => { onTrigger() })

  return () => {
    stopBot()
    stopStore()
    stopPlaced()
    cancelReview(rt)
  }
}

/** Test seam: drive the review runtime without a live editor store. */
export function createReviewController(editor: Editor, onError: ErrorSink = () => {}) {
  const rt: ReviewRuntime = { phase: 'idle', timer: 0, gen: 0, pending: false, lastSig: '' }
  return {
    get phase() { return rt.phase },
    get pending() { return rt.pending },
    trigger: () => scheduleReview(editor, rt, onError),
    cancel: () => cancelReview(rt),
    /** Mark lastSig so an identical canvas is treated as unchanged (AC4). */
    rememberSig: () => { rt.lastSig = canvasSignature(editor) },
  }
}
