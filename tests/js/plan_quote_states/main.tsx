// The buttons PlanQuote renders: ChatInlineConfirm, with the same labels the card passes.
import { createRoot } from 'react-dom/client'
import { ChatInlineConfirm } from '../../../src/ui/ChatInlineConfirm'
import { setLang, t } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
setLang(lang)
const zh = lang === 'zh'
const kind = q.get('kind') || 'unpriced'
const repriceOnly = kind !== 'exact'

const copy = {
  unpriced: {
    desc: t('quote.unpricedPrompt'),
    lines: [{ text: 'GPT Image 2.6 Flare', price: zh ? '未定价' : 'Unpriced' }],
    total: zh ? '未定价' : 'Unpriced',
  },
  estimate: {
    desc: zh
      ? '这个任务共 1 步，预计约 5 积分。可以重新取价，或取消。'
      : 'This task has 1 step and will cost about 5 credits. Re-price, or cancel.',
    lines: [{ text: 'GPT Image 2.6 Flare', price: zh ? '约 5 积分' : 'about 5 credits' }],
    total: zh ? '约 5 积分' : 'about 5 credits',
  },
  exact: {
    desc: zh
      ? '这个任务共 1 步，预计 64 积分，超过了你设置的 50 积分确认线。确定开始吗？'
      : 'This task has 1 step and will cost 64 credits, above your 50 credits confirm limit. Start?',
    lines: [{ text: 'GPT Image 2.6 Flare', price: zh ? '64 积分' : '64 credits' }],
    total: zh ? '64 积分' : '64 credits',
  },
}[kind] ?? {
  desc: '',
  lines: [],
  total: '',
}

createRoot(document.getElementById('root')!).render(
  <ChatInlineConfirm
    title={repriceOnly ? (kind === 'unpriced' ? t('quote.unpricedTitle') : t('quote.estimateTitle')) : t('jobs.confirmTitle')}
    desc={copy.desc}
    okLabel={repriceOnly ? t('quote.reprice') : t('jobs.confirmOk')}
    cancelLabel={t('common.cancel')}
    lines={copy.lines}
    totalLabel={zh ? '总价' : 'Total'}
    total={copy.total}
    testId="chat-inline-planquote"
    onConfirm={() => { (globalThis as any).__choice = repriceOnly ? 'reprice' : 'start' }}
    onCancel={() => { (globalThis as any).__choice = 'cancel' }}
  />,
)
