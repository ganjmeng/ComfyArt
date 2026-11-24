import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { brandConfirmClosed, brandDeadlineClock, brandQuoteAction } from '../src/brandQuoteCard.ts'

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
  const closed = view.indexOf('if (closed)')
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
