import { useEffect } from 'react'
import { createRoot } from 'react-dom/client'

import { confirmDesc } from '../../src/confirmText'
import { previewLang, t } from '../../src/i18n'
import '../../src/styles/base.css'
import '../../src/styles/home.css'
import '../../src/styles/overlays.css'
import '../../src/styles/shell.css'
import '../../src/styles/controls.css'
import { Button, IconButton } from '../../src/ui/Button'
import { Confirm, confirmAtom } from '../../src/ui/Confirm'
import { Icons } from '../../src/ui/icons'

document.documentElement.dataset.fixture = 'ran'
const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
previewLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'
const force = q.get('force')
if (force) document.documentElement.dataset.force = force

// Same sentence askCost puts in the product Confirm dialog.
// 0.05 is a local stand-in for confirm_usd, not a live WaveSpeed price response.
const gif = { frame_count: 16, frame_duration_ms: 20, asked_frame_count: 99, asked_frame_duration_ms: 5 }
const scene = q.get('scene') || 'cost'
const selftest = q.get('selftest') || ''
const counts = { runs: 0, cancels: 0, submits: 0 }

function publish(extra: Record<string, string> = {}) {
  const root = document.documentElement
  root.dataset.submits = String(counts.submits)
  root.dataset.runs = String(counts.runs)
  root.dataset.cancels = String(counts.cancels)
  for (const [key, value] of Object.entries(extra)) root.dataset[key] = value
  root.dataset.ready = '1'
}

function costAsk(danger = false) {
  confirmAtom.set({
    title: danger ? t('arti.memory.deleteTitle') : t('jobs.confirmTitle'),
    desc: danger ? t('arti.memory.deleteDesc', 'mock memory text') : confirmDesc(0.05, undefined, false, { live: true, gif }),
    ok: danger ? t('common.delete') : t('jobs.confirmOk'),
    danger,
    ...(['submit', 'submit-reject', 'submit-unpriced'].includes(scene) ? {
      okDisabled: scene === 'submit-unpriced',
      submit: async () => {
        counts.submits += 1; publish()
        const delay = Math.min(60000, Math.max(0, Number(q.get('submit-delay') || '1000') || 0))
        await new Promise<void>((resolve, reject) => setTimeout(() => {
          if (scene === 'submit-reject') reject(new Error('MOCK response lost'))
          else resolve()
        }, delay))
      },
      submissionFailed: () => publish({ submission: 'uncertain' }),
    } : {}),
    run: () => { counts.runs += 1; publish() },
    cancel: () => { counts.cancels += 1; publish() },
  })
}

function SelfTest({ mode }: { mode: string }) {
  useEffect(() => {
    const desc = document.querySelector('[data-testid=confirm-desc]')?.textContent ?? ''
    const focus = (document.activeElement as HTMLElement | null)?.dataset?.testid ?? ''
    const ok = document.querySelector<HTMLButtonElement>('[data-testid=confirm-ok]')
    const cancel = document.querySelector<HTMLButtonElement>('[data-testid=confirm-cancel]')
    if (mode === 'ok' && ok) { ok.click(); ok.click() }
    if (mode === 'cancel' && cancel) { cancel.click(); cancel.click() }
    if (mode === 'escape') {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    }
    publish({ desc, focus, selftest: mode })
  }, [mode])
  return null
}

function States() {
  return (
    <main className="ca-rename__body" data-testid="button-states" style={{ maxWidth: 420, margin: '48px auto', background: 'var(--ca-float)', borderRadius: 16, padding: 20 }}>
      <p data-testid="states-note">LOCAL FIXTURE · Button states · not the settings page · not an SVG product wire</p>
      <div className="ca-panel__foot ca-confirm-actions">
        <Button variant="secondary">{t('common.cancel')}</Button>
        <Button variant="primary">{t('jobs.confirmOk')}</Button>
        <IconButton variant="danger" icon={Icons.trash} label={t('common.delete')} />
        <Button variant="primary" disabled>{t('jobs.confirmOk')}</Button>
        <Button variant="secondary" loading>{t('common.cancel')}</Button>
      </div>
    </main>
  )
}

function MemoryShot({ pick }: { pick: boolean }) {
  useEffect(() => {
    if (!pick) return
    document.querySelector<HTMLInputElement>('[data-testid=memory-chooser-row] input')?.click()
  }, [pick])
  return null
}

async function boot() {
  const label = document.querySelector('[data-testid=fixture-label]')
  const root = createRoot(document.getElementById('root')!)
  if (scene === 'states') {
    if (label) label.textContent = 'LOCAL FIXTURE · button states · not a product screen'
    root.render(<States />)
    return
  }
  if (scene === 'memory') {
    if (label) label.textContent = 'LOCAL FIXTURE · product MemoryChooser · mock rows · not a live memory write'
    const { memoryChoiceAtom } = await import('../../src/memory')
    const { MemoryChooser } = await import('../../src/ui/MemoryChooser')
    memoryChoiceAtom.set({
      action: 'forget',
      text: 'mock',
      source: 'fixture',
      candidates: [
        { id: 'm1', text: 'mock memory · warm wood table', time: Date.UTC(2026, 9, 27, 10, 20) },
        { id: 'm2', text: 'mock memory · second row', time: Date.UTC(2026, 9, 26, 8, 0) },
      ],
    })
    root.render(<><MemoryChooser /><MemoryShot pick={q.get('pick') === '1'} /></>)
    return
  }
  if (label) label.textContent = scene === 'danger'
    ? 'LOCAL FIXTURE · product Confirm · danger · mock memory text'
    : 'LOCAL FIXTURE · mock price 0.05 · async scenes are local timers only · no network submission'
  costAsk(scene === 'danger')
  root.render(<>
    <Confirm />
    {selftest ? <SelfTest mode={selftest} /> : null}
  </>)
}

void boot()
