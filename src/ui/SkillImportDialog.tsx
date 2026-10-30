/** #463 G4 — "Import" drop dialog: drop a Skill folder or a .zip; click opens a file picker. */
import { useState, useRef, type DragEvent } from 'react'

import { t } from '../i18n'
import { importEntries, importZip, SkillImportCancelled, SkillImportError, type Skill, type SkillConflictChoice, type SkillEntry } from '../skills'
import { Icons } from './icons'
import { Modal } from './Modal'

type Entry = { isFile: boolean; isDirectory: boolean; name: string; fullPath: string }
type FileEntry = Entry & { file: (ok: (f: File) => void, err: (e: unknown) => void) => void }
type DirEntry = Entry & { createReader: () => { readEntries: (ok: (list: Entry[]) => void, err: (e: unknown) => void) => void } }

/** Walks a dropped directory (webkitGetAsEntry) into path + file pairs. */
async function walk(entry: Entry, out: SkillEntry[]): Promise<void> {
  if (entry.isFile) {
    const file = await new Promise<File>((ok, err) => (entry as FileEntry).file(ok, err))
    out.push({ path: entry.fullPath.replace(/^\//, ''), file })
    return
  }
  if (!entry.isDirectory) return
  const reader = (entry as DirEntry).createReader()
  for (;;) {
    const batch = await new Promise<Entry[]>((ok, err) => reader.readEntries(ok, err))
    if (!batch.length) break
    for (const child of batch) await walk(child, out)
  }
}

export function SkillImportDialog({ onClose, onImported }: { onClose: () => void; onImported: (skill: Skill, skipped: string[]) => void }) {
  const zip = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const [conflict, setConflict] = useState<{ name: string; answer: (c: SkillConflictChoice) => void } | null>(null)

  const onConflict = (existing: Skill) => new Promise<SkillConflictChoice>((answer) => {
    setConflict({ name: existing.name, answer: (c) => { setConflict(null); answer(c) } })
  })
  const run = (fn: () => Promise<{ skill: Skill; skipped: string[] }>) => {
    setBusy(true)
    setError('')
    void fn()
      .then(({ skill, skipped }) => onImported(skill, skipped))
      .catch((e) => {
        if (e instanceof SkillImportCancelled) return
        setError((e instanceof SkillImportError ? e : new SkillImportError('unreadable')).message)
      })
      .finally(() => setBusy(false))
  }
  const takeZip = (f: File | undefined) => {
    if (!f) return
    run(() => importZip(f, { onConflict }))
  }
  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    if (busy) return
    const entry = Array.from(e.dataTransfer.items ?? []).map((i) => (i as DataTransferItem & { webkitGetAsEntry?: () => Entry | null }).webkitGetAsEntry?.()).find(Boolean)
    if (entry?.isDirectory) {
      run(async () => { const out: SkillEntry[] = []; await walk(entry, out); return importEntries(out, entry.name, { strict: true, onConflict }) })
      return
    }
    takeZip(Array.from(e.dataTransfer.files)[0])
  }

  return (
    <Modal title={t('skillsImport.title')} className="ca-rename ca-skimport" onClose={onClose}>
      <div className="ca-rename__body" data-testid="skill-import-dialog">
        <button
          type="button"
          className="ca-skimport__drop"
          data-over={over || undefined}
          data-busy={busy || undefined}
          data-error={error ? true : undefined}
          data-testid="skill-import-drop"
          disabled={busy}
          onClick={() => zip.current?.click()}
          onDragEnter={(e) => { e.preventDefault(); setOver(true) }}
          onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; setOver(true) }}
          onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOver(false) }}
          onDrop={onDrop}
        >
          <span className="ca-skimport__icon ca-icon">{Icons.upload}</span>
          <span className="ca-skimport__title">{busy ? t('skillsImport.importing') : over ? t('skillsImport.release') : t('skillsImport.drop')}</span>
          {error && !over && <span className="ca-skimport__error" role="alert" data-testid="skill-import-error">{error}</span>}
        </button>
        <ul className="ca-skimport__notes" data-testid="skill-import-notes">
          <li>{t('skillsImport.note.formats')}</li>
          <li>{t('skillsImport.note.skillMd')}</li>
        </ul>
        {conflict && (
          <div className="ca-skimport__conflict" role="alertdialog" data-testid="skill-import-conflict">
            <span>{t('skillsImport.conflict', conflict.name)}</span>
            <div className="ca-panel__foot">
              <button type="button" className="ca-panel__secondary" onClick={() => conflict.answer('cancel')}>{t('common.cancel')}</button>
              <button type="button" className="ca-panel__secondary" data-testid="skill-import-keep-both" onClick={() => conflict.answer('keepBoth')}>{t('skillsImport.conflict.keepBoth')}</button>
              <button type="button" className="ca-panel__primary" data-testid="skill-import-replace" onClick={() => conflict.answer('replace')}>{t('skillsImport.conflict.replace')}</button>
            </div>
          </div>
        )}
        <input ref={zip} type="file" accept=".zip,application/zip" hidden data-testid="skill-import-zip-input" onChange={(e) => { takeZip(e.target.files?.[0]); e.target.value = '' }} />
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary" onClick={onClose}>{t('common.cancel')}</button>
        </div>
      </div>
    </Modal>
  )
}
