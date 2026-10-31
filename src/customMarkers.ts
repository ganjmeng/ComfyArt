import { BRAND } from './brand'
import { api } from './comfy'
import { lang, t } from './i18n'

export type CustomAction = 'generate' | 'edit' | 'style' | 'inpaint' | 'expand' | 'upscale' | 'cutout' | 'erase' | 'angles' | 'layers' | 'video' | 'animate' | 'extend' | 'videoUpscale' | 'videoCutout' | 'music' | 'speech' | 'clone' | 'sfx' | 'model3d'
export type Marker = 'image' | 'image2' | 'mask' | 'last' | 'audio' | 'video' | 'prompt' | 'lyrics' | 'size' | 'width' | 'height' | 'count' | 'seconds'

export type CustomGroup = 'image' | 'edit' | 'tools' | 'video' | 'audio' | 'model'

interface ActionSpec { id: CustomAction; group: CustomGroup; required: Marker[]; optional: Marker[]; feature: string; note: string }

// Cloud version of upstream's custom workflows: a "workflow" is a WaveSpeed model id plus a mapping of
// ComfyArt values (the same @markers) onto that model's request fields.
export const CUSTOM_ACTIONS: ActionSpec[] = [
  { id: 'generate', group: 'image', required: ['prompt', 'size'], optional: ['count'], feature: 'text_to_image', note: 'Text to image. Shows up as an extra model in the image generator. Reference and base images are not passed.' },
  { id: 'edit', group: 'edit', required: ['image', 'prompt'], optional: [], feature: 'image_edit', note: 'Instruction edit: quick edit, edit text, compose and mockup blending. @prompt receives the edit instruction.' },
  { id: 'style', group: 'edit', required: ['image', 'prompt'], optional: ['image2'], feature: 'image_edit', note: 'Style transfer. @image2 is the style reference; without one ' + BRAND.name + ' passes the source image again.' },
  { id: 'inpaint', group: 'edit', required: ['image', 'prompt'], optional: [], feature: 'image_edit', note: 'Edit a region: @prompt names the area to change and what to do there.' },
  { id: 'expand', group: 'edit', required: ['image', 'prompt'], optional: ['size'], feature: 'expand_image', note: 'Outpaint. @size receives the new canvas size.' },
  { id: 'angles', group: 'edit', required: ['image'], optional: ['prompt'], feature: 'change_angle', note: 'horizontal_angle is sent in 0..359 (360 becomes 0; a non-finite value becomes 0), plus vertical_angle and distance. The panel sentence is a caption only; cloud calls do not send it as prompt.' },
  { id: 'upscale', group: 'tools', required: ['image'], optional: [], feature: 'upscale_image', note: 'Image upscale; the target size the user picked goes to target_resolution when the model has it.' },
  { id: 'cutout', group: 'tools', required: ['image'], optional: [], feature: 'remove_background', note: 'Background removal. The result should keep an alpha channel.' },
  { id: 'erase', group: 'tools', required: ['image', 'mask'], optional: [], feature: 'erase_region', note: 'Object removal. @mask is the area to remove (white = remove).' },
  { id: 'layers', group: 'tools', required: ['image'], optional: ['prompt', 'count'], feature: 'split_layers', note: '@count receives the number of layers. The result is several RGBA images.' },
  { id: 'video', group: 'video', required: ['prompt'], optional: ['image', 'last', 'size', 'seconds'], feature: 'image_to_video', note: 'Replaces the built-in model in the video generator\'s first/last frame mode (reference, motion, lip sync and storyboard modes stay built in).' },
  { id: 'animate', group: 'video', required: ['image', 'prompt'], optional: ['size', 'seconds', 'last'], feature: 'image_to_video', note: 'Animate an image into a short clip. With loop on, @last receives the source image again so the clip ends where it starts.' },
  { id: 'extend', group: 'video', required: ['video'], optional: ['prompt', 'seconds'], feature: 'extend_video', note: 'Extend a selected video. Same result handling as the built-in WaveSpeed video-extend: the model returns the extended clip; ' + BRAND.name + ' does not stitch or concatenate locally.' },
  { id: 'videoUpscale', group: 'video', required: ['video'], optional: [], feature: 'upscale_video', note: 'Upscale a selected video. Passes nearest-up target_resolution (1080p / 2k / 4k) from the user\'s pick; never smaller than that pick; no exact post-scale resize after the model returns.' },
  { id: 'videoCutout', group: 'video', required: ['video'], optional: [], feature: 'remove_video_background', note: 'Remove the background of a selected video. @video receives the clip (uploaded to WaveSpeed, sent as a URL).' },
  { id: 'music', group: 'audio', required: ['prompt'], optional: ['lyrics', 'seconds'], feature: 'music', note: 'Text to music. Shows up as an extra model in the audio dialog. @prompt receives the style, @lyrics the lyrics (empty lyrics are sent as [instrumental]), @seconds the length, clamped to the model\'s duration range; a model with no duration field gets none.' },
  { id: 'speech', group: 'audio', required: ['prompt'], optional: [], feature: 'text_to_speech', note: 'Voiceover. Replaces the built-in model when no recording is cloned. @prompt receives the text to read. The workflow picks its own voice (set voice under params, otherwise the model\'s default), so the voice setting is not passed.' },
  { id: 'clone', group: 'audio', required: ['audio', 'prompt'], optional: [], feature: 'voice_clone', note: 'Voice clone. @audio receives the selected recording (URL) and @prompt the text to read.' },
  { id: 'sfx', group: 'audio', required: ['prompt'], optional: ['seconds'], feature: 'sound_effect', note: 'Sound effect. Replaces the built-in model. @prompt receives the description, @seconds the length, clamped to the model\'s duration range.' },
  { id: 'model3d', group: 'model', required: ['image'], optional: [], feature: 'image_to_3d', note: 'Image to 3D. Appears as a third item in the image toolbar 3D menu (filename); TRELLIS.2 and Pixal3D stay built-in. Agent model=custom uses this when assigned.' },
]

export const MARKERS: { id: Marker; fill: string }[] = [
  { id: 'image', fill: 'the input image (uploaded to WaveSpeed, sent as a URL)' },
  { id: 'image2', fill: 'a second image, e.g. a style reference (URL)' },
  { id: 'mask', fill: 'mask image URL, white = area to change' },
  { id: 'last', fill: 'the last frame of a video (URL)' },
  { id: 'audio', fill: 'the input recording (uploaded to WaveSpeed, sent as a URL)' },
  { id: 'video', fill: 'the input video (uploaded to WaveSpeed, sent as a URL)' },
  { id: 'prompt', fill: 'the text prompt or instruction (for voiceover and voice clone: the text to read)' },
  { id: 'lyrics', fill: 'song lyrics; [instrumental] when empty' },
  { id: 'size', fill: 'output size as "width*height"' },
  { id: 'width', fill: 'output width in pixels' },
  { id: 'height', fill: 'output height in pixels' },
  { id: 'count', fill: 'how many results / layers' },
  { id: 'seconds', fill: 'video or audio length in seconds' },
]

export const NO_LYRICS = '[instrumental]'

/** A custom workflow file: comfyart/workflows/<feature>/<name>.json */
export interface CustomSpec { model: string; fields?: Partial<Record<string, string>>; params?: Record<string, unknown> }

export const specOf = (action: CustomAction) => CUSTOM_ACTIONS.find((a) => a.id === action)!

export function parseApiWorkflow(text: string): CustomSpec {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    throw new Error(t('customWorkflows.notJson'))
  }
  return asApiWorkflow(data)
}

export function asApiWorkflow(data: unknown): CustomSpec {
  if (!data || typeof data !== 'object' || Array.isArray(data) || typeof (data as CustomSpec).model !== 'string') throw new Error(t('customWorkflows.notApiFormat'))
  const { model, fields, params } = data as CustomSpec
  if (fields != null && (typeof fields !== 'object' || Array.isArray(fields))) throw new Error(t('customWorkflows.notApiFormat'))
  if (params != null && (typeof params !== 'object' || Array.isArray(params))) throw new Error(t('customWorkflows.notApiFormat'))
  return { model: model.trim(), ...(fields ? { fields } : {}), ...(params ? { params } : {}) }
}

export interface CheckCode { code: string; model?: string; marker?: string; field?: string; param?: string; markers?: string[]; params?: string[] }
export interface Check { fields: Partial<Record<string, string>>; errors: string[]; warnings: string[]; codes?: CheckCode[]; price?: number | null }

const joinList = (items: string[] = []) => items.join(lang === 'zh' ? '、' : ', ')

/** One localized line for a failed check, e.g. 「broken.json 安装失败：模型 acme/my-edit 缺少 @image 的对应字段」. */
export function checkProblem(file: string, check: Pick<Check, 'errors' | 'codes'>): string {
  const codes = check.codes ?? []
  if (!codes.length) return t('customWorkflows.installFailed', file, check.errors.join(' '))
  const hasMissing = codes.some((c) => c.code === 'missingFields')
  const parts = codes.map((c) => {
    const model = c.model ?? ''
    switch (c.code) {
      case 'unknownModel': return t('customWorkflows.err.unknownModel', model)
      case 'badModelId': return t('customWorkflows.err.badModelId', model)
      case 'missingFields': return t('customWorkflows.err.missingFields', model, joinList(c.markers))
      case 'requiredParams': return t(hasMissing ? 'customWorkflows.err.requiredParamsAlso' : 'customWorkflows.err.requiredParams', model, joinList(c.params))
      case 'badField': return t('customWorkflows.err.badField', c.marker ?? '', c.field ?? '', model)
      case 'badParam': return t('customWorkflows.err.badParam', c.param ?? '', model)
      default: return c.code
    }
  })
  return t('customWorkflows.installFailed', file, parts.join(lang === 'zh' ? '，' : '; '))
}

/** Checks the model exists on WaveSpeed and the mapping fits its request schema (free model-list lookup). */
export async function checkWorkflow(spec: CustomSpec, action: CustomAction): Promise<Check> {
  const { required, optional } = specOf(action)
  const res = await api('/comfyart/wavespeed/custom/check', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ spec, required, optional }) })
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new Error(String(body?.error?.message ?? body?.error ?? `check failed: ${res.status}`))
  return { fields: body.fields ?? {}, errors: body.errors ?? [], warnings: body.warnings ?? [], codes: body.codes ?? [], price: body.price }
}

export function rulesText(): string {
  const markers = MARKERS.map((m) => `- @${m.id}: ${m.fill}`).join('\n')
  const actions = CUSTOM_ACTIONS.map((a) => `- ${a.id}: needs ${a.required.map((m) => `@${m}`).join(', ')}${a.optional.length ? `; optional ${a.optional.map((m) => `@${m}`).join(', ')}` : ''}. ${a.note}`).join('\n')
  return [
    `Connect a WaveSpeed model of the user's choice to a ${BRAND.name} feature. ${BRAND.name} runs every feature on WaveSpeed; a custom workflow swaps the built-in model for another one and says which request field gets each value.`,
    `Steps:\n1. A workflow is a JSON object: {"model": "owner/model-name", "fields": {"@prompt": "prompt", "@image": "image"}, "params": {"num_inference_steps": 30}}. model is a WaveSpeed model id (wavespeed.ai/models). fields maps ${BRAND.name} markers to the model's request field names; common names (prompt, text, image, images, video, audio, mask_image, size, aspect_ratio, duration, last_image) are filled automatically, so fields is only needed for other names. params are fixed values sent on every run. Do not invent fields the model does not have.\n2. Pick the feature (action) below.\n3. Call custom_workflow with action check, the workflow and the feature; fix every error it reports (unknown model, field the model does not accept, required field left empty).\n4. Call custom_workflow with action install, a short name, the workflow and the feature. It saves the file to comfyart/workflows/<feature>/ in the ComfyUI user folder and assigns it to that feature. There is no delete: to remove a workflow, the user deletes its file there.\n5. Tell the user which feature now uses it; assign with file "" switches back to built in.`,
    `Markers (${BRAND.name} values a field can receive):\n${markers}`,
    `Features:\n${actions}`,
    `Runs are billed by WaveSpeed at the chosen model's price; jobs of $0.50 or more ask the user first. Features not listed above (storyboard, creative upscale, move object) always use the built-in models.`,
  ].join('\n\n')
}
