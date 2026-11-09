import { firstGate } from '../../src/ui/firstAction.ts'

const gate = firstGate()
const fresh = firstGate()
console.log(JSON.stringify({
  first: gate(),
  second: gate(),
  again: fresh(),
}))
