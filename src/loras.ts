// #202 LoRA on WaveSpeed: the user pastes a HuggingFace or Civitai URL plus a weight; picks go in the model's `loras`
// field ([{path, scale}], scale = weight / 100) and are priced with it. Saved URLs are reused across cards and projects.
import { atom } from 'tldraw'

import { readUserJson, writeUserJson } from './comfy'
import type { ModelDef } from './models'

/** A LoRA on a generator card: `name` is the URL, `strength` the weight in percent (100 = scale 1). */
export interface LoraPick { name: string; strength: number }

export const DEFAULT_LORA_STRENGTH = 100
export const MAX_LORA_STRENGTH = 200

const SAVED = 'comfyart/lora-saved.json'

/** Saved LoRAs (URL + last weight), newest first; null until loaded. */
export const savedLorasAtom = atom<LoraPick[] | null>('saved loras', null)

const HF = /^https:\/\/(?:huggingface\.co|hf\.co)\/[\w.-]+\/[\w.-]+\/(?:resolve|blob)\/[^\s?#]+\.safetensors(?:\?[^\s#]*)?$/
const CIVITAI = /^https:\/\/civitai\.com\/(?:api\/download\/models\/\d+(?:\?[^\s#]*)?|models\/\d+(?:\/[\w.-]*)?\?(?:[^\s#]*&)?modelVersionId=(\d+)[^\s#]*)$/

/** The downloadable URL for a HuggingFace LoRA file or Civitai link, or null (same rule as api/wavespeed.py lora_url). */
export function loraUrl(url: string): string | null {
  const u = url.trim()
  if (HF.test(u)) return u.replace('/blob/', '/resolve/')
  const m = CIVITAI.exec(u)
  if (m) return m[1] ? `https://civitai.com/api/download/models/${m[1]}` : u
  return null
}

/** True when the model's WaveSpeed schema has a `loras` field. */
export const supportsLora = (model: ModelDef | null | undefined) => !!model?.inputs?.includes('loras')

export async function loadSavedLoras() {
  if (savedLorasAtom.get()) return
  const list = await readUserJson<LoraPick[]>(SAVED, [])
  savedLorasAtom.set(Array.isArray(list) ? list.filter((l) => l && typeof l.name === 'string' && loraUrl(l.name)) : [])
}

/** Remember a LoRA (or its new weight) for reuse. */
export async function saveLora(pick: LoraPick) {
  const next = [pick, ...(savedLorasAtom.get() ?? []).filter((l) => l.name !== pick.name)]
  savedLorasAtom.set(next)
  await writeUserJson(SAVED, next)
}

export async function forgetLora(name: string) {
  const next = (savedLorasAtom.get() ?? []).filter((l) => l.name !== name)
  savedLorasAtom.set(next)
  await writeUserJson(SAVED, next)
}

/** Short label: the file name without its extension, or 'Civitai #id'. */
export function loraLabel(name: string) {
  const civitai = /civitai\.com\/api\/download\/models\/(\d+)/.exec(name)
  if (civitai) return `Civitai #${civitai[1]}`
  return decodeURIComponent(name.split('?')[0].split(/[\\/]/).pop()!).replace(/\.safetensors$/, '')
}
