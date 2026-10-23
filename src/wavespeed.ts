// WaveSpeed cloud generation: tools build a one-node pseudo graph that the backend
// (/comfyart/wavespeed/*) runs on api.wavespeed.ai. No local ComfyUI model is loaded.
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
  scenes?: { prompt: string; duration: number }[]
  /** #80 structure control: the backend maps it onto the WaveSpeed control model. */
  control?: { mode: string; strength: number; start: number; end: number; res: number; resize: 'crop' | 'stretch' }
  /** #80 color modes, parallel to images: the backend preprocesses those refs. */
  prep?: (string | null)[]
  params?: Record<string, unknown>
}

export interface CloudModel { id: string; label: string; subtitle?: string; price: number | null; desc: string; local_equivalent?: string | null; default: boolean; inputs?: string[]; max_images?: number | null }
export interface CloudFeature { default: string; available: boolean; models: CloudModel[] }

let pending: string | undefined

/** Model the agent (or user) asked for on the tool call being handled right now; startJob takes it. */
export function setPendingModel(model: unknown) {
  // WaveSpeed ids look like owner/model; legacy local names (trellis2, pixal3d) fall back to the default
  pending = typeof model === 'string' && model.includes('/') ? model : undefined
}

let features: Record<string, CloudFeature> = {}

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

export async function loadCloudModels(): Promise<Record<string, CloudFeature>> {
  const res = await fetch('/comfyart/wavespeed/models')
  if (!res.ok) return {}
  features = ((await res.json()).features ?? {}) as Record<string, CloudFeature>
  return features
}
