import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { brandCardPresentation, brandConfirmClosed, brandDeadlineClock, brandQuoteAction, brandQuotePositions, brandRequoteRequest } from '../src/brandQuoteCard.ts'

const NOW = 1_700_000_000_000

test('a brand card at the deadline does not offer Start', () => {
  const block = { brand_confirm: true, status: 'pending', expires_at: NOW / 1000 }
  assert.equal(brandConfirmClosed(block, NOW), true)
  assert.equal(brandConfirmClosed(block, NOW - 1), false)
})

test('restoring an expired brand card stays closed on the first check', () => {
  const block = { brand_confirm: true, status: 'pending', expires_at: (NOW / 1000) - 1 }
  assert.equal(brandConfirmClosed(block, NOW), true)
})

test('a missing deadline fails closed and other cards are untouched', () => {
  assert.equal(brandConfirmClosed({ brand_confirm: true, status: 'pending' }, NOW), true)
  assert.equal(brandConfirmClosed({ brand_confirm: true, status: 'expired', expires_at: NOW / 1000 + 10 }, NOW), true)
  assert.equal(brandConfirmClosed({ status: 'pending', expires_at: 1 }, NOW), false)
})

test('the expired brand card uses the product sentence and does not keep Start', () => {
  const zh = readFileSync(new URL('../src/locales/zh.json', import.meta.url), 'utf8')
  const en = readFileSync(new URL('../src/locales/en.json', import.meta.url), 'utf8')
  const view = readFileSync(new URL('../src/ui/ChatMessage.tsx', import.meta.url), 'utf8')
  const inline = readFileSync(new URL('../src/ui/ChatInlineConfirm.tsx', import.meta.url), 'utf8')
  assert.match(zh, /"jobs\.quoteExpired": "报价已过期，请重新取价"/)
  assert.match(zh, /"jobs\.brandStart": "开始"/)
  assert.match(zh, /"jobs\.requote": "重新取价"/)
  assert.match(zh, /"jobs\.quoteDeadline": "报价 10 分钟内有效，截止 \{0\}（北京时间）"/)
  assert.match(en, /"jobs\.quoteDeadline": "This quote is valid for 10 minutes, until \{0\} \(Beijing time\)\."/)
  assert.match(view, /brandConfirmClosed\(b, now\)/)
  const closed = view.indexOf('if (closed &&')
  const button = view.indexOf('testId="chat-inline-planquote"', closed)
  assert.ok(closed > 0 && button > closed)
  assert.match(view, /data-testid="brand-quote-expired"/)
  assert.match(view, /data-testid="brand-quote-requote"/)
  assert.doesNotMatch(view, /data-testid="brand-fixed-size"/)
  assert.match(view, /brandDeadlineClock\(b\.expires_at\)/)
  assert.match(view, /brandQuoteAction\(b\.price_state\)/)
  const total = inline.indexOf('ca-plan__head')
  const note = inline.indexOf('data-testid="brand-quote-deadline"')
  const actions = inline.indexOf('ca-chat-confirm__actions')
  assert.ok(total > 0 && note > total && actions > note)
})

test('the deadline is the stored expires_at in Beijing time and does not follow the clock', () => {
  const expiresAt = Date.UTC(2026, 10, 24, 5, 30, 0) / 1000
  assert.equal(brandDeadlineClock(expiresAt), '13:30')
  assert.equal(brandDeadlineClock(expiresAt), brandDeadlineClock(expiresAt))
  const later = Date.UTC(2026, 10, 24, 5, 39, 0) / 1000
  assert.equal(brandDeadlineClock(later), '13:39')
  assert.notEqual(brandDeadlineClock(expiresAt), brandDeadlineClock(later))
})

test('a real price starts and an estimate or unpriced card does not offer Start', () => {
  assert.equal(brandQuoteAction('quote'), 'start')
  assert.equal(brandQuoteAction(undefined), 'start')
  assert.equal(brandQuoteAction('estimate'), 'requote')
  assert.equal(brandQuoteAction('unpriced'), 'requote')
})

test('estimate and expired requote buttons both post the server re-quote', () => {
  const view = readFileSync(new URL('../src/ui/ChatMessage.tsx', import.meta.url), 'utf8')
  const bot = readFileSync(new URL('../src/bot.ts', import.meta.url), 'utf8')
  const expiredAt = view.indexOf('data-testid="brand-quote-requote"')
  const expiredClick = view.slice(expiredAt, expiredAt + 280)
  assert.match(expiredClick, /requoteBrandCard\(b\.ask_id/)
  assert.doesNotMatch(expiredClick, /sendMessage/)
  const estimateAt = view.indexOf('await requoteBrandCard(askId)')
  const estimateClick = view.slice(estimateAt, estimateAt + 80)
  assert.match(estimateClick, /requoteBrandCard\(askId\)/)
  assert.doesNotMatch(view, /answer\(\['requote'\]\)/)
  assert.equal(view.split('requoteBrandCard(').length - 1, 2)
  assert.match(bot, /requoteBrandCard/)
  assert.match(bot, /brandRequoteRequest/)
  assert.deepEqual(brandRequoteRequest('chat 1', 'ask/2'), {
    path: '/comfyart/bot/chats/chat%201/brand-requote',
    body: { ask_id: 'ask/2' },
  })
})

test('a replaced card is one line with no buttons and the new card keeps its own deadline', () => {
  const zh = readFileSync(new URL('../src/locales/zh.json', import.meta.url), 'utf8')
  const en = readFileSync(new URL('../src/locales/en.json', import.meta.url), 'utf8')
  const view = readFileSync(new URL('../src/ui/ChatMessage.tsx', import.meta.url), 'utf8')
  assert.match(zh, /"jobs\.quoteRequoted": "已重新取价，此报价已失效"/)
  assert.match(en, /"jobs\.quoteRequoted": "A new price was requested\. This quote is no longer valid\."/)
  const supersededAt = view.indexOf('data-testid="brand-quote-superseded"')
  const superseded = view.slice(supersededAt, view.indexOf('if (closed', supersededAt))
  assert.ok(supersededAt > 0)
  assert.match(superseded, /t\('jobs\.quoteRequoted'\)/)
  assert.doesNotMatch(superseded, /<button/)
  const oldAt = Date.UTC(2026, 10, 24, 5, 30, 0) / 1000
  const newAt = oldAt + 600
  const now = oldAt * 1000 + 1000
  const oldCard = {
    brand_confirm: true, ask_id: 'old', status: 'answered', selected: ['requote'],
    replaced_by: 'new', expires_at: oldAt, price_state: 'estimate', prompt: '预计约 3 积分',
  }
  const nextCard = {
    brand_confirm: true, ask_id: 'new', status: 'pending', expires_at: newAt,
    price_state: 'estimate', prompt: '这次生成预计约 3 积分。实时价暂不可用。',
  }
  const placed = brandQuotePositions([
    { blocks: [{ type: 'text' }, oldCard] },
    { blocks: [{ type: 'text', text: 'a later note stays above the new card' }] },
    { blocks: [nextCard] },
  ], now)
  assert.equal(placed.length, 2)
  assert.equal(placed[0].askId, 'old')
  assert.equal(placed[0].face, 'superseded')
  assert.deepEqual(placed[0].buttons, [])
  assert.equal(placed[0].messageIndex, 0)
  assert.equal(placed[0].blockIndex, 1)
  assert.equal(placed[1].askId, 'new')
  assert.equal(placed[1].messageIndex, 2)
  assert.ok(placed[1].messageIndex > placed[0].messageIndex)
  assert.equal(placed[1].deadline, '13:40')
  assert.equal(brandDeadlineClock(oldAt), '13:30')
  assert.notEqual(placed[1].deadline, brandDeadlineClock(oldAt))
  assert.deepEqual(placed[1].buttons, ['requote', 'cancel'])
  assert.equal(placed[1].buttons.includes('start'), false)
  assert.match(placed[1].sentence, /约/)
  assert.deepEqual(brandCardPresentation(nextCard, now).buttons, ['requote', 'cancel'])
  const stillOpen = { ...oldCard, replaced_by: '' }
  assert.equal(brandCardPresentation(stillOpen, now).face, 'pending')
})

test('an expired card with replaced_by collapses to one line and a second click does not surface 409', () => {
  const now = Date.UTC(2026, 10, 24, 6, 0, 0)
  const expired = {
    brand_confirm: true, ask_id: 'old', status: 'pending',
    expires_at: now / 1000 - 60, price_state: 'quote', prompt: '6 积分',
  }
  assert.equal(brandCardPresentation(expired, now).face, 'expired')
  assert.deepEqual(brandCardPresentation(expired, now).buttons, ['requote'])
  const replaced = { ...expired, replaced_by: 'new-ask' }
  const face = brandCardPresentation(replaced, now)
  assert.equal(face.face, 'superseded')
  assert.deepEqual(face.buttons, [])
  assert.equal(face.deadline, '')
  const view = readFileSync(new URL('../src/ui/ChatMessage.tsx', import.meta.url), 'utf8')
  const bot = readFileSync(new URL('../src/bot.ts', import.meta.url), 'utf8')
  const clickAt = view.indexOf('data-testid="brand-quote-requote"')
  const click = view.slice(clickAt, view.indexOf('{t(\'jobs.requote\')}', clickAt))
  assert.match(click, /disabled=\{requoted\}/)
  assert.match(click, /if \(requoteLock\.current\) return/)
  assert.match(click, /setRequoted\(true\)/)
  assert.match(click, /requoteBrandCard\(b\.ask_id/)
  const fnAt = bot.indexOf('export async function requoteBrandCard')
  const fn = bot.slice(fnAt, bot.indexOf('export function quoteAnswer', fnAt))
  assert.match(fn, /requoteInflight\.has\(askId\)/)
  assert.match(fn, /if \(res\.status === 409\) return/)
  assert.doesNotMatch(fn, /setError/)
})
