// #249: angle params the panel and the cloud request share. No WaveSpeed call.
import { angleDistance, angleParams, anglePrompt } from '../../src/workflows'

const WORDS = ['close-up', 'medium shot', 'wide shot'] as const
const STEPS: [number, string][] = [
  [0, 'front view'], [45, 'front-right quarter view'], [90, 'right side view'], [135, 'back-right quarter view'],
  [180, 'back view'], [225, 'back-left quarter view'], [270, 'left side view'], [315, 'front-left quarter view'],
]
const cases = [
  { h: -90, v: 0, z: 1.3 },
  { h: 90, v: 0, z: 5 },
  { h: 270, v: 0, z: 8 },
  { h: 0, v: 80, z: 7 },
  { h: 180, v: -40, z: 2.9 },
  { h: 359, v: 0, z: 5 },
  { h: 400, v: 0, z: 1.3 },
]
function nearest(h: number): string {
  const az = ((h % 360) + 360) % 360
  return STEPS.reduce((best, cur) => {
    const d = (a: number) => Math.min(Math.abs(az - a), 360 - Math.abs(az - a))
    return d(cur[0]) < d(best[0]) ? cur : best
  })[1]
}
const out = cases.map((c) => {
  const params = angleParams(c.h, c.v, c.z)
  const caption = anglePrompt(c.h, c.v, c.z)
  if (params.horizontal_angle < 0 || params.horizontal_angle > 359) throw new Error(`horizontal out of 0..359: ${params.horizontal_angle}`)
  if (params.vertical_angle < -30 || params.vertical_angle > 60) throw new Error(`vertical out of -30..60: ${params.vertical_angle}`)
  if (params.distance !== angleDistance(c.z) || !caption.includes(WORDS[params.distance])) {
    throw new Error(`panel caption diverges from distance at z=${c.z}: ${caption}`)
  }
  const view = nearest(params.horizontal_angle)
  if (!caption.includes(view)) throw new Error(`caption "${caption}" does not match sent ${params.horizontal_angle} (${view})`)
  return { h: c.h, v: c.v, z: c.z, ...params, caption }
})
console.log(JSON.stringify(out))
