import { drawFrame, layout, sample, type Edit, type Frame } from './videoEdit'

const DRIFT = 0.25

function bind(el: HTMLMediaElement, src: string) {
  if (el.dataset.src === src) return
  el.dataset.src = src
  el.src = src
}

function settled(v: HTMLVideoElement): Promise<void> {
  return new Promise((resolve, reject) => {
    const done = () => {
      v.removeEventListener('seeked', check)
      v.removeEventListener('loadeddata', check)
      v.removeEventListener('error', fail)
    }
    const check = () => { if (!v.seeking && v.readyState >= 2) { done(); resolve() } }
    const fail = () => { done(); reject(new Error(`failed to load ${v.dataset.src}`)) }
    v.addEventListener('seeked', check)
    v.addEventListener('loadeddata', check)
    v.addEventListener('error', fail)
    check()
  })
}

export class Player {
  private videos: HTMLVideoElement[]
  private music: HTMLAudioElement
  private audio: AudioContext
  private gains: GainNode[]
  private musicGain: GainNode
  private raf = 0
  private origin = 0
  private time = 0
  playing = false
  onTime: (t: number) => void = () => {}

  constructor(private canvas: HTMLCanvasElement, private edit: () => Edit) {
    this.audio = new AudioContext()
    this.videos = [0, 1].map(() => {
      const v = document.createElement('video')
      v.crossOrigin = 'anonymous'
      v.preload = 'auto'
      return v
    })
    this.gains = this.videos.map((v) => {
      const g = this.audio.createGain()
      this.audio.createMediaElementSource(v).connect(g).connect(this.audio.destination)
      return g
    })
    this.music = new Audio()
    this.music.crossOrigin = 'anonymous'
    this.music.preload = 'auto'
    this.musicGain = this.audio.createGain()
    this.audio.createMediaElementSource(this.music).connect(this.musicGain).connect(this.audio.destination)
  }

  dispose() {
    this.pause()
    for (const el of [...this.videos, this.music]) { el.removeAttribute('src'); el.load() }
    void this.audio.close()
  }

  get current() { return this.time }

  private sync(frame: Frame, playing: boolean) {
    const edit = this.edit()
    const used = new Set<number>()
    for (const l of frame.layers) {
      const v = this.videos[l.clip % 2]
      const clip = edit.clips[l.clip]
      used.add(l.clip % 2)
      bind(v, clip.src)
      v.playbackRate = clip.speed
      this.gains[l.clip % 2].gain.value = clip.volume * l.alpha * (frame.dip ? 1 - frame.dip.alpha : 1)
      if (Math.abs(v.currentTime - l.src) > DRIFT || !playing) v.currentTime = l.src
      if (playing && v.paused) void v.play()
      if (!playing && !v.paused) v.pause()
    }
    const next = frame.layers.length ? frame.layers[frame.layers.length - 1].clip + 1 : -1
    this.videos.forEach((v, i) => {
      if (used.has(i)) return
      v.pause()
      this.gains[i].gain.value = 0
      const clip = edit.clips[next]
      if (clip && next % 2 === i) {
        bind(v, clip.src)
        if (Math.abs(v.currentTime - clip.start) > 0.04 && !v.seeking) v.currentTime = clip.start
      }
    })
    const m = edit.music
    if (!m) {
      this.music.pause()
      return
    }
    bind(this.music, m.src)
    this.musicGain.gain.value = m.volume
    const at = m.start + this.time
    const inside = Number.isFinite(this.music.duration) ? at < this.music.duration : true
    if (Math.abs(this.music.currentTime - at) > DRIFT || !playing) this.music.currentTime = at
    if (playing && inside && this.music.paused) void this.music.play()
    if ((!playing || !inside) && !this.music.paused) this.music.pause()
  }

  private draw(frame: Frame) {
    drawFrame(this.canvas.getContext('2d')!, this.edit(), frame, this.time, (l) => this.videos[l.clip % 2])
  }

  async seek(t: number) {
    const total = layout(this.edit()).total
    this.time = Math.min(Math.max(t, 0), total)
    const frame = sample(this.edit(), this.time)
    this.sync(frame, false)
    await Promise.all(frame.layers.map((l) => settled(this.videos[l.clip % 2])))
    this.draw(frame)
    this.onTime(this.time)
  }

  play(onEnd?: () => void) {
    if (this.playing) return
    void this.audio.resume()
    const total = layout(this.edit()).total
    if (this.time >= total - 0.05) this.time = 0
    this.playing = true
    this.origin = performance.now() - this.time * 1000
    const tick = () => {
      if (!this.playing) return
      this.time = (performance.now() - this.origin) / 1000
      if (this.time >= layout(this.edit()).total) {
        this.time = layout(this.edit()).total
        this.pause()
        onEnd?.()
        return
      }
      const frame = sample(this.edit(), this.time)
      this.sync(frame, true)
      this.draw(frame)
      this.onTime(this.time)
      this.raf = requestAnimationFrame(tick)
    }
    this.raf = requestAnimationFrame(tick)
  }

  pause() {
    this.playing = false
    cancelAnimationFrame(this.raf)
    this.videos.forEach((v) => v.pause())
    this.music.pause()
  }
}
