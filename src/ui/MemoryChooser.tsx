import { useState } from 'react'
import { createPortal } from 'react-dom'
import { atom, useValue } from 'tldraw'

import { t } from '../i18n'
import { correct, forget, memoryChoiceAtom } from '../memory'
import { Icons } from './icons'
import { Modal } from './Modal'

/** #381: a text edit matched several memories — nothing was written; the user picks one (delete-confirm style). */
export function MemoryChooser() {
  const choice = useValue(memoryChoiceAtom)
  const [picked, setPicked] = useState<string | null>(null)
  if (!choice) return null
  const close = () => { memoryChoiceAtom.set(null); setPicked(null) }
  const run = async () => {
    if (!picked) return
    close()
    if (choice.action === 'forget') { if ((await forget([{ id: picked }], choice.source)).changed.length) showMemoryToast(t('arti.memory.deletedToast')) }
    else await correct([{ id: picked, old: '', new: choice.next ?? '' }], choice.source)
  }
  const danger = choice.action === 'forget'
  return createPortal(
    <Modal title={t('memory.choose.title', choice.candidates.length)} onClose={close}>
      <div className="ca-rename__body" data-testid="memory-chooser">
        <div className="ca-mem-choose__list" role="radiogroup">
          {choice.candidates.map((m) => (
            <label key={m.id} className="ca-mem-choose__row" data-testid="memory-chooser-row" data-id={m.id}>
              <input type="radio" name="ca-mem-choose" checked={picked === m.id} onChange={() => setPicked(m.id)} />
              <span className="ca-mem-choose__text">{m.text}</span>
            </label>
          ))}
        </div>
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary" data-testid="memory-chooser-cancel" onClick={close}>{t('common.cancel')}</button>
          <button type="button" data-testid="memory-chooser-ok" disabled={!picked} className={danger ? 'ca-panel__primary ca-panel__danger' : 'ca-panel__primary'} onClick={() => void run()}>
            {t(danger ? 'common.delete' : 'memory.choose.correct')}
          </button>
        </div>
      </div>
    </Modal>,
    document.body,
  )
}

const toastAtom = atom<{ text: string; key: number } | null>('memory toast', null)
let toastTimer: ReturnType<typeof setTimeout> | undefined
/** #381: Lovart-style top-left confirmation toast (e.g. 记忆已删除). */
export function showMemoryToast(text: string) {
  toastAtom.set({ text, key: Date.now() })
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => toastAtom.set(null), 2400)
}

export function MemoryToast() {
  const toast = useValue(toastAtom)
  if (!toast) return null
  return createPortal(<div key={toast.key} className="ca-mem-toast" role="status" data-testid="memory-toast"><span className="ca-icon ca-mem-toast__icon">{Icons.trash}</span>{toast.text}</div>, document.body)
}
