// Static contracts only. Browser screenshots/interaction are separate evidence.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const postcss = require('postcss')
const css = fs.readFileSync('src/styles/controls.css', 'utf8')
const tree = postcss.parse(css)
const declarations = selector => {
  const rule = tree.nodes.find(node => node.type === 'rule' && node.selector === selector)
  assert.ok(rule, selector)
  return Object.fromEntries(rule.nodes.filter(node => node.type === 'decl').map(node => [node.prop, node.value]))
}
test('confirmation owns footer layout without the canvas stylesheet', () => {
  const d = declarations('.ca-confirm-actions')
  assert.equal(d.display, 'flex')
  assert.equal(d.gap, '8px')
  assert.equal(d['justify-content'], 'flex-end')
  assert.equal(d['flex-wrap'], 'wrap')
})
test('keyboard focus remains visible with a single neutral ring', () => {
  const d = declarations('.ca-btn:focus-visible')
  assert.equal(d.outline, '1px solid var(--ca-text-2)')
  assert.equal(d['outline-offset'], '2px')
  assert.equal(css.includes('html[data-force='), false)
})
test('secondary action uses the subtle boundary token, not text-strength border', () => {
  assert.equal(declarations('.ca-btn.ca-panel__secondary').border, '1px solid var(--ca-border)')
})
