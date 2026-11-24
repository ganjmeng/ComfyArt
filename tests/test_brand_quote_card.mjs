import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { brandConfirmClosed } from '../src/brandQuoteCard.ts'

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
  const view = readFileSync(new URL('../src/ui/ChatMessage.tsx', import.meta.url), 'utf8')
  assert.match(zh, /"jobs\.quoteExpired": "报价已过期，请重新取价"/)
  assert.match(view, /brandConfirmClosed\(b, now\)/)
  const closed = view.indexOf('if (closed)')
  const button = view.indexOf('testId="chat-inline-planquote"', closed)
  assert.ok(closed > 0 && button > closed)
  assert.match(view, /data-testid="brand-quote-expired"/)
  assert.match(view, /data-testid="brand-fixed-size"/)
  assert.match(view, /data-size-locked/)
})
