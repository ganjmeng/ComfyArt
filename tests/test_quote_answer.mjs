import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createQuoteAnswer } from '../src/ui/quoteAnswer.ts'
import { ConfirmationSubmission } from '../src/ui/confirmationSubmission.ts'
const tick = () => new Promise(resolve => setImmediate(resolve))

test('quote approval is bound to the original chat and exact selected answer', async () => {
  const calls = []
  let currentChat = 'original/chat'
  const answer = createQuoteAnswer(currentChat, 'ask/one', async (...args) => { calls.push(args); return { ok: true } })
  currentChat = 'different-chat'
  await answer(['start'])
  assert.deepEqual(calls, [['/comfyart/bot/chats/original%2Fchat/asks/ask%2Fone/answer', { selected: ['start'], other_text: '' }]])
})
test('missing conversation does not silently approve or send', async () => {
  let calls = 0
  const request = async () => { calls++; return { ok: true } }
  await assert.rejects(createQuoteAnswer(null, 'ask', request)(['start']))
  await assert.rejects(createQuoteAnswer('chat', '', request)(['start']))
  assert.equal(calls, 0)
})
test('malformed or missing acknowledgements cannot count as approval', async () => {
  for (const ack of [null, undefined, {}, { ok: false }, { ok: 'true' }]) {
    await assert.rejects(createQuoteAnswer('chat', 'ask', async () => ack)(['start']))
  }
})
test('both quote choices use a single pending request; rejection stays uncertain without retry', async () => {
  for (const choice of ['start', 'confirm']) {
    let calls = 0, fail, success = 0
    const answer = createQuoteAnswer('chat', 'ask', async () => {
      calls++
      return await new Promise((_, reject) => { fail = reject })
    })
    const machine = new ConfirmationSubmission(() => answer([choice]), {
      onSuccess: () => success++, onFailure: () => {},
      schedule: () => 1, unschedule: () => {},
    })
    machine.start(); machine.start(); await tick()
    assert.equal(calls, 1)
    assert.equal(machine.canClose(), false)
    fail(new Error('response lost')); await tick()
    assert.equal(machine.getSnapshot(), 'uncertain')
    assert.equal(machine.canClose(), true)
    assert.equal(machine.start(), false)
    assert.equal(success, 0)
    assert.equal(calls, 1)
  }
})
test('cancel and decline retain their exact non-approval answer', async () => {
  const selected = []
  const answer = createQuoteAnswer('chat', 'ask', async (_, body) => { selected.push(body.selected); return { ok: true } })
  await answer(['cancel']); await answer(['decline'])
  assert.deepEqual(selected, [['cancel'], ['decline']])
})
test('static wiring: both quote components opt into shared lifecycle and no error reopens an approval', () => {
  const source = readFileSync('src/ui/ChatMessage.tsx', 'utf8')
  const start = source.indexOf('export function OverQuote(')
  const end = source.indexOf('function Task(', start)
  const quotes = source.slice(start, end)
  assert.equal((quotes.match(/submit: async/g) ?? []).length, 2)
  assert.equal((quotes.match(/const answer = quoteAnswer\(askId\)/g) ?? []).length, 2)
  assert.equal((quotes.match(/if \(confirmAtom.get\(\) === ask\)/g) ?? []).length, 2)
  assert.equal(quotes.includes('open()'), false)
  assert.equal(quotes.includes('void answerAsk('), false)
})
