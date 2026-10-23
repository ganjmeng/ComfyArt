import { useState, type ReactNode } from 'react'
import { useValue, type Editor } from 'tldraw'

import { libraryAtom } from '../library'
import { confirmDelete } from '../home/confirmDelete'
import { saveNow, saveStateAtom } from '../autosave'
import { duplicateProject, newProject, openProject, openView, UNTITLED } from '../projects'
import { importFiles } from './DropHandlers'
import { historyAtom } from './HistoryDialog'
import { Icons } from './icons'
import { memoryOpenAtom } from './MemoryDialog'
import { workflowsOpenAtom } from './WorkflowsDialog'
import { Popover } from './Popover'
import { t } from '../i18n'
import { isEnter } from './keys'

function Item({ icon, label, kbd, danger, disabled, run, close }: { icon: ReactNode; label: string; kbd?: string; danger?: boolean; disabled?: boolean; run: () => void; close: () => void }) {
  return (
    <button type="button" className={`ca-menu__item${danger ? ' ca-menu__item--danger' : ''}`} disabled={disabled} onClick={() => { close(); run() }}>
      <span className="ca-icon">{icon}</span><span className="ca-menu__grow">{label}</span>{kbd && <span className="ca-menu__key">{kbd}</span>}
    </button>
  )
}

export function ProjectHeader({ editor, projectId, children }: { editor: Editor; projectId: string; children?: ReactNode }) {
  const name = useValue('doc name', () => editor.getDocumentSettings().name, [editor])
  const [open, setOpen] = useState(false)
  const canUndo = useValue('can undo', () => editor.getCanUndo(), [editor])
  const canRedo = useValue('can redo', () => editor.getCanRedo(), [editor])
  const selected = useValue('has selection', () => editor.getSelectedShapeIds().length > 0, [editor])
  const close = () => setOpen(false)
  const kits = useValue('brand kits', () => libraryAtom.get().filter((x) => x.kind === 'brand'), [])
  const linked = useValue('linked kit', () => editor.getDocumentSettings().meta.brandKit ?? null, [editor])
  const link = (id: string | null) => {
    const doc = editor.getDocumentSettings()
    editor.updateDocumentSettings({ meta: { ...doc.meta, brandKit: linked === id ? null : id } })
  }

  return (
    <div className="ca-head" onPointerDown={(e) => e.stopPropagation()}>
      <Popover
        open={open}
        onOpenChange={setOpen}
        trigger={({ open: o, toggle: flip }) => (
          <button type="button" className="ca-head__logo" title={t('projectHeader.projects')} data-open={o || undefined} onClick={flip}>{Icons.agent}</button>
        )}
      >
        <div className="ca-menu ca-head__list">
          <Item close={close} icon={Icons.home} label={t('home.home')} run={() => openView('home')} />
          <Item close={close} icon={Icons.folder} label={t('home.projectLibrary')} run={() => openView('projects')} />
          <Item close={close} icon={Icons.plus} label={t('projectHeader.newProject')} run={() => newProject()} />
          <Item close={close} icon={Icons.page} label={t('projectHeader.duplicateProject')} run={() => void saveNow().then(() => duplicateProject(projectId)).then(openProject)} />
          <Item close={close} icon={Icons.trash} label={t('home.deleteCurrentProject')} danger run={() => confirmDelete([projectId], () => openView('projects'))} />
          <div className="ca-menu__sep" />
          <Item close={close} icon={Icons.restore} label={t('historyDialog.canvasHistory')} run={() => historyAtom.set(true)} />
          <Item close={close} icon={Icons.upload} label={t('projectHeader.importImage')} run={() => importFiles(editor, 'image/*')} />
          <div className="ca-menu__sep" />
          <Item close={close} icon={Icons.undo} label={t('common.undo')} kbd="Ctrl Z" disabled={!canUndo} run={() => editor.undo()} />
          <Item close={close} icon={Icons.redo} label={t('shortcuts.redo')} kbd="Ctrl Shift Z" disabled={!canRedo} run={() => editor.redo()} />
          <Item close={close} icon={Icons.page} label={t('common.duplicate')} kbd="Ctrl D" disabled={!selected} run={() => editor.duplicateShapes(editor.getSelectedShapeIds())} />
          <div className="ca-menu__sep" />
          <Item close={close} icon={Icons.expand} label={t('zoom.fitAll')} kbd="Shift 1" run={() => editor.zoomToFit({ animation: { duration: 200 } })} />
          <Item close={close} icon={Icons.plus} label={t('common.zoomIn')} kbd="Ctrl +" run={() => editor.zoomIn(undefined, { animation: { duration: 200 } })} />
          <Item close={close} icon={Icons.minus} label={t('common.zoomOut')} kbd="Ctrl -" run={() => editor.zoomOut(undefined, { animation: { duration: 200 } })} />
          <div className="ca-menu__sep" />
          <Item close={close} icon={Icons.memory} label={t('common.memory')} run={() => memoryOpenAtom.set(true)} />
          <Item close={close} icon={Icons.grid} label={t('customWorkflows.title')} run={() => workflowsOpenAtom.set(true)} />
          {kits.length > 0 && (
            <>
              <div className="ca-menu__sep" />
              <div className="ca-gen__label">{t('projectHeader.projectBrandKit')}</div>
              {kits.map((k) => (
                <button key={k.id} type="button" className="ca-menu__item" onClick={() => link(k.id)}>
                  <span className="ca-icon">{Icons.palette}</span><span className="ca-menu__grow">{k.name}</span>
                  {linked === k.id && <span className="ca-icon">{Icons.check}</span>}
                </button>
              ))}
            </>
          )}
        </div>
      </Popover>
      <input
        className="ca-head__name"
        value={name}
        placeholder={UNTITLED}
        onChange={(e) => editor.updateDocumentSettings({ name: e.target.value })}
        onKeyDown={(e) => {
          e.stopPropagation()
          if (isEnter(e)) e.currentTarget.blur()
        }}
      />
      <SaveStatus />
      {children}
    </div>
  )
}

function SaveStatus() {
  const { state, error, time } = useValue(saveStateAtom)
  if (state === 'error') return <button type="button" className="ca-save" data-state={state} title={error} onClick={() => void saveNow()}>{t('projectHeader.saveFailed')}</button>
  return <span className="ca-save" data-state={state} title={time ? t('projectHeader.savedAt', new Date(time).toLocaleTimeString()) : undefined}>{state === 'saved' ? t('projectHeader.saved') : t('projectHeader.saving')}</span>
}
