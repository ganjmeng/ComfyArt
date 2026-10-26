import { useState } from 'react'
import { atom, useValue, type Editor, type TLShapeId } from 'tldraw'

import { CommentsList } from './CommentsList'
import { Icons } from './icons'
import { generated, LayerTree, Preview } from './LayersPanel'
import { LibraryPanel } from './LibraryPanel'
import { ReferencePanel } from './ReferencePanel'
import { t } from '../i18n'

export type Side = 'layers' | 'files' | 'assets' | 'comments' | 'references'
export const sideAtom = atom<Side | null>('side panel', null)
const TITLES: Record<Side, string> = { layers: t('common.layers'), files: t('canvasTools.generatedFiles'), assets: t('sidePanel.myAssets'), comments: t('common.allComments'), references: t('common.reference') }

function reveal(editor: Editor, id: TLShapeId) {
  const page = editor.getAncestorPageId(id)
  if (page) editor.setCurrentPage(page)
  editor.select(id)
  editor.zoomToSelection({ animation: { duration: 200 } })
}

function Layers({ editor }: { editor: Editor }) {
  const [history, setHistory] = useState(true)
  const items = useValue('history', () => generated(editor), [editor])
  return (
    <>
      <button type="button" className="ca-side__section" onClick={() => setHistory(!history)}>
        <span>{t('sidePanel.history')}</span><span className="ca-icon" data-flip={history || undefined}>{Icons.chevron}</span>
      </button>
      {history && (items.length
        ? <div className="ca-side__grid">{items.map((m) => <button key={m.id} type="button" className="ca-side__cell" onClick={() => reveal(editor, m.id)}><Preview m={m} /></button>)}</div>
        : <div className="ca-side__empty">{t('sidePanel.noHistoryYet')}</div>)}
      <div className="ca-side__rule" />
      <LayerTree editor={editor} />
    </>
  )
}

function Files({ editor }: { editor: Editor }) {
  const items = useValue('files', () => generated(editor), [editor])
  if (!items.length) return <div className="ca-side__empty">{t('sidePanel.noFilesYet')}</div>
  return (
    <>
      {items.map((m) => (
        <div key={m.id} className="ca-file">
          <span className="ca-file__thumb"><Preview m={m} /></span>
          <span className="ca-file__name">{new URL(m.src, location.origin).searchParams.get('filename')}</span>
          <a className="ca-bar__btn ca-bar__btn--icon" href={m.src} download={m.name} title={t('common.download')}><span className="ca-icon">{Icons.download}</span></a>
        </div>
      ))}
      <div className="ca-side__empty">{t('sidePanel.noMoreItems')}</div>
    </>
  )
}

const LEFT: Side[] = ['assets', 'references']

export function SidePanel({ editor, left, onError }: { editor: Editor; left?: boolean; onError: (msg: string) => void }) {
  const side = useValue(sideAtom)
  if (!side || LEFT.includes(side) !== !!left) return null
  const onClose = () => sideAtom.set(null)
  return (
    <div className="ca-side" data-left={left || undefined} onPointerDown={(e) => e.stopPropagation()} onWheel={(e) => e.stopPropagation()}>
      <div className="ca-side__head">
        <span>{TITLES[side]}</span>
        <button type="button" className="ca-panel__icon" title={t('common.close')} onClick={onClose}>{Icons.close}</button>
      </div>
      <div className="ca-side__body">
        {side === 'layers' && <Layers editor={editor} />}
        {side === 'files' && <Files editor={editor} />}
        {side === 'assets' && <LibraryPanel editor={editor} onError={onError} />}
        {side === 'comments' && <CommentsList editor={editor} onError={onError} />}
        {side === 'references' && <ReferencePanel editor={editor} onError={onError} />}
      </div>
    </div>
  )
}
