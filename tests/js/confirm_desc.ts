import { confirmDesc } from '../../src/confirmText'
import { uiCredits } from '../../src/usd'

// 0.05 is a local stand-in for the quote field. This file does not call a price API.
const price = 0.05
const live99 = confirmDesc(price, undefined, false, {
  live: true,
  gif: { frame_count: 16, frame_duration_ms: 20, asked_frame_count: 99, asked_frame_duration_ms: 5 },
}, 'zh')
const live1 = confirmDesc(price, undefined, false, {
  live: true,
  gif: { frame_count: 2, frame_duration_ms: 200, asked_frame_count: 1 },
}, 'zh')
const unpriced = confirmDesc(null, undefined, false, {
  unpriced: true,
  gif: { frame_count: 16, frame_duration_ms: 20, asked_frame_count: 99, asked_frame_duration_ms: 5 },
}, 'zh')
const estimate = confirmDesc(price, undefined, false, {
  estimate: true,
  gif: { frame_count: 16, frame_duration_ms: 20, asked_frame_count: 99 },
}, 'zh')

console.log(JSON.stringify({
  mockPrice: true,
  credits: uiCredits(price),
  live99,
  live1,
  unpriced,
  estimate,
}))
