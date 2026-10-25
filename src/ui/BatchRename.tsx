import { useState } from 'react'
import { atom, useValue, type Editor, type TLShapeId } from 'tldraw'

import { Modal } from './Modal'
import { Chips } from './Chips'
import { t } from '../i18n'

export const renameAtom = atom<TLShapeId[] | null>('batch rename', null)

const FORMATS: [number, string][] = [[1, '1, 2, 3'], [2, '01, 02, 03'], [3, '001, 002, 003']]

export function BatchRename({ editor }: { editor: Editor }) {
  const ids = useValue(renameAtom)
  const [prefix, setPrefix] = useState('')
  const [pad, setPad] = useState(1)
  const [start, setStart] = useState(1)
  if (!ids) return null
  const name = (i: number) => `${prefix}${String(start + i).padStart(pad, '0')}`
  const close = () => renameAtom.set(null)
  const apply = () => {
    editor.run(() => ids.forEach((id, i) => {
      const s = editor.getShape(id)
      if (s) editor.updateShape({ id, type: s.type, meta: { ...s.meta, name: name(i) } })
    }), { ignoreShapeLock: true })
    close()
  }

  return (
    <Modal title={t('batchRename.batchRename')} onClose={close}>
      <div className="ca-rename__body">
        <div className="ca-chat__hint">{t('batchRename.nameTheSelectedElementsIn')}</div>
        <label className="ca-rename__field ca-rename__field--batch"><span>{t('batchRename.prefixOptional')}</span>
          <input className="ca-panel__input" value={prefix} placeholder={t('batchRename.optional')} onChange={(e) => setPrefix(e.target.value)} onKeyDown={(e) => e.stopPropagation()} />
        </label>
        <div className="ca-rename__field"><span>{t('batchRename.numberFormat')}</span>
          <Chips value={pad} options={FORMATS} onPick={setPad} />
        </div>
        <label className="ca-rename__field ca-rename__field--batch"><span>{t('batchRename.startAt')}</span>
          <input className="ca-panel__input" type="number" min={0} value={start} onChange={(e) => setStart(Math.max(0, Number(e.target.value) || 0))} onKeyDown={(e) => e.stopPropagation()} />
        </label>
        <div className="ca-chat__hint">{t('batchRename.preview', [0, 1, 2].slice(0, ids.length).map(name).join(t('common.listSep')) + (ids.length > 3 ? '…' : ''))}</div>
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary" onClick={close}>{t('common.cancel')}</button>
          <button type="button" className="ca-panel__primary" onClick={apply}>{t('batchRename.rename')}</button>
        </div>
      </div>
    </Modal>
  )
}
