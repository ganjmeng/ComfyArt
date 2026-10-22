import type { PromptGraph } from './comfy'
import type { ModelDef } from './models'
import type { GeneratorShape } from './shapes/GeneratorShape'
import { annotated } from './workflows'
import { t } from './i18n'

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
  { id: 'mlsd', label: t('refModes.mlsdLines'), group: t('refModes.structure'), hint: 'Follow the straight architectural lines of image {n}.', node: ['M-LSDPreprocessor', { score_threshold: 0.1, dist_threshold: 0.1, resolution: RES }], control: true, download: true },
  { id: 'scribble', label: t('refModes.scribble'), group: t('refModes.structure'), hint: 'Use the rough scribble in image {n} as the layout.', node: ['ScribblePreprocessor', { resolution: RES }], control: true },
  { id: 'softedge', label: t('refModes.softEdge'), group: t('refModes.structure'), hint: 'Follow the soft outlines of image {n}.', node: ['HEDPreprocessor', { safe: 'enable', resolution: RES }], control: true, download: true },
  { id: 'depth', label: t('refModes.depth'), group: t('refModes.structure'), hint: 'Match the depth and spatial layout of image {n}.', node: ['DepthAnythingV2Preprocessor', { ckpt_name: 'depth_anything_v2_vitl.pth', resolution: RES }], control: true },
  { id: 'normal', label: t('refModes.normalMap'), group: t('refModes.structure'), hint: 'Match the surface shapes of the normal map in image {n}.', node: ['BAE-NormalMapPreprocessor', { resolution: RES }], control: true, download: true },
  { id: 'pose', label: t('refModes.pose'), group: t('refModes.structure'), hint: 'Match the body pose of the skeleton in image {n}.', node: ['DWPreprocessor', { detect_hand: 'enable', detect_body: 'enable', detect_face: 'enable', resolution: RES, bbox_detector: 'yolox_l.onnx', pose_estimator: 'dw-ll_ucoco_384_bs5.torchscript.pt', scale_stick_for_xinsr_cn: 'disable' }], control: true },
  { id: 'seg', label: t('refModes.segmentation'), group: t('refModes.structure'), hint: 'Follow the region layout of the segmentation map in image {n}.', node: ['OneFormer-COCO-SemSegPreprocessor', { resolution: RES }], control: true, download: true },
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

export function preprocessNode(mode: RefMode, image: unknown, res: number) {
  const [type, inputs] = mode.node!
  return { class_type: type, inputs: { image, ...inputs, ...('resolution' in inputs ? { resolution: res } : {}) } }
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

export function applyRefs(graph: PromptGraph, id: Record<string, string>, model: ModelDef, used: UsedRef[], strengths: Record<string, number>, controls: Record<string, RefControl>, width: number, height: number) {
  const images = used.map(({ src, mode }, i) => {
    graph[`r${i}`] = { class_type: 'LoadImage', inputs: { image: annotated(src) } }
    if (!mode.node) return { node: `r${i}`, mode, src }
    graph[`x${i}`] = preprocessNode(mode, [`r${i}`, 0], (controls[src] ?? DEFAULT_CONTROL).res)
    return { node: `x${i}`, mode, src }
  })
  if (model.refs === 'qwen' && images.length) {
    graph[id.prompt].inputs.vae = [id.vae, 0]
    images.forEach(({ node }, i) => { graph[id.prompt].inputs[`images.image_${i + 1}`] = [node, 0] })
  }
  if (model.refs === 'latent' && images.length) {
    let [pos, neg]: [unknown, unknown] = [graph[id.guider].inputs.positive, graph[id.guider].inputs.negative]
    images.forEach(({ node }, i) => {
      graph[`s${i}`] = { class_type: 'ImageScaleToTotalPixels', inputs: { image: [node, 0], upscale_method: 'lanczos', megapixels: 1, resolution_steps: 1 } }
      graph[`e${i}`] = { class_type: 'VAEEncode', inputs: { pixels: [`s${i}`, 0], vae: [id.vae, 0] } }
      graph[`p${i}`] = { class_type: 'ReferenceLatent', inputs: { conditioning: pos, latent: [`e${i}`, 0] } }
      graph[`n${i}`] = { class_type: 'ReferenceLatent', inputs: { conditioning: neg, latent: [`e${i}`, 0] } }
      ;[pos, neg] = [[`p${i}`, 0], [`n${i}`, 0]]
    })
    Object.assign(graph[id.guider].inputs, { positive: pos, negative: neg })
  }
  const hints = images.filter(({ mode }) => mode.control)
  if (model.control && hints.length) {
    graph.cn = { class_type: 'ControlNetLoader', inputs: { control_net_name: model.control } }
    let [pos, neg]: [unknown, unknown] = [graph[id.sampler].inputs.positive, graph[id.sampler].inputs.negative]
    hints.forEach(({ node, src }, i) => {
      const c = controls[src] ?? DEFAULT_CONTROL
      graph[`cs${i}`] = { class_type: 'ImageScale', inputs: { image: [node, 0], upscale_method: 'lanczos', width, height, crop: c.resize === 'crop' ? 'center' : 'disabled' } }
      graph[`ca${i}`] = { class_type: 'ControlNetApplyAdvanced', inputs: { positive: pos, negative: neg, control_net: ['cn', 0], image: [`cs${i}`, 0], vae: [id.vae, 0], strength: (strengths[src] ?? DEFAULT_STRENGTH) / 100, start_percent: c.start / 100, end_percent: c.end / 100 } }
      ;[pos, neg] = [[`ca${i}`, 0], [`ca${i}`, 1]]
    })
    Object.assign(graph[id.sampler].inputs, { positive: pos, negative: neg })
  }
}
