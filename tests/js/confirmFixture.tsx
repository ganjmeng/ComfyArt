import { createRoot } from 'react-dom/client'

import { confirmDesc } from '../../src/confirmText'
import { previewLang, t } from '../../src/i18n'
import '../../src/styles/base.css'
import '../../src/styles/home.css'
import '../../src/styles/overlays.css'
import '../../src/styles/shell.css'
import { Confirm, confirmAtom } from '../../src/ui/Confirm'

document.documentElement.dataset.fixture = 'ran'
previewLang('zh')
// Same sentence askCost puts in the product Confirm dialog.
// 0.05 is a local stand-in for confirm_usd, not a live WaveSpeed price response.
const gif = { frame_count: 16, frame_duration_ms: 20, asked_frame_count: 99, asked_frame_duration_ms: 5 }
confirmAtom.set({
  title: t('jobs.confirmTitle'),
  desc: confirmDesc(0.05, undefined, false, { live: true, gif }),
  ok: t('jobs.confirmOk'),
  run: () => undefined,
  cancel: () => undefined,
})
createRoot(document.getElementById('root')!).render(<Confirm />)
