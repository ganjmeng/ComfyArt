import { useState } from 'react'
import { useValue, type Editor, type TLPageId, type TLShapeId } from 'tldraw'

import { COMMENT } from '../shapes/CommentShape'
import { allComments } from './CommentsList'
import { confirmAtom } from './Confirm'
import { exportAtom } from './ExportDialog'
import { Icons } from './icons'
import { SettingsMenu } from './SettingsMenu'
import { sideAtom } from './SidePanel'
import { t } from '../i18n'
import { isEnter } from './keys'
import { keySettingsOpenAtom, keyStatusAtom } from '../wavespeedKey'
import { keyStateText } from './KeySettings'

function exportTargets(editor: Editor): TLShapeId[] {
  const selected = editor.getSelectedShapeIds()
  if (selected.length) return selected
  return editor.getSortedChildIdsForParent(editor.getCurrentPageId()).filter((id) => editor.getShape(id)?.type !== COMMENT)
}

export function TopBar({ editor, left }: { editor: Editor; left?: React.ReactNode }) {
  const pages = useValue('pages', () => editor.getPages(), [editor])
  const current = useValue('current page', () => editor.getCurrentPageId(), [editor])
  const [renaming, setRenaming] = useState<TLPageId | null>(null)
  const side = useValue(sideAtom)
  const exportable = useValue('exportable', () => exportTargets(editor).length > 0, [editor])
  const keyStatus = useValue(keyStatusAtom)
  const openComments =useValue('open comments', () => allComments(editor).filter((c) => !c.props.done).length, [editor])

  const add = () => {
    const name = t('topBar.page', pages.length + 1)
    editor.createPage({ name })
    const page = editor.getPages().at(-1)!
    editor.setCurrentPage(page.id)
  }

  return (
    <div className="ca-top" onPointerDown={(e) => e.stopPropagation()}>
      {left}
      <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('common.reference')} data-on={side === 'references' || undefined} onClick={() => sideAtom.set(side === 'references' ? null : 'references')}>
        <span className="ca-icon">{Icons.refs}</span>
      </button>
      <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('sidePanel.myAssets')} data-on={side === 'assets' || undefined} onClick={() => sideAtom.set(side === 'assets' ? null : 'assets')}>
        <span className="ca-icon">{Icons.assets}</span>
      </button>
      <div className="ca-bar__sep" />
      <div className="ca-tabs" role="tablist">
        {pages.map((p) => (
          <div key={p.id} role="tab" aria-selected={p.id === current} className="ca-tab" data-on={p.id === current || undefined} onClick={() => editor.setCurrentPage(p.id)} onDoubleClick={() => setRenaming(p.id)}>
            <span className="ca-icon">{Icons.page}</span>
            {renaming === p.id ? (
              <input
                autoFocus
                className="ca-tab__input"
                defaultValue={p.name}
                onBlur={(e) => { editor.renamePage(p.id, e.target.value.trim() || p.name); setRenaming(null) }}
                onKeyDown={(e) => {
                  e.stopPropagation()
                  if (isEnter(e)) e.currentTarget.blur()
                  if (e.key === 'Escape') setRenaming(null)
                }}
              />
            ) : (
              <span className="ca-tab__name">{p.name}</span>
            )}
            {pages.length > 1 && (
              <button type="button" className="ca-tab__close" title={t('topBar.deletePage')} onClick={(e) => { e.stopPropagation(); confirmAtom.set({ danger: true, title: t('topBar.deleteThisCanvasPage'), desc: t('topBar.everythingOnCanvasPageWill', p.name), ok: t('common.delete'), run: () => editor.deletePage(p.id) }) }}>
                <span className="ca-icon">{Icons.close}</span>
              </button>
            )}
          </div>
        ))}
        <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('topBar.newPage')} onClick={add}>
          <span className="ca-icon">{Icons.plus}</span>
        </button>
      </div>
      <div className="ca-gen__spacer" />
      {keyStatus && (
        <button type="button" className="ca-bar__btn" data-testid="ws-balance" title={`${t('wsKey.balanceTitle')}: ${keyStateText()}`} onClick={() => keySettingsOpenAtom.set(true)}>
          <span>{!keyStatus.configured ? t('wsKey.noKeyChip') : keyStatus.balance !== null ? `$${keyStatus.balance.toFixed(2)}` : '$—'}</span>
        </button>
      )}
      <button type="button" className="ca-bar__btn" disabled={!exportable} onClick={() => exportAtom.set(exportTargets(editor))}>
        <span className="ca-icon">{Icons.export}</span><span>{t('common.export')}</span>
      </button>
      <button type="button" className="ca-bar__btn" title={t('common.allComments')} data-on={side === 'comments' || undefined} onClick={() => sideAtom.set(side === 'comments' ? null : 'comments')}>
        <span className="ca-icon">{Icons.comment}</span>{openComments > 0 && <span className="ca-badge">{openComments}</span>}
      </button>
      <SettingsMenu editor={editor} trigger={({ open, toggle }) => (
        <button type="button" className="ca-bar__btn ca-bar__btn--icon" title={t('settings.settings')} data-open={open || undefined} onClick={toggle}>
          <span className="ca-icon">{Icons.settings}</span>
        </button>
      )} />
    </div>
  )
}
