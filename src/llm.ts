import { atom } from 'tldraw'

import { api, loadNamed, queuePrompt, uploadImage, viewUrl, waitForText } from './comfy'
import { t } from './i18n'
import { botEnabledAtom, settingsAtom } from './bot'
import { annotated } from './workflows'

function firstObject(text: string): string {
  const start = text.indexOf('{')
  let depth = 0
  let quoted = false
  for (let i = Math.max(start, 0); i < text.length; i++) {
    const c = text[i]
    if (quoted) {
      if (c === '\\') i++
      else if (c === '"') quoted = false
    } else if (c === '"') quoted = true
    else if (c === '{') depth++
    else if (c === '}' && --depth === 0) return text.slice(start, i + 1)
  }
  return text.slice(start)
}

export function stripThink(raw: string): string {
  return raw.replace(/<think>[\s\S]*?<\/think>/g, '').replace(/^[\s\S]*<\/think>/, '').trim()
}

export function parseJson(raw: string): Record<string, unknown> | null {
  const text = stripThink(raw)
  try {
    return JSON.parse(firstObject(text))
  } catch {
    return null
  }
}

export async function ask(prompt: string, system: string, images: string[]): Promise<string> {
  const res = await api('/comfyart/bot/complete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: prompt, system, images }) })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.error ?? t('llm.agentCallFailed', res.status))
  return body.text as string
}

export async function transcribe(audio: Blob): Promise<string> {
  const ref = await uploadImage(audio, `voice-${Date.now()}.webm`)
  return transcribeFile(viewUrl(ref))
}

export async function transcribeFile(src: string): Promise<string> {
  const { graph: g, id } = await loadNamed('transcribe-gemma4.api.json', 'prompt', 'save')
  g.a = { class_type: 'LoadAudio', inputs: { audio: annotated(src) } }
  Object.assign(g[id.prompt].inputs, {
    audio: ['a', 0],
    prompt: 'Transcribe the speech exactly. Output only the transcript. Write Chinese in simplified characters.',
    system_prompt: 'You are a speech recognition engine.',
  })
  return stripThink(await waitForText(await queuePrompt(g), id.save))
}

const OCR_PROMPT = 'List every piece of text visible in this image exactly as written, one text block per line, from top to bottom. Output only the text lines, nothing else.'
const OCR_SYSTEM = 'You are a precise OCR engine.'
const ocrCache = new Map<string, Promise<string[]>>()

export interface OcrStatus { stage: 'queued' | 'loading' | 'reading' | 'agent'; tokens: number }
export const ocrStatusAtom = atom<Record<string, OcrStatus>>('ocr status', {})

function setStatus(src: string, status: OcrStatus | null) {
  const { [src]: _, ...rest } = ocrStatusAtom.get()
  ocrStatusAtom.set(status ? { ...rest, [src]: status } : rest)
}

async function cloudOcr(src: string): Promise<string> {
  // cloud paddle-ocr via api/ocr.py; the local gemma OCR workflow is no longer used
  setStatus(src, { stage: 'reading', tokens: 0 })
  const res = await api('/comfyart/ocr', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ src }) })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.error ?? `OCR failed: ${res.status}`)
  return ((body.lines ?? []) as { text: string }[]).map((l) => l.text).join('\n')
}

async function agentOcr(src: string): Promise<string> {
  setStatus(src, { stage: 'agent', tokens: 0 })
  return ask(OCR_PROMPT, OCR_SYSTEM, [src])
}

export function ocrLines(src: string): Promise<string[]> {
  const engine = settingsAtom.get()['ocr-engine'] === 'agent' && botEnabledAtom.get() ? 'agent' : 'cloud'
  const key = `${engine}|${src}`
  if (!ocrCache.has(key)) {
    const job = (engine === 'agent' ? agentOcr(src) : cloudOcr(src))
      .then((text) => [...new Set(stripThink(text).split('\n').map((l) => l.trim()).filter(Boolean))])
      .finally(() => setStatus(src, null))
    job.catch(() => ocrCache.delete(key))
    ocrCache.set(key, job)
  }
  return ocrCache.get(key)!
}
