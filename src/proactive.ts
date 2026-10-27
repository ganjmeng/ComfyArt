import type { Editor } from 'tldraw'

import { api, readUserJson, uploadImage, viewUrl, writeUserJson } from './comfy'
import { botEnabledAtom, settingsAtom, type BotMessage } from './bot'
import { errorText, type ErrorSink } from './jobs'
import { ask, parseJson } from './llm'
import { announceMemoryUpdated } from './bot'
import { logMemory, memoryAtom, remember, toInputs } from './memory'
import { currentProject, notify } from './notices'
import { exportImage } from './shapes/ArtboardShape'
import { loadSkills, saveSkill, slug } from './skills'
import { onComfyEvent } from './ws'
import { lang, t } from './i18n'

export type Ability = 'memory' | 'skills' | 'review'
interface State { day: string; runs: Partial<Record<Ability, number>>; prompts: string[]; skillMark: number; reviewed: Record<string, string>; seen: string[] }

export const ABILITY_SETTINGS: Record<Ability, string> = { memory: 'proactive-memory', skills: 'proactive-skills', review: 'proactive-review' }
const FILE = 'comfyart/proactive.json'
const LOCK = 'comfyart-proactive'
const MAX_PROMPTS = 30
const SKILL_EVERY = 6
const MAX_SEEN = 50
const REVIEW_DELAY = 60000
const REVIEW_MIN_SHAPES = 3
const REVIEW_PX = 1024

const MEMORY_SYSTEM = 'You keep a long-term memory of a designer. From one exchange with their design agent, pull out only lasting preferences or facts the user stated about themselves, their taste or how they like to work. Ignore one-off requests and anything already remembered. Reply with ONE JSON object and nothing else: {"memories": [{"text": "<one short statement about the user, e.g. \\"Freelance illustrator based in Shanghai\\", in the user\'s language>", "category": "about|taste|work|assets"}]} (an empty list when there is nothing lasting).'
const SKILL_SYSTEM = 'You turn a designer\'s repeated way of working into a reusable skill for their design agent. You get their latest requests, numbered. If at least three of them follow the same workflow (same kind of deliverable, steps, format or style rules), write a skill for it; otherwise return null. Do not repeat an existing skill. Reply with ONE JSON object and nothing else: {"skill": null} or {"skill": {"name": "<short name in the user\'s language>", "instructions": "<step-by-step instructions for the agent, in English>", "samples": [<numbers of the requests it was learned from>]}}'
const REVIEW_SYSTEM = `You review a design canvas for a designer. The picture is cropped tightly around the content, so elements touching its edges are fine. Look for concrete problems: typos or garbled text in images, inconsistent colors or styles across a set, cut-off subjects inside an image, broken layouts, wrong aspect ratios, low-quality or deformed generations. Reply with ONE JSON object and nothing else: {"issues": ["<one problem and a fix, written in ${lang === 'zh' ? 'Simplified Chinese' : 'English'}>"]} (empty when nothing is wrong). At most 5 issues.`

const today = () => new Date().toLocaleDateString('sv')
const enabled = (a: Ability) => !!botEnabledAtom.get() && settingsAtom.get()[ABILITY_SETTINGS[a]] === true && (a !== 'memory' || settingsAtom.get()['memory-enabled'] !== false)
const dailyLimit = () => Number(settingsAtom.get()['proactive-daily']) || 0

async function withState<T>(fn: (s: State) => T | Promise<T>): Promise<T> {
  return navigator.locks.request(LOCK, async () => {
    const saved = await readUserJson<State>(FILE, { day: today(), runs: {}, prompts: [], skillMark: 0, reviewed: {}, seen: [] })
    const state = saved.day === today() ? saved : { ...saved, day: today(), runs: {} }
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
  return reply && user ? { user: text(user), reply: text(reply) } : null
}

async function learnMemory(ex: { user: string; reply: string }, chatId: string, messageId: string) {
  const known = memoryAtom.get().map((m) => `- ${m.text}`).join('\n')
  const raw = await ask(`Already remembered:\n${known || '(nothing)'}\n\nUser: ${ex.user}\n\nAgent: ${ex.reply.slice(0, 2000)}`, MEMORY_SYSTEM, [])
  const added = await remember(toInputs(parseJson(raw)?.memories), t('proactive.source'))
  if (added.length) await announceMemoryUpdated(chatId, messageId, added)
}

async function evolveSkill(prompts: string[]) {
  const existing = (await loadSkills()).map((s) => s.name).join(', ')
  const raw = await ask(`Existing skills: ${existing}\n\nLatest requests:\n${prompts.map((p, i) => `${i + 1}. ${p}`).join('\n')}`, SKILL_SYSTEM, [])
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
    const memory = take(s, 'memory')
    const due = s.prompts.length - Math.min(s.skillMark, s.prompts.length) >= SKILL_EVERY
    const skills = due && take(s, 'skills') ? s.prompts.slice(-SKILL_EVERY * 2) : null
    if (skills) s.skillMark = s.prompts.length
    return { memory, skills }
  })
  if (plan?.memory) await learnMemory(ex, e.chat_id, e.message_id)
  if (plan?.skills) await evolveSkill(plan.skills)
}

const signature = (editor: Editor) => [...editor.getCurrentPageShapeIds()].sort().join(',')

async function review(editor: Editor) {
  const ids = [...editor.getCurrentPageShapeIds()]
  if (ids.length < REVIEW_MIN_SHAPES) return
  const project = currentProject()
  const sig = signature(editor)
  const go = await withState((s) => {
    if (s.reviewed[project] === sig || !take(s, 'review')) return false
    s.reviewed[project] = sig
    return true
  })
  if (!go) return
  const bounds = editor.getCurrentPageBounds()!
  const { blob } = await exportImage(editor, ids, { format: 'png', background: true, scale: Math.min(1, REVIEW_PX / Math.max(bounds.w, bounds.h)) })
  const src = viewUrl(await uploadImage(blob, `review-${project}.png`))
  const issues = parseJson(await ask('Review this canvas.', REVIEW_SYSTEM, [src]))?.issues
  if (Array.isArray(issues) && issues.length) await notify({ kind: 'suggestion', title: t('proactive.reviewTitle'), body: issues.map((x) => `• ${x}`).join('\n') })
}

export function startProactive(editor: Editor, onError: ErrorSink) {
  const fail = (e: unknown) => onError(errorText(e))
  const stop = onComfyEvent('comfyart-bot', (e: { event: string; chat_id: string; message_id: string; status: string }) => {
    if (e.event === 'turn_done') void onTurnDone(e).catch(fail)
  })
  const timer = window.setTimeout(() => { if (enabled('review')) void review(editor).catch(fail) }, REVIEW_DELAY)
  return () => { stop(); clearTimeout(timer) }
}
