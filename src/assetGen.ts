import { createShapeId, type Editor, type TLImageShape, type TLShapeId } from 'tldraw'

import { freeSpot, GAP, registerPlacer, rowSpots, selectResults, spawnHolder, startJob, type ErrorSink } from './jobs'
import { AUDIO, AUDIO_SIZE, MODEL } from './shapes/EmbedShapes'
import { GENERATOR } from './shapes/GeneratorShape'
import { annotated, type Built } from './workflows'
import { t } from './i18n'
import { wsBuilt } from './wavespeed'
import { musicJobInputs } from './music'

const QWEN_VOICES = ['Serena', 'Vivian', 'Uncle_fu', 'Dylan', 'Eric', 'Ryan', 'Aiden', 'Ono_anna', 'Sohee']
export const voices = () => QWEN_VOICES // WaveSpeed qwen3-tts voices
export { MUSIC_MODELS, musicModels } from './music'
export const SFX_SECONDS = [3, 5, 8, 15]
const MODEL_SIZE = 480

export type AudioSpec =
  | { kind: 'music'; model: string; prompt: string; lyrics: string; seconds: number; bpm?: number; language?: string; key?: string; seed?: number }
  | { kind: 'speech'; text: string; voice: string }
  | { kind: 'clone'; text: string; reference: string }
  | { kind: 'sfx'; prompt: string; seconds: number }

async function audioGraph(spec: AudioSpec): Promise<Built> {
  if (spec.kind === 'music') return wsBuilt(musicJobInputs(spec))
  if (spec.kind === 'sfx') return wsBuilt({ feature: 'sound_effect', prompt: spec.prompt, duration: spec.seconds })
  if (spec.kind === 'speech') return wsBuilt({ feature: 'text_to_speech', text: spec.text, voice: spec.voice })
  return wsBuilt({ feature: 'voice_clone', text: spec.text, audio: annotated(spec.reference) })
}

const LABELS: Record<AudioSpec['kind'], string> = { music: t('audio.music'), speech: t('audio.voiceover'), clone: t('audio.voiceover'), sfx: t('audio.soundEffect') }

export function generateAudio(editor: Editor, spec: AudioSpec, onError: ErrorSink, quiet = false): TLShapeId {
  const [w, h] = AUDIO_SIZE
  const [x, y] = freeSpot(editor, w, h)
  const id = createShapeId()
  editor.createShape({ id, type: GENERATOR, x, y, props: { w, h }, meta: { temp: true, quiet } })
  if (!quiet) editor.zoomToBounds({ x, y, w, h }, { inset: 200, animation: { duration: 200 } })
  const text = spec.kind === 'speech' || spec.kind === 'clone' ? spec.text : spec.prompt
  void startJob(editor, id, audioGraph(spec), { name: `${LABELS[spec.kind]} · ${text.slice(0, 24)}`, kind: 'audio', placer: 'audio' }, onError)
  return id
}

export type Model3d = 'trellis2' | 'pixal3d'

async function modelGraph(image: string, model: Model3d): Promise<Built> {
  void model // legacy local names; the curated WaveSpeed default or the agent's model is used
  return wsBuilt({ feature: 'image_to_3d', image })
}

const VIEWS = ['front', 'left', 'back', 'right'] as const
export const MAX_VIEWS = VIEWS.length

async function multiViewGraph(images: string[]): Promise<Built> {
  return wsBuilt({ feature: 'image_to_3d', model: 'tripo3d/h3.1/multiview-to-3d', images })
}

export function viewsTo3d(editor: Editor, shapes: TLImageShape[], onError: ErrorSink) {
  const srcs = shapes.flatMap((s) => {
    const asset = s.props.assetId ? editor.getAsset(s.props.assetId) : null
    return asset?.type === 'image' && asset.props.src ? [annotated(asset.props.src)] : []
  }).slice(0, MAX_VIEWS)
  if (!srcs.length) return
  const holder = spawnHolder(editor, shapes[shapes.length - 1], [MODEL_SIZE, MODEL_SIZE])
  void startJob(editor, holder, multiViewGraph(srcs), { name: `${t('imageToolbar.multiViewTo3d')} · ${srcs.length}`, kind: 'model', placer: 'model' }, onError)
  return holder
}

export function imageTo3d(editor: Editor, shape: TLImageShape, onError: ErrorSink, model: Model3d = 'trellis2') {
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== 'image' || !asset.props.src) return
  const holder = spawnHolder(editor, shape, [MODEL_SIZE, MODEL_SIZE])
  void startJob(editor, holder, modelGraph(annotated(asset.props.src), model), { name: `${asset.props.name || t('common.image')} · 3D`, kind: 'model', placer: 'model' }, onError)
  return holder
}

registerPlacer('audio', async (editor, holder, media, job) => {
  const ids: TLShapeId[] = []
  editor.run(() => {
    editor.deleteShape(holder.id)
    media.forEach((m, i) => {
      const id = createShapeId()
      editor.createShape({ id, type: AUDIO, x: holder.x, y: holder.y + i * (AUDIO_SIZE[1] + GAP), parentId: holder.parentId, props: { src: m.src, name: job.name } })
      ids.push(id)
    })
  }, { history: 'ignore' })
  selectResults(editor, holder, ids)
})

registerPlacer('model', async (editor, holder, media, job) => {
  const { w, h } = holder.props as { w: number; h: number }
  const b = editor.getShapePageBounds(holder)!
  const ids: TLShapeId[] = []
  editor.run(() => {
    editor.deleteShape(holder.id)
    rowSpots(editor, holder, media.map(() => [w, h]), [b.minX, b.minY]).forEach((p, i) => {
      const id = createShapeId()
      editor.createShape({ id, type: MODEL, x: p.x, y: p.y, parentId: holder.parentId, props: { w, h, src: media[i].src, name: job.name, ext: 'glb' } })
      ids.push(id)
    })
  }, { history: 'ignore' })
  selectResults(editor, holder, ids)
})
