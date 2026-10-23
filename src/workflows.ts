import { type PromptGraph } from './comfy'
import { wsBuilt } from './wavespeed'

export const randomSeed = () => Math.floor(Math.random() * 2 ** 31)

export interface Built { graph: PromptGraph; result: string; partial?: string[] }

export function annotated(src: string): string {
  const q = new URL(src, location.origin).searchParams
  const sub = q.get('subfolder')
  return `${sub ? `${sub}/` : ''}${q.get('filename')} [${q.get('type') || 'input'}]`
}

export async function eraseGraph(image: string, mask: string): Promise<Built> {
  return wsBuilt({ feature: 'erase_region', custom: 'erase', image, mask })
}

export async function editGraph(image: string, prompt: string): Promise<Built> {
  // cloud edit (image_edit default: alibaba/qwen-image-3.0/edit)
  return wsBuilt({ feature: 'edit_image', custom: 'edit', image, prompt })
}

export interface Crop { x: number; y: number; w: number; h: number }

const AZIMUTHS: [number, string][] = [
  [0, 'front view'], [45, 'front-right quarter view'], [90, 'right side view'], [135, 'back-right quarter view'],
  [180, 'back view'], [225, 'back-left quarter view'], [270, 'left side view'], [315, 'front-left quarter view'],
]

export function anglePrompt(horizontal: number, vertical: number, zoom: number): string {
  const az = ((horizontal % 360) + 360) % 360
  const azKw = AZIMUTHS.reduce((best, cur) => {
    const d = (a: number) => Math.min(Math.abs(az - a), 360 - Math.abs(az - a))
    return d(cur[0]) < d(best[0]) ? cur : best
  })[1]
  const elKw = vertical <= -15 ? 'low-angle shot' : vertical <= 15 ? 'eye-level shot' : vertical <= 45 ? 'elevated shot' : 'high-angle shot'
  const distKw = zoom >= 7 ? 'close-up' : zoom >= 3 ? 'medium shot' : 'wide shot'
  return `<qma> ${azKw} ${elKw} ${distKw}`
}

export async function layersGraph(image: string, layers: number, prompt: string): Promise<Built> {
  return wsBuilt({ feature: 'split_layers', custom: 'layers', image, prompt, layers, png: true })
}

export type SamTarget = { text: string } | { x: number; y: number } | { points: { x: number; y: number }[] } | { box: Crop }

/** SAM3 on WaveSpeed (wavespeed-ai/sam3-image): returns a white-on-black mask image, like the old local graph. */
export function samGraph(image: string, target: SamTarget): Built {
  const params: Record<string, unknown> = { apply_mask: false, output_format: 'png' }
  if ('box' in target) params.box_prompts = [{ x_min: Math.round(target.box.x), y_min: Math.round(target.box.y), x_max: Math.round(target.box.x + target.box.w), y_max: Math.round(target.box.y + target.box.h) }]
  else if (!('text' in target)) params.point_prompts = ('points' in target ? target.points : [target]).map((p) => ({ x: Math.round(p.x), y: Math.round(p.y), label: 1 }))
  return wsBuilt({ feature: 'segment', image, prompt: 'text' in target ? target.text : undefined, params })
}

/** One SAM job per box (WaveSpeed returns one mask per call). */
export function samBoxesGraph(image: string, boxes: Crop[]): Built[] {
  return boxes.map((box) => samGraph(image, { box }))
}
