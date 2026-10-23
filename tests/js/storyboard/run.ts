// #168: real comfy.ts queuePrompt -> cost confirm -> waitForImages, then real jobs.ts placeMedia onto a mock canvas,
// all against the live mock backend started by tests/test_storyboard_flow.py (BASE). Mocks only, $0.
import { asked } from './stubs'
import { setLang } from '../i18n_stub'
import { queuePrompt, viewUrl, waitForImages } from '../../../src/comfy'
import { placeMedia } from '../../../src/jobs'
import { wsBuilt } from '../../../src/wavespeed'

setLang('zh')
const base = process.env.BASE!
const calls: { path: string; body: unknown }[] = []
const realFetch = globalThis.fetch
globalThis.fetch = (async (u: string, init?: RequestInit) => {
  const path = String(u).replace(/^\/api/, '')
  calls.push({ path, body: init?.body ? JSON.parse(String(init.body)) : null })
  return realFetch(base + path, init)
}) as typeof fetch
const realSetTimeout = globalThis.setTimeout
;(globalThis as any).setTimeout = ((f: () => void, ms = 0, ...a: unknown[]) => realSetTimeout(f, ms === 1500 ? 20 : ms, ...a)) as any  // shorten the 1.5 s poll nap

const inputs = JSON.parse(process.env.INPUTS!)
const { graph, result } = wsBuilt(inputs)  // same builder generate.ts uses for a storyboard card
const id = await queuePrompt(graph)
const refs = await waitForImages(id, result)
const media = refs.map((ref) => ({ ref, src: viewUrl(ref), w: Number(process.env.W), h: Number(process.env.H), kind: 'video' as const }))
const assets: any[] = [], shapes: any[] = []
const editor = { createAssets: (a: any[]) => assets.push(...a), createShape: (s: any) => shapes.push(s) }
const placed = media.map((m, i) => placeMedia(editor as never, m, 'Storyboard', 100 + i * 10, 200, 480, 'shape:frame1' as never))
console.log(JSON.stringify({ id, asked, calls: calls.filter((c) => c.path.includes('/run')), refs, assets, shapes, placed }))
