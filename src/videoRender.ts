import { queuePrompt, uploadImage, viewUrl, waitForImages, type ImageRef } from './comfy'
import { clipLength, drawSubtitle, layout, type Edit, type Subtitle } from './videoEdit'
import { annotated, type Built } from './workflows'
import { onComfyEvent } from './ws'

const RENDER_FPS = 24

async function overlay(s: Subtitle, i: number, width: number, height: number) {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  drawSubtitle(canvas.getContext('2d')!, s)
  const blob = await new Promise<Blob>((resolve) => canvas.toBlob((b) => resolve(b!), 'image/png'))
  const ref = await uploadImage(blob, `caption-${Date.now()}-${i}.png`)
  return { image: annotated(viewUrl(ref)), x: 0, y: 0, start: s.start, duration: s.end - s.start }
}

function spec(edit: Edit) {
  const { offsets, total } = layout(edit)
  const fade = (i: number) => {
    const tr = edit.transitions[i - 1]
    return tr?.type === 'fade' ? Math.min(tr.duration, clipLength(edit.clips[i]), clipLength(edit.clips[i - 1])) : 0
  }
  const dip = (i: number) => {
    const tr = edit.transitions[i - 1]
    return tr && (tr.type === 'black' || tr.type === 'white') ? tr : null
  }
  const video = edit.clips.map((c, i) => {
    const head = fade(i) / 2
    const tail = i + 1 < edit.clips.length ? fade(i + 1) / 2 : 0
    const into = dip(i)
    const out = dip(i + 1)
    const transition = head ? { type: 'fade', duration: head * 2 } : into ? { type: into.type, duration: into.duration } : null
    return {
      src: annotated(c.src), start: offsets[i] + head, duration: clipLength(c) - head - tail, offset: c.start + head * c.speed, speed: c.speed,
      track: 0, fit: 'cover', muted: c.volume === 0, volume: c.volume,
      fadeIn: into ? into.duration / 2 : head, fadeOut: out ? out.duration / 2 : tail,
      ...(transition ? { transition } : {}),
    }
  })
  const m = edit.music
  const audio = m ? [{ src: annotated(m.src), start: 0, duration: total, offset: m.start, speed: 1, volume: m.volume }] : []
  return { total, video, audio }
}

export async function timelineGraph(edit: Edit, width: number, height: number): Promise<Built> {
  const { total, video, audio } = spec(edit)
  const overlays = await Promise.all(edit.subtitles.filter((s) => s.text && s.end > s.start).map((s, i) => overlay(s, i, width, height)))
  const timeline = { width, height, fps: RENDER_FPS, duration: total, format: 'mp4', video, audio, overlays }
  return { graph: { r: { class_type: 'ComfyArtTimeline', inputs: { timeline: JSON.stringify(timeline), filename_prefix: 'comfyart/edit' } } }, result: 'r' }
}

export async function renderEdit(edit: Edit, width: number, height: number, onProgress: (p: number) => void): Promise<ImageRef> {
  const { graph, result } = await timelineGraph(edit, width, height)
  const id = await queuePrompt(graph, 'local')
  const stop = onComfyEvent('progress', (d: { prompt_id?: string; value?: number; max?: number }) => {
    if (d?.prompt_id === id && d.max) onProgress(d.value! / d.max)
  })
  try {
    return (await waitForImages(id, result))[0]
  } finally {
    stop()
  }
}
