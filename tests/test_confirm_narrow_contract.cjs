// Static CSS contract only. Does not assert browser layout or visual PASS.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const postcss = require('postcss')
const css = postcss.parse(fs.readFileSync('src/styles/controls.css', 'utf8'))
const narrow = css.nodes.find(n => n.type === 'atrule' && n.name === 'media' && n.params === '(width < 380px)')
assert.ok(narrow, 'viewport breakpoint must exclude exactly 380px')
function declarations(selector) {
  const rule = narrow.nodes.find(n => n.selector === selector)
  assert.ok(rule, selector)
  return Object.fromEntries(rule.nodes.filter(n => n.type === 'decl').map(n => [n.prop, n.value]))
}
const card = declarations('.ca-modal__card.ca-confirm')
assert.equal(card['box-sizing'], 'border-box')
assert.equal(card.width, 'calc(100vw - 32px)')
for (const selector of ['.ca-confirm > .ca-side__head', '.ca-confirm > .ca-rename__body']) {
  const d = declarations(selector)
  assert.equal(d['padding-left'], '24px')
  assert.equal(d['padding-right'], '24px')
}
const facts = declarations('.ca-confirm .ca-keys__row')
assert.equal(facts['flex-direction'], 'column')
assert.equal(facts.height, 'auto')
assert.equal(declarations('.ca-confirm .ca-keys__row > span')['overflow-wrap'], 'anywhere')
console.log('PASS: narrow CSS contract (breakpoint, outer sizing, padding, facts, wrapping); browser not tested')

// Shared buttons and the footer override must both retain the approved metrics.
for (const selector of ['.ca-btn', '.ca-panel__foot > .ca-btn']) {
  const rule = css.nodes.find(n => n.type === 'rule' && n.selector === selector)
  assert.ok(rule, selector)
  const values = Object.fromEntries(rule.nodes.filter(n => n.type === 'decl').map(n => [n.prop, n.value]))
  assert.equal(values['min-height'], '36px')
  assert.equal(values['border-radius'], '8px')
}
console.log('PASS: static shared button metrics (36px minimum height, 8px radius); browser not tested')
