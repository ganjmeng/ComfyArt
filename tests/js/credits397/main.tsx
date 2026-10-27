// #397: cloud confirm dialog + settings confirm-line, credits only (no $).
import { createRoot } from 'react-dom/client'
import { Confirm, confirmAtom } from '../../../src/ui/Confirm'
import { setLang } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
const view = q.get('view') || 'cloud'
setLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'
const zh = lang === 'zh'

if (view === 'cloud') {
  confirmAtom.set({
    title: zh ? '确认费用' : 'Confirm cost',
    desc: zh ? '这次云端生成约需 75 积分，确定继续吗？' : 'This cloud job costs about 75 credits. Continue?',
    ok: zh ? '继续生成' : 'Generate',
    run: () => {},
    cancel: () => {},
  })
  createRoot(document.getElementById('root')!).render(<Confirm />)
} else {
  // settings confirm-line strip (matches KeySettings row)
  const label = zh
    ? '单次费用达到 50 积分时先确认（0 = 每次都确认）'
    : 'Ask before jobs costing 50 credits or more (0 = always)'
  createRoot(document.getElementById('root')!).render(
    <div className="ca-modal ca-modal--open" style={{ position: 'static', inset: 'auto', background: 'transparent' }}>
      <div className="ca-modal__card ca-rename ca-rename--key" style={{ width: 420 }}>
        <div className="ca-modal__head"><div className="ca-modal__title">{zh ? 'WaveSpeed Key' : 'WaveSpeed key'}</div></div>
        <div className="ca-rename__body">
          <label className="ca-rename__field ca-rename__field--key">
            <span>{label}</span>
            <input className="ca-panel__input" data-testid="ws-confirm-credits" readOnly value="50" />
          </label>
        </div>
      </div>
    </div>,
  )
}
