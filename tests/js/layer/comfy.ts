// #145 browser stand-in for ./comfy: control_preview answers 409 (needs confirm) until confirmed, then a PNG.
import { confirmAtom } from '../../../src/ui/Confirm'
import { t } from '../i18n_stub'
const g = globalThis as any
g.__calls = []
export const api = async (url: string, init?: { body: string }) => {
  const body = JSON.parse(init?.body ?? '{}')
  g.__calls.push({ url, confirmed: !!body.inputs?.confirmed })
  if (!body.inputs?.confirmed) return new Response(JSON.stringify({ error: { confirm_usd: 0.06 } }), { status: 409 })
  return new Response(new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }), { status: 200 })
}
// same dialog as src/comfy.ts askCost (that module pulls in the whole app)
export function askCost(price: number): Promise<boolean> {
  const p = price.toFixed(2)
  return new Promise((resolve) => confirmAtom.set({
    title: t('jobs.confirmTitle'),
    desc: t('jobs.confirmCost', p),
    ok: t('jobs.confirmOk'),
    run: () => resolve(true),
    cancel: () => resolve(false),
  }))
}
