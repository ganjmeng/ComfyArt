import { t } from './i18n'
export interface Clip { src: string; start: number; end: number; speed: number; volume: number }
export type TransitionType = 'none' | 'fade' | 'black' | 'white'
export interface Transition { type: TransitionType; duration: number }
export interface Subtitle { id: string; start: number; end: number; text: string; size: number; color: string }
export interface Music { src: string; name: string; start: number; volume: number }
export interface Edit { clips: Clip[]; transitions: Transition[]; subtitles: Subtitle[]; music: Music | null }
export interface Source { name: string; duration: number; width: number; height: number; thumbs: string[] }

export const MIN_CLIP = 0.1

export const clipLength = (c: Clip) => (c.end - c.start) / c.speed

export function freshEdit(src: string, duration: number): Edit {
  return { clips: [{ src, start: 0, end: duration, speed: 1, volume: 1 }], transitions: [], subtitles: [], music: null }
}

export function appendClip(edit: Edit, src: string, duration: number): Edit {
  return { ...edit, clips: [...edit.clips, { src, start: 0, end: duration, speed: 1, volume: 1 }], transitions: [...edit.transitions, { type: 'none', duration: 0.5 }] }
}

export function moveClip(edit: Edit, i: number, to: number): Edit {
  if (to < 0 || to >= edit.clips.length) return edit
  const clips = [...edit.clips]
  const [c] = clips.splice(i, 1)
  clips.splice(to, 0, c)
  return { ...edit, clips }
}

export function layout(edit: Edit): { offsets: number[]; total: number } {
  const offsets: number[] = []
  let t = 0
  edit.clips.forEach((c, i) => {
    const tr = edit.transitions[i - 1]
    if (i > 0 && tr?.type === 'fade') t -= Math.min(tr.duration, clipLength(c), clipLength(edit.clips[i - 1]))
    offsets.push(t)
    t += clipLength(c)
  })
  return { offsets, total: Math.max(t, 0) }
}

export interface Frame { layers: { clip: number; src: number; alpha: number }[]; dip: { color: string; alpha: number } | null }

export function sample(edit: Edit, t: number): Frame {
  const { offsets } = layout(edit)
  const layers: Frame['layers'] = []
  let dip: Frame['dip'] = null
  edit.clips.forEach((c, i) => {
    const len = clipLength(c)
    const local = t - offsets[i]
    if (local < 0 || local > len) return
    const prev = edit.transitions[i - 1]
    const next = edit.transitions[i]
    let alpha = 1
    if (prev?.type === 'fade' && local < prev.duration) alpha = local / prev.duration
    layers.push({ clip: i, src: c.start + local * c.speed, alpha })
    const half = (tr: Transition) => tr.duration / 2
    const color = (tr: Transition) => (tr.type === 'white' ? '#ffffff' : '#000000')
    if (next && (next.type === 'black' || next.type === 'white') && local > len - half(next)) {
      dip = { color: color(next), alpha: (local - (len - half(next))) / half(next) }
    }
    if (prev && (prev.type === 'black' || prev.type === 'white') && local < half(prev)) {
      dip = { color: color(prev), alpha: 1 - local / half(prev) }
    }
  })
  return { layers: layers.slice(-2), dip }
}

export function splitAt(edit: Edit, t: number): Edit | null {
  const { offsets } = layout(edit)
  const i = edit.clips.findIndex((c, j) => t > offsets[j] + MIN_CLIP && t < offsets[j] + clipLength(c) - MIN_CLIP)
  if (i < 0) return null
  const c = edit.clips[i]
  const cut = c.start + (t - offsets[i]) * c.speed
  const clips = [...edit.clips.slice(0, i), { ...c, end: cut }, { ...c, start: cut }, ...edit.clips.slice(i + 1)]
  const transitions = [...edit.transitions.slice(0, i), { type: 'none' as const, duration: 0.5 }, ...edit.transitions.slice(i)]
  return { ...edit, clips, transitions }
}

export function removeClip(edit: Edit, i: number): Edit {
  if (edit.clips.length < 2) return edit
  const transitions = [...edit.transitions]
  transitions.splice(Math.min(i, transitions.length - 1), 1)
  return { ...edit, clips: edit.clips.filter((_, j) => j !== i), transitions }
}

export function filmstrip(src: string, count: number, height: number): Promise<Omit<Source, 'name'>> {
  return new Promise((resolve, reject) => {
    const v = document.createElement('video')
    v.muted = true
    v.preload = 'auto'
    v.crossOrigin = 'anonymous'
    v.src = src
    v.onerror = () => reject(new Error(t('videoEdit.failedToLoadVideo')))
    v.onloadedmetadata = async () => {
      const c = document.createElement('canvas')
      c.height = height
      c.width = Math.round(height * v.videoWidth / v.videoHeight)
      const ctx = c.getContext('2d')!
      const thumbs: string[] = []
      for (let i = 0; i < count; i++) {
        v.currentTime = ((i + 0.5) * v.duration) / count
        await new Promise((r) => v.addEventListener('seeked', r, { once: true }))
        ctx.drawImage(v, 0, 0, c.width, c.height)
        thumbs.push(c.toDataURL('image/jpeg', 0.7))
      }
      resolve({ duration: v.duration, width: v.videoWidth, height: v.videoHeight, thumbs })
      v.removeAttribute('src')
      v.load()
    }
  })
}

function drawCover(ctx: CanvasRenderingContext2D, v: HTMLVideoElement) {
  const { width, height } = ctx.canvas
  const k = Math.max(width / v.videoWidth, height / v.videoHeight)
  const w = v.videoWidth * k
  const h = v.videoHeight * k
  ctx.drawImage(v, (width - w) / 2, (height - h) / 2, w, h)
}

export function drawFrame(ctx: CanvasRenderingContext2D, edit: Edit, frame: Frame, t: number, video: (layer: Frame['layers'][number]) => HTMLVideoElement) {
  const { width, height } = ctx.canvas
  ctx.globalAlpha = 1
  ctx.fillStyle = '#000'
  ctx.fillRect(0, 0, width, height)
  for (const l of frame.layers) {
    ctx.globalAlpha = l.alpha
    drawCover(ctx, video(l))
  }
  if (frame.dip) {
    ctx.globalAlpha = Math.min(1, Math.max(0, frame.dip.alpha))
    ctx.fillStyle = frame.dip.color
    ctx.fillRect(0, 0, width, height)
  }
  ctx.globalAlpha = 1
  for (const s of edit.subtitles) if (t >= s.start && t <= s.end && s.text) drawSubtitle(ctx, s)
}

export function drawSubtitle(ctx: CanvasRenderingContext2D, s: Subtitle) {
  const { width, height } = ctx.canvas
  const size = (s.size / 1080) * height
  ctx.font = `600 ${size}px Inter, "Microsoft YaHei", sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'bottom'
  ctx.lineJoin = 'round'
  ctx.lineWidth = size / 6
  ctx.strokeStyle = 'rgba(0,0,0,.75)'
  ctx.strokeText(s.text, width / 2, height * 0.92)
  ctx.fillStyle = s.color
  ctx.fillText(s.text, width / 2, height * 0.92)
}
