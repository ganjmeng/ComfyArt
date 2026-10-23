const HOP = 256
const MIN_BPM = 60
const MAX_BPM = 200
const STEP_BPM = 0.1
const HARMONICS = [1, 2, 3, 4]
const PRIOR_BPM = 120

export interface Beats { bpm: number; times: number[] }

function at(env: Float32Array, x: number): number {
  const i = Math.floor(x)
  const f = x - i
  return i + 1 < env.length ? env[i] * (1 - f) + env[i + 1] * f : 0
}

function correlation(env: Float32Array, lag: number): number {
  const n = Math.floor(env.length - lag - 1)
  let s = 0
  for (let f = 0; f < n; f++) s += env[f] * at(env, f + lag)
  return n > 0 ? s / n : 0
}

export async function detectBeats(src: string): Promise<Beats> {
  const buf = await new OfflineAudioContext(1, 1, 44100).decodeAudioData(await (await fetch(src)).arrayBuffer())
  const channels = Array.from({ length: buf.numberOfChannels }, (_, i) => buf.getChannelData(i))
  const n = Math.floor(buf.length / HOP)
  const energy = new Float32Array(n)
  for (let f = 0; f < n; f++) {
    let s = 0
    for (const c of channels) for (let k = f * HOP; k < (f + 1) * HOP; k++) s += c[k] * c[k]
    energy[f] = Math.log1p(s)
  }
  const env = energy.map((e, f) => (f ? Math.max(0, e - energy[f - 1]) : 0))
  const mean = env.reduce((a, b) => a + b, 0) / n
  for (let f = 0; f < n; f++) env[f] -= mean
  const rate = buf.sampleRate / HOP
  let bpm = PRIOR_BPM
  let best = -Infinity
  for (let b = MIN_BPM; b <= MAX_BPM; b += STEP_BPM) {
    const lag = (60 * rate) / b
    const s = HARMONICS.reduce((a, k) => a + correlation(env, k * lag), 0) * Math.exp(-0.5 * Math.log2(b / PRIOR_BPM) ** 2)
    if (s > best) { best = s; bpm = b }
  }
  const lag = (60 * rate) / bpm
  let phase = 0
  best = -Infinity
  for (let p = 0; p < lag; p += 0.25) {
    let s = 0
    for (let f = p; f < n; f += lag) s += at(env, f)
    if (s > best) { best = s; phase = p }
  }
  const times: number[] = []
  for (let f = phase; f < n; f += lag) times.push(f / rate)
  return { bpm, times }
}

export function snap(t: number, points: number[], within: number): number {
  let best = t
  let gap = within
  for (const p of points) if (Math.abs(p - t) < gap) { best = p; gap = Math.abs(p - t) }
  return best
}
