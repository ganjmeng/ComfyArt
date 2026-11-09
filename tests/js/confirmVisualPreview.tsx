// Offline component preview only: actual Confirm, mock quote, no product/backend acceptance.
import { createRoot } from 'react-dom/client'
import { Confirm, confirmAtom } from '../../src/ui/Confirm'
import { previewLang } from '../../src/i18n'
previewLang('zh')
const q = new URLSearchParams(location.search)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'
const scene = q.get('scene')
confirmAtom.set({
  title: '确认费用',
  desc: '本次生成预计消耗 5 积分。确认后开始生成。',
  ok: '继续生成',
  run: () => {},
  ...((scene === 'submitting' || scene === 'uncertain') ? {
    submit: () => scene === 'uncertain' ? Promise.reject(new Error('MOCK response lost')) : new Promise<void>(() => {}),
  } : {}),
})
createRoot(document.getElementById('root')!).render(<Confirm />)
