// #235 / #397: the real cost-confirm card (src/ui/Confirm), with a plan quote filled in (credits, no $).
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
    ? '这个任务共 2 步，预计约 64 积分，超过了你设置的 50 积分确认线。确定开始吗？'
    : 'This task has 2 steps and will cost about 64 credits, above your 50 credits confirm limit. Start?',
  ok: zh ? '开始' : 'Start',
  lines: [
    { text: zh ? '生成海报 · Nano Banana' : 'Generate poster · Nano Banana', price: zh ? '40 积分' : '40 credits' },
    { text: zh ? '生成视频 · Seedance' : 'Generate video · Seedance', price: zh ? '约 24 积分' : 'about 24 credits' },
  ],
  totalLabel: zh ? '总价' : 'Total',
  total: zh ? '约 64 积分' : 'about 64 credits',
  run: () => { (globalThis as any).__choice = 'start' },
  cancel: () => { (globalThis as any).__choice = 'cancel' },
})

createRoot(document.getElementById('root')!).render(<Confirm />)
