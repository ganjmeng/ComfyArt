import { visibleToolError } from '../../src/ui/toolErrorLine.ts'

const model = 'wavespeed-ai/minimax-h3/text-to-video'
const msg = '没有返回图片，可能已扣费。'
const raw = JSON.stringify({ status: 'failed', generation_succeeded: false, error: msg, user_message: msg, model })
const got = visibleToolError(raw)
if (got !== msg) {
  console.error('user_message', JSON.stringify(got))
  process.exit(1)
}
if (got.includes('wavespeed') || got.includes('{') || got.includes('status')) process.exit(2)
if (visibleToolError(JSON.stringify({ status: 'failed', model }))) process.exit(3)
if (visibleToolError(`[tool error] ${JSON.stringify({ error: 'plain fail', model })}`) !== 'plain fail') process.exit(4)
if (visibleToolError('请先调用 quote_plan') !== '请先调用 quote_plan') process.exit(5)
const stripped = visibleToolError(`failed ${model} after submit`)
if (stripped.includes('wavespeed') || stripped.includes('/')) {
  console.error('model id', JSON.stringify(stripped))
  process.exit(6)
}
if (visibleToolError('https://wavespeed.ai/top-up') !== 'https://wavespeed.ai/top-up') process.exit(7)
console.log('ok')
