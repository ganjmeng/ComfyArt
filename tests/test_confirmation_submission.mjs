import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ConfirmationSubmission, canSubmitPricedConfirmation } from '../src/ui/confirmationSubmission.ts'
const tick = () => new Promise(resolve => setImmediate(resolve))
function harness(submit) {
  let timeout, succeeded = 0, failed = 0, cleared = 0
  const phases = []
  const machine = new ConfirmationSubmission(submit, {
    onPhase: p => phases.push(p), onSuccess: () => succeeded++, onFailure: () => failed++,
    schedule: (fn, ms) => { assert.equal(ms, 30000); timeout = fn; return 123 },
    unschedule: id => { assert.equal(id, 123); cleared++; timeout = undefined },
  })
  return { machine, phases, timeout: () => timeout?.(), counts: () => ({ succeeded, failed, cleared }) }
}
test('idle cancellation has not executed any request', () => {
  let calls = 0
  const h = harness(async () => { calls++ })
  assert.equal(h.machine.getSnapshot(), 'idle')
  assert.equal(h.machine.canClose(), true)
  assert.equal(calls, 0)
})
test('double submit invokes once and closes only after acknowledgement', async () => {
  let done, calls = 0
  const h = harness(() => { calls++; return new Promise(resolve => { done = resolve }) })
  assert.equal(h.machine.start(), true)
  assert.equal(h.machine.canClose(), false)
  assert.equal(h.machine.start(), false)
  await tick()
  assert.equal(calls, 1)
  assert.equal(h.counts().succeeded, 0)
  done(); await tick()
  assert.equal(h.machine.getSnapshot(), 'succeeded')
  assert.equal(h.counts().succeeded, 1)
  assert.equal(h.machine.start(), false)
  h.timeout()
  assert.equal(h.machine.getSnapshot(), 'succeeded')
})
test('timeout preserves the original request; no retry and late success is accepted', async () => {
  let done, calls = 0
  const h = harness(() => { calls++; return new Promise(resolve => { done = resolve }) })
  h.machine.start(); await tick(); h.timeout()
  assert.equal(h.machine.getSnapshot(), 'uncertain')
  assert.equal(h.machine.canClose(), true)
  assert.equal(h.machine.start(), false)
  assert.deepEqual(h.counts(), { succeeded: 0, failed: 0, cleared: 0 })
  done(); await tick()
  assert.equal(calls, 1)
  assert.deepEqual(h.phases, ['submitting', 'uncertain', 'succeeded'])
  assert.equal(h.counts().succeeded, 1)
})
test('network rejection is uncertain, never cancellation or automatic retry', async () => {
  let calls = 0
  const h = harness(async () => { calls++; throw new Error('response lost') })
  h.machine.start(); await tick()
  assert.equal(h.machine.getSnapshot(), 'uncertain')
  assert.equal(h.machine.canClose(), true)
  assert.equal(h.machine.start(), false)
  assert.equal(calls, 1)
  assert.deepEqual(h.counts(), { succeeded: 0, failed: 1, cleared: 1 })
})
test('synchronous callback failure is caught and does not leave closing locked', async () => {
  const h = harness(() => { throw new Error('sync failure') })
  h.machine.start(); await tick()
  assert.equal(h.machine.getSnapshot(), 'uncertain')
  assert.equal(h.machine.canClose(), true)
  assert.equal(h.counts().failed, 1)
})
test('phase subscription can be removed without affecting an outstanding request', async () => {
  const h = harness(async () => {})
  let observed = 0
  const unsubscribe = h.machine.subscribe(() => observed++)
  h.machine.start(); unsubscribe(); await tick()
  assert.equal(observed, 1)
  assert.equal(h.counts().succeeded, 1)
})
test('unpriced, missing, nonfinite or negative quotes cannot enable real paid submit', () => {
  for (const price of [null, NaN, Infinity, -Infinity, -1]) assert.equal(canSubmitPricedConfirmation(price), false)
  assert.equal(canSubmitPricedConfirmation(0.05, true), false)
  assert.equal(canSubmitPricedConfirmation(0.05), true)
  assert.equal(canSubmitPricedConfirmation(0), true)
})
test('static wiring: busy disables actions, stale events guarded, uncertain close does not cancel', () => {
  const confirm = readFileSync('src/ui/Confirm.tsx', 'utf8')
  const comfy = readFileSync('src/comfy.ts', 'utf8')
  assert.ok(confirm.includes('cancelDisabled={busy}'))
  assert.ok(confirm.includes('okDisabled={ask.okDisabled || busy || uncertain}'))
  assert.ok(confirm.includes('if (submission && !submission.canClose()) return'))
  assert.ok(confirm.includes('if (uncertain) { close(); return }'))
  assert.ok(confirm.includes('if (confirmAtom.get() !== ask || ask.okDisabled) return'))
  assert.ok(confirm.includes('if (confirmAtom.get() === ask) confirmAtom.set(null)'))
  assert.ok(comfy.includes('submit?: () => Promise<void>'))
  assert.ok(comfy.includes('!canSubmitPricedConfirmation(price, !!estimate?.unpriced)'))
})
