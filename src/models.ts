import { atom } from 'tldraw'

import { api, loadModelPaths, readUserJson, writeUserJson } from './comfy'
import { loadCloudModels } from './wavespeed'

export interface ModelDef {
  id: string
  label: string
  desc: string
  /** WaveSpeed model description, for the agent (the picker shows desc). */
  about?: string
  files: string[]
  video?: boolean
  cloud?: boolean
  refs?: 'qwen' | 'latent'
  prompt?: string
  steps?: [string, Record<string, number>]
  sizes?: string[]
  caption?: string
  control?: string
  negative?: [string, string]
  lora?: string | null
}

export const IMAGE_MODELS: ModelDef[] = []

export const VIDEO_MODELS: ModelDef[] = []

export const isVideo = (workflow: string) => VIDEO_MODELS.some((m) => m.id === workflow)
export const modelOf = (workflow: string) => [...IMAGE_MODELS, ...VIDEO_MODELS].find((m) => m.id === workflow)

export interface ModelPrefs { auto: boolean; enabled: string[] }

const FILE = 'comfyart/models.json'
const ALL = [...IMAGE_MODELS, ...VIDEO_MODELS].map((m) => m.id)

export const modelPrefsAtom = atom<ModelPrefs>('model prefs', { auto: true, enabled: ALL })
export const installedAtom = atom<string[] | null>('installed models', null)

/** Swap the local image models for the curated WaveSpeed text-to-image list (api/wavespeed_models.json). */
async function useCloudImageModels() {
  const all = await loadCloudModels().catch(() => ({}) as Awaited<ReturnType<typeof loadCloudModels>>)
  const defs = (names: string[], video: boolean): ModelDef[] => {
    const seen = new Set<string>()
    return names.flatMap((n) => all[n]?.models ?? []).filter((m) => !seen.has(m.id) && seen.add(m.id)).map((m) => ({
      id: m.id, label: m.label + (m.price != null ? ` · $${m.price}` : ''), desc: m.subtitle || m.id.split('/').slice(1).join('/') || m.id, about: m.desc || undefined, files: [], cloud: true, lora: null,
      ...(video ? { video: true } : { refs: 'qwen' as const }),
    }))
  }
  const image = defs(['text_to_image'], false)
  const video = defs(['text_to_video', 'image_to_video'], true)
  if (image.length) IMAGE_MODELS.splice(0, IMAGE_MODELS.length, ...image)
  if (video.length) VIDEO_MODELS.splice(0, VIDEO_MODELS.length, ...video)
  const added = [...image, ...video].map((m) => m.id)
  if (!modelPrefsAtom.get().auto) modelPrefsAtom.set({ ...modelPrefsAtom.get(), enabled: [...modelPrefsAtom.get().enabled, ...added] })
}

export const isCloudModel = (id: string) => [...IMAGE_MODELS, ...VIDEO_MODELS].some((m) => m.id === id && m.cloud)

export async function loadModels() {
  const [prefs, files, paths] = await Promise.all([readUserJson<ModelPrefs | null>(FILE, null), api('/models/diffusion_models'), loadModelPaths(), useCloudImageModels()])
  if (prefs) modelPrefsAtom.set(prefs)
  const names: string[] = files.ok ? await files.json() : []
  installedAtom.set([...IMAGE_MODELS, ...VIDEO_MODELS].filter((m) => m.files.every((f) => names.includes(f) || f in paths)).map((m) => m.id))
}

export async function saveModelPrefs(prefs: ModelPrefs) {
  modelPrefsAtom.set(prefs)
  await writeUserJson(FILE, prefs)
}

export function installedModels(video: boolean): ModelDef[] {
  const builtin = (video ? VIDEO_MODELS : IMAGE_MODELS).filter((m) => isInstalled(m.id))
  return video ? builtin : [...builtin]
}

export function agentModels(video: boolean): ModelDef[] {
  const { auto, enabled } = modelPrefsAtom.get()
  const list = installedModels(video)
  const picked = auto ? list : list.filter((m) => enabled.includes(m.id))
  return picked.length ? picked : list.length ? list.slice(0, 1) : (video ? VIDEO_MODELS : IMAGE_MODELS).slice(0, 1)
}

export function isInstalled(_id: string, _runOn?: string): boolean {
  // cloud models need no local files
  return true
}
