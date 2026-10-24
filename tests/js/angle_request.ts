// #249: angle params the panel and the cloud request share. No WaveSpeed call.
import { angleDistance, angleParams, anglePrompt } from '../../src/workflows'

const WORDS = ['close-up', 'medium shot', 'wide shot'] as const
const cases = [
  { h: -90, v: 0, z: 1.3 },
  { h: 90, v: 0, z: 5 },
  { h: 270, v: 0, z: 8 },
  { h: 0, v: 80, z: 7 },
  { h: 0, v: -40, z: 2.9 },
]
const out = cases.map((c) => {
  const params = angleParams(c.h, c.v, c.z)
  const caption = anglePrompt(c.h, c.v, c.z)
  if (params.distance !== angleDistance(c.z) || !caption.includes(WORDS[params.distance])) {
    throw new Error(`panel caption diverges from distance at z=${c.z}: ${caption}`)
  }
  return { h: c.h, v: c.v, z: c.z, ...params, caption }
})
console.log(JSON.stringify(out))
