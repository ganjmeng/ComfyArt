// #145 browser stand-in for ./comfy: control_preview answers 409 (needs confirm) until confirmed, then a PNG.
import { confirmAtom } from '../../../src/ui/Confirm'
import { t } from '../i18n_stub'
import { usd } from '../../../src/usd'
const g = globalThis as any
g.__calls = []
export const api = async (url: string, init?: { body: string }) => {
  const body = JSON.parse(init?.body ?? '{}')
  g.__calls.push({ url, confirmed: !!body.inputs?.confirmed })
  if (!body.inputs?.confirmed) return new Response(JSON.stringify({ error: { confirm_usd: 0.06 } }), { status: 409 })
  return new Response(new Blob([new Uint8Array([137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82,0,0,0,1,0,0,0,1,8,6,0,0,0,31,21,196,137,0,0,0,13,73,68,65,84,120,218,99,252,207,192,80,15,0,4,133,1,128,132,169,140,33,0,0,0,0,73,69,78,68,174,66,96,130])], { type: 'image/png' }), { status: 200 })
}
// same dialog as src/comfy.ts askCost (that module pulls in the whole app)
export function askCost(price: number): Promise<boolean> {
  const p = usd(price)
  return new Promise((resolve) => confirmAtom.set({
    title: t('jobs.confirmTitle'),
    desc: t('jobs.confirmCost', p),
    ok: t('jobs.confirmOk'),
    run: () => resolve(true),
    cancel: () => resolve(false),
  }))
}
// same as src/comfy.ts CostDeclined (#127)
export class CostDeclined extends Error {
  constructor() { super('cost declined'); this.name = 'CostDeclined' }
}
