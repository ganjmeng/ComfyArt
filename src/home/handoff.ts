import type { Editor, TLImageShape } from 'tldraw'

import { agentModeAtom, draftAtom, extraRefsAtom, generateDirect, sendToAgent, type AgentMode } from '../agent'
import { refreshBot } from '../bot'
import { refFromUrl } from '../comfy'
import { editElements } from '../elements'
import { placeMedia, toMedia, type ErrorSink } from '../jobs'
import { loadSkills, skillAtom, skillCreatorAtom } from '../skills'

const KEYS = ['ask', 'mode', 'ref', 'skill', 'tool', 'createSkill']
const REF_LONG = 512
const GAP = 20

async function placeRefs(editor: Editor, srcs: string[]): Promise<TLImageShape[]> {
  const media = await Promise.all(srcs.map((src) => toMedia(refFromUrl(src), 'image')))
  const sizes = media.map((m) => Math.min(1, REF_LONG / Math.max(m.w, m.h)))
  const total = media.reduce((n, m, i) => n + m.w * sizes[i], 0) + GAP * (media.length - 1)
  const center = editor.getViewportPageBounds().center
  let x = center.x - total / 2
  return media.map((m, i) => {
    const w = m.w * sizes[i]
    const id = placeMedia(editor, m, m.ref.filename, x, center.y - m.h * sizes[i] / 2, w)
    x += w + GAP
    return editor.getShape<TLImageShape>(id)!
  })
}

export async function takeHandoff(editor: Editor, onError: ErrorSink) {
  const url = new URL(location.href)
  const text = url.searchParams.get('ask')?.trim() ?? ''
  const mode = (url.searchParams.get('mode') ?? 'agent') as AgentMode
  const refs = url.searchParams.getAll('ref')
  const skillId = url.searchParams.get('skill')
  const tool = url.searchParams.get('tool')
  const createSkill = url.searchParams.get('createSkill') === '1'
  if (!text && !refs.length && !skillId && !createSkill) return
  for (const k of KEYS) url.searchParams.delete(k)
  history.replaceState(null, '', url)
  if (createSkill) {
    skillCreatorAtom.set({ on: true })
    agentModeAtom.set('agent')
    if (!text && !refs.length && !skillId) return
  }
  if (tool === 'elements') {
    const [shape] = await placeRefs(editor, refs.slice(0, 1))
    if (shape) editElements(editor, shape, onError)
    return
  }

  agentModeAtom.set(mode)
  const skill = skillId ? (await loadSkills()).find((s) => s.id === skillId) ?? null : null
  if (skill) skillAtom.set(skill)
  const shapes = await placeRefs(editor, refs)
  if (!text) {
    extraRefsAtom.set(shapes.map((s) => s.id))
    return
  }
  await refreshBot()
  if (mode !== 'agent') return generateDirect(editor, text, [{ refs: shapes, prompt: text }], mode === 'video', onError)
  skillAtom.set(null)
  await sendToAgent(editor, text, shapes, skill)
}

/** #286: the project couldn't be created on the canvas page, so the home draft would be lost. Put the prompt from
 *  the URL back into the canvas chat box (and its mode), drop the handoff params so nothing auto-sends, and report. */
export function restoreHandoff(onError: ErrorSink, message: string) {
  const url = new URL(location.href)
  const text = url.searchParams.get('ask')?.trim() ?? ''
  const mode = url.searchParams.get('mode') as AgentMode | null
  for (const k of KEYS) url.searchParams.delete(k)
  history.replaceState(null, '', url)
  if (mode) agentModeAtom.set(mode)
  if (text) draftAtom.set(text)
  onError(message)
}
