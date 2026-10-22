import { atom } from 'tldraw'

import { api, readUserJson, writeUserJson } from './comfy'

export interface LoraEntry { name: string; family: string | null }
export interface LoraPick { name: string; strength: number }

export const DEFAULT_LORA_STRENGTH = 100

const FAVORITES = 'comfyart/lora-favorites.json'
const ARCHITECTURES: [RegExp, string][] = [[/flux[-_.]?3/i, 'flux3-klein'], [/flux[-_.]?2[-_.]?klein/i, 'flux2-klein'], [/z[-_.]?image/i, 'z-image'], [/qwen[-_.]?image[-_.]?2(?![0-9])/i, 'qwen-image-2.1'], [/qwen[-_.]?image/i, 'qwen-image']]
const NAMES: [RegExp, string][] = [[/edit/i, 'other'], [/qwen[-_ ]?image[-_ ]?2\.1/i, 'qwen-image-2.1'], [/z[-_ ]?image/i, 'z-image'], [/flux[-_ ]?3/i, 'flux3-klein'], [/flux[-_ ]?2[-_ ]?klein|klein/i, 'flux2-klein'], [/qwen/i, 'qwen-image']]

export const lorasAtom = atom<LoraEntry[] | null>('loras', null)
export const loraFavoritesAtom = atom<string[]>('lora favorites', [])

async function familyOf(name: string): Promise<string | null> {
  const res = await api(`/view_metadata/loras?filename=${encodeURIComponent(name)}`)
  const meta: Record<string, string> = res.ok ? await res.json() : {}
  const arch = `${meta['modelspec.architecture'] ?? ''} ${meta.ss_base_model_version ?? ''}`.trim()
  if (arch) return ARCHITECTURES.find(([re]) => re.test(arch))?.[1] ?? 'other'
  return NAMES.find(([re]) => re.test(name))?.[1] ?? null
}

export async function loadLoras() {
  if (lorasAtom.get()) return
  const res = await api('/models/loras')
  const names: string[] = res.ok ? await res.json() : []
  loraFavoritesAtom.set(await readUserJson<string[]>(FAVORITES, []))
  lorasAtom.set(await Promise.all(names.map(async (name) => ({ name, family: await familyOf(name) }))))
}

export async function toggleFavorite(name: string) {
  const list = loraFavoritesAtom.get()
  const next = list.includes(name) ? list.filter((n) => n !== name) : [...list, name]
  loraFavoritesAtom.set(next)
  await writeUserJson(FAVORITES, next)
}

export const loraLabel = (name: string) => name.split(/[\\/]/).pop()!.replace(/\.safetensors$/, '')
