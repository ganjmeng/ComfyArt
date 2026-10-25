// #235: the real cost-confirm card (src/ui/Confirm), with a plan quote filled in.
import { createRoot } from 'react-dom/client'
import { Confirm, confirmAtom } from '../../../src/ui/Confirm'
import { setLang } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
setLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'

const zh = lang === 'zh'
confirmAtom.set({
  title: zh ? '确认费用' : 'Confirm cost',
  desc: zh
    ? '这个任务共 2 步，预计约 $0.64，超过了你设置的 $0.50 确认线。确定开始吗？'
    : 'This task has 2 steps and will cost about $0.64, above your $0.50 confirm limit. Start?',
  ok: zh ? '开始' : 'Start',
  lines: [
    { text: zh ? '生成海报 · Nano Banana' : 'Generate poster · Nano Banana', price: '$0.40' },
    { text: zh ? '生成视频 · Seedance' : 'Generate video · Seedance', price: zh ? '约 $0.24' : 'about $0.24' },
  ],
  totalLabel: zh ? '总价' : 'Total',
  total: zh ? '约 $0.64' : 'about $0.64',
  run: () => { (globalThis as any).__choice = 'start' },
  cancel: () => { (globalThis as any).__choice = 'cancel' },
})

createRoot(document.getElementById('root')!).render(<Confirm />)
