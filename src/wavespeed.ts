// WaveSpeed cloud generation: tools build a one-node pseudo graph that the backend
// (/comfyart/wavespeed/*) runs on api.wavespeed.ai. No local ComfyUI model is loaded.
import { atom } from 'tldraw'

import type { PromptGraph } from './comfy'
import type { Built } from './workflows'

export const WS_NODE = 'WaveSpeedRun'
export const WS_ID = 'ws:'

export interface WsInputs {
  feature: string
  model?: string
  prompt?: string
  image?: string
  images?: string[]
  mask?: string
  width?: number
  height?: number
  ratio?: string
  seed?: number
  /** #201: sent only for models whose schema has negative_prompt. */
  negative_prompt?: string
  /** #202: [{name: URL, strength: %}]; the backend sends them in the model's `loras` field. */
  loras?: { name: string; strength: number }[]
  png?: boolean
  video?: string
  audio?: string
  last_image?: string
  reference_images?: string[]
  reference_videos?: string[]
  reference_audios?: string[]
  duration?: number
  resolution?: string
  text?: string
  lyrics?: string
  voice?: string
  layers?: number
  /** ACE-Step only (src/music.ts): tempo, lyrics language and key; build_payload maps them. */
  music?: { bpm?: number; language?: string; key?: string }
  scenes?: { prompt: string; duration: number }[]
  /** #80 structure control: the backend maps it onto the WaveSpeed control model. */
  control?: { mode: string; strength: number; start: number; end: number; res: number; resize: 'crop' | 'stretch' }
  /** #80 every structure ref with its own image and knobs (supersedes `control`). */
  controls?: { image: string; mode: string; strength: number; start: number; end: number; res: number; resize: 'crop' | 'stretch' }[]
  /** #80 color modes, parallel to images: the backend preprocesses those refs. */
  prep?: (string | null)[]
  params?: Record<string, unknown>
  /** custom_workflow action (customMarkers.ts) this job belongs to; the user's model replaces the built-in one. */
  custom?: string
  /** #45 region edit: crop box in image pixels; only this crop is edited, then pasted back with `mask` (crop-sized). */
  paste?: { x: number; y: number; w: number; h: number }
  /** #45 move object offset in image pixels (feature move_object). */
  dx?: number
  dy?: number
}

export interface CloudModel { id: string; label: string; subtitle?: string; price: number | null; desc: string; local_equivalent?: string | null; default: boolean; inputs?: string[]; max_images?: number | null; vendor?: string; recommended?: boolean; qualities?: string[]; aspect_ratios?: string[]; durations?: number[]; resolutions?: string[]; defaults?: Record<string, string | number>; name?: string; blurb?: { zh: string; en: string } }
export interface CloudFeature { default: string; available: boolean; models: CloudModel[]; picker_order?: string[] }

let pending: string | undefined

/** Model the agent (or user) asked for on the tool call being handled right now; startJob takes it. */
export function setPendingModel(model: unknown) {
  // WaveSpeed ids look like owner/model; legacy local names (trellis2, pixal3d) fall back to the default
  pending = typeof model === 'string' && model.includes('/') ? model : undefined
}

let features: Record<string, CloudFeature> = {}

/** Catalog base_price of a feature's default model, once `loadCloudModels` has filled `features`. */
export function featurePrice(name: string): number | null {
  const feature = features[name]
  const model = feature?.models.find((m) => m.id === feature.default) ?? feature?.models[0]
  const price = model?.price
  return typeof price === 'number' && Number.isFinite(price) ? price : null
}

/** model if it belongs to the feature's curated list, else undefined (backend default). */
export const modelIn = (feature: string, model: string | undefined) => (model && features[feature]?.models.some((m) => m.id === model) ? model : undefined)

export function takePendingModel(): string | undefined {
  const m = pending
  pending = undefined
  return m
}

export function wsBuilt(inputs: WsInputs): Built {
  const clean = Object.fromEntries(Object.entries(inputs).filter(([, v]) => v !== undefined && v !== null && v !== ''))
  return { graph: { ws: { class_type: WS_NODE, inputs: clean } }, result: 'ws' }
}

export const isWsGraph = (graph: PromptGraph) => Object.values(graph).some((n) => n.class_type === WS_NODE)

export function withModel(graph: PromptGraph, model: string | undefined) {
  if (!model) return
  for (const node of Object.values(graph)) if (node.class_type === WS_NODE && !node.inputs.model) node.inputs.model = model
}

/** #305: mirrors backend `enabled: has_key()` so UI cannot look generatable when cloud is disabled. */
export const cloudEnabledAtom = atom<boolean | null>('cloud enabled', null)

export async function loadCloudModels(): Promise<Record<string, CloudFeature>> {
  const res = await fetch('/comfyart/wavespeed/models')
  if (!res.ok) return {}
  const body = await res.json() as { enabled?: boolean; features?: Record<string, CloudFeature> }
  const enabled = body.enabled !== false
  cloudEnabledAtom.set(enabled)
  // when no key, keep catalog empty so generate paths cannot look ready
  features = enabled ? ((body.features ?? {}) as Record<string, CloudFeature>) : {}
  return features
}
