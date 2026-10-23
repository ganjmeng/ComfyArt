import { atom, useValue } from 'tldraw'

import { Modal } from './Modal'
import { t } from '../i18n'

interface Ask { title: string; desc: string; ok: string; danger?: boolean; run: () => void; cancel?: () => void }

export const confirmAtom = atom<Ask | null>('confirm', null)

export function Confirm() {
  const ask = useValue(confirmAtom)
  if (!ask) return null
  const close = () => confirmAtom.set(null)
  const dismiss = () => { close(); ask.cancel?.() }
  return (
    <Modal title={ask.title} onClose={dismiss}>
      <div className="ca-rename__body">
        <div>{ask.desc}</div>
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary" onClick={dismiss}>{t('common.cancel')}</button>
          <button type="button" className={ask.danger ? 'ca-panel__primary ca-panel__danger' : 'ca-panel__primary'} onClick={() => { close(); ask.run() }}>{ask.ok}</button>
        </div>
      </div>
    </Modal>
  )
}
