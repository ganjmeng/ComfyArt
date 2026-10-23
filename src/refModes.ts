import type { ModelDef } from './models'
import type { GeneratorShape } from './shapes/GeneratorShape'
import { wsBodyError } from './wsErrors'
import { t } from './i18n'
import { annotated } from './workflows'
import { api, askCost, CostDeclined } from './comfy'
import { previewKey, wantsFresh } from './refFresh'

export interface RefMode {
  id: string
  label: string
  group: string
  hint: string
  node?: [string, Record<string, unknown>]
  control?: boolean
  download?: boolean
}

const RES = 1024

export const REF_MODES: RefMode[] = [
  { id: 'content', label: t('refModes.content'), group: t('common.reference'), hint: '' },
  { id: 'style', label: t('refModes.style'), group: t('common.reference'), hint: 'Use only the visual style, palette and rendering of image {n}, not its content.' },
  { id: 'composition', label: t('refModes.composition'), group: t('common.reference'), hint: 'Keep the layout and composition of image {n}.' },
  { id: 'canny', label: t('refModes.lineArt'), group: t('refModes.structure'), hint: 'Follow the edges of image {n} exactly for shapes and composition.', node: ['Canny', { low_threshold: 0.4, high_threshold: 0.8 }], control: true },
  { id: 'lineart', label: t('refModes.lineart'), group: t('refModes.structure'), hint: 'Follow the line art of image {n} for shapes and composition.', node: ['LineArtPreprocessor', { coarse: 'disable', resolution: RES }], control: true },
  { id: 'mlsd', label: t('refModes.mlsdLines'), group: t('refModes.structure'), hint: 'Follow the straight architectural lines of image {n}.', node: ['M-LSDPreprocessor', { score_threshold: 0.1, dist_threshold: 0.1, resolution: RES }], control: true },
  { id: 'scribble', label: t('refModes.scribble'), group: t('refModes.structure'), hint: 'Use the rough scribble in image {n} as the layout.', node: ['ScribblePreprocessor', { resolution: RES }], control: true },
  { id: 'softedge', label: t('refModes.softEdge'), group: t('refModes.structure'), hint: 'Follow the soft outlines of image {n}.', node: ['HEDPreprocessor', { safe: 'enable', resolution: RES }], control: true },
  { id: 'depth', label: t('refModes.depth'), group: t('refModes.structure'), hint: 'Match the depth and spatial layout of image {n}.', node: ['DepthAnythingV2Preprocessor', { ckpt_name: 'depth_anything_v2_vitl.pth', resolution: RES }], control: true },
  { id: 'normal', label: t('refModes.normalMap'), group: t('refModes.structure'), hint: 'Match the surface shapes of the normal map in image {n}.', node: ['BAE-NormalMapPreprocessor', { resolution: RES }], control: true },
  { id: 'pose', label: t('refModes.pose'), group: t('refModes.structure'), hint: 'Match the body pose of the skeleton in image {n}.', node: ['DWPreprocessor', { detect_hand: 'enable', detect_body: 'enable', detect_face: 'enable', resolution: RES, bbox_detector: 'yolox_l.onnx', pose_estimator: 'dw-ll_ucoco_384_bs5.torchscript.pt', scale_stick_for_xinsr_cn: 'disable' }], control: true },
  { id: 'seg', label: t('refModes.segmentation'), group: t('refModes.structure'), hint: 'Follow the region layout of the segmentation map in image {n}.', node: ['OneFormer-COCO-SemSegPreprocessor', { resolution: RES }], control: true },
  { id: 'tile', label: t('refModes.tile'), group: t('refModes.structure'), hint: 'Keep the details and layout of image {n}, add fine detail.', node: ['TilePreprocessor', { pyrUp_iters: 3, resolution: RES }], control: true },
  { id: 'recolor', label: t('refModes.recolor'), group: t('refModes.color'), hint: 'Image {n} is a grayscale guide: keep its shapes and lighting and add new colors.', node: ['ImageIntensityDetector', { gamma_correction: 1, resolution: RES }] },
  { id: 'color', label: t('refModes.colorPickerReference'), group: t('refModes.color'), hint: 'Use the color palette of image {n}.', node: ['ColorPreprocessor', { resolution: RES }] },
  { id: 'shuffle', label: t('refModes.colorMood'), group: t('refModes.color'), hint: 'Use the colors and textures of image {n} loosely, not its layout.', node: ['ShufflePreprocessor', { resolution: RES, seed: 0 }] },
  { id: 'brightness', label: t('refModes.lighting'), group: t('refModes.color'), hint: 'Match the lighting and brightness distribution of image {n}.', node: ['ImageLuminanceDetector', { gamma_correction: 1, resolution: RES }] },
]

export const DEFAULT_STRENGTH = 80

export interface RefControl { start: number; end: number; res: number; resize: 'crop' | 'stretch' }
export const DEFAULT_CONTROL: RefControl = { start: 0, end: 100, res: RES, resize: 'crop' }
export const CONTROL_RESOLUTIONS = [512, 1024, 2048]

export function refControlsOf(shape: GeneratorShape): Record<string, RefControl> {
  return (shape.meta.refControls as Record<string, RefControl> | undefined) ?? {}
}

export const PALETTE_MODE: RefMode = { id: 'palette', label: '', group: '', hint: 'Image {n} is only a color swatch: use its colors as the palette and ignore its layout, shapes and pattern.' }

export const modeOf = (id: string | undefined) => REF_MODES.find((m) => m.id === id) ?? REF_MODES[0]

export function refModesOf(shape: GeneratorShape): Record<string, string> {
  return (shape.meta.refModes as Record<string, string> | undefined) ?? {}
}

export function refStrengthsOf(shape: GeneratorShape): Record<string, number> {
  return (shape.meta.refStrengths as Record<string, number> | undefined) ?? {}
}

const QWEN_EDIT_IMAGES = 16

export const refLimit = (model: ModelDef) => (model.refs === 'qwen' ? QWEN_EDIT_IMAGES : Infinity)

export function modesFor(model: ModelDef): RefMode[] {
  return model.refs ? REF_MODES : model.control ? REF_MODES.filter((m) => m.control) : []
}

export const PREVIEW_TIMEOUT_MS = 60_000

// #81/#109: last preview URL per (src, mode, res); fresh only while that preview is still displayed (button shows 重新提取)
const issued = new Map<string, string>()
const shownPreviews = () => Array.from(document.querySelectorAll<HTMLImageElement>('img.ca-refctl__preview'), (i) => i.getAttribute('src') ?? '')

/** Upstream previewControl, now a cloud extraction (#81): the backend builds the same control map the job uses. */
export async function previewControl(src: string, mode: RefMode, res: number): Promise<string> {
  const init = { method: 'POST', headers: { 'Content-Type': 'application/json' } }
  const seen = previewKey(src, mode.id, res)
  const inputs = { image: annotated(src), mode: mode.id, res, ...(wantsFresh(issued, seen, shownPreviews()) ? { fresh: true } : {}) }
  // #81: each request gives up after PREVIEW_TIMEOUT_MS so the button comes back with an error instead of spinning
  const send = async (body: object) => {
    const ctl = new AbortController()
    const timer = setTimeout(() => ctl.abort(), PREVIEW_TIMEOUT_MS)
    try {
      const r = await api('/comfyart/wavespeed/control_preview', { ...init, body: JSON.stringify(body), signal: ctl.signal })
      return { r, blob: r.ok ? await r.blob() : null, err: r.ok || r.status === 409 ? null : await r.json().catch(() => null), conf: r.status === 409 ? await r.json().catch(() => null) : null }
    } catch (e) {
      if (ctl.signal.aborted) throw new Error(t('refControls.timeout'))
      throw e
    } finally {
      clearTimeout(timer)
    }
  }
  let res1 = await send({ inputs })
  if (res1.r.status === 409) {
    const price = res1.conf?.error?.confirm_usd
    if (typeof price !== 'number' || !(await askCost(price, res1.conf?.error?.seg_splits, res1.conf?.error?.seg_capped))) throw new CostDeclined()
    res1 = await send({ inputs: { ...inputs, confirmed: true } })
  }
  if (!res1.blob) throw new Error(wsBodyError(res1.err, `preview failed: ${res1.r.status}`))
  const url = URL.createObjectURL(res1.blob)
  issued.set(seen, url)
  return url
}

export interface UsedRef { src: string; mode: RefMode }

export function refModeFor(model: ModelDef, picked: string | undefined): RefMode | null {
  const available = modesFor(model)
  return picked ? available.find((m) => m.id === picked) ?? null : available[0] ?? null
}

export function usableRefs(model: ModelDef, refs: string[], picked: Record<string, string>): UsedRef[] {
  return refs.flatMap((src) => {
    const mode = refModeFor(model, picked[src])
    return mode ? [{ src, mode }] : []
  })
}

export function refHints(used: UsedRef[]): string[] {
  return used.map(({ mode }, i) => mode.hint.replace('{n}', String(i + 1))).filter(Boolean)
}


/** Pose: WaveSpeed has no pose estimator, so a custom window / multi-ref pose uses a soft-edge map: labelled 「近似效果」 (#80). */
export const APPROX_MODES = new Set(['pose'])
for (const m of REF_MODES) if (APPROX_MODES.has(m.id)) m.label = `${m.label}${t('refModes.approx')}`

export interface CloudControl { src: string; mode: string; strength: number; start: number; end: number; res: number; resize: 'crop' | 'stretch' }

/**
 * Cloud counterpart of upstream applyRefs: every structure ref drives the WaveSpeed control job with its own
 * strength / start / end / resolution / crop (upstream chained one ControlNetApplyAdvanced per ref; the backend
 * composites their maps into the one control_image the cloud model takes). Color refs are preprocessed before image_edit.
 */
export function applyRefs(used: UsedRef[], strengths: Record<string, number>, controls: Record<string, RefControl>): { controls: CloudControl[]; prep: (string | null)[] } {
  return {
    controls: used.filter(({ mode }) => mode.control).map(({ src, mode }) => {
      const c = controls[src] ?? DEFAULT_CONTROL
      return { src, mode: mode.id, strength: strengths[src] ?? DEFAULT_STRENGTH, start: c.start, end: c.end, res: c.res, resize: c.resize }
    }),
    prep: used.map(({ mode }) => (mode.node && !mode.control ? mode.id : null)),
  }
}
