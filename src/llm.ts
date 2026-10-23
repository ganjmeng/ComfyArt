import { atom } from 'tldraw'

import { api, uploadImage, viewUrl } from './comfy'
import { wsBodyError } from './wsErrors'
import { estimateCost } from './wavespeedKey'
import { t } from './i18n'
import { botEnabledAtom, settingsAtom } from './bot'

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
  const res = await api('/comfyart/llm/complete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: prompt, system, images }) })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(wsBodyError(body, t('llm.agentCallFailed', res.status)))
  return body.text as string
}

/** #185: audio length in seconds from the media element's metadata (whisper is charged per second); undefined when
 * the browser can't tell (the quote then uses the 60 s fallback, labelled). MediaRecorder webm reports Infinity until
 * seeked to the end, so seek far once before giving up. */
export function mediaDuration(src: string | Blob, timeoutMs = 4000): Promise<number | undefined> {
  return new Promise((resolve) => {
    const el = document.createElement('audio')
    const url = typeof src === 'string' ? src : URL.createObjectURL(src)
    let done = false
    const finish = (d?: number) => {
      if (done) return
      done = true
      clearTimeout(timer)
      el.removeAttribute('src'); el.load()
      if (typeof src !== 'string') URL.revokeObjectURL(url)
      resolve(d != null && Number.isFinite(d) && d > 0 ? d : undefined)
    }
    const timer = setTimeout(() => finish(), timeoutMs)
    el.preload = 'metadata'
    el.onerror = () => finish()
    el.onloadedmetadata = () => {
      if (Number.isFinite(el.duration)) return finish(el.duration)
      el.ondurationchange = () => { if (Number.isFinite(el.duration)) finish(el.duration) }
      el.currentTime = 1e101
    }
    el.src = url
  })
}

export type TranscribeQuote = { price: number | null; durationEstimated: boolean }

export async function transcribe(audio: Blob, onQuote?: (q: TranscribeQuote) => void): Promise<string> {
  const [ref, duration] = await Promise.all([uploadImage(audio, `voice-${Date.now()}.webm`), mediaDuration(audio)])
  return transcribeFile(viewUrl(ref), duration, onQuote)
}

export async function transcribeFile(src: string, duration?: number, onQuote?: (q: TranscribeQuote) => void): Promise<string> {
  // speech-to-text runs on WaveSpeed (wavespeed-ai/openai-whisper-turbo), charged per second of audio (#185)
  if (duration === undefined) duration = await mediaDuration(src)
  if (onQuote) void estimateCost({ feature: 'transcribe', audio: src, ...(duration ? { duration } : {}) })
    .then((e) => { if (e) onQuote({ price: e.price ?? null, durationEstimated: !!e.duration_estimated }) }).catch(() => {})
  const res = await api('/comfyart/wavespeed/transcribe', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ src, ...(duration ? { duration } : {}) }) })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(wsBodyError(body, `transcribe failed: ${res.status}`))
  return String(body.text ?? '')
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
  // OCR runs on WaveSpeed paddle-ocr (backend /comfyart/ocr)
  setStatus(src, { stage: 'reading', tokens: 0 })
  const res = await api('/comfyart/ocr', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ src }) })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(wsBodyError(body, `ocr failed: ${res.status}`))
  return ((body.lines ?? []) as { text?: string }[]).map((l) => l.text ?? '').join('\n')
}

export async function captionImage(src: string): Promise<string> {
  // image captioning runs on WaveSpeed (wavespeed-ai/image-captioner)
  const res = await api('/comfyart/wavespeed/caption', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ src }) })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(wsBodyError(body, `caption failed: ${res.status}`))
  return String(body.text ?? '')
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
