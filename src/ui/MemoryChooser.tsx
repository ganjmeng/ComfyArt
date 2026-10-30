import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useValue } from 'tldraw'

import { lang, t } from '../i18n'
import { correct, forget, memoryChoiceAtom, memoryToastAtom, showMemoryToast } from '../memory'

export { showMemoryToast } from '../memory'
import { Icons } from './icons'
import { Modal } from './Modal'

const validTime = (time: unknown): time is number => typeof time === 'number' && Number.isFinite(time) && time > 0

/** 「10月27日 18:20」 (zh) / "Oct 27 18:20" (en), local time; '' for a legacy record without a valid time. */
export function chooserTime(time: unknown): string {
  if (!validTime(time)) return ''
  const d = new Date(time)
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  return lang === 'zh' ? `${d.getMonth() + 1}月${d.getDate()}日 ${hm}` : `${d.toLocaleString('en-US', { month: 'short' })} ${d.getDate()} ${hm}`
}

/** #381: a text edit matched several memories — nothing was written; the user picks one (delete-confirm style). */
export function MemoryChooser() {
  const choice = useValue(memoryChoiceAtom)
  const [picked, setPicked] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  // rows below the fold → bottom fade + an always-visible scrollbar (native ones are overlay/hidden on macOS)
  const [bar, setBar] = useState<{ more: boolean; top: number; size: number } | null>(null)
  const measure = () => {
    const el = listRef.current
    if (!el || el.scrollHeight <= el.clientHeight + 1) { setBar(null); return }
    const size = (el.clientHeight / el.scrollHeight) * 100
    setBar({ more: el.scrollTop + el.clientHeight < el.scrollHeight - 1, size, top: (el.scrollTop / el.scrollHeight) * 100 })
  }
  const more = !!bar?.more
  useEffect(measure, [choice])
  if (!choice) return null
  const close = () => { memoryChoiceAtom.set(null); setPicked(null) }
  const run = async () => {
    if (!picked) return
    close()
    try {
      if (choice.action === 'forget') { if ((await forget([{ id: picked }], choice.source)).changed.length) showMemoryToast(t('arti.memory.deletedToast')) }
      else await correct([{ id: picked, old: '', new: choice.next ?? '' }], choice.source)
    } catch { /* the store already showed 保存失败，请重试 */ }
  }
  const danger = choice.action === 'forget'
  const rows = [...choice.candidates].sort((a, b) => (validTime(b.time) ? b.time : -Infinity) - (validTime(a.time) ? a.time : -Infinity) || 0)  // newest first, untimed last
  return createPortal(
    <Modal title={t(danger ? 'memory.choose.titleForget' : 'memory.choose.title', rows.length)} className="ca-rename ca-confirm" closable={false} onClose={close}>
      <div className="ca-rename__body" data-testid="memory-chooser">
        <div className="ca-mem-choose__scroll" data-more={more || undefined} data-testid="memory-chooser-scroll">
        <div className="ca-mem-choose__list" role="radiogroup" ref={listRef} onScroll={measure} data-testid="memory-chooser-list">
          {rows.map((m) => (
            <label key={m.id} className="ca-mem-choose__row" data-testid="memory-chooser-row" data-id={m.id}>
              <input type="radio" name="ca-mem-choose" checked={picked === m.id} onChange={() => setPicked(m.id)} />
              <span className="ca-mem-choose__text">{m.text}</span>
              {chooserTime(m.time) ? <span className="ca-mem-choose__time" data-testid="memory-chooser-time">{chooserTime(m.time)}</span> : null}
            </label>
          ))}
        </div>
        {bar ? <div className="ca-mem-choose__bar" aria-hidden data-testid="memory-chooser-bar"><i style={{ top: `${bar.top}%`, height: `${bar.size}%` }} /></div> : null}
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

/** #381: Lovart-style top-left toast: 记忆已删除 (trash) or 保存失败，请重试 (error). */
export function MemoryToast() {
  const toast = useValue(memoryToastAtom)
  if (!toast) return null
  return createPortal(<div key={toast.key} className="ca-mem-toast" data-kind={toast.kind} role={toast.kind === 'error' ? 'alert' : 'status'} data-testid="memory-toast">{toast.kind !== 'info' && <span className="ca-icon ca-mem-toast__icon">{toast.kind === 'error' ? Icons.question : Icons.trash}</span>}{toast.text}</div>, document.body)
}
