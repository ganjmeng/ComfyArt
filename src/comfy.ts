import { confirmAtom } from './ui/Confirm'
import { readLocal } from './localPrefs'
import { t } from './i18n'
import { onComfyEvent } from './ws'
import { isWsGraph, WS_ID } from './wavespeed'
import { keySettingsOpenAtom, keyStatusAtom, outOfCredit, refreshKeyStatus } from './wavespeedKey'

const POLL_MS = 1500

export type PromptGraph = Record<string, { class_type: string; inputs: Record<string, unknown>; _meta?: { title?: string } }>

export interface ImageRef { filename: string; subfolder: string; type: string; metadata?: { width?: number; height?: number } }

function comfyUser(): string | null {
  return readLocal('Comfy.userId')
}

// WaveSpeed is the only generation provider; jobs always run there.
export const validTarget = (t: unknown): string | null => (t === 'auto' ? 'auto' : null)
export const defaultTarget = () => 'auto'

export function api(path: string, init?: RequestInit) {
  const user = comfyUser()
  return fetch(`/api${path}`, user ? { ...init, headers: { ...init?.headers, 'Comfy-User': user } } : init)
}

const userFile = (path: string) => `/userdata/${encodeURIComponent(path)}`

export async function readUserText(path: string): Promise<string | null> {
  const res = await api(`/comfyart${userFile(path)}`)
  if (res.status === 204) return null
  if (!res.ok) throw new Error(`read ${path} failed: ${res.status}`)
  return res.text()
}

export async function readUserJson<T>(path: string, fallback: T): Promise<T> {
  const text = await readUserText(path)
  return text === null ? fallback : JSON.parse(text)
}

export async function writeUserText(path: string, body: string) {
  const res = await api(`${userFile(path)}?overwrite=true&full_info=false`, { method: 'POST', body })
  if (!res.ok) throw new Error(`save ${path} failed: ${res.status}`)
}

export const writeUserJson = (path: string, data: unknown) => writeUserText(path, JSON.stringify(data))

export async function listUserFiles(dir: string, recurse = false): Promise<string[]> {
  const res = await api(`/userdata?dir=${encodeURIComponent(dir)}${recurse ? '&recurse=true&split=false&full_info=false' : ''}`)
  if (res.status === 404) return []
  if (!res.ok) throw new Error(`list ${dir} failed: ${res.status}`)
  return ((await res.json()) as string[]).map((f) => f.replaceAll('\\', '/'))
}

export async function deleteUserFile(path: string) {
  await api(userFile(path), { method: 'DELETE' })
}

export function viewUrl(ref: ImageRef): string {
  const q = new URLSearchParams({ filename: ref.filename, subfolder: ref.subfolder, type: ref.type })
  return `/api/view?${q}`
}

export function thumbUrl(src: string, max = 256): string {
  return `/comfyart/thumb?${new URLSearchParams({ url: src, max: String(max) })}`
}

const THUMB_SIZES = [256, 512, 1024]

export const thumbSize = (edge: number) => THUMB_SIZES.find((s) => edge <= s)

export const isViewUrl = (src: string) => src.startsWith('/api/view?')

export function refFromUrl(src: string): ImageRef {
  const q = new URL(src, location.origin).searchParams
  return { filename: q.get('filename') ?? '', subfolder: q.get('subfolder') ?? '', type: q.get('type') ?? 'input' }
}

export const AUDIO_EXTS = ['mp3', 'wav', 'flac', 'ogg', 'm4a', 'opus']
const VIDEO_EXTS = ['mp4', 'webm', 'mov', 'mkv']
export type RefKind = 'image' | 'video' | 'audio'

export function refKind(src: string): RefKind {
  const ext = refFromUrl(src).filename.toLowerCase().split('.').pop() ?? ''
  return VIDEO_EXTS.includes(ext) ? 'video' : AUDIO_EXTS.includes(ext) ? 'audio' : 'image'
}

export function mediaMeta(src: string, kind: RefKind): Promise<{ seconds: number; w: number; h: number }> {
  return new Promise((resolve, reject) => {
    if (kind === 'image') {
      const img = new Image()
      img.onload = () => resolve({ seconds: 0, w: img.naturalWidth, h: img.naturalHeight })
      img.onerror = () => reject(new Error(`cannot read ${src}`))
      img.src = src
      return
    }
    const el = document.createElement(kind)
    el.preload = 'metadata'
    el.onloadedmetadata = () => resolve({ seconds: el.duration, w: el instanceof HTMLVideoElement ? el.videoWidth : 0, h: el instanceof HTMLVideoElement ? el.videoHeight : 0 })
    el.onerror = () => reject(new Error(`cannot read ${src}`))
    el.src = src
  })
}

export async function uploadImage(file: Blob, name: string): Promise<ImageRef> {
  const body = new FormData()
  body.append('image', file, name)
  body.append('subfolder', 'comfyart')
  body.append('type', 'input')
  const res = await api('/upload/image', { method: 'POST', body })
  if (!res.ok) throw new Error(`upload failed: ${res.status}`)
  const data = await res.json()
  return { filename: data.name, subfolder: data.subfolder ?? 'comfyart', type: data.type ?? 'input' }
}

export const titleTags = (node: PromptGraph[string]) => (node._meta?.title ?? '').toLowerCase().split(/[\s,]+/).filter((w) => w.startsWith('@'))

let modelPaths: Record<string, string> = {}

export async function loadModelPaths(): Promise<Record<string, string>> {
  const res = await fetch('/comfyart/model-paths')
  modelPaths = res.ok ? await res.json() : {}
  return modelPaths
}

function promptError(body: any, status: number): string {
  const lines = Object.entries<any>(body?.node_errors ?? {}).flatMap(([id, ne]) =>
    (ne?.errors ?? []).map((er: any) => `${ne.class_type ?? ''} #${id}: ${er.message}${er.details ? ` — ${er.details}` : ''}`))
  if (lines.length) return lines.join('\n')
  const top = body?.error
  if (!top?.message) return `queue failed: ${status}`
  return top.details ? `${top.message}: ${top.details}` : top.message
}

type WsHook = (inputs: Record<string, unknown>) => Promise<Record<string, unknown>>
let wsHook: WsHook = async ({ custom: _custom, ...rest }) => rest

/** custom_workflow swaps in the user's WaveSpeed model for jobs tagged with a custom action. */
export function setWsHook(hook: WsHook) {
  wsHook = hook
}

/** Second confirmation for costly cloud jobs, in the app's own Confirm dialog. */
export function askCost(price: number, segSplits?: number, segCapped?: boolean): Promise<boolean> {
  // #138: seg maps quote an upper bound before anything is recognised (nothing is charged before this dialog);
  // on a retry only the classes still missing a mask are quoted
  const p = price.toFixed(2)
  const desc = typeof segSplits !== 'number' ? t('jobs.confirmCost', p)
    : segCapped ? t('jobs.confirmSegMax', p, segSplits) : t('jobs.confirmSegLeft', p, segSplits)
  return new Promise((resolve) => confirmAtom.set({
    title: t('jobs.confirmTitle'), desc, ok: t('jobs.confirmOk'),
    run: () => resolve(true), cancel: () => resolve(false),
  }))
}

export async function queuePrompt(prompt: PromptGraph, _runOn = defaultTarget()): Promise<string> {
  const init = { method: 'POST', headers: { 'Content-Type': 'application/json' } }
  if (isWsGraph(prompt)) {
    const key = keyStatusAtom.get()
    if (key && !key.configured) { keySettingsOpenAtom.set(true); throw new Error(t('wsKey.needKey')) }
    if (outOfCredit(key)) throw new Error(t('wsKey.needCredit'))
    const inputs = await wsHook(Object.values(prompt)[0].inputs as Record<string, unknown>)
    let ws = await api('/comfyart/wavespeed/run', { ...init, body: JSON.stringify({ inputs }) })
    let wsBody = await ws.json().catch(() => null)
    const price = wsBody?.error?.confirm_usd
    if (ws.status === 409 && typeof price === 'number') {
      // jobs of $0.50 or more need an explicit yes before they are submitted
      if (!(await askCost(price, wsBody?.error?.seg_splits, wsBody?.error?.seg_capped))) throw new Error(t('jobs.costDeclined'))
      ws = await api('/comfyart/wavespeed/run', { ...init, body: JSON.stringify({ inputs: { ...inputs, confirmed: true } }) })
      wsBody = await ws.json().catch(() => null)
    }
    if (!ws.ok) throw new Error(promptError(wsBody, ws.status))
    return String(wsBody.prompt_id)
  }
  // Only WaveSpeed graphs can run; tools not yet ported fail clearly.
  throw new Error(t('jobs.notInCloud'))
}

const queued = (list: unknown[] | undefined, promptId: string) => (list ?? []).some((e) => Array.isArray(e) && String(e[1]) === promptId)

async function inQueue(promptId: string): Promise<boolean> {
  const q = await (await api('/queue')).json()
  return queued(q.queue_running, promptId) || queued(q.queue_pending, promptId)
}

export async function cancelPrompt(promptId: string) {
  if (promptId.startsWith(WS_ID)) {
    await api(`/comfyart/wavespeed/cancel/${promptId.slice(WS_ID.length)}`, { method: 'POST' })
    return
  }
  const q = await (await api('/queue')).json()
  const post = (path: string, body: unknown) => api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (queued(q.queue_pending, promptId)) await post('/queue', { delete: [promptId] })
  else if (queued(q.queue_running, promptId)) await post('/interrupt', { prompt_id: promptId })
}

const wakers = new Map<string, Set<() => void>>()
for (const type of ['execution_success', 'execution_error', 'execution_interrupted']) {
  onComfyEvent(type, (d: { prompt_id?: string }) => { for (const wake of wakers.get(String(d?.prompt_id)) ?? []) wake() })
}

function nap(promptId: string) {
  return new Promise<void>((resolve) => {
    const set = wakers.get(promptId) ?? new Set()
    wakers.set(promptId, set)
    const wake = () => {
      clearTimeout(timer)
      set.delete(wake)
      if (!set.size) wakers.delete(promptId)
      resolve()
    }
    const timer = setTimeout(wake, POLL_MS)
    set.add(wake)
  })
}

export async function promptHistory(promptId: string): Promise<any> {
  const res = promptId.startsWith(WS_ID) ? await api(`/comfyart/wavespeed/history/${promptId.slice(WS_ID.length)}`)

      : await api(`/history/${promptId}`)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.error?.message ?? `history failed: ${res.status}`)
  return body[promptId]
}

async function waitForOutput<T>(promptId: string, node: string, pick: (out: Record<string, any>) => T | null): Promise<T> {
  let misses = 0
  for (;;) {
    const hist = await promptHistory(promptId)
    if (hist) {
      const messages: [string, any][] = hist.status?.messages ?? []
      const err = messages.find((m) => m[0] === 'execution_error')
      if (err) throw new Error(String(err[1]?.exception_message ?? 'execution failed'))
      if (messages.some((m) => m[0] === 'execution_interrupted')) throw new Error(t('jobs.interrupted'))
      const value = hist.outputs?.[node] ? pick(hist.outputs[node]) : null
      if (value) {
        if (promptId.startsWith(WS_ID)) void refreshKeyStatus()
        return value
      }
      if (hist.status?.completed || hist.status?.status_str === 'error') throw new Error(t('jobs.noOutput'))
    } else if (promptId.startsWith(WS_ID) || await inQueue(promptId)) {
      misses = 0
    } else if (++misses >= 2) {
      throw new Error(t('jobs.lost'))
    }
    await nap(promptId)
  }
}

export function waitForImages(promptId: string, node: string): Promise<ImageRef[]> {
  return waitForOutput(promptId, node, (out) => {
    const items = [...(out.images ?? []), ...(out.videos ?? []), ...(out.gifs ?? []), ...(out.audio ?? []), ...(out['3d'] ?? [])]
    return items.length ? items as ImageRef[] : null
  })
}

export function waitForText(promptId: string, node: string): Promise<string> {
  return waitForOutput(promptId, node, (out) => (out.text ? String(out.text.join('')) : null))
}
