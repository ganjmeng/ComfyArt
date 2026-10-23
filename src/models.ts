import { atom } from 'tldraw'

import { api, loadModelPaths, readUserJson, writeUserJson } from './comfy'
import { loadCloudModels } from './wavespeed'
import { CUSTOM_GENERATE, workflowConfigAtom } from './customWorkflows'
import { t } from './i18n'

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
  /** Picker group header (model family), starting price and quality tiers from the WaveSpeed schema (#95). */
  vendor?: string
  price?: number | null
  recommended?: boolean
  qualities?: string[]
  /** Schema enums and defaults (#95): the settings panel offers only these; switching models keeps what still fits. */
  ratios?: string[]
  durations?: number[]
  resolutions?: string[]
  maxImages?: number | null
  defaults?: Record<string, string | number>
  /** The 'Auto' entry: the agent / backend default picks the model. */
  auto?: boolean
}

/** Per-feature tabs of the generator's model menu (#95); the first tab's pick is the shape's workflow. */
export const IMAGE_FEATURES = ['text_to_image', 'image_edit']
export const VIDEO_FEATURES = ['text_to_video', 'image_to_video']
export const FEATURE_MODELS: Record<string, ModelDef[]> = {}

export const AUTO_IMAGE = 'auto'
export const AUTO_VIDEO = 'auto:video'
const autoDef = (video: boolean): ModelDef => ({ id: video ? AUTO_VIDEO : AUTO_IMAGE, label: t('common.auto'), desc: t('genPanel.autoDesc'), files: [], cloud: true, lora: null, auto: true, ...(video ? { video: true } : { refs: 'qwen' as const, control: 'wavespeed' }) })
export const isAuto = (workflow: string) => workflow === AUTO_IMAGE || workflow === AUTO_VIDEO

export const IMAGE_MODELS: ModelDef[] = []

export const VIDEO_MODELS: ModelDef[] = []

export const isVideo = (workflow: string) => workflow === AUTO_VIDEO || VIDEO_MODELS.some((m) => m.id === workflow)
function customModels(): ModelDef[] {
  const file = workflowConfigAtom.get().generate
  return file ? [{ id: CUSTOM_GENERATE, label: file.replace(/\.json$/, ''), desc: t('customWorkflows.customModelDesc'), files: [], cloud: true, lora: null }] : []
}

export const modelOf = (workflow: string) => [autoDef(false), autoDef(true), ...IMAGE_MODELS, ...VIDEO_MODELS, ...customModels()].find((m) => m.id === workflow)

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
      id: m.id, label: m.label, price: m.price, vendor: m.vendor, recommended: m.recommended, qualities: m.qualities, ratios: m.aspect_ratios, durations: m.durations, resolutions: m.resolutions, maxImages: m.max_images, defaults: m.defaults, desc: m.subtitle || m.id.split('/').slice(1).join('/') || m.id, about: m.desc || undefined, files: [], cloud: true, lora: null,
      // control: structure refs run on WaveSpeed control models (#80), so the ControlNet knobs show like upstream
      ...(video ? { video: true } : { refs: 'qwen' as const, control: 'wavespeed' }),
    }))
  }
  for (const f of [...IMAGE_FEATURES, ...VIDEO_FEATURES]) FEATURE_MODELS[f] = defs([f], VIDEO_FEATURES.includes(f))
  const image = defs(['text_to_image'], false)
  const video = defs(['text_to_video', 'image_to_video'], true)
  if (image.length) IMAGE_MODELS.splice(0, IMAGE_MODELS.length, ...image)
  if (video.length) VIDEO_MODELS.splice(0, VIDEO_MODELS.length, ...video)
  const added = [...image, ...video].map((m) => m.id)
  if (!modelPrefsAtom.get().auto) modelPrefsAtom.set({ ...modelPrefsAtom.get(), enabled: [...modelPrefsAtom.get().enabled, ...added] })
}

export const isCloudModel = (id: string) => isAuto(id) || [...IMAGE_MODELS, ...VIDEO_MODELS, ...customModels()].some((m) => m.id === id && m.cloud)

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
  return video ? builtin : [...builtin, ...customModels()]
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

type GenProps = { ratio: string; duration: number; resolution: string; quality: string }
/** Settings to change when switching to `model` (#95): values the new model also supports are kept,
 * the rest reset to its schema default (else its first option). Empty when nothing needs to change. */
export function adjustForModel(p: GenProps, model: ModelDef | undefined, video: boolean): Partial<GenProps> {
  if (!model || model.auto) return {}
  const out: Partial<GenProps> = {}
  const d = model.defaults ?? {}
  const fit = <T,>(cur: T, opts: T[] | undefined, def: unknown): T | undefined => (opts?.length && !opts.includes(cur) ? (opts.includes(def as T) ? (def as T) : opts[0]) : undefined)
  const ratio = fit(p.ratio, model.ratios?.filter((r) => /^\d+:\d+$/.test(r)), d.aspect_ratio)
  if (ratio !== undefined) out.ratio = ratio
  if (video) {
    const dur = fit(Number(p.duration), model.durations?.map(Number), Number(d.duration))
    if (dur !== undefined) out.duration = dur
    const res = fit(p.resolution, model.resolutions, d.resolution)
    if (res !== undefined) out.resolution = res
  }
  const q = fit(p.quality, model.qualities, d.quality)
  if (q !== undefined) out.quality = q
  return out
}

/** How many reference images this model takes; extra ones are dropped (with a notice) rather than failing the paid job. */
export const refCap = (model: ModelDef | undefined, n: number) => (model?.maxImages && n > model.maxImages ? model.maxImages : null)
